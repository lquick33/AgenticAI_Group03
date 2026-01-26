"""
Flashcard Generation Task Service

Manages background tasks for flashcard generation with progress tracking.
"""

import asyncio
import logging
import time
import uuid
from enum import Enum
from typing import Any, Dict, Optional

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import MemorySaver

from app.agents.flashcards import FlashcardGeneratorAgent
from app.services.flashcard_service import build_anki_apkg
from app.services.storage import save_flashcards
from app.services.db_migration_helper import get_postgres_connection_string

logger = logging.getLogger(__name__)

# Singleton checkpointer instance
_checkpointer = None


def _get_checkpointer():
    """
    Get or create checkpointer instance for flashcard agent.
    
    Tries to use PostgresSaver for persistent checkpointing.
    Falls back to MemorySaver if database connection is unavailable.
    
    Returns:
        BaseCheckpointSaver instance (PostgresSaver or MemorySaver)
    """
    global _checkpointer
    if _checkpointer is None:
        try:
            conn_string = get_postgres_connection_string()
            _checkpointer = PostgresSaver.from_conn_string(conn_string)
            # Setup database tables (idempotent - safe to call multiple times)
            try:
                _checkpointer.setup()
                logger.info("PostgresSaver tables initialized successfully")
            except Exception as setup_error:
                # If setup fails (e.g., tables already exist), log warning but continue
                # PostgresSaver may auto-create tables on first use in some versions
                logger.warning(f"PostgresSaver.setup() failed (may be normal if tables exist): {setup_error}")
            logger.info("Using PostgresSaver for flashcard agent checkpointing")
        except (ValueError, Exception) as e:
            logger.warning(f"Failed to initialize PostgresSaver, falling back to MemorySaver: {e}")
            _checkpointer = MemorySaver()
            logger.info("Using MemorySaver for flashcard agent checkpointing (fallback)")
    return _checkpointer


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
    ):
        self.task_id = task_id
        self.course_material_id = course_material_id
        self.user_id = user_id
        self.course_id = course_id
        self.status = TaskStatus.PENDING
        self.progress = 0.0  # 0.0 to 1.0
        self.total_pages = 0
        self.processed_pages = 0
        self.cards_generated = 0
        self.error_message: Optional[str] = None
        self.apkg_bytes: Optional[bytes] = None
        self.filename: Optional[str] = None
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
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }
    
    def cancel(self):
        """Cancel the task."""
        self._cancelled = True
        self.status = TaskStatus.CANCELLED


class FlashcardTaskService:
    """
    Service for managing flashcard generation tasks.
    
    In production, this could be replaced with a proper task queue
    (e.g., Celery, RQ, or cloud task services).
    """
    
    def __init__(self):
        self._tasks: Dict[str, FlashcardTask] = {}
        self._lock = asyncio.Lock()
    
    async def create_task(
        self,
        course_material_id: str,
        user_id: str,
        course_id: str,
    ) -> str:
        """
        Create a new flashcard generation task.
        
        Args:
            course_material_id: Course material ID
            user_id: User ID
            course_id: Course ID
            
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        task = FlashcardTask(
            task_id=task_id,
            course_material_id=course_material_id,
            user_id=user_id,
            course_id=course_id,
        )
        
        async with self._lock:
            self._tasks[task_id] = task
        
        # Start background task
        asyncio.create_task(self._run_task(task))
        
        return task_id
    
    async def get_task(self, task_id: str) -> Optional[FlashcardTask]:
        """
        Get task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task or None if not found
        """
        async with self._lock:
            return self._tasks.get(task_id)
    
    async def get_active_task_for_material(
        self,
        course_material_id: str,
        user_id: str,
    ) -> Optional[FlashcardTask]:
        """
        Get the active (pending or running) task for a course material.
        
        Args:
            course_material_id: Course material ID
            user_id: User ID for authorization
            
        Returns:
            Active task or None if not found
        """
        async with self._lock:
            for task in self._tasks.values():
                if (
                    task.course_material_id == course_material_id
                    and task.user_id == user_id
                    and task.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
                ):
                    return task
            return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task.
        
        Args:
            task_id: Task ID
            
        Returns:
            True if task was cancelled, False if not found
        """
        async with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.cancel()
                return True
            return False
    
    async def _run_task(self, task: FlashcardTask):
        """
        Run the flashcard generation task in the background.
        
        Args:
            task: Task to run
        """
        try:
            task.status = TaskStatus.RUNNING
            logger.info(f"Starting flashcard generation task {task.task_id}")
            
            # Initialize agent with checkpointer for state persistence
            checkpointer = _get_checkpointer()
            agent = FlashcardGeneratorAgent(checkpointer=checkpointer)
            
            # Get page count for progress tracking
            from app.services.storage import get_all_page_analyses_for_material
            page_analyses = get_all_page_analyses_for_material(
                task.course_material_id,
                task.user_id
            )
            task.total_pages = len(page_analyses) if page_analyses else 0
            
            if task.total_pages == 0:
                task.status = TaskStatus.FAILED
                task.error_message = "No page analyses found for this material"
                task.completed_at = time.time()
                return
            
            # Generate flashcards using the graph-based agent with progress tracking
            # The agent now handles all page processing internally with state persistence
            
            def progress_callback(current_page_index, total_pages, processed_pages, skipped_pages, cards_generated, progress):
                """Update task progress from graph state."""
                try:
                    task.processed_pages = processed_pages
                    task.progress = progress
                    task.cards_generated = cards_generated
                    # total_pages already set before graph execution, but update if needed
                    if total_pages > 0 and task.total_pages != total_pages:
                        task.total_pages = total_pages
                    logger.debug(
                        f"Progress update for task {task.task_id}: "
                        f"{processed_pages}/{total_pages} pages ({progress*100:.1f}%), "
                        f"{cards_generated} cards generated"
                    )
                except Exception as e:
                    # Don't let callback errors crash the generation
                    logger.warning(f"Error updating task progress in callback: {e}")
            
            cards = await asyncio.to_thread(
                agent.generate_flashcards_with_progress,
                course_material_id=task.course_material_id,
                user_id=task.user_id,
                course_id=task.course_id,
                save_to_db=False,  # We'll save manually after generation
                task_id=task.task_id,
                progress_callback=progress_callback,
            )
            
            if task._cancelled:
                task.status = TaskStatus.CANCELLED
                task.completed_at = time.time()
                return
            
            if not cards:
                task.status = TaskStatus.FAILED
                task.error_message = "No flashcards could be generated"
                task.completed_at = time.time()
                return
            
            task.cards_generated = len(cards)
            
            # Save flashcards to Supabase
            try:
                save_flashcards(cards, task.user_id, task.course_id)
                logger.info(f"Saved {len(cards)} flashcards to database for task {task.task_id}")
            except Exception as e:
                logger.warning(f"Failed to save flashcards to database: {str(e)}")
                # Continue anyway - APKG generation should still work
            
            # Generate filename first (needed for deck name)
            from app.services.storage import get_supabase_client, get_all_page_analyses_for_material
            client = get_supabase_client()
            
            # Fetch ALL flashcards from DB for this material (not just newly generated ones)
            # This ensures the .apkg includes all cards, even from previous runs
            page_analyses = get_all_page_analyses_for_material(task.course_material_id, task.user_id)
            page_analysis_ids = [pa.get("id") for pa in page_analyses if pa.get("id")]
            
            if page_analysis_ids:
                all_cards_response = (
                    client.table("flashcards")
                    .select("front, back, source_page_analysis_id")
                    .eq("user_id", task.user_id)
                    .in_("source_page_analysis_id", page_analysis_ids)
                    .execute()
                )
                
                if all_cards_response.data:
                    # Convert DB format to the format expected by build_anki_apkg
                    all_cards = []
                    for card in all_cards_response.data:
                        # Get page number from page_analysis
                        page_num = None
                        for pa in page_analyses:
                            if pa.get("id") == card.get("source_page_analysis_id"):
                                page_num = pa.get("page_number")
                                break
                        
                        all_cards.append({
                            "front": card.get("front", ""),
                            "back": card.get("back", ""),
                            "tags": [f"page:{page_num}"] if page_num else []
                        })
                    
                    cards = all_cards
                    logger.info(f"Using {len(cards)} cards from database for .apkg generation")
            
            material_response = (
                client.table("course_materials")
                .select("file_name")
                .eq("id", task.course_material_id)
                .single()
                .execute()
            )
            
            course_response = (
                client.table("courses")
                .select("title")
                .eq("id", task.course_id)
                .single()
                .execute()
            )
            
            file_name = material_response.data.get("file_name", "material") if material_response.data else "material"
            course_title = course_response.data.get("title", "course") if course_response.data else "course"
            
            import re
            safe_course_title = re.sub(r'[^\w\s-]', '', course_title).strip()[:50]
            safe_file_name = re.sub(r'[^\w\s-]', '', file_name.replace('.pdf', '')).strip()[:50]
            
            # Build .apkg with embedded images
            deck_name = f"{course_title} - {file_name.replace('.pdf', '')}"
            task.apkg_bytes = build_anki_apkg(cards, deck_name=deck_name)
            task.filename = f"flashcards_{safe_course_title}_{safe_file_name}.apkg"
            
            task.status = TaskStatus.COMPLETED
            task.progress = 1.0
            task.completed_at = time.time()
            
            logger.info(
                f"Flashcard generation task {task.task_id} completed: "
                f"{len(cards)} cards generated"
            )
            
        except Exception as e:
            logger.error(f"Flashcard generation task {task.task_id} failed: {str(e)}", exc_info=True)
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = time.time()
    
    # Note: _generate_flashcards_async method removed
    # The agent now handles all page processing internally via LangGraph
    # Progress tracking can be added in the future by checking graph state


# Global task service instance
_task_service: Optional[FlashcardTaskService] = None


def get_flashcard_task_service() -> FlashcardTaskService:
    """Get or create the global task service instance."""
    global _task_service
    if _task_service is None:
        _task_service = FlashcardTaskService()
    return _task_service
