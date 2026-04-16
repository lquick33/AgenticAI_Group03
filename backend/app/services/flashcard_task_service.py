"""
Flashcard Generation Task Service

Manages background tasks for flashcard generation with progress tracking via Redis.
"""

import atexit
import asyncio
import logging
import time
import uuid
import json
import base64
from contextlib import ExitStack
from enum import Enum
from typing import Any, Dict, Optional

import redis.asyncio as redis
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

from app.core.config import settings
from app.services.db_migration_helper import get_postgres_connection_string
from app.services.tasks.flashcard_tasks import generate_flashcards_celery

logger = logging.getLogger(__name__)

# Singleton checkpointer instance
_checkpointer = None
_checkpointer_stack: ExitStack | None = None

def _close_checkpointer_stack() -> None:
    global _checkpointer
    global _checkpointer_stack

    if _checkpointer_stack is not None:
        _checkpointer_stack.close()
        _checkpointer_stack = None

    _checkpointer = None

def _get_checkpointer():
    global _checkpointer
    global _checkpointer_stack

    if _checkpointer is None:
        try:
            conn_string = get_postgres_connection_string()
            stack = ExitStack()
            saver = stack.enter_context(PostgresSaver.from_conn_string(conn_string))
            try:
                saver.setup()
                logger.info("PostgresSaver tables initialized successfully")
            except Exception as setup_error:
                logger.warning(
                    f"PostgresSaver.setup() failed (may be normal if tables exist): {setup_error}"
                )
            _checkpointer = saver
            _checkpointer_stack = stack
            logger.info("Using PostgresSaver for flashcard agent checkpointing")
        except Exception as e:
            logger.warning(
                f"Failed to initialize PostgresSaver, falling back to MemorySaver: {e}"
            )
            _close_checkpointer_stack()
            _checkpointer = MemorySaver()
            logger.info("Using MemorySaver for flashcard agent checkpointing (fallback)")
    return _checkpointer

atexit.register(_close_checkpointer_stack)

class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class FlashcardTask:
    """Represents a flashcard generation task."""
    
    def __init__(
        self,
        task_id: str,
        course_material_id: str,
        user_id: str,
        course_id: str,
        deduplicate_course: bool = False,
        parent_deck_name: Optional[str] = None,
        target_deck_name: Optional[str] = None,
    ):
        self.task_id = task_id
        self.course_material_id = course_material_id
        self.user_id = user_id
        self.course_id = course_id
        self.deduplicate_course = deduplicate_course
        self.parent_deck_name = parent_deck_name
        self.target_deck_name = target_deck_name
        self.status = TaskStatus.PENDING
        self.progress = 0.0
        self.total_pages = 0
        self.processed_pages = 0
        self.cards_generated = 0
        self.error_message: Optional[str] = None
        self.apkg_bytes: Optional[bytes] = None
        self.filename: Optional[str] = None
        self.anki_synced: bool = False
        self.ankiweb_synced: bool = False
        self.created_at = time.time()
        self.completed_at: Optional[float] = None
        self._cancelled = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for API response."""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "progress": self.progress,
            "total_pages": self.total_pages,
            "processed_pages": self.processed_pages,
            "cards_generated": self.cards_generated,
            "error_message": self.error_message,
            "filename": self.filename,
            "anki_synced": self.anki_synced,
            "ankiweb_synced": self.ankiweb_synced,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }
    
    def cancel(self):
        """Cancel the task."""
        self._cancelled = True
        self.status = TaskStatus.CANCELLED

class FlashcardTaskService:
    """
    Stateless Service for managing flashcard generation tasks using Redis and Celery.
    """
    
    def __init__(self):
        self._redis_client: Optional[redis.Redis] = None

    def _get_redis(self) -> redis.Redis:
        if self._redis_client is None:
            redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
            if redis_url.startswith("rediss://"):
                self._redis_client = redis.from_url(redis_url, ssl_cert_reqs="required")
            else:
                self._redis_client = redis.from_url(redis_url)
        return self._redis_client
    
    async def create_task(
        self,
        course_material_id: str,
        user_id: str,
        course_id: str,
        deduplicate_course: bool = False,
        parent_deck_name: Optional[str] = None,
        target_deck_name: Optional[str] = None,
    ) -> str:
        task_id = str(uuid.uuid4())
        
        task_data = {
            "task_id": task_id,
            "course_material_id": course_material_id,
            "user_id": user_id,
            "course_id": course_id,
            "status": TaskStatus.PENDING.value,
            "progress": 0.0,
            "total_pages": 0,
            "processed_pages": 0,
            "cards_generated": 0,
            "created_at": time.time(),
        }
        
        r = self._get_redis()
        await r.setex(f"flashcard_task:{task_id}", 86400, json.dumps(task_data))
        
        # Dispatch to Celery
        generate_flashcards_celery.delay(
            task_id=task_id,
            course_material_id=course_material_id,
            user_id=user_id,
            course_id=course_id,
            deduplicate_course=deduplicate_course,
            parent_deck_name=parent_deck_name,
            target_deck_name=target_deck_name,
        )
        
        return task_id
    
    async def get_task(self, task_id: str) -> Optional[FlashcardTask]:
        """Get task by ID."""
        r = self._get_redis()
        data = await r.get(f"flashcard_task:{task_id}")
        if data:
            task_dict = json.loads(data)
            
            task = FlashcardTask(
                task_id=task_dict["task_id"],
                course_material_id=task_dict["course_material_id"],
                user_id=task_dict["user_id"],
                course_id=task_dict["course_id"],
            )
            task.status = TaskStatus(task_dict.get("status", "pending"))
            task.progress = task_dict.get("progress", 0.0)
            task.total_pages = task_dict.get("total_pages", 0)
            task.processed_pages = task_dict.get("processed_pages", 0)
            task.cards_generated = task_dict.get("cards_generated", 0)
            task.error_message = task_dict.get("error_message")
            task.filename = task_dict.get("filename")
            task.anki_synced = task_dict.get("anki_synced", False)
            task.ankiweb_synced = task_dict.get("ankiweb_synced", False)
            task.created_at = task_dict.get("created_at", time.time())
            task.completed_at = task_dict.get("completed_at")
            
            # Reconstruct apkg_bytes from base64 if present
            b64 = task_dict.get("apkg_base64")
            if b64:
                task.apkg_bytes = base64.b64decode(b64)
                
            return task
        return None
    
    async def get_active_task_for_material(
        self,
        course_material_id: str,
        user_id: str,
    ) -> Optional[FlashcardTask]:
        """Get the active task for a course material. Iterates over active keys."""
        r = self._get_redis()
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match="flashcard_task:*", count=100)
            if keys:
                values = await r.mget(keys)
                for val in values:
                    if val:
                        t = json.loads(val)
                        if (
                            t.get("course_material_id") == course_material_id and
                            t.get("user_id") == user_id and
                            t.get("status") in ("pending", "running")
                        ):
                            return await self.get_task(t["task_id"])
            if cursor == 0:
                break
        return None
    
    async def cancel_task(self, task_id: str) -> bool:
        r = self._get_redis()
        data = await r.get(f"flashcard_task:{task_id}")
        if data:
            task_dict = json.loads(data)
            task_dict["status"] = "cancelled"
            await r.setex(f"flashcard_task:{task_id}", 86400, json.dumps(task_dict))
            return True
        return False

# Global task service instance
_task_service: Optional[FlashcardTaskService] = None

def get_flashcard_task_service() -> FlashcardTaskService:
    """Get or create the global task service instance."""
    global _task_service
    if _task_service is None:
        _task_service = FlashcardTaskService()
    return _task_service
