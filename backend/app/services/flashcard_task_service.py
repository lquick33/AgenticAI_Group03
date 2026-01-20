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

from app.agents.flashcards import FlashcardGeneratorAgent
from app.services.flashcard_service import build_anki_csv
from app.services.storage import save_flashcards

logger = logging.getLogger(__name__)


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
        self.csv_bytes: Optional[bytes] = None
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
            
            # Initialize agent
            agent = FlashcardGeneratorAgent()
            
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
            
            # Generate flashcards asynchronously with progress updates
            cards = await self._generate_flashcards_async(
                agent=agent,
                course_material_id=task.course_material_id,
                user_id=task.user_id,
                course_id=task.course_id,
                task=task,
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
                # Continue anyway - CSV generation should still work
            
            # Build CSV
            task.csv_bytes = build_anki_csv(cards)
            
            # Generate filename
            from app.services.storage import get_supabase_client
            client = get_supabase_client()
            
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
            task.filename = f"flashcards_{safe_course_title}_{safe_file_name}.csv"
            
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
    
    async def _generate_flashcards_async(
        self,
        agent: FlashcardGeneratorAgent,
        course_material_id: str,
        user_id: str,
        course_id: str,
        task: FlashcardTask,
    ) -> list:
        """
        Generate flashcards asynchronously with progress updates.
        
        This wraps the synchronous generate_flashcards method and adds
        async/await support with progress tracking.
        """
        from app.services.storage import (
            get_all_page_analyses_for_material,
            get_messages_for_page,
        )
        
        # Get all page analyses
        page_analyses = get_all_page_analyses_for_material(course_material_id, user_id)
        
        if not page_analyses:
            return []
        
        all_cards = []
        
        # Process each page with progress updates
        for idx, page_analysis in enumerate(page_analyses):
            if task._cancelled:
                break
            
            page_number = page_analysis.get("page_number", 0)
            page_id = page_analysis.get("id")
            
            # Update progress
            task.processed_pages = idx + 1
            task.progress = (idx + 1) / len(page_analyses)
            
            # Check if page should be skipped (async with timeout)
            try:
                should_skip, reason = await asyncio.wait_for(
                    asyncio.to_thread(
                        agent._should_skip_page,
                        page_analysis,
                        task.user_id,
                        task.course_material_id,
                        task.course_id,
                        page_number
                    ),
                    timeout=30.0  # 30 second timeout per skip decision
                )
                
                if should_skip:
                    logger.debug(f"Skipping page {page_number}: {reason}")
                    continue
            except asyncio.TimeoutError:
                logger.warning(f"Timeout checking if page {page_number} should be skipped, skipping it")
                continue
            except Exception as e:
                logger.warning(f"Error checking if page {page_number} should be skipped: {e}, continuing")
                continue
            
            # Get messages for this page
            messages = []
            if page_id:
                try:
                    messages = get_messages_for_page(page_id, user_id)
                except Exception as e:
                    logger.warning(f"Error getting messages for page {page_number}: {e}")
            
            # Generate cards for this page (async with timeout)
            try:
                cards = await asyncio.wait_for(
                    asyncio.to_thread(
                        agent._generate_cards_for_page,
                        page_analysis,
                        messages,
                        course_id,
                        course_material_id,
                        page_number,
                        task.user_id,
                    ),
                    timeout=60.0  # 60 second timeout per card generation
                )
                all_cards.extend(cards)
            except asyncio.TimeoutError:
                logger.warning(f"Timeout generating cards for page {page_number}, skipping")
                continue
            except Exception as e:
                logger.warning(f"Error generating cards for page {page_number}: {e}, continuing")
                continue
        
        return all_cards


# Global task service instance
_task_service: Optional[FlashcardTaskService] = None


def get_flashcard_task_service() -> FlashcardTaskService:
    """Get or create the global task service instance."""
    global _task_service
    if _task_service is None:
        _task_service = FlashcardTaskService()
    return _task_service
