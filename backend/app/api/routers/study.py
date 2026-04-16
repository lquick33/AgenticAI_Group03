import logging
from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.services.snippet_service import (
    create_snippet,
    get_snippets_for_material,
    delete_snippet
)
from app.services.session_storage import (
    get_or_create_study_conversation,
    load_conversation_with_messages,
    update_conversation_progress,
)
from app.adapters.supabase.client import get_supabase_client
from app.core.adapters import get_course

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/study/session", status_code=200)
async def get_study_session_state(
    material_id: str = Query(...),
    user_id: str = Query(...)
):
    """
    Get the state of the current or most recent study session for a material.
    Returns the last viewed page and recent chat history to resume the session smoothly.
    """
    try:
        # Validate user
        if not get_course().validate_user_exists(user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found. Please sign up first."
            )
            
        # First verify the user has access to this material
        client = get_supabase_client()
        material_response = client.table("course_materials").select("id").eq(
            "id", material_id
        ).eq("user_id", user_id).single().execute()
        
        if not material_response.data:
            raise HTTPException(
                status_code=404,
                detail="Course material not found or access denied"
            )

        conversation, recent_messages = load_conversation_with_messages(
            user_id=user_id,
            course_material_id=material_id,
            limit=20,
        )

        if not conversation:
            # No existing session found
            return {
                "has_session": False,
                "current_page": 1,
                "recent_messages": []
            }

        conversation_id = conversation["id"]
        
        # Extract last page from metadata if available
        current_page = 1
        metadata = conversation.get("metadata") or {}
        if isinstance(metadata, dict) and "last_page_number" in metadata:
            current_page = metadata["last_page_number"]
        
        return {
            "has_session": True,
            "session_id": conversation_id,
            "current_page": current_page,
            "recent_messages": [
                {
                    "id": msg["id"],
                    "role": msg["role"],
                    "content": msg["content"],
                    "context_page": msg.get("context_page_id")
                } 
                for msg in recent_messages
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching study session state: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch study session state: {str(e)}"
        )


@router.post("/study/save-page", status_code=200)
async def save_current_page(
    material_id: str = Query(...),
    page_number: int = Query(...),
    user_id: str = Query(...)
):
    """
    Continuously saves the currently viewed page without initiating a chat.
    Used for resuming state when the user returns.
    """
    try:
        conversation = get_or_create_study_conversation(user_id, material_id)
        update_conversation_progress(conversation["id"], page_number)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error saving current page: {str(e)}")
        # We don't want to crash the UI for background saves
        return {"status": "error", "message": "Failed to save progress, but ignoring"}


@router.post("/study/snippets")
async def upload_snippet(
    file: UploadFile = File(...),
    course_material_id: str = Form(...),
    page_number: int = Form(...),
    user_id: str = Form(...)
):
    """Upload a new slide snippet."""
    try:
        if not get_course().validate_user_exists(user_id):
            raise HTTPException(status_code=404, detail="User not found")
            
        file_bytes = await file.read()
        snippet = create_snippet(
            file_bytes=file_bytes,
            course_material_id=course_material_id,
            page_number=page_number,
            user_id=user_id
        )
        return snippet
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed: {str(e)}")


@router.get("/study/snippets/{material_id}")
async def get_snippets(material_id: str, user_id: str = Query(...)):
    """Get all snippets for a material."""
    try:
        return get_snippets_for_material(material_id, user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/study/snippets/{snippet_id}")
async def remove_snippet(snippet_id: str, user_id: str = Query(...)):
    """Delete a snippet."""
    try:
        delete_snippet(snippet_id, user_id)
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
