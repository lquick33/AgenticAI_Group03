import logging
import io
import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import StreamingResponse

from app.models.schemas import FlashcardTaskResponse, FlashcardTaskStatusResponse
from app.services.flashcard_task_service import get_flashcard_task_service
from app.adapters.supabase.client import get_supabase_client
from app.services.flashcard_service import build_anki_apkg
from app.services.observability import get_client
from app.core.adapters import get_flashcard
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Helper function
def validate_user_exists(user_id: str) -> bool:
    from app.core.adapters import get_course
    return get_course().validate_user_exists(user_id)


@router.post("/flashcards/generate", response_model=FlashcardTaskResponse, status_code=202)
async def generate_flashcards(
    course_material_id: str = Query(...),
    user_id: str = Query(...),
    deduplicate_course: bool = Query(False)
):
    """Start flashcard generation as a background task."""
    langfuse = None
    trace_ctx = None
    if settings.LANGFUSE_ENABLED:
        try:
            langfuse = get_client()
            if langfuse:
                trace_ctx = langfuse.start_as_current_observation(
                    name="flashcard-api-request",
                    input={"course_material_id": course_material_id, "user_id": user_id},
                    metadata={"endpoint": "/flashcards/generate"}
                )
        except Exception as e:
            logger.warning(f"Langfuse init failed: {e}")

    try:
        if not validate_user_exists(user_id):
            raise HTTPException(status_code=404, detail="User not found")
            
        client = get_supabase_client()
        material_response = client.table("course_materials").select("id, course_id, file_name").eq("id", course_material_id).eq("user_id", user_id).single().execute()
        
        if not material_response.data:
            raise HTTPException(status_code=404, detail="Course material not found")
            
        material = material_response.data
        course_id = material["course_id"]
        
        parent_deck_name = None
        target_deck_name = None
        
        course_response = client.table("courses").select("title").eq("id", course_id).single().execute()
        if course_response.data:
            from pathlib import Path
            course_title = course_response.data.get("title", "Course")
            file_name = material.get("file_name", "Lecture")
            lecture_name = Path(file_name).stem
            parent_deck_name = course_title
            target_deck_name = f"{course_title}::{lecture_name}"
            
        task_service = get_flashcard_task_service()
        task_id = await task_service.create_task(
            course_material_id=course_material_id,
            user_id=user_id,
            course_id=course_id,
            deduplicate_course=deduplicate_course,
            parent_deck_name=parent_deck_name,
            target_deck_name=target_deck_name,
        )
        
        if trace_ctx:
            trace_ctx.update(output={"status": "pending", "task_id": task_id})
            try: trace_ctx.__exit__(None, None, None)
            except: pass
            
        return FlashcardTaskResponse(task_id=task_id, status="pending", message="Started")
        
    except HTTPException:
        if trace_ctx:
            try: trace_ctx.__exit__(None, None, None)
            except: pass
        raise
    except Exception as e:
        if trace_ctx:
            try: trace_ctx.__exit__(type(e), e, None)
            except: pass
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flashcards/sync", status_code=200)
async def sync_flashcards_from_anki(
    course_id: str = Query(...),
    user_id: str = Query(...),
):
    """
    Sync flashcard cache from Anki to local cache.

    Note: Anki integration may be disabled; in that case, this returns zeroed stats.
    """
    try:
        if not validate_user_exists(user_id):
            raise HTTPException(status_code=404, detail="User not found")

        client = get_supabase_client()
        course_response = (
            client.table("courses")
            .select("title")
            .eq("id", course_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        if not course_response.data:
            raise HTTPException(status_code=404, detail="Course not found or access denied")

        course_title = course_response.data["title"]
        stats = get_flashcard().sync_cache_from_anki(
            parent_deck=course_title,
            user_id=user_id,
            course_id=course_id,
        )
        return {"status": "success", "course_title": course_title, "sync_stats": stats}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/flashcards/retry-ankiweb-sync", status_code=200)
async def retry_ankiweb_sync(user_id: str = Query(...)):
    """
    Retry syncing unsynced cards to AnkiWeb.

    With disabled live Anki integration, this marks pending cards as synced.
    """
    try:
        if not validate_user_exists(user_id):
            raise HTTPException(status_code=404, detail="User not found")

        unsynced_count = get_flashcard().get_unsynced_count(user_id)
        if unsynced_count == 0:
            return {
                "status": "success",
                "message": "No unsynced cards found",
                "synced_count": 0,
            }

        synced_count = get_flashcard().mark_as_synced(user_id)
        return {
            "status": "success",
            "message": f"Marked {synced_count} cards as synced",
            "synced_count": synced_count,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retry sync failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Retry sync failed: {str(e)}")


@router.get("/flashcards/status/{task_id}", response_model=FlashcardTaskStatusResponse)
async def get_flashcard_task_status(task_id: str, user_id: str = Query(...)):
    """Get the status of a flashcard generation task."""
    try:
        task_service = get_flashcard_task_service()
        task = await task_service.get_task(task_id)
        if not task or task.user_id != user_id:
            raise HTTPException(status_code=404, detail="Task not found or access denied")
        return task.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flashcards/download/{task_id}")
async def download_flashcards(task_id: str, user_id: str = Query(...)):
    """Download the generated flashcard APKG file from task cache."""
    try:
        task_service = get_flashcard_task_service()
        task = await task_service.get_task(task_id)
        
        if not task or task.user_id != user_id:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.status != "completed":
            raise HTTPException(status_code=400, detail="Not completed")
            
        return StreamingResponse(
            io.BytesIO(task.apkg_bytes),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{task.filename}"',
                "Content-Type": "application/zip"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flashcards/active/{course_material_id}", response_model=Optional[FlashcardTaskStatusResponse])
async def get_active_flashcard_task(course_material_id: str, user_id: str = Query(...)):
    try:
        task_service = get_flashcard_task_service()
        task = await task_service.get_active_task_for_material(course_material_id, user_id)
        if not task:
            return None
        return task.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flashcards/cancel/{task_id}")
async def cancel_flashcard_task(task_id: str, user_id: str = Query(...)):
    try:
        task_service = get_flashcard_task_service()
        task = await task_service.get_task(task_id)
        if not task or task.user_id != user_id:
            raise HTTPException(status_code=404, detail="Access denied")
            
        cancelled = await task_service.cancel_task(task_id)
        if not cancelled:
            raise HTTPException(status_code=400, detail="Cannot cancel")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flashcards/{course_material_id}")
async def get_flashcards(course_material_id: str, user_id: str = Query(...)):
    try:
        client = get_supabase_client()
        material = client.table("course_materials").select("id, file_name, course_id").eq("id", course_material_id).eq("user_id", user_id).single().execute().data
        if not material:
            raise HTTPException(status_code=404, detail="Not found")
            
        course = client.table("courses").select("title").eq("id", material["course_id"]).single().execute().data
        
        from pathlib import Path
        lecture_name = Path(material.get("file_name", "lecture")).stem
        course_title = course.get("title", "course") if course else "course"
        deck_name = f"{course_title}::{lecture_name}"
        
        flashcards = get_flashcard().get_cached_for_material(deck_name, user_id)
        
        return {
            "flashcards": flashcards,
            "count": len(flashcards)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flashcards/{course_material_id}/download")
async def download_flashcards_from_db(course_material_id: str, user_id: str = Query(...)):
    """Download Flashcards for a material directly from DB as APKG."""
    try:
        client = get_supabase_client()
        material = client.table("course_materials").select("file_name, course_id").eq("id", course_material_id).eq("user_id", user_id).single().execute().data
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
            
        course = client.table("courses").select("title").eq("id", material["course_id"]).single().execute().data
        
        from pathlib import Path
        import re
        
        course_title = course.get("title", "course") if course else "course"
        lecture_name = Path(material.get("file_name", "")).stem
        deck_name = f"{course_title}::{lecture_name}"
        
        flashcards = get_flashcard().get_cached_for_material(deck_name, user_id)
        if not flashcards:
            raise HTTPException(status_code=404, detail="No flashcards found")
            
        cards_for_apkg = [{"front": c.get("front", ""), "back": c.get("back", ""), "tags": c.get("tags", [])} for c in flashcards]
        
        safe_deck_name = re.sub(r'[/\\:*?"<>|]', '', f"{course_title} - {lecture_name}").strip()[:100]
        apkg_bytes = build_anki_apkg(cards_for_apkg, deck_name=deck_name)
        
        return StreamingResponse(
            io.BytesIO(apkg_bytes),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_deck_name}.apkg"',
                "Content-Type": "application/zip"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
