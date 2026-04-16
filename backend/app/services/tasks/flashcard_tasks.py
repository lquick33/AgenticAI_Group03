import logging
import time
import json
import re
from typing import Optional, Dict, Any

from celery import Task
import redis

from app.core.celery_app import celery_app
from app.core.config import settings
from app.agents.flashcards import FlashcardGeneratorAgent
from app.services.flashcard_service import build_anki_apkg

logger = logging.getLogger(__name__)

def _get_redis() -> redis.Redis:
    redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
    if redis_url.startswith("rediss://"):
        return redis.from_url(redis_url, ssl_cert_reqs="required")
    return redis.from_url(redis_url)

def _update_task_state(task_id: str, updates: Dict[str, Any]):
    """Update the task state in Redis."""
    try:
        r = _get_redis()
        key = f"flashcard_task:{task_id}"
        existing = r.get(key)
        data = json.loads(existing) if existing else {}
        data.update(updates)
        # Keep task info for 24 hours
        r.setex(key, 86400, json.dumps(data))
    except Exception as e:
        logger.warning(f"Failed to update task state in Redis: {e}")

@celery_app.task(bind=True, name="app.services.tasks.flashcard_tasks.generate_flashcards_celery")
def generate_flashcards_celery(
    self: Task,
    task_id: str,
    course_material_id: str,
    user_id: str,
    course_id: str,
    deduplicate_course: bool = False,
    parent_deck_name: Optional[str] = None,
    target_deck_name: Optional[str] = None,
):
    """
    Background Celery task to generate flashcards.
    """
    logger.info(f"Starting Celery flashcard task {task_id} for material {course_material_id}")
    _update_task_state(task_id, {"status": "running"})

    try:
        from app.services.flashcard_task_service import _get_checkpointer
        checkpointer = _get_checkpointer()
        agent = FlashcardGeneratorAgent(checkpointer=checkpointer)

        # Get total pages for initial tracking
        from app.core.adapters import get_page_analysis
        page_analyses = get_page_analysis().get_all_for_material(course_material_id, user_id)
        total_pages = len(page_analyses) if page_analyses else 0

        if total_pages == 0:
            _update_task_state(task_id, {
                "status": "failed",
                "error_message": "No page analyses found for this material",
                "completed_at": time.time(),
                "total_pages": 0
            })
            return

        _update_task_state(task_id, {"total_pages": total_pages})

        def progress_callback(current_page_index, callback_total, processed_pages, skipped_pages, cards_generated, progress):
            _update_task_state(task_id, {
                "processed_pages": processed_pages,
                "progress": progress,
                "cards_generated": cards_generated,
                "total_pages": callback_total if callback_total > 0 else total_pages
            })
            logger.debug(f"Task {task_id} progress: {progress*100:.1f}%")

        # Call the synchronous version (generate_flashcards_with_progress handles IO)
        result = agent.generate_flashcards_with_progress(
            course_material_id=course_material_id,
            user_id=user_id,
            course_id=course_id,
            save_to_db=True,
            task_id=task_id,
            progress_callback=progress_callback,
            deduplicate_course=deduplicate_course,
            parent_deck_name=parent_deck_name,
            target_deck_name=target_deck_name,
        )

        # Check if cancelled
        r = _get_redis()
        current_state_str = r.get(f"flashcard_task:{task_id}")
        if current_state_str:
            current_state = json.loads(current_state_str)
            if current_state.get("status") == "cancelled":
                logger.info(f"Task {task_id} was cancelled")
                return

        cards = result.get("cards", []) if isinstance(result, dict) else result
        anki_synced = result.get("anki_synced", False) if isinstance(result, dict) else False
        ankiweb_synced = result.get("ankiweb_synced", False) if isinstance(result, dict) else False

        if not cards:
            _update_task_state(task_id, {
                "status": "failed",
                "error_message": "No flashcards could be generated",
                "completed_at": time.time()
            })
            return

        # Setup packaging
        from app.adapters.supabase.client import get_supabase_client
        client = get_supabase_client()

        # Fetch all cards to build the complete apkg
        page_analysis_ids = [pa.get("id") for pa in page_analyses if pa.get("id")]
        all_cards = []

        if page_analysis_ids:
            all_cards_response = (
                client.table("flashcards")
                .select("front, back, source_page_analysis_id")
                .eq("user_id", user_id)
                .in_("source_page_analysis_id", page_analysis_ids)
                .execute()
            )
            if all_cards_response.data:
                for card in all_cards_response.data:
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
        
        material_response = client.table("course_materials").select("file_name").eq("id", course_material_id).single().execute()
        course_response = client.table("courses").select("title").eq("id", course_id).single().execute()
        
        file_name = material_response.data.get("file_name", "material") if material_response.data else "material"
        course_title = course_response.data.get("title", "course") if course_response.data else "course"
        
        lecture_name = file_name.replace('.pdf', '')
        deck_name = f"{course_title}::{lecture_name}"
        
        # Build Apkg
        apkg_bytes = build_anki_apkg(cards, deck_name=deck_name)
        safe_deck_name = re.sub(r'[/\\:*?"<>|]', '', f"{course_title} - {lecture_name}").strip()[:100]
        filename = f"{safe_deck_name}.apkg"

        # Note: Celery cannot pass large bytes back elegantly in Redis without bloat, 
        # so we must save the apkg temporarily to Supabase Storage, or let the API 
        # reconstruct it, or base64 encode it in Redis. 
        # Since it's a Redis cache, let's base64 encode it, OR we'll write it to Supabase Storage.
        import base64
        b64_apkg = base64.b64encode(apkg_bytes).decode('utf-8')

        try:
            client.table("course_materials").update(
                {"has_flashcards": True}
            ).eq("id", course_material_id).execute()
        except:
            pass

        _update_task_state(task_id, {
            "status": "completed",
            "progress": 1.0,
            "completed_at": time.time(),
            "cards_generated": len(cards),
            "anki_synced": anki_synced,
            "ankiweb_synced": ankiweb_synced,
            "filename": filename,
            "apkg_base64": b64_apkg
        })
        logger.info(f"Task {task_id} completed successfully.")

    except Exception as e:
        logger.error(f"Celery Task {task_id} failed: {e}", exc_info=True)
        _update_task_state(task_id, {
            "status": "failed",
            "error_message": str(e),
            "completed_at": time.time()
        })
