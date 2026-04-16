import logging

from fastapi import APIRouter, Body, HTTPException, Path, Query
from fastapi.responses import StreamingResponse

from app.adapters.supabase.client import get_supabase_client
from app.core.adapters import get_course, get_page_analysis
from app.models.schemas import (
    QuickChatInitiateRequest,
    QuickChatMessageRequest,
    QuickChatSearchResponse,
    QuickChatSearchResult,
    QuickChatWarmupRequest,
)
from app.services.chat_service import get_chat_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _streaming_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


@router.post("/quickchat/initiate")
async def initiate_quickchat(request: QuickChatInitiateRequest = Body(...)) -> dict:
    return get_chat_service().create_quickchat_session(request.user_id)


@router.post("/quickchat/warmup")
async def warmup_quickchat(request: QuickChatWarmupRequest = Body(...)) -> dict:
    # user_id is intentionally accepted for API parity and future authorization hooks.
    _ = request.user_id
    return await get_chat_service().warmup_quickchat_agent(request.thread_id)


@router.post("/quickchat/message")
async def send_quickchat_message(
    request: QuickChatMessageRequest = Body(...),
) -> StreamingResponse:
    try:
        if not get_course().validate_user_exists(request.user_id):
            raise HTTPException(status_code=404, detail="User not found.")

        stream = get_chat_service().stream_quickchat_message(
            user_id=request.user_id,
            message=request.message,
            thread_id=request.thread_id,
            material_id=request.material_id,
            page_number=request.page_number,
            course_id=request.course_id,
        )

        return StreamingResponse(
            stream,
            media_type="text/event-stream",
            headers=_streaming_headers(),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error sending quick chat message: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to send message: {exc}")


@router.get("/quickchat/search", response_model=QuickChatSearchResponse)
async def search_quickchat_topics(
    user_id: str = Query(...),
    query: str = Query(...),
    language: str = Query("auto"),
    limit: int = Query(10, ge=1, le=50),
) -> QuickChatSearchResponse:
    try:
        if not get_course().validate_user_exists(user_id):
            raise HTTPException(status_code=404, detail="User not found")

        results = get_page_analysis().search(
            user_id=user_id, query=query, language=language, limit=limit
        )

        if not results:
            return QuickChatSearchResponse(
                found=False,
                message=f"Keine Ergebnisse fuer '{query}'.",
                results=[],
            )

        search_results = [
            QuickChatSearchResult(
                course_id=result.get("course_id", ""),
                course_title=result.get("course_title", ""),
                course_color=result.get("course_color"),
                material_id=result.get("material_id", ""),
                material_name=result.get("material_name", ""),
                page_number=result.get("page_number", 0),
                summary=result.get("summary", ""),
                key_terms=result.get("key_terms", []),
                rank=float(result.get("rank", 0)),
            )
            for result in results
        ]
        return QuickChatSearchResponse(
            found=True,
            message=f"{len(search_results)} Ergebnis(se) gefunden.",
            results=search_results,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error searching quickchat topics: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to search topics: {exc}")


@router.get("/quickchat/material/{material_id}")
async def get_quickchat_material_info(material_id: str = Path(...)) -> dict:
    try:
        client = get_supabase_client()
        material_response = (
            client.table("course_materials")
            .select("id, file_name, file_path, page_count, processing_status")
            .eq("id", material_id)
            .single()
            .execute()
        )

        if not material_response.data:
            raise HTTPException(status_code=404, detail="Material not found")

        material = material_response.data
        if material.get("processing_status") != "completed":
            raise HTTPException(status_code=400, detail="Material is still processing")

        file_path = material.get("file_path")
        if not file_path:
            raise HTTPException(status_code=400, detail="Material has no file path")

        signed_url_response = client.storage.from_("course_materials").create_signed_url(
            file_path, 3600
        )
        if not signed_url_response or not signed_url_response.get("signedURL"):
            raise HTTPException(status_code=500, detail="Failed to create signed URL")

        return {
            "material_id": material.get("id"),
            "file_name": material.get("file_name"),
            "pdf_url": signed_url_response.get("signedURL"),
            "page_count": material.get("page_count", 0),
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error getting quickchat material info: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get material info: {exc}")
