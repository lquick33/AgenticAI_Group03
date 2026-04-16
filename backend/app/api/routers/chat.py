import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.adapters.supabase.client import get_supabase_client
from app.core.adapters import get_course, get_material, get_page_analysis
from app.models.schemas import ChatInitiateRequest, ChatMessageRequest
from app.services.chat_service import get_chat_service
from app.services.session_storage import (
    append_messages,
    get_or_create_study_conversation,
    get_tutor_graph_version_from_metadata,
    load_conversation_with_messages,
    set_conversation_tutor_graph_version,
    update_conversation_progress,
)
from app.services.tutor_rollout import TutorGraphResolution, resolve_tutor_graph_version

logger = logging.getLogger(__name__)

router = APIRouter()


def _streaming_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


def _build_initiate_prompt(
    *,
    page_number: int,
    page_summary: str,
    has_history: bool,
    is_initial_open: bool,
) -> str:
    summary = page_summary or "Kein Seiten-Summary verfuegbar."
    if is_initial_open and has_history:
        return (
            f"Der Student ist zurueck in der Lernsitzung auf Seite {page_number}. "
            f"Kurzer Seitenkontext: {summary} "
            "Begruesse den Studenten kurz und knuepfe an das bisher Gelernte an."
        )
    if is_initial_open:
        return (
            f"Der Student startet eine neue Lernsitzung auf Seite {page_number}. "
            f"Kurzer Seitenkontext: {summary} "
            "Gib einen motivierenden Einstieg und erklaere die wichtigsten Punkte der Seite."
        )
    return (
        f"Der Student hat auf Seite {page_number} gewechselt. "
        f"Kurzer Seitenkontext: {summary} "
        "Erklaere den Inhalt dieser Seite klar und studentengerecht."
    )


def _persist_graph_resolution(
    conversation: dict[str, Any],
    resolution: TutorGraphResolution,
) -> TutorGraphResolution:
    metadata = conversation.get("metadata") or {}
    stored_version = get_tutor_graph_version_from_metadata(metadata)
    if stored_version == resolution.graph_version:
        return resolution

    updated_metadata = set_conversation_tutor_graph_version(
        conversation["id"],
        resolution.graph_version,
    )
    conversation["metadata"] = updated_metadata
    return resolution


def _resolve_initiate_graph_version(
    conversation: dict[str, Any],
    request_version: str | None,
) -> TutorGraphResolution:
    metadata = conversation.get("metadata") or {}
    stored_version = get_tutor_graph_version_from_metadata(metadata)
    resolution = resolve_tutor_graph_version(
        request_version,
        stored_version,
        allow_request_override=True,
    )
    return _persist_graph_resolution(conversation, resolution)


def _resolve_message_graph_version(
    conversation: dict[str, Any],
    request_version: str | None,
) -> TutorGraphResolution:
    metadata = conversation.get("metadata") or {}
    stored_version = get_tutor_graph_version_from_metadata(metadata)

    if stored_version is not None:
        if request_version and request_version != stored_version:
            logger.info(
                "Ignoring conflicting tutor_graph_version override on /chat/message for conversation %s: requested=%s stored=%s",
                conversation["id"],
                request_version,
                stored_version,
            )
        return TutorGraphResolution(graph_version=stored_version, source="metadata")

    resolution = resolve_tutor_graph_version(
        request_version,
        stored_version,
        allow_request_override=True,
    )
    return _persist_graph_resolution(conversation, resolution)


@router.post("/chat/initiate")
async def initiate_chat(request: ChatInitiateRequest) -> StreamingResponse:
    try:
        if not get_course().validate_user_exists(request.user_id):
            raise HTTPException(status_code=404, detail="User not found.")

        client = get_supabase_client()
        material_response = (
            client.table("course_materials")
            .select("id, course_id, page_count")
            .eq("id", request.material_id)
            .eq("user_id", request.user_id)
            .single()
            .execute()
        )
        if not material_response.data:
            raise HTTPException(
                status_code=404,
                detail="Course material not found or access denied",
            )

        course_material_id = material_response.data["id"]
        course_id = material_response.data.get("course_id")

        conversation = get_or_create_study_conversation(
            user_id=request.user_id,
            course_material_id=course_material_id,
            course_id=course_id,
            initial_page=request.page_number,
        )
        resolution = _resolve_initiate_graph_version(
            conversation,
            request.tutor_graph_version,
        )
        conversation_id = conversation["id"]
        thread_id = str(conversation_id)

        _, stored_messages = load_conversation_with_messages(
            user_id=request.user_id,
            course_material_id=course_material_id,
            limit=20,
        )
        has_history = bool(stored_messages)

        page_summary = "Inhalt wird noch analysiert."
        try:
            analysis = get_page_analysis().get(
                course_material_id=course_material_id,
                page_number=request.page_number,
                user_id=request.user_id,
            )
            page_summary = analysis.get("summary") or page_summary
        except Exception:
            pass

        course_summary: dict[str, Any] | None = None
        try:
            course_summary = get_material().get_summary(
                course_material_id=course_material_id, user_id=request.user_id
            )
        except Exception as exc:
            logger.warning("Failed to load course summary for chat/initiate: %s", exc)

        prompt = _build_initiate_prompt(
            page_number=request.page_number,
            page_summary=page_summary,
            has_history=has_history,
            is_initial_open=request.is_initial_open,
        )

        async def on_complete(assistant_text: str) -> None:
            try:
                context_page_id = get_page_analysis().get_id(
                    course_material_id=course_material_id,
                    page_number=request.page_number,
                    user_id=request.user_id,
                )
            except Exception:
                context_page_id = None

            try:
                if assistant_text:
                    append_messages(
                        conversation_id,
                        [
                            {
                                "role": "assistant",
                                "content": assistant_text,
                                "context_page_id": context_page_id,
                            }
                        ],
                    )
                update_conversation_progress(conversation_id, request.page_number)
            except Exception as exc:
                logger.error("Failed to persist /chat/initiate messages: %s", exc)

        stream = get_chat_service().stream_tutor(
            thread_id=thread_id,
            conversation_id=str(conversation_id),
            user_id=request.user_id,
            material_id=course_material_id,
            user_message=prompt,
            graph_version=resolution.graph_version,
            rollout_source=resolution.source,
            current_page=request.page_number,
            course_material_summary=course_summary,
            bootstrap_messages=stored_messages,
            on_complete=on_complete,
        )

        return StreamingResponse(
            stream,
            media_type="text/event-stream",
            headers=_streaming_headers(),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error in /chat/initiate: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to initiate chat: {exc}")


@router.post("/chat/message")
async def send_chat_message(request: ChatMessageRequest) -> StreamingResponse:
    try:
        if not get_course().validate_user_exists(request.user_id):
            raise HTTPException(status_code=404, detail="User not found.")

        client = get_supabase_client()
        material_response = (
            client.table("course_materials")
            .select("id, course_id")
            .eq("id", request.material_id)
            .eq("user_id", request.user_id)
            .single()
            .execute()
        )
        if not material_response.data:
            raise HTTPException(
                status_code=404,
                detail="Course material not found or access denied",
            )

        course_material_id = material_response.data["id"]
        course_id = material_response.data.get("course_id")

        conversation = get_or_create_study_conversation(
            user_id=request.user_id,
            course_material_id=course_material_id,
            course_id=course_id,
        )
        resolution = _resolve_message_graph_version(
            conversation,
            request.tutor_graph_version,
        )
        conversation_id = conversation["id"]
        thread_id = str(conversation_id)

        _, stored_messages = load_conversation_with_messages(
            user_id=request.user_id,
            course_material_id=course_material_id,
            limit=20,
        )

        current_page = request.page_number
        if current_page is None:
            metadata = conversation.get("metadata") or {}
            if isinstance(metadata, dict):
                current_page = metadata.get("last_page_number")

        course_summary: dict[str, Any] | None = None
        try:
            course_summary = get_material().get_summary(
                course_material_id=course_material_id,
                user_id=request.user_id,
            )
        except Exception as exc:
            logger.warning("Failed to load course summary for /chat/message: %s", exc)

        page_context = ""
        if current_page is not None:
            try:
                analysis = get_page_analysis().get(
                    course_material_id=course_material_id,
                    page_number=current_page,
                    user_id=request.user_id,
                )
                summary = analysis.get("summary") or ""
                if summary:
                    page_context = (
                        f"\n\n[Kontext: Der Student ist auf Seite {current_page}. "
                        f"Inhalt dieser Seite: {summary[:500]}"
                        f"{'...' if len(summary) > 500 else ''}]"
                    )
            except Exception as exc:
                logger.warning("Failed to load page context: %s", exc)

        message_with_context = request.message + page_context if page_context else request.message

        async def on_complete(assistant_text: str) -> None:
            context_page_id = None
            if current_page is not None:
                try:
                    context_page_id = get_page_analysis().get_id(
                        course_material_id=course_material_id,
                        page_number=current_page,
                        user_id=request.user_id,
                    )
                except Exception:
                    context_page_id = None

            try:
                messages_to_store = [
                    {
                        "role": "user",
                        "content": request.message,
                        "context_page_id": context_page_id,
                    }
                ]
                if assistant_text:
                    messages_to_store.append(
                        {
                            "role": "assistant",
                            "content": assistant_text,
                            "context_page_id": context_page_id,
                        }
                    )
                append_messages(conversation_id, messages_to_store)
                if current_page is not None:
                    update_conversation_progress(conversation_id, current_page)
            except Exception as exc:
                logger.error("Failed to persist /chat/message messages: %s", exc)

        stream = get_chat_service().stream_tutor(
            thread_id=thread_id,
            conversation_id=str(conversation_id),
            user_id=request.user_id,
            material_id=course_material_id,
            user_message=message_with_context,
            graph_version=resolution.graph_version,
            rollout_source=resolution.source,
            current_page=current_page,
            course_material_summary=course_summary,
            bootstrap_messages=stored_messages,
            on_complete=on_complete,
        )

        return StreamingResponse(
            stream,
            media_type="text/event-stream",
            headers=_streaming_headers(),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error in /chat/message: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to send message: {exc}")
