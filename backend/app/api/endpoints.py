"""
API Endpoints

FastAPI route handlers for PDF upload and processing.
"""

import io
import json
import logging
import sys
import traceback
import uuid
import time
from collections import defaultdict
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Form, BackgroundTasks, Path, Body, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pdf2image import convert_from_bytes, pdfinfo_from_bytes
from PIL import Image
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver

from app.agents.tutor import TutorAgent
from app.services.analyzer import get_gemini_model

from app.models.schemas import (
    UploadResponse,
    ErrorResponse,
    CourseResponse,
    CourseUpdateRequest,
    PageAnalysisQuery,
    PageAnalysisDataResponse,
    ChatInitiateRequest,
    ChatMessageRequest,
    FlashcardTaskResponse,
    FlashcardTaskStatusResponse,
    MaterialUpdateRequest,
    MaterialResponse,
    QuizSubmit,
    QuizResult,
    QuizResponse,
)
from app.services.pdf_processor import process_pdf_background
from app.services.snippet_service import (
    create_snippet,
    get_snippets_for_material,
    delete_snippet
)
from app.services.storage import (
    upload_pdf_to_storage,
    create_course_material,
    validate_user_exists,
    get_course,
    get_supabase_client,
    get_page_analysis,
    get_page_analysis_id,
    get_flashcards_for_material,
    get_cached_flashcards_for_material,
    get_course_material_summary,
    update_course_material_filename,
    delete_course_material,
    get_study_history,
    sync_anki_study_history,
)
from app.agents.flashcards import FlashcardGeneratorAgent
from app.services.flashcard_service import build_anki_apkg
from app.services.anki import AnkiClient, AnkiConnectionError, AnkiError, DailyStudyStats
from app.services.flashcard_task_service import get_flashcard_task_service
from app.services.observability import get_langfuse_client
from app.services.session_storage import (
    get_or_create_study_conversation,
    update_conversation_progress,
    append_messages,
    load_conversation_with_messages,
)
from app.services.quiz_service import (
    submit_quiz_results,
    get_quiz,
    get_quiz_result,
)
from app.services.quiz_creation_lock import get_quiz_creation_lock
from langfuse import get_client, propagate_attributes
from app.core.config import settings
import os

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Rate Limiting for Login Endpoints
# =============================================================================

class RateLimiter:
    """
    Simple in-memory rate limiter for protecting sensitive endpoints.
    
    Limits requests per IP address within a time window.
    Resets on server restart (acceptable for this use case).
    """
    
    def __init__(self, max_requests: int = 5, window_seconds: int = 900):
        """
        Args:
            max_requests: Maximum number of requests allowed in the window
            window_seconds: Time window in seconds (default: 15 minutes)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)
    
    def _cleanup_old_requests(self, key: str) -> None:
        """Remove expired requests from tracking."""
        current_time = time.time()
        cutoff = current_time - self.window_seconds
        self.requests[key] = [t for t in self.requests[key] if t > cutoff]
    
    def is_rate_limited(self, key: str) -> tuple[bool, int]:
        """
        Check if a key (IP address) is rate limited.
        
        Returns:
            Tuple of (is_limited, remaining_requests)
        """
        self._cleanup_old_requests(key)
        current_count = len(self.requests[key])
        remaining = max(0, self.max_requests - current_count)
        return current_count >= self.max_requests, remaining
    
    def record_request(self, key: str) -> None:
        """Record a request for rate limiting."""
        self._cleanup_old_requests(key)
        self.requests[key].append(time.time())
    
    def get_retry_after(self, key: str) -> int:
        """Get seconds until rate limit resets."""
        if not self.requests[key]:
            return 0
        oldest = min(self.requests[key])
        return max(0, int(self.window_seconds - (time.time() - oldest)))


# Rate limiter for AnkiWeb login: 5 attempts per 15 minutes per IP
ankiweb_login_limiter = RateLimiter(max_requests=5, window_seconds=900)


# =============================================================================
# AnkiWeb Status Cache
# =============================================================================

# Cache for AnkiWeb login status to avoid slow Docker/AnkiConnect checks
# TTL: 30 seconds - long enough for UI responsiveness, short enough to catch changes
_ankiweb_status_cache: dict = {
    "data": None,
    "timestamp": 0.0
}
ANKIWEB_STATUS_CACHE_TTL = 30  # seconds


def _clear_ankiweb_status_cache() -> None:
    """Clear the AnkiWeb status cache (call after login/logout)."""
    _ankiweb_status_cache["data"] = None
    _ankiweb_status_cache["timestamp"] = 0.0


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check for forwarded header (when behind reverse proxy)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # Check for real IP header
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    # Fallback to direct client
    return request.client.host if request.client else "unknown"


def generate_message_id(prefix: str = "msg") -> str:
    """
    Generate a unique message ID for SSE events.
    
    Args:
        prefix: Optional prefix for the message ID (default: "msg")
        
    Returns:
        Unique message ID string (e.g., "msg-550e8400-e29b-41d4-a716-446655440000")
    """
    return f"{prefix}-{uuid.uuid4()}"


def get_tutor_prompt(prompt_name: str, **variables) -> str:
    """
    Load a tutor agent prompt from Langfuse and compile it with variables.
    
    Args:
        prompt_name: Name of the prompt (e.g., "tutor-agent/welcome-back")
        **variables: Variables to compile into the prompt
        
    Returns:
        Compiled prompt string
        
    Raises:
        RuntimeError: If Langfuse client is not available or prompt cannot be loaded
    """
    langfuse_client = get_langfuse_client()
    if not langfuse_client:
        raise RuntimeError(f"Langfuse client is not available. Cannot load prompt '{prompt_name}'.")
    
    try:
        langfuse_prompt = langfuse_client.get_prompt(
            prompt_name,
            label="production"
        )
        compiled_prompt = langfuse_prompt.compile(**variables)
        logger.debug(f"✅ Using Langfuse prompt for {prompt_name}")
        return compiled_prompt
    except Exception as e:
        logger.error(f"Failed to load Langfuse prompt '{prompt_name}': {e}")
        raise RuntimeError(f"Cannot load prompt '{prompt_name}' from Langfuse: {e}") from e


def pil_image_to_bytes(image: Image.Image, format: str = "JPEG") -> bytes:
    """
    Convert PIL Image to bytes.
    
    Args:
        image: PIL Image object
        format: Output format (default: JPEG)
        
    Returns:
        Image bytes
    """
    img_bytes = io.BytesIO()
    image.save(img_bytes, format=format)
    return img_bytes.getvalue()


@router.post("/upload", response_model=UploadResponse, status_code=200)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Form(..., description="User ID (UUID)"),
    course_id: str = Form(..., description="Course ID (required - must exist)")
) -> UploadResponse:
    """
    Upload and process a PDF file (asynchronous background processing).
    
    This endpoint:
    1. Validates user exists
    2. Validates course exists and belongs to user
    3. Accepts PDF file upload
    4. Uploads PDF to storage
    5. Creates course_material record with status 'uploading'
    6. Starts background task for PDF processing
    7. Returns immediately with status 'queued'
    
    Note: Course must be created beforehand (e.g., via web app).
    This endpoint does not create courses automatically.
    Processing happens asynchronously in the background with parallel page analysis.
    
    Args:
        background_tasks: FastAPI BackgroundTasks for async processing
        file: PDF file to upload
        user_id: User ID (required)
        course_id: Course ID (required - must be created beforehand)
        
    Returns:
        UploadResponse with status 'queued' and material_id
        
    Raises:
        HTTPException: If validation fails or course doesn't exist
    """
    # Langfuse Tracing Setup für Upload-Endpoint
    langfuse = None
    trace_ctx = None
    if settings.LANGFUSE_ENABLED:
        try:
            # Set environment variables if needed
            if settings.LANGFUSE_PUBLIC_KEY and "LANGFUSE_PUBLIC_KEY" not in os.environ:
                os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
            if settings.LANGFUSE_SECRET_KEY and "LANGFUSE_SECRET_KEY" not in os.environ:
                os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
            if settings.LANGFUSE_BASE_URL and "LANGFUSE_HOST" not in os.environ:
                os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_BASE_URL
            
            langfuse = get_client()
            if langfuse:
                trace_input = {
                    "filename": file.filename,
                    "user_id": user_id,
                    "course_id": course_id
                }
                logger.info(f"🟡 Langfuse: Starting trace 'pdf-api-upload' with input: {trace_input}")
                trace_ctx = langfuse.start_as_current_observation(
                    name="pdf-api-upload",
                    input=trace_input,
                    metadata={
                        "user_id": user_id,
                        "course_id": course_id,
                        "endpoint": "/upload"
                    }
                )
                logger.info("🟢 Langfuse: Trace 'pdf-api-upload' started successfully")
        except Exception as e:
            logger.warning(f"🔴 Langfuse: Failed to start trace: {e}")
    
    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="File must be a PDF"
        )
    
    # 1. Validate user exists
    logger.info(f"Validating user: {user_id}")
    try:
        if not validate_user_exists(user_id):
            logger.warning(f"User not found: {user_id}")
            raise HTTPException(
                status_code=404,
                detail="User not found. Please sign up first."
            )
        logger.info(f"User validated: {user_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate user: {str(e)}"
        )
    
    # 2. Validate course exists and belongs to user
    logger.info(f"Validating course: {course_id} for user: {user_id}")
    try:
        course_data = get_course(
            user_id=user_id,
            course_id=course_id
        )
        actual_course_id = course_data["id"]
        logger.info(f"Course validated: {actual_course_id}")
        
    except ValueError as e:
        logger.warning(f"Course validation failed: {str(e)}")
        raise HTTPException(
            status_code=404,
            detail=str(e)  # "Course not found or access denied"
        )
    except Exception as e:
        logger.error(f"Error validating course: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )
    
    try:
        logger.info(f"Reading PDF file: {file.filename}")
        # Read file bytes
        file_bytes = await file.read()
        
        if len(file_bytes) == 0:
            logger.warning("Uploaded file is empty")
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty"
            )
        
        logger.info(f"PDF file read: {len(file_bytes)} bytes")
        
        # Get page count using pdfinfo (faster than converting to images)
        try:
            logger.info("Getting PDF info...")
            info = pdfinfo_from_bytes(file_bytes)
            page_count = info["Pages"]
            logger.info(f"PDF has {page_count} pages")
        except Exception as e:
            logger.error(f"Failed to get PDF info: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=400,
                detail=f"Failed to read PDF info: {str(e)}"
            )
        
        if page_count == 0:
            raise HTTPException(
                status_code=400,
                detail="PDF contains no pages"
            )
        
        # Upload PDF to storage
        try:
            storage_path = upload_pdf_to_storage(
                file_bytes=file_bytes,
                filename=file.filename or "uploaded.pdf",
                user_id=user_id
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload PDF to storage: {str(e)}"
            )
        
        # Create course_material record
        try:
            material_record = create_course_material(
                course_id=actual_course_id,  # Use actual course ID from above
                filename=file.filename or "uploaded.pdf",
                file_path=storage_path,
                user_id=user_id,
                page_count=page_count,
                file_type="pdf"
            )
            material_id = material_record["id"]
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create course material record: {str(e)}"
            )
        
        # Page count is already determined above

        
        # Start background processing task
        logger.info(f"Starting background processing task for material {material_id}")
        background_tasks.add_task(
            process_pdf_background,
            material_id=material_id,
            file_bytes=file_bytes,
            user_id=user_id,
            course_id=actual_course_id,
            max_concurrent=5  # Process 5 pages in parallel
        )
        
        # Update Langfuse trace with success
        if trace_ctx and langfuse:
            try:
                trace_ctx.update(
                    output={
                        "status": "queued",
                        "material_id": material_id,
                        "page_count": page_count
                    },
                    metadata={
                        "material_id": material_id,
                        "page_count": page_count
                    }
                )
                logger.info("🟢 Langfuse: Trace 'pdf-api-upload' updated with success")
            except Exception as e:
                logger.warning(f"🔴 Langfuse: Failed to update trace: {e}")
        
        # Return immediately with queued status
        response = UploadResponse(
            message="PDF upload successful. Processing started in background.",
            course_material_id=material_id,
            page_count=page_count,
            pages_analyzed=0,  # Will be updated by background task
            status="queued",
            error_message=None
        )
        
        # Close Langfuse trace
        if trace_ctx:
            try:
                trace_ctx.__exit__(None, None, None)
                logger.info("🟢 Langfuse: Trace 'pdf-api-upload' closed - data sent to Langfuse")
            except Exception as e:
                logger.warning(f"🔴 Langfuse: Error closing trace: {e}")
        
        return response
    
    except HTTPException:
        # Update Langfuse trace with error before raising
        if trace_ctx and langfuse:
            try:
                trace_ctx.update(
                    output={"error": "HTTPException raised"},
                    level="ERROR"
                )
            except Exception:
                pass
        raise
    except Exception as e:
        # Log the full error with traceback
        logger.error(f"Unexpected error during PDF processing: {str(e)}", exc_info=True)
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Update Langfuse trace with error
        if trace_ctx and langfuse:
            try:
                trace_ctx.update(
                    output={"error": str(e)},
                    level="ERROR"
                )
                logger.warning("🔴 Langfuse: Trace 'pdf-api-upload' marked as ERROR")
            except Exception as trace_error:
                logger.warning(f"🔴 Langfuse: Error updating trace: {trace_error}")
        
        # Close Langfuse trace
        if trace_ctx:
            try:
                trace_ctx.__exit__(type(e), e, None)
            except Exception:
                pass
        
        # Handle unexpected errors
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error during PDF processing: {str(e)}"
        )


@router.get("/courses", response_model=list[CourseResponse], status_code=200)
async def list_courses_endpoint(
    user_id: str = Query(..., description="User ID (UUID)")
) -> list[CourseResponse]:
    """
    List all courses for a user.
    
    Args:
        user_id: User ID (UUID) - required for authorization
        
    Returns:
        List of CourseResponse with all user's courses
        
    Raises:
        HTTPException: If validation fails
    """
    # Validate user exists
    try:
        if not validate_user_exists(user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found. Please sign up first."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate user: {str(e)}"
        )
    
    # Fetch courses
    client = get_supabase_client()
    try:
        response = client.table("courses").select("*").eq(
            "user_id", user_id
        ).order("updated_at", desc=False).execute()
        
        if response.data:
            return [CourseResponse(**course) for course in response.data]
        else:
            return []
    except Exception as e:
        logger.error(f"Error fetching courses: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch courses: {str(e)}"
        )


@router.get("/courses/{course_id}", response_model=CourseResponse, status_code=200)
async def get_course_endpoint(
    course_id: str = Path(..., description="Course ID (UUID)"),
    user_id: str = Query(..., description="User ID (UUID)")
) -> CourseResponse:
    """
    Get course details by ID.
    
    Validates that the course exists and belongs to the user.
    
    Args:
        course_id: Course ID (UUID)
        user_id: User ID (UUID) - required for authorization
        
    Returns:
        CourseResponse with course data
        
    Raises:
        HTTPException: If course not found or access denied
    """
    try:
        course_data = get_course(user_id=user_id, course_id=course_id)
        return CourseResponse(**course_data)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error fetching course: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch course: {str(e)}"
        )


@router.post("/courses", response_model=CourseResponse, status_code=201)
async def create_course_endpoint(
    user_id: str = Query(..., description="User ID (UUID)"),
    course_data: CourseUpdateRequest = ...
) -> CourseResponse:
    """
    Create a new course.
    
    Args:
        user_id: User ID (UUID) - required for authorization
        course_data: CourseUpdateRequest with course data
        
    Returns:
        CourseResponse with created course data
        
    Raises:
        HTTPException: If validation fails
    """
    # Validate user exists
    try:
        if not validate_user_exists(user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found. Please sign up first."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate user: {str(e)}"
        )
    
    # Build insert data
    insert_data = {
        "user_id": user_id,
    }
    if course_data.title:
        insert_data["title"] = course_data.title
    else:
        raise HTTPException(
            status_code=400,
            detail="Title is required"
        )
    if course_data.description is not None:
        insert_data["description"] = course_data.description
    if course_data.exam_date is not None:
        insert_data["exam_date"] = course_data.exam_date if course_data.exam_date else None
    if course_data.color_code is not None:
        insert_data["color_code"] = course_data.color_code
    
    # Create course
    client = get_supabase_client()
    try:
        response = client.table("courses").insert(insert_data).execute()
        
        if response.data and len(response.data) > 0:
            return CourseResponse(**response.data[0])
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to create course"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating course: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create course: {str(e)}"
        )


@router.put("/courses/{course_id}", response_model=CourseResponse, status_code=200)
async def update_course_endpoint(
    course_id: str = Path(..., description="Course ID (UUID)"),
    user_id: str = Query(..., description="User ID (UUID)"),
    course_update: CourseUpdateRequest = ...
) -> CourseResponse:
    """
    Update course data.
    
    Validates that the course exists and belongs to the user.
    Only provided fields will be updated.
    
    Args:
        course_id: Course ID (UUID)
        user_id: User ID (UUID) - required for authorization
        course_update: CourseUpdateRequest with fields to update
        
    Returns:
        CourseResponse with updated course data
        
    Raises:
        HTTPException: If course not found or access denied
    """
    # First validate course exists and belongs to user
    try:
        get_course(user_id=user_id, course_id=course_id)
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    
    # Build update dict (only include non-None fields)
    update_data = {}
    if course_update.title is not None:
        update_data["title"] = course_update.title
    if course_update.description is not None:
        update_data["description"] = course_update.description
    if course_update.exam_date is not None:
        # Handle empty string as null
        update_data["exam_date"] = course_update.exam_date if course_update.exam_date else None
    if course_update.color_code is not None:
        update_data["color_code"] = course_update.color_code
    
    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields provided for update"
        )
    
    # Update course
    client = get_supabase_client()
    try:
        response = client.table("courses").update(update_data).eq(
            "id", course_id
        ).eq("user_id", user_id).execute()
        
        if response.data and len(response.data) > 0:
            return CourseResponse(**response.data[0])
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to update course"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating course: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update course: {str(e)}"
        )


@router.get("/page-analysis", response_model=PageAnalysisDataResponse, status_code=200)
async def get_page_analysis_endpoint(
    course_material_id: str = Query(..., description="Course material ID (UUID)"),
    page_number: int = Query(..., description="Page number (1-indexed)"),
    user_id: str = Query(..., description="User ID (UUID)")
) -> PageAnalysisDataResponse:
    """
    Get page analysis data for a specific page.
    
    Retrieves structured analysis data (summary, key terms, exam questions, diagram descriptions)
    from the page_analyses table for the specified course material and page number.
    
    Args:
        course_material_id: Course material ID (UUID)
        page_number: Page number (1-indexed)
        user_id: User ID (UUID) - required for authorization
        
    Returns:
        PageAnalysisDataResponse with analysis data
        
    Raises:
        HTTPException: If page analysis not found, access denied, or query fails
    """
    try:
        # Validate user exists
        if not validate_user_exists(user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found. Please sign up first."
            )
        
        # Get page analysis using service function
        analysis_data = get_page_analysis(
            course_material_id=course_material_id,
            page_number=page_number,
            user_id=user_id
        )
        
        return PageAnalysisDataResponse(**analysis_data)
        
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching page analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch page analysis: {str(e)}"
        )


# Global checkpointer for agent persistence
_checkpointer = MemorySaver()


async def _stream_agent_response(
    agent: TutorAgent,
    message: str,
    thread_id: str,
    user_id: str
) -> AsyncGenerator[str, None]:
    """
    Stream agent response as SSE events.
    
    Args:
        agent: TutorAgent instance
        message: User message
        thread_id: Thread ID for conversation persistence
        user_id: User ID
        
    Yields:
        SSE-formatted chunks
    """
    try:
        # Stream agent response
        async for chunk in agent.graph.astream(
            {"messages": [HumanMessage(content=message)]},
            config={"configurable": {"thread_id": thread_id, "user_id": user_id}}
        ):
            # Format as SSE
            chunk_data = {}
            for node_name, node_data in chunk.items():
                if "messages" in node_data:
                    # Convert messages to serializable format
                    messages = []
                    for msg in node_data["messages"]:
                        if hasattr(msg, "content"):
                            messages.append({
                                "role": "assistant" if hasattr(msg, "tool_calls") else "assistant",
                                "content": msg.content
                            })
                    chunk_data[node_name] = {"messages": messages}
            
            yield f"data: {json.dumps(chunk_data)}\n\n"
        
        # Send end marker
        yield "data: [DONE]\n\n"
        
    except Exception as e:
        logger.error(f"Error streaming agent response: {str(e)}", exc_info=True)
        error_data = {"error": str(e)}
        yield f"data: {json.dumps(error_data)}\n\n"


@router.post("/chat/initiate")
async def initiate_chat(
    request: ChatInitiateRequest = Body(...)
) -> StreamingResponse:
    """
    Initiate a chat session for a study session.
    
    When a user navigates to a new page, this endpoint:
    1. Creates or retrieves the tutor agent
    2. Injects a system message about the page change
    3. Retrieves page analysis data
    4. Streams the agent's greeting and explanation
    
    Args:
        request: ChatInitiateRequest with material_id, page_number, user_id
        
    Returns:
        StreamingResponse with SSE events
    """
    try:
        # Validate user
        if not validate_user_exists(request.user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found. Please sign up first."
            )
        
        # Get course material to find course_material_id and course_id
        client = get_supabase_client()
        material_response = client.table("course_materials").select(
            "id, course_id, page_count"
        ).eq("id", request.material_id).eq("user_id", request.user_id).single().execute()
        
        if not material_response.data:
            raise HTTPException(
                status_code=404,
                detail="Course material not found or access denied"
            )
        course_material_id = material_response.data["id"]
        course_id = material_response.data.get("course_id")
        total_pages = material_response.data.get("page_count")
        
        # Get page analysis data for system message
        try:
            page_analysis = get_page_analysis(
                course_material_id=course_material_id,
                page_number=request.page_number,
                user_id=request.user_id
            )
            summary = page_analysis.get("summary", "No summary available")
        except ValueError:
            # Page analysis not found, use default
            summary = "Content is being analyzed"
        
        # Get course material summary for persistent context
        course_summary = None
        try:
            course_summary = get_course_material_summary(
                course_material_id=course_material_id,
                user_id=request.user_id
            )
        except Exception as summary_error:
            logger.warning(f"Failed to load course material summary: {summary_error}")
        
        # Initialize LLM and agent
        llm = get_gemini_model()
        agent = TutorAgent(llm=llm, checkpointer=_checkpointer)
        
        # Get or create study conversation in Supabase
        conversation = get_or_create_study_conversation(
            user_id=request.user_id,
            course_material_id=course_material_id,
            course_id=course_id,
            initial_page=request.page_number,
        )
        conversation_id = conversation["id"]
        
        # Thread ID: conversation_id for continuous conversation
        thread_id = str(conversation_id)
        
        # Base system message about the current page
        # This is added to the conversation context but not shown directly to the user
        system_message = (
            f"The student is currently on Page {request.page_number}. "
            f"Summary of Page {request.page_number}: {summary}. "
            f"Help them understand this slide in a clear and student-friendly way."
        )
        
        # Stream response
        async def event_generator() -> AsyncGenerator[str, None]:
            # Langfuse Tracing Setup
            # WICHTIG: get_client() liest direkt aus os.environ, nicht aus settings!
            # Daher müssen wir die Werte aus settings in os.environ setzen
            if settings.LANGFUSE_PUBLIC_KEY and "LANGFUSE_PUBLIC_KEY" not in os.environ:
                os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
            if settings.LANGFUSE_SECRET_KEY and "LANGFUSE_SECRET_KEY" not in os.environ:
                os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
            if settings.LANGFUSE_BASE_URL and "LANGFUSE_HOST" not in os.environ:
                # Langfuse SDK verwendet LANGFUSE_HOST für die Base URL
                os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_BASE_URL
            
            langfuse = get_client()
            trace = None
            trace_ctx = None  # Context Manager für __exit__()
            propagate_ctx = None
            
            # Context Manager manuell starten
            if langfuse and settings.LANGFUSE_ENABLED:
                try:
                    trace_input = {
                        "user_id": request.user_id,
                        "material_id": course_material_id,
                        "page_number": request.page_number
                    }
                    logger.info(f"🟡 Langfuse: Starting trace 'tutor-agent-initiate' with input: {trace_input}")
                    trace_ctx = langfuse.start_as_current_observation(
                        as_type="span",
                        name="tutor-agent-initiate",
                        input=trace_input
                    )
                    # WICHTIG: __enter__() gibt den aktiven span zurück, aber wir brauchen den Context Manager für __exit__()
                    trace = trace_ctx.__enter__()
                    logger.info("🟢 Langfuse: Trace 'tutor-agent-initiate' started successfully")
                    
                    propagate_metadata = {
                        "material_id": course_material_id,
                        "page_number": request.page_number,
                        "course_id": course_id
                    }
                    logger.info(f"🟡 Langfuse: Propagating attributes - user_id={request.user_id}, session_id={thread_id}, metadata={propagate_metadata}")
                    propagate_ctx = propagate_attributes(
                        user_id=request.user_id,
                        session_id=thread_id,  # conversation_id als session
                        tags=["tutor-agent", "chat-initiate"],
                        metadata=propagate_metadata
                    )
                    propagate_ctx.__enter__()
                    logger.info("🟢 Langfuse: Attributes propagated successfully")
                except Exception as e:
                    logger.error(f"🔴 Langfuse: Setup failed: {e}", exc_info=True)
                    # Wir machen weiter, auch wenn Tracing fehlschlägt
                    trace = None
                    trace_ctx = None
                    propagate_ctx = None
            
            try:
                # First, inject system message and initial message
                config = {"configurable": {"thread_id": thread_id, "user_id": request.user_id}}
                
                # Check if thread exists and load existing messages from LangGraph
                snapshot = agent.graph.get_state(config)
                is_new_thread = snapshot is None or not snapshot.values or not snapshot.values.get("messages")

                # Base messages for the LLM call
                base_messages = []

                stored_messages = []
                conversation_has_history = False
                last_message_is_welcome_back = False

                # Helper function to detect if a message is a "Welcome Back" message
                def is_welcome_back_message(content: str) -> bool:
                    """Check if a message contains typical Welcome Back phrases."""
                    if not content:
                        return False
                    content_lower = content.lower()
                    welcome_phrases = [
                        "schön, dass du wieder da bist",
                        "wir haben jetzt",
                        "von",
                        "seiten abgearbeitet",
                        "kannst du dich an alles erinnern",
                        "soll ich dir nochmal eine kurze zusammenfassung geben"
                    ]
                    # Check if at least 2 of the key phrases are present
                    matches = sum(1 for phrase in welcome_phrases if phrase in content_lower)
                    return matches >= 2
                
                # Helper function to fix incomplete tool call pairs and validate message ordering
                def fix_incomplete_tool_calls(messages: list) -> list:
                    """
                    Validate and fix message ordering to comply with Gemini API requirements.
                    Gemini API requires strict ordering:
                    - User message (HumanMessage)
                    - Assistant with tool_calls (AIMessage with tool_calls)
                    - Tool responses (ToolMessage) - MUST come immediately after AIMessage with tool_calls
                    - (Optional) Assistant final response (AIMessage without tool_calls)
                    - User message (HumanMessage)
                    
                    This function:
                    1. Removes any AIMessage with tool_calls that doesn't have corresponding ToolMessages
                    2. Ensures ToolMessages come immediately after their AIMessage
                    3. Removes orphaned ToolMessages (without preceding AIMessage)
                    
                    Args:
                        messages: List of messages to check
                        
                    Returns:
                        Fixed list of messages that comply with Gemini API requirements
                    """
                    if not messages:
                        return messages
                    
                    fixed_messages = []
                    i = 0
                    
                    while i < len(messages):
                        msg = messages[i]
                        
                        # Check if this is an AIMessage with tool_calls
                        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                            # Collect all tool call IDs from this AIMessage
                            tool_call_ids = set()
                            for tool_call in msg.tool_calls:
                                tool_call_id = tool_call.get("id") if isinstance(tool_call, dict) else getattr(tool_call, "id", None)
                                if tool_call_id:
                                    tool_call_ids.add(tool_call_id)
                            
                            # Look ahead to find corresponding ToolMessages
                            # They should come immediately after the AIMessage
                            found_tool_messages = []
                            j = i + 1
                            while j < len(messages) and isinstance(messages[j], ToolMessage):
                                tool_msg = messages[j]
                                tool_call_id = getattr(tool_msg, "tool_call_id", None)
                                if tool_call_id in tool_call_ids:
                                    found_tool_messages.append(tool_msg)
                                j += 1
                            
                            # Check if all tool calls have corresponding ToolMessages
                            found_tool_call_ids = {getattr(tm, "tool_call_id", None) for tm in found_tool_messages}
                            
                            if found_tool_call_ids == tool_call_ids and len(found_tool_messages) == len(tool_call_ids):
                                # All tool calls have responses - keep the AIMessage and ToolMessages
                                fixed_messages.append(msg)
                                fixed_messages.extend(found_tool_messages)
                                i = j  # Skip past the ToolMessages
                            else:
                                # Incomplete tool call pair - remove the AIMessage
                                logger.warning(
                                    f"Incomplete tool call pair detected at index {i}: AIMessage has {len(tool_call_ids)} tool_calls, "
                                    f"but only {len(found_tool_messages)} ToolMessages found. Removing incomplete AIMessage to prevent API error."
                                )
                                i += 1  # Skip the incomplete AIMessage
                        elif isinstance(msg, ToolMessage):
                            # Orphaned ToolMessage (no preceding AIMessage with tool_calls)
                            # Remove it to prevent API errors
                            logger.warning(f"Orphaned ToolMessage detected at index {i}, removing to prevent API error.")
                            i += 1
                        else:
                            # Regular message (HumanMessage, AIMessage without tool_calls, SystemMessage)
                            fixed_messages.append(msg)
                            i += 1
                    
                    return fixed_messages

                def has_pending_quiz_creation(material_id: str, user_id: str) -> bool:
                    """
                    Check if there is a pending quiz creation using the lock service.
                    
                    This is a simplified version that uses the QuizCreationLock service
                    instead of parsing messages, which is more reliable and efficient.
                    
                    Args:
                        material_id: Course material ID
                        user_id: User ID
                        
                    Returns:
                        True if a quiz creation is pending (lock exists), False otherwise
                    """
                    try:
                        lock_service = get_quiz_creation_lock()
                        is_locked = lock_service.is_locked(material_id, user_id)
                        
                        if is_locked:
                            lock_info = lock_service.get_lock_info(material_id, user_id)
                            if lock_info:
                                logger.info(
                                    f"Pending quiz creation detected via lock service: "
                                    f"material={material_id}, pages={lock_info['start_page']}-{lock_info['end_page']}"
                                )
                        
                        return is_locked
                    
                    except Exception as e:
                        # Log error but don't break the flow - return False to allow normal processing
                        logger.warning(
                            f"Error checking for pending quiz creation via lock service: {str(e)}. "
                            "Continuing with normal flow.",
                            exc_info=True
                        )
                        return False

                # Always check Supabase for conversation history when is_initial_open is true
                # This allows us to detect returning users even if LangGraph state exists
                if request.is_initial_open:
                    try:
                        _, stored_messages = load_conversation_with_messages(
                            user_id=request.user_id,
                            course_material_id=course_material_id,
                            limit=20,
                        )
                        conversation_has_history = len(stored_messages) > 0

                        # Check if the last assistant message is already a Welcome Back message
                        if conversation_has_history:
                            # Find the last assistant message
                            for stored in reversed(stored_messages):
                                if stored.get("role") == "assistant":
                                    last_content = stored.get("content", "")
                                    if is_welcome_back_message(last_content):
                                        last_message_is_welcome_back = True
                                    break

                        # Bootstrap messages into LangGraph state if needed
                        if is_new_thread:
                            for stored in stored_messages:
                                role = stored.get("role")
                                content = stored.get("content", "")
                                if not content:
                                    continue
                                if role == "user":
                                    base_messages.append(HumanMessage(content=content))
                                elif role == "assistant":
                                    base_messages.append(AIMessage(content=content))
                                elif role == "system":
                                    base_messages.append(SystemMessage(content=content))
                    except Exception as bootstrap_error:
                        logger.error(
                            f"Failed to load conversation history from Supabase: {bootstrap_error}",
                            exc_info=True,
                        )
                elif is_new_thread:
                    # Only bootstrap if not initial open but LangGraph state is empty
                    try:
                        _, stored_messages = load_conversation_with_messages(
                            user_id=request.user_id,
                            course_material_id=course_material_id,
                            limit=20,
                        )
                        conversation_has_history = len(stored_messages) > 0

                        for stored in stored_messages:
                            role = stored.get("role")
                            content = stored.get("content", "")
                            if not content:
                                continue
                            if role == "user":
                                base_messages.append(HumanMessage(content=content))
                            elif role == "assistant":
                                base_messages.append(AIMessage(content=content))
                            elif role == "system":
                                base_messages.append(SystemMessage(content=content))
                    except Exception as bootstrap_error:
                        logger.error(
                            f"Failed to bootstrap LangGraph state from Supabase: {bootstrap_error}",
                            exc_info=True,
                        )

                # Update state with current page information (according to AGENT_DEVELOPMENT_RULES.md)
                # The agent should always know which page we are currently viewing
                
                # Determine greeting type based on is_initial_open flag and conversation history
                if request.is_initial_open:
                    # This is an initial opening of the study reader (first load or reopening)
                    last_page_number = None
                    metadata = conversation.get("metadata") or {}
                    if isinstance(metadata, dict):
                        last_page_number = metadata.get("last_page_number")

                    if conversation_has_history:
                        # Returning to an existing study session
                        completed_pages = last_page_number or request.page_number
                        total_pages_safe = total_pages or "unbekannt"

                        if last_message_is_welcome_back:
                            # Last message was already a Welcome Back message, send a normal greeting instead
                            initial_human_content = get_tutor_prompt(
                                "tutor-agent/normal-greeting-after-welcome-back",
                                page_number=request.page_number,
                                summary=summary
                            )
                        else:
                            # No recent Welcome Back message, send one now
                            # IMPORTANT:
                            # For the list of \"already covered\" topics we now rely ONLY on the actual
                            # chat history, not on syllabus/overview summaries from the slides.
                            # This prevents the model from listing future topics that were only
                            # announced on an agenda slide but not yet discussed in the conversation.
                            topics_instructions = (
                                "\n\nANALYSE DER BISHERIGEN THEMEN (nur Chat-Verlauf, keine Agenda-Folien!):\n"
                                "- Analysiere ausschließlich den obigen Chat-Verlauf, um herauszufinden,\n"
                                "  welche Themen ihr bereits inhaltlich BESPROCHEN habt.\n"
                                "- Themen, die nur als zukünftige Inhalte auf einer Übersichts-/Agenda-Folie\n"
                                "  erwähnt wurden (z.B. Rechengesetze, Binomische Formeln, Logarithmusgesetze),\n"
                                "  dürfen NICHT in der Liste auftauchen, solange sie im Chat noch nicht erklärt\n"
                                "  oder diskutiert wurden.\n"
                                "- Fasse verwandte Punkte sinnvoll zusammen und formuliere eine kurze,\n"
                                "  natürlich klingende Liste von 2–5 Hauptthemen, die bisher wirklich\n"
                                "  behandelt wurden (z.B. \"Einführung in die Vorlesung\", \"Zahlenbereiche\",\n"
                                "  \"imaginäre und komplexe Zahlen\").\n"
                            )

                            initial_human_content = get_tutor_prompt(
                                "tutor-agent/welcome-back",
                                completed_pages=completed_pages,
                                total_pages=total_pages_safe,
                                topics_instructions=topics_instructions
                            )
                    else:
                        # First visit for this material (no previous chat history)
                        total_pages_safe = total_pages or "unbekannt"
                        initial_human_content = get_tutor_prompt(
                            "tutor-agent/first-visit",
                            page_number=request.page_number,
                            total_pages=total_pages_safe,
                            summary=summary
                        )

                    # Fix incomplete tool call pairs in base_messages before adding new messages
                    # This ensures message ordering is valid before adding new HumanMessage
                    base_messages = fix_incomplete_tool_calls(base_messages)
                    
                    # Use bootstrapped messages if available, otherwise start fresh
                    initial_state = {
                    "messages": base_messages
                    + [
                        SystemMessage(content=system_message),
                        HumanMessage(content=initial_human_content),
                    ],
                        "current_page": request.page_number,
                        "material_id": request.material_id,
                        "user_id": request.user_id,
                        "course_material_summary": course_summary,
                    }
                else:
                    # This is just a page change within an ongoing session
                    # Use existing LangGraph state if available, otherwise bootstrap
                    if is_new_thread:
                        # LangGraph state is empty, but we might have bootstrapped messages
                        # Check for pending quiz creation BEFORE fixing incomplete tool calls
                        has_pending_quiz = has_pending_quiz_creation(course_material_id, request.user_id)
                        
                        if has_pending_quiz:
                            # Quiz is being created - suppress init message and only update state
                            logger.info(
                                f"Pending quiz creation detected during page change to {request.page_number}. "
                                "Suppressing init message and updating state only."
                            )
                            
                            # Only update current_page in state, don't add init messages
                            # The quiz creation will complete and send its own response
                            initial_state = {
                                "messages": base_messages,  # Keep existing messages as-is
                                "current_page": request.page_number,
                                "material_id": request.material_id,
                                "user_id": request.user_id,
                                "course_material_summary": course_summary,
                            }
                            
                            # Update state silently without generating a response
                            # This ensures current_page is updated even when quiz is pending
                            try:
                                # Use a minimal state update to persist the current_page change
                                # We don't invoke the graph, just update the state directly
                                config = {"configurable": {"thread_id": thread_id, "user_id": request.user_id}}
                                # Update state by invoking with empty messages (state update only)
                                # The state fields (current_page, etc.) will be updated
                                agent.graph.update_state(config, initial_state)
                                logger.debug(f"State updated silently for page {request.page_number} (quiz pending)")
                            except Exception as state_update_error:
                                # If state update fails, log but don't break - quiz will still complete
                                logger.warning(
                                    f"Failed to update state silently: {state_update_error}. "
                                    "Quiz creation will still complete normally.",
                                    exc_info=True
                                )
                            
                            # Skip agent stream - just update state silently
                            # The quiz tool call will complete and handle the response
                            # We'll yield a minimal response to indicate state was updated
                            # Send a minimal response indicating state was updated
                            yield f"data: {json.dumps({'type': 'state_update', 'current_page': request.page_number})}\n\n"
                            yield "data: [DONE]\n\n"
                            return
                        
                        # No pending quiz - proceed with normal flow
                        # Fix incomplete tool call pairs in base_messages before adding new messages
                        base_messages = fix_incomplete_tool_calls(base_messages)
                        
                        initial_state = {
                            "messages": base_messages
                            + [
                                SystemMessage(content=system_message),
                                HumanMessage(
                                    content=get_tutor_prompt(
                                        "tutor-agent/page-change-new-thread",
                                        page_number=request.page_number,
                                        summary=summary
                                    )
                                ),
                            ],
                            "current_page": request.page_number,
                            "material_id": request.material_id,
                            "user_id": request.user_id,
                            "course_material_summary": course_summary,
                        }
                    else:
                        # Existing thread in this backend process: load existing messages from snapshot
                        existing_messages = snapshot.values.get("messages", [])
                        
                        # Check for pending quiz creation BEFORE fixing incomplete tool calls
                        has_pending_quiz = has_pending_quiz_creation(course_material_id, request.user_id)
                        
                        if has_pending_quiz:
                            # Quiz is being created - suppress init message and only update state
                            logger.info(
                                f"Pending quiz creation detected during page change to {request.page_number}. "
                                "Suppressing init message and updating state only."
                            )
                            
                            # Only update current_page in state, don't add init messages
                            # The quiz creation will complete and send its own response
                            initial_state = {
                                "messages": existing_messages,  # Keep existing messages as-is (don't fix incomplete calls)
                                "current_page": request.page_number,
                                "material_id": request.material_id,
                                "user_id": request.user_id,
                                "course_material_summary": snapshot.values.get("course_material_summary") or course_summary,
                            }
                            
                            # Update state silently without generating a response
                            # This ensures current_page is updated even when quiz is pending
                            try:
                                # Use a minimal state update to persist the current_page change
                                # We don't invoke the graph, just update the state directly
                                config = {"configurable": {"thread_id": thread_id, "user_id": request.user_id}}
                                # Update state by invoking with empty messages (state update only)
                                # The state fields (current_page, etc.) will be updated
                                agent.graph.update_state(config, initial_state)
                                logger.debug(f"State updated silently for page {request.page_number} (quiz pending)")
                            except Exception as state_update_error:
                                # If state update fails, log but don't break - quiz will still complete
                                logger.warning(
                                    f"Failed to update state silently: {state_update_error}. "
                                    "Quiz creation will still complete normally.",
                                    exc_info=True
                                )
                            
                            # Skip agent stream - just update state silently
                            # The quiz tool call will complete and handle the response
                            # We'll yield a minimal response to indicate state was updated
                            # Send a minimal response indicating state was updated
                            yield f"data: {json.dumps({'type': 'state_update', 'current_page': request.page_number})}\n\n"
                            yield "data: [DONE]\n\n"
                            return
                        
                        # No pending quiz - proceed with normal flow
                        # Fix incomplete tool call pairs to prevent Gemini API errors
                        # Gemini requires: AIMessage with tool_calls -> ToolMessages -> (optional) AIMessage -> HumanMessage
                        existing_messages = fix_incomplete_tool_calls(existing_messages)

                        # For simple page changes within an ongoing conversation, we use a lighter hint
                        page_change_human = HumanMessage(
                            content=get_tutor_prompt(
                                "tutor-agent/page-change-existing-thread",
                                page_number=request.page_number,
                                summary=summary
                            )
                        )

                        # Validate that adding HumanMessage won't break message ordering
                        # If last message is AIMessage with tool_calls, we need ToolMessages first
                        validated_messages = fix_incomplete_tool_calls(existing_messages)
                        
                        # Ensure course_material_summary is in state (for old conversations)
                        existing_summary = snapshot.values.get("course_material_summary")
                        if not existing_summary and course_summary:
                            # Summary not in state yet, use the one we loaded
                            existing_summary = course_summary
                        elif not existing_summary:
                            # Try to load it if we haven't already
                            try:
                                existing_summary = get_course_material_summary(
                                    course_material_id=course_material_id,
                                    user_id=request.user_id
                                )
                            except Exception:
                                pass  # Non-critical
                        
                        initial_state = {
                            "messages": validated_messages
                            + [
                                SystemMessage(content=system_message),
                                page_change_human,
                            ],
                            "current_page": request.page_number,
                            "material_id": request.material_id,
                            "user_id": request.user_id,
                            "course_material_summary": existing_summary,
                        }
                
                # Prepare buffer for assistant response text for persistence
                assistant_response_chunks: list[str] = []
                last_sent_content = ""  # Track what we've already sent for incremental updates
                
                # Stream agent response with incremental content updates
                logger.info(f"Starting agent stream for page {request.page_number}")
                
                # Wrap graph execution with Langfuse span for unique trace naming
                langfuse_client = get_langfuse_client()
                graph_span_ctx = None
                graph_span = None
                if langfuse_client and settings.LANGFUSE_ENABLED:
                    try:
                        graph_span_ctx = langfuse_client.start_as_current_observation(
                            as_type="span",
                            name="tutor-agent/graph-execution-initiate",
                            input={
                                "user_id": request.user_id,
                                "material_id": course_material_id,
                                "page_number": request.page_number,
                                "thread_id": thread_id
                            }
                        )
                        graph_span = graph_span_ctx.__enter__()
                        logger.info(f"🟡 Langfuse: Started graph execution span 'tutor-agent/graph-execution-initiate'")
                    except Exception as e:
                        logger.warning(f"🔴 Langfuse: Failed to start graph execution span: {e}")
                        graph_span_ctx = None
                        graph_span = None
                
                try:
                    async for chunk in agent.graph.astream(initial_state, config):
                        chunk_data = {}
                        for node_name, node_data in chunk.items():
                            if "messages" in node_data:
                                messages = []
                                for msg in node_data["messages"]:
                                    # Extract tool responses (ToolMessage contains tool results)
                                    if isinstance(msg, ToolMessage):
                                        # ToolMessage should have tool_call_id attribute
                                        tool_call_id = getattr(msg, "tool_call_id", None)
                                        if not tool_call_id:
                                            # Fallback: try to get from name attribute (shouldn't happen normally)
                                            tool_call_id = getattr(msg, "name", None)
                                        
                                        tool_content = getattr(msg, "content", "")
                                        
                                        if tool_call_id and tool_content:
                                            # Log for debugging
                                            logger.info(f"🟡 Tool response: tool_call_id={tool_call_id}, content_length={len(tool_content)}, is_create_quiz={'create_quiz' in tool_content[:100]}")
                                            
                                            # Check if this is an error response (from tool exception handling)
                                            is_error_response = False
                                            try:
                                                if tool_content:
                                                    parsed_content = json.loads(tool_content)
                                                    if isinstance(parsed_content, dict) and parsed_content.get("error"):
                                                        is_error_response = True
                                                        logger.warning(f"Tool returned error response: {parsed_content.get('error')[:200]}")
                                            except (json.JSONDecodeError, TypeError):
                                                # Not JSON or not a dict - treat as normal response
                                                pass
                                            
                                            # Send tool response event
                                            # Validate tool response content before sending (only for non-error responses)
                                            if not is_error_response:
                                                try:
                                                    # Try to parse as JSON to validate structure
                                                    if tool_content:
                                                        json.loads(tool_content)
                                                except json.JSONDecodeError:
                                                    logger.warning(f"Tool response is not valid JSON: {tool_content[:200]}")
                                            
                                            tool_response_event = {
                                                "type": "tool_response",
                                                "tool_call_id": tool_call_id,
                                                "result": tool_content,
                                                "message_id": generate_message_id()
                                            }
                                            yield f"data: {json.dumps(tool_response_event)}\n\n"
                                        else:
                                            logger.warning(f"⚠️ ToolMessage missing tool_call_id or content: tool_call_id={tool_call_id}, has_content={bool(tool_content)}")
                                        continue

                                    if hasattr(msg, "content"):
                                        role = "assistant"
                                        if isinstance(msg, SystemMessage):
                                            role = "system"
                                        elif isinstance(msg, HumanMessage):
                                            role = "user"
                                        elif isinstance(msg, AIMessage):
                                            role = "assistant"
                                            
                                            # Extract tool calls if present
                                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                                tool_calls_data = []
                                                for tool_call in msg.tool_calls:
                                                    # Extract tool call information
                                                    tool_id = getattr(tool_call, "id", None) or tool_call.get("id", "") if isinstance(tool_call, dict) else ""
                                                    tool_name = getattr(tool_call, "name", None) or tool_call.get("name", "") if isinstance(tool_call, dict) else ""
                                                    tool_args = getattr(tool_call, "args", None) or tool_call.get("args", {}) if isinstance(tool_call, dict) else {}
                                                    
                                                    if tool_id and tool_name:
                                                        tool_calls_data.append({
                                                            "id": tool_id,
                                                            "name": tool_name,
                                                            "args": tool_args if isinstance(tool_args, dict) else {}
                                                        })
                                                        # Log for debugging
                                                        logger.info(f"🟡 Tool call: id={tool_id}, name={tool_name}, is_create_quiz={tool_name == 'create_quiz'}")
                                                
                                                if tool_calls_data:
                                                    # Send tool call event
                                                    tool_event = {
                                                        "type": "tool_call",
                                                        "tool_calls": tool_calls_data,
                                                        "message_id": generate_message_id()
                                                    }
                                                    yield f"data: {json.dumps(tool_event)}\n\n"

                                        # Handle assistant messages with incremental streaming
                                        if role == "assistant":
                                            # Check if message has content (not just tool calls)
                                            # Also check if this is a message with tool calls but no content
                                            has_tool_calls = hasattr(msg, "tool_calls") and bool(msg.tool_calls)
                                            has_content = bool(msg.content)
                                            
                                            # Handle list content
                                            if isinstance(msg.content, list):
                                                has_content = bool(msg.content) and any(
                                                    part.get("text", "") if isinstance(part, dict) else str(part)
                                                    for part in msg.content
                                                )
                                            
                                            # If message has tool calls but no content, skip adding to messages
                                            # Tool calls are already sent separately above
                                            if has_tool_calls and not has_content:
                                                logger.debug(f"Skipping AIMessage with tool calls but no content (tool_calls: {len(msg.tool_calls) if has_tool_calls else 0})")
                                                continue
                                            
                                            if has_content:
                                                content_text = msg.content
                                                if isinstance(msg.content, list):
                                                    try:
                                                        content_text = "".join(
                                                            part.get("text", "") if isinstance(part, dict) else str(part)
                                                            for part in msg.content
                                                        )
                                                    except Exception:
                                                        content_text = str(msg.content)
                                                
                                                # Send incremental delta if content has grown
                                                if content_text and content_text != last_sent_content:
                                                    # Calculate and send delta
                                                    if last_sent_content and content_text.startswith(last_sent_content):
                                                        delta = content_text[len(last_sent_content):]
                                                        if delta:
                                                            # Send delta for ghostwriter effect
                                                            delta_data = {
                                                                "type": "delta",
                                                                "role": "assistant",
                                                                "delta": delta,
                                                                "content": content_text
                                                            }
                                                            yield f"data: {json.dumps(delta_data)}\n\n"
                                                            last_sent_content = content_text
                                                    else:
                                                        # Content changed in a way we can't calculate delta
                                                        # Send full message structure for compatibility
                                                        messages.append({
                                                            "role": role,
                                                            "content": content_text
                                                        })
                                                        last_sent_content = content_text
                                                
                                                # Store for persistence
                                                if str(content_text) not in assistant_response_chunks:
                                                    assistant_response_chunks.append(str(content_text))
                                            # If assistant message has no content (only tool calls), skip adding to messages
                                            # Tool calls are already sent separately above
                                        else:
                                            # Non-assistant messages: send normally, but only if they have content
                                            content = msg.content if hasattr(msg, "content") else ""
                                            if content or role != "assistant":  # Allow non-assistant messages even if empty
                                                messages.append({
                                                    "role": role,
                                                    "content": content,
                                                })
                                
                                if messages:  # Only add if there are messages
                                    chunk_data[node_name] = {"messages": messages}
                        
                        if chunk_data:  # Only yield if there's data
                            logger.debug(f"Yielding chunk: {chunk_data}")
                            yield f"data: {json.dumps(chunk_data)}\n\n"
                    
                    logger.info(f"Agent stream completed for page {request.page_number}")

                    # Persist conversation messages and progress in Supabase
                    try:
                        full_assistant_response = "".join(assistant_response_chunks).strip()
                        messages_to_store = []

                        # Get page_analysis_id for context_page_id
                        context_page_id = None
                        try:
                            context_page_id = get_page_analysis_id(
                                course_material_id=course_material_id,
                                page_number=request.page_number,
                                user_id=request.user_id
                            )
                        except Exception as page_id_error:
                            logger.warning(
                                f"Failed to get page_analysis_id for page {request.page_number}: {page_id_error}"
                            )

                        if full_assistant_response:
                            messages_to_store.append(
                                {
                                    "role": "assistant",
                                    "content": full_assistant_response,
                                    "context_page_id": context_page_id,
                                }
                            )

                        if messages_to_store:
                            append_messages(conversation_id, messages_to_store)
                            update_conversation_progress(conversation_id, request.page_number)
                    except Exception as persist_error:
                        logger.error(
                            f"Failed to persist chat initiate messages: {persist_error}",
                            exc_info=True,
                        )

                    # Wenn der Stream erfolgreich durchläuft:
                    if trace:
                        logger.info("🟡 Langfuse: Updating trace 'tutor-agent-initiate' with completion status...")
                        trace.update(output={"status": "completed"})
                        logger.info("🟢 Langfuse: Trace 'tutor-agent-initiate' updated with completion status")
                    
                    # Update graph execution span with success
                    if graph_span:
                        try:
                            graph_span.update(output={"status": "completed"})
                            logger.info("🟢 Langfuse: Graph execution span updated with success")
                        except Exception as e:
                            logger.warning(f"🔴 Langfuse: Failed to update graph execution span: {e}")
                    
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    logger.error(f"Error in agent stream: {str(e)}", exc_info=True)
                    
                    # Trace als Error markieren
                    if trace:
                        logger.warning(f"🟡 Langfuse: Updating trace 'tutor-agent-initiate' with ERROR status: {str(e)}")
                        trace.update(level="ERROR", status_message=str(e))
                        logger.warning("🔴 Langfuse: Trace 'tutor-agent-initiate' marked as ERROR")
                    
                    # Update graph execution span with error
                    if graph_span:
                        try:
                            graph_span.update(output={"status": "error", "error": str(e)})
                            logger.warning("🔴 Langfuse: Graph execution span updated with error")
                        except Exception as e:
                            logger.warning(f"🔴 Langfuse: Failed to update graph execution span: {e}")
                    
                    error_data = {"error": str(e)}
                    yield f"data: {json.dumps(error_data)}\n\n"
                    yield "data: [DONE]\n\n"
                
                finally:
                    # Cleanup Langfuse tracing
                    # WICHTIG: Kein flush() hier! Das blockiert den Stream-Exit.
                    exc_info = sys.exc_info()  # Holt die aktuelle Exception, falls vorhanden
                    
                    # Close graph execution span
                    if graph_span_ctx:
                        try:
                            logger.info("🟡 Langfuse: Closing graph execution span...")
                            graph_span_ctx.__exit__(*exc_info)
                            logger.info("🟢 Langfuse: Graph execution span closed")
                        except Exception as e:
                            logger.warning(f"🔴 Langfuse: Error closing graph execution span: {e}")
                    
                    if propagate_ctx:
                        try:
                            logger.info("🟡 Langfuse: Closing propagate context...")
                            propagate_ctx.__exit__(*exc_info)
                            logger.info("🟢 Langfuse: Propagate context closed")
                        except Exception as e:
                            logger.warning(f"🔴 Langfuse: Error closing propagate context: {e}")

                    if trace_ctx:
                        try:
                            # Übergibt Exception-Infos korrekt an Langfuse
                            # WICHTIG: __exit__() muss auf dem Context Manager aufgerufen werden, nicht auf dem Span
                            logger.info("🟡 Langfuse: Closing trace 'tutor-agent-initiate'...")
                            trace_ctx.__exit__(*exc_info)
                            logger.info("🟢 Langfuse: Trace 'tutor-agent-initiate' closed - data sent to Langfuse")
                        except Exception as e:
                            logger.warning(f"🔴 Langfuse: Error closing trace: {e}")
            except Exception as e:
                logger.error(f"Error in agent setup or streaming: {str(e)}", exc_info=True)
                raise
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating chat: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate chat: {str(e)}"
        )


@router.post("/chat/message")
async def send_chat_message(
    request: ChatMessageRequest = Body(...)
) -> StreamingResponse:
    """
    Send a message in an existing chat session.
    
    Args:
        request: ChatMessageRequest with material_id, message, user_id
        
    Returns:
        StreamingResponse with SSE events
    """
    try:
        # Validate user
        if not validate_user_exists(request.user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found. Please sign up first."
            )
        
        # Initialize LLM and agent
        llm = get_gemini_model()
        agent = TutorAgent(llm=llm, checkpointer=_checkpointer)
        
        # Get course material to find course_material_id (for conversation lookup)
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

        # Get or create study conversation in Supabase
        conversation = get_or_create_study_conversation(
            user_id=request.user_id,
            course_material_id=course_material_id,
            course_id=course_id,
        )
        conversation_id = conversation["id"]

        # Thread ID: conversation_id for continuous conversation
        thread_id = str(conversation_id)
        
        # Stream response
        async def event_generator() -> AsyncGenerator[str, None]:
            # Langfuse Tracing Setup
            # WICHTIG: get_client() liest direkt aus os.environ, nicht aus settings!
            # Daher müssen wir die Werte aus settings in os.environ setzen
            if settings.LANGFUSE_PUBLIC_KEY and "LANGFUSE_PUBLIC_KEY" not in os.environ:
                os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
            if settings.LANGFUSE_SECRET_KEY and "LANGFUSE_SECRET_KEY" not in os.environ:
                os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
            if settings.LANGFUSE_BASE_URL and "LANGFUSE_HOST" not in os.environ:
                # Langfuse SDK verwendet LANGFUSE_HOST für die Base URL
                os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_BASE_URL
            
            langfuse = get_client()
            trace = None
            trace_ctx = None  # Context Manager für __exit__()
            propagate_ctx = None
            
            if langfuse and settings.LANGFUSE_ENABLED:
                try:
                    trace_input = {
                        "user_id": request.user_id,
                        "material_id": course_material_id,
                        "message": request.message[:100]  # Truncate for input
                    }
                    logger.info(f"🟡 Langfuse: Starting trace 'tutor-agent-message' with input: {trace_input}")
                    trace_ctx = langfuse.start_as_current_observation(
                        as_type="span",
                        name="tutor-agent-message",
                        input=trace_input
                    )
                    # WICHTIG: __enter__() gibt den aktiven span zurück, aber wir brauchen den Context Manager für __exit__()
                    trace = trace_ctx.__enter__()
                    logger.info("🟢 Langfuse: Trace 'tutor-agent-message' started successfully")
                    
                    propagate_metadata = {
                        "material_id": course_material_id,
                        "course_id": course_id
                    }
                    logger.info(f"🟡 Langfuse: Propagating attributes - user_id={request.user_id}, session_id={thread_id}, metadata={propagate_metadata}")
                    propagate_ctx = propagate_attributes(
                        user_id=request.user_id,
                        session_id=thread_id,  # conversation_id als session
                        tags=["tutor-agent", "chat-message"],
                        metadata=propagate_metadata
                    )
                    propagate_ctx.__enter__()
                    logger.info("🟢 Langfuse: Attributes propagated successfully")
                except Exception as e:
                    logger.error(f"🔴 Langfuse: Setup failed: {e}", exc_info=True)
                    # Wir machen weiter, auch wenn Tracing fehlschlägt
                    trace = None
                    trace_ctx = None
                    propagate_ctx = None
            
            try:
                config = {"configurable": {"thread_id": thread_id, "user_id": request.user_id}}
                
                # Get current state to preserve current_page, material_id, user_id
                snapshot = agent.graph.get_state(config)
                current_page = None
                material_id = request.material_id
                user_id = request.user_id
                
                if snapshot and snapshot.values:
                    # Preserve current_page from existing state if available
                    current_page = snapshot.values.get("current_page")
                # If LangGraph state is empty (e.g., after restart), fall back to conversation metadata
                if current_page is None:
                    metadata = conversation.get("metadata") or {}
                    current_page = metadata.get("last_page_number")
                
                # Ensure course_material_summary is in state (for old conversations)
                course_summary = None
                if snapshot and snapshot.values:
                    course_summary = snapshot.values.get("course_material_summary")
                
                if not course_summary:
                    # Try to load it if not in state
                    try:
                        course_summary = get_course_material_summary(
                            course_material_id=course_material_id,
                            user_id=request.user_id
                        )
                    except Exception:
                        pass  # Non-critical
                
                # Add user message to existing thread and preserve state
                initial_state = {
                    "messages": [HumanMessage(content=request.message)],
                    "material_id": material_id,
                    "user_id": user_id
                }
                
                # Only add current_page if it exists in previous state or metadata
                if current_page is not None:
                    initial_state["current_page"] = current_page
                
                # Add course_material_summary if available
                if course_summary:
                    initial_state["course_material_summary"] = course_summary

                # Prepare buffer for assistant response text for persistence
                assistant_response_chunks: list[str] = []
                last_sent_content = ""  # Track what we've already sent for incremental updates

                # Stream agent response with incremental content updates
                
                # Wrap graph execution with Langfuse span for unique trace naming
                langfuse_client = get_langfuse_client()
                graph_span_ctx = None
                graph_span = None
                if langfuse_client and settings.LANGFUSE_ENABLED:
                    try:
                        graph_span_ctx = langfuse_client.start_as_current_observation(
                            as_type="span",
                            name="tutor-agent/graph-execution-message",
                            input={
                                "user_id": request.user_id,
                                "material_id": course_material_id,
                                "message": request.message[:100],  # Truncate for input
                                "thread_id": thread_id
                            }
                        )
                        graph_span = graph_span_ctx.__enter__()
                        logger.info(f"🟡 Langfuse: Started graph execution span 'tutor-agent/graph-execution-message'")
                    except Exception as e:
                        logger.warning(f"🔴 Langfuse: Failed to start graph execution span: {e}")
                        graph_span_ctx = None
                        graph_span = None
                
                async for chunk in agent.graph.astream(initial_state, config):
                    chunk_data = {}
                    for node_name, node_data in chunk.items():
                        if "messages" in node_data:
                            messages = []
                            for msg in node_data["messages"]:
                                # Extract tool responses (ToolMessage contains tool results)
                                if isinstance(msg, ToolMessage):
                                    # ToolMessage should have tool_call_id attribute
                                    tool_call_id = getattr(msg, "tool_call_id", None)
                                    if not tool_call_id:
                                        # Fallback: try to get from name attribute (shouldn't happen normally)
                                        tool_call_id = getattr(msg, "name", None)
                                    
                                    tool_content = getattr(msg, "content", "")
                                    
                                    if tool_call_id and tool_content:
                                        # Log for debugging
                                        logger.info(f"🟡 Tool response: tool_call_id={tool_call_id}, content_length={len(tool_content)}, is_create_quiz={'create_quiz' in tool_content[:100]}")
                                        
                                        # Check if this is an error response (from tool exception handling)
                                        is_error_response = False
                                        try:
                                            if tool_content:
                                                parsed_content = json.loads(tool_content)
                                                if isinstance(parsed_content, dict) and parsed_content.get("error"):
                                                    is_error_response = True
                                                    logger.warning(f"Tool returned error response: {parsed_content.get('error')[:200]}")
                                        except (json.JSONDecodeError, TypeError):
                                            # Not JSON or not a dict - treat as normal response
                                            pass
                                        
                                        # Send tool response event
                                        # Validate tool response content before sending (only for non-error responses)
                                        tool_response_content = tool_content
                                        if not is_error_response:
                                            try:
                                                # Try to parse as JSON to validate structure
                                                if tool_content:
                                                    parsed_json = json.loads(tool_content)
                                                    
                                                    # Check if this is a get_page_image response with large image data
                                                    # We truncate the image data for the frontend to prevent stream issues
                                                    if isinstance(parsed_json, dict) and "image_data" in parsed_json:
                                                        # Create a copy to modify for frontend display
                                                        frontend_json = parsed_json.copy()
                                                        image_data = frontend_json.get("image_data", "")
                                                        if image_data and len(image_data) > 100:
                                                            frontend_json["image_data"] = f"{image_data[:50]}...[truncated]...{image_data[-20:]}"
                                                            tool_response_content = json.dumps(frontend_json)
                                                            logger.info(f"Truncated large image data in tool response for frontend (original length: {len(image_data)})")
                                            except json.JSONDecodeError:
                                                logger.warning(f"Tool response is not valid JSON: {tool_content[:200]}")
                                        
                                        tool_response_event = {
                                            "type": "tool_response",
                                            "tool_call_id": tool_call_id,
                                            "result": tool_response_content,
                                            "message_id": generate_message_id()
                                        }
                                        yield f"data: {json.dumps(tool_response_event)}\n\n"
                                    else:
                                        logger.warning(f"⚠️ ToolMessage missing tool_call_id or content: tool_call_id={tool_call_id}, has_content={bool(tool_content)}")
                                    continue

                                if hasattr(msg, "content"):
                                    role = "assistant"
                                    if isinstance(msg, SystemMessage):
                                        role = "system"
                                    elif isinstance(msg, HumanMessage):
                                        role = "user"
                                    elif isinstance(msg, AIMessage):
                                        role = "assistant"
                                        
                                        # Extract tool calls if present
                                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                                            tool_calls_data = []
                                            for tool_call in msg.tool_calls:
                                                # Extract tool call information
                                                tool_id = getattr(tool_call, "id", None) or tool_call.get("id", "") if isinstance(tool_call, dict) else ""
                                                tool_name = getattr(tool_call, "name", None) or tool_call.get("name", "") if isinstance(tool_call, dict) else ""
                                                tool_args = getattr(tool_call, "args", None) or tool_call.get("args", {}) if isinstance(tool_call, dict) else {}
                                                
                                                if tool_id and tool_name:
                                                    tool_calls_data.append({
                                                        "id": tool_id,
                                                        "name": tool_name,
                                                        "args": tool_args if isinstance(tool_args, dict) else {}
                                                    })
                                            
                                            if tool_calls_data:
                                                # Send tool call event
                                                tool_event = {
                                                    "type": "tool_call",
                                                    "tool_calls": tool_calls_data,
                                                    "message_id": generate_message_id()
                                                }
                                                yield f"data: {json.dumps(tool_event)}\n\n"

                                    # Handle assistant messages with incremental streaming
                                    if role == "assistant":
                                        # Check if message has content (not just tool calls)
                                        # Also check if this is a message with tool calls but no content
                                        has_tool_calls = hasattr(msg, "tool_calls") and bool(msg.tool_calls)
                                        has_content = bool(msg.content)
                                        
                                        # Handle list content
                                        if isinstance(msg.content, list):
                                            has_content = bool(msg.content) and any(
                                                part.get("text", "") if isinstance(part, dict) else str(part)
                                                for part in msg.content
                                            )
                                        
                                        # If message has tool calls but no content, skip adding to messages
                                        # Tool calls are already sent separately above
                                        if has_tool_calls and not has_content:
                                            logger.debug(f"Skipping AIMessage with tool calls but no content (tool_calls: {len(msg.tool_calls) if has_tool_calls else 0})")
                                            continue
                                        
                                        if has_content:
                                            content_text = msg.content
                                            if isinstance(msg.content, list):
                                                try:
                                                    content_text = "".join(
                                                        part.get("text", "") if isinstance(part, dict) else str(part)
                                                        for part in msg.content
                                                    )
                                                except Exception:
                                                    content_text = str(msg.content)
                                            
                                            # Send incremental delta if content has grown
                                            if content_text and content_text != last_sent_content:
                                                # Calculate and send delta
                                                if last_sent_content and content_text.startswith(last_sent_content):
                                                    delta = content_text[len(last_sent_content):]
                                                    if delta:
                                                        # Send delta for ghostwriter effect
                                                        delta_data = {
                                                            "type": "delta",
                                                            "role": "assistant",
                                                            "delta": delta,
                                                            "content": content_text
                                                        }
                                                        yield f"data: {json.dumps(delta_data)}\n\n"
                                                        last_sent_content = content_text
                                                else:
                                                    # Content changed in a way we can't calculate delta
                                                    # Send full message structure for compatibility
                                                    messages.append({
                                                        "role": role,
                                                        "content": content_text
                                                    })
                                                    last_sent_content = content_text
                                            
                                            # Store for persistence
                                            if str(content_text) not in assistant_response_chunks:
                                                assistant_response_chunks.append(str(content_text))
                                        # If assistant message has no content (only tool calls), skip adding to messages
                                        # Tool calls are already sent separately above
                                    else:
                                        # Non-assistant messages: send normally, but only if they have content
                                        content = msg.content if hasattr(msg, "content") else ""
                                        if content or role != "assistant":  # Allow non-assistant messages even if empty
                                            messages.append({
                                                "role": role,
                                                "content": content,
                                            })
                            if messages:
                                chunk_data[node_name] = {"messages": messages}
                    
                    if chunk_data:
                        yield f"data: {json.dumps(chunk_data)}\n\n"

                # Persist user and assistant messages and update progress
                try:
                    full_assistant_response = "".join(assistant_response_chunks).strip()
                    messages_to_store = []

                    # Get page_analysis_id for context_page_id if current_page is available
                    context_page_id = None
                    if current_page is not None:
                        try:
                            context_page_id = get_page_analysis_id(
                                course_material_id=course_material_id,
                                page_number=current_page,
                                user_id=request.user_id
                            )
                        except Exception as page_id_error:
                            logger.warning(
                                f"Failed to get page_analysis_id for page {current_page}: {page_id_error}"
                            )

                    # Persist only the real user message and the final assistant reply
                    messages_to_store.append(
                        {
                            "role": "user",
                            "content": request.message,
                            "context_page_id": context_page_id,
                        }
                    )
                    if full_assistant_response:
                        messages_to_store.append(
                            {
                                "role": "assistant",
                                "content": full_assistant_response,
                                "context_page_id": context_page_id,
                            }
                        )

                    append_messages(conversation_id, messages_to_store)
                    if current_page is not None:
                        update_conversation_progress(conversation_id, current_page)
                except Exception as persist_error:
                    logger.error(
                        f"Failed to persist chat message conversation: {persist_error}",
                        exc_info=True,
                    )

                # Wenn der Stream erfolgreich durchläuft:
                if trace:
                    logger.info("🟡 Langfuse: Updating trace 'tutor-agent-message' with completion status...")
                    trace.update(output={"status": "completed"})
                    logger.info("🟢 Langfuse: Trace 'tutor-agent-message' updated with completion status")
                
                # Update graph execution span with success
                if graph_span:
                    try:
                        graph_span.update(output={"status": "completed"})
                        logger.info("🟢 Langfuse: Graph execution span updated with success")
                    except Exception as e:
                        logger.warning(f"🔴 Langfuse: Failed to update graph execution span: {e}")
                
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Error in agent stream: {str(e)}", exc_info=True)
                
                # Trace als Error markieren
                if trace:
                    logger.warning(f"🟡 Langfuse: Updating trace 'tutor-agent-message' with ERROR status: {str(e)}")
                    trace.update(level="ERROR", status_message=str(e))
                    logger.warning("🔴 Langfuse: Trace 'tutor-agent-message' marked as ERROR")
                
                # Update graph execution span with error
                if graph_span:
                    try:
                        graph_span.update(output={"status": "error", "error": str(e)})
                        logger.warning("🔴 Langfuse: Graph execution span updated with error")
                    except Exception as e:
                        logger.warning(f"🔴 Langfuse: Failed to update graph execution span: {e}")
                
                error_data = {"error": str(e)}
                yield f"data: {json.dumps(error_data)}\n\n"
                yield "data: [DONE]\n\n"
                
            finally:
                # Cleanup - KEIN FLUSH
                exc_info = sys.exc_info()
                
                # Close graph execution span
                if graph_span_ctx:
                    try:
                        logger.info("🟡 Langfuse: Closing graph execution span...")
                        graph_span_ctx.__exit__(*exc_info)
                        logger.info("🟢 Langfuse: Graph execution span closed")
                    except Exception as e:
                        logger.warning(f"🔴 Langfuse: Error closing graph execution span: {e}")
                
                if propagate_ctx:
                    try:
                        logger.info("🟡 Langfuse: Closing propagate context...")
                        propagate_ctx.__exit__(*exc_info)
                        logger.info("🟢 Langfuse: Propagate context closed")
                    except Exception as e:
                        logger.warning(f"🔴 Langfuse: Error closing propagate context: {e}")
                
                if trace_ctx:
                    try:
                        # Übergibt Exception-Infos korrekt an Langfuse
                        # WICHTIG: __exit__() muss auf dem Context Manager aufgerufen werden, nicht auf dem Span
                        logger.info("🟡 Langfuse: Closing trace 'tutor-agent-message'...")
                        trace_ctx.__exit__(*exc_info)
                        logger.info("🟢 Langfuse: Trace 'tutor-agent-message' closed - data sent to Langfuse")
                    except Exception as e:
                        logger.warning(f"🔴 Langfuse: Error closing trace: {e}")
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending chat message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send message: {str(e)}"
        )


@router.get("/study/session", status_code=200)
async def get_study_session(
    material_id: str = Query(..., description="Course material ID (UUID)"),
    user_id: str = Query(..., description="User ID (UUID)"),
    limit: int = Query(50, description="Maximum number of messages to return"),
) -> dict:
    """
    Get persisted study session state for a given user and course material.

    Returns the last visited page and recent chat messages so the frontend
    can restore the reader position and chat history.
    """
    try:
        # Validate user exists
        if not validate_user_exists(user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found. Please sign up first.",
            )

        client = get_supabase_client()

        # Validate that course material belongs to user and get course_material_id
        material_response = (
            client.table("course_materials")
            .select("id, page_count")
            .eq("id", material_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )

        if not material_response.data:
            raise HTTPException(
                status_code=404,
                detail="Course material not found or access denied",
            )

        course_material_id = material_response.data["id"]
        page_count = material_response.data.get("page_count") or 0

        # Load conversation and messages
        conversation, messages = load_conversation_with_messages(
            user_id=user_id,
            course_material_id=course_material_id,
            limit=limit,
        )

        last_page = 1
        if conversation and isinstance(conversation.get("metadata"), dict):
            last_page = conversation["metadata"].get("last_page_number") or 1

        # Ensure last_page is within bounds
        if page_count and last_page > page_count:
            last_page = page_count
        if last_page < 1:
            last_page = 1

        # Map messages to frontend format
        mapped_messages = [
            {
                "id": msg["id"],
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": msg.get("created_at"),
            }
            for msg in messages
        ]

        return {
            "lastPage": last_page,
            "messages": mapped_messages,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading study session: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load study session: {str(e)}",
        )


@router.post("/flashcards/generate", response_model=FlashcardTaskResponse, status_code=202)
async def generate_flashcards(
    course_material_id: str = Query(..., description="Course material ID (UUID)"),
    user_id: str = Query(..., description="User ID (UUID)"),
    deduplicate_course: bool = Query(False, description="Enable course-wide deduplication via Anki")
) -> FlashcardTaskResponse:
    """
    Start flashcard generation as a background task.
    
    This endpoint:
    1. Validates user exists
    2. Validates course material belongs to user
    3. Creates a background task for flashcard generation
    4. Returns immediately with task ID for progress tracking
    
    Args:
        course_material_id: Course material ID (UUID)
        user_id: User ID (UUID)
        deduplicate_course: Enable course-wide deduplication (compares against existing Anki cards)
        
    Returns:
        FlashcardTaskResponse with task_id and status
        
    Raises:
        HTTPException: If validation fails
    """
    # Langfuse Tracing Setup für Flashcard-Endpoint
    langfuse = None
    trace_ctx = None
    if settings.LANGFUSE_ENABLED:
        try:
            # Set environment variables if needed
            if settings.LANGFUSE_PUBLIC_KEY and "LANGFUSE_PUBLIC_KEY" not in os.environ:
                os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
            if settings.LANGFUSE_SECRET_KEY and "LANGFUSE_SECRET_KEY" not in os.environ:
                os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
            if settings.LANGFUSE_BASE_URL and "LANGFUSE_HOST" not in os.environ:
                os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_BASE_URL
            
            langfuse = get_client()
            if langfuse:
                trace_input = {
                    "course_material_id": course_material_id,
                    "user_id": user_id
                }
                logger.info(f"🟡 Langfuse: Starting trace 'flashcard-api-request' with input: {trace_input}")
                trace_ctx = langfuse.start_as_current_observation(
                    name="flashcard-api-request",
                    input=trace_input,
                    metadata={
                        "user_id": user_id,
                        "course_material_id": course_material_id,
                        "endpoint": "/flashcards/generate"
                    }
                )
                logger.info("🟢 Langfuse: Trace 'flashcard-api-request' started successfully")
        except Exception as e:
            logger.warning(f"🔴 Langfuse: Failed to start trace: {e}")
    
    try:
        # Validate user exists
        if not validate_user_exists(user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found. Please sign up first.",
            )
        
        client = get_supabase_client()
        
        # Get course material and validate ownership
        material_response = (
            client.table("course_materials")
            .select("id, course_id, user_id, file_name")
            .eq("id", course_material_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        
        if not material_response.data:
            raise HTTPException(
                status_code=404,
                detail="Course material not found or access denied",
            )
        
        material = material_response.data
        course_id = material["course_id"]
        
        # Build deck names for Anki integration
        parent_deck_name = None
        target_deck_name = None
        
        if deduplicate_course or True:  # Always build deck names for Anki integration
            # Get course title
            course_response = (
                client.table("courses")
                .select("title")
                .eq("id", course_id)
                .single()
                .execute()
            )
            
            if course_response.data:
                from pathlib import Path
                course_title = course_response.data.get("title", "Course")
                file_name = material.get("file_name", "Lecture")
                lecture_name = Path(file_name).stem  # Remove extension
                
                parent_deck_name = course_title
                target_deck_name = f"{course_title}::{lecture_name}"
        
        # Create background task
        task_service = get_flashcard_task_service()
        task_id = await task_service.create_task(
            course_material_id=course_material_id,
            user_id=user_id,
            course_id=course_id,
            deduplicate_course=deduplicate_course,
            parent_deck_name=parent_deck_name,
            target_deck_name=target_deck_name,
        )
        
        logger.info(f"Created flashcard generation task {task_id} for material {course_material_id}")
        
        # Update Langfuse trace with success
        if trace_ctx and langfuse:
            try:
                trace_ctx.update(
                    output={
                        "status": "pending",
                        "task_id": task_id,
                        "course_id": course_id
                    },
                    metadata={
                        "task_id": task_id,
                        "course_id": course_id
                    }
                )
                logger.info("🟢 Langfuse: Trace 'flashcard-api-request' updated with success")
            except Exception as e:
                logger.warning(f"🔴 Langfuse: Failed to update trace: {e}")
        
        response = FlashcardTaskResponse(
            task_id=task_id,
            status="pending",
            message="Flashcard generation started. Use the task_id to check progress."
        )
        
        # Close Langfuse trace
        if trace_ctx:
            try:
                trace_ctx.__exit__(None, None, None)
                logger.info("🟢 Langfuse: Trace 'flashcard-api-request' closed - data sent to Langfuse")
            except Exception as e:
                logger.warning(f"🔴 Langfuse: Error closing trace: {e}")
        
        return response
        
    except HTTPException:
        # Update Langfuse trace with error before raising
        if trace_ctx and langfuse:
            try:
                trace_ctx.update(
                    output={"error": "HTTPException raised"},
                    level="ERROR"
                )
            except Exception:
                pass
        raise
    except Exception as e:
        logger.error(f"Error creating flashcard generation task: {str(e)}", exc_info=True)
        
        # Update Langfuse trace with error
        if trace_ctx and langfuse:
            try:
                trace_ctx.update(
                    output={"error": str(e)},
                    level="ERROR"
                )
                logger.warning("🔴 Langfuse: Trace 'flashcard-api-request' marked as ERROR")
            except Exception as trace_error:
                logger.warning(f"🔴 Langfuse: Error updating trace: {trace_error}")
        
        # Close Langfuse trace
        if trace_ctx:
            try:
                trace_ctx.__exit__(type(e), e, None)
            except Exception:
                pass
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start flashcard generation: {str(e)}",
        )


@router.post("/flashcards/sync", status_code=200)
async def sync_flashcards_from_anki(
    course_id: str = Query(..., description="Course ID (UUID)"),
    user_id: str = Query(..., description="User ID (UUID)")
) -> dict:
    """
    Sync flashcard cache from Anki.
    
    Pulls any manual edits/additions from Anki into the local cache.
    Useful for debugging or forcing a cache refresh.
    
    Args:
        course_id: Course ID to sync
        user_id: User ID (UUID)
        
    Returns:
        Sync statistics (inserted, updated, deleted, unchanged)
    """
    from app.services.storage import sync_cache_from_anki
    
    # Validate user
    if not validate_user_exists(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get course title to build deck name
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
    
    try:
        stats = sync_cache_from_anki(course_title, user_id, course_id)
        return {
            "status": "success",
            "course_title": course_title,
            "sync_stats": stats
        }
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.post("/flashcards/retry-ankiweb-sync", status_code=200)
async def retry_ankiweb_sync(
    user_id: str = Query(..., description="User ID (UUID)")
) -> dict:
    """
    Retry syncing unsynced flashcards to AnkiWeb.
    
    Call this when AnkiWeb connection is restored to sync any cards
    that were added to local Anki but failed to sync to AnkiWeb.
    
    Args:
        user_id: User ID (UUID)
        
    Returns:
        Dict with sync status and count of synced cards
    """
    from app.services.storage import get_unsynced_flashcard_count, mark_flashcards_as_synced
    from app.services.anki.client import AnkiClient
    
    try:
        # Validate user exists
        if not validate_user_exists(user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found. Please sign up first.",
            )
        
        # Check how many cards need syncing
        unsynced_count = get_unsynced_flashcard_count(user_id)
        
        if unsynced_count == 0:
            return {
                "status": "success",
                "message": "No unsynced cards found",
                "synced_count": 0
            }
        
        # Try to sync to AnkiWeb
        try:
            anki = AnkiClient()
            anki.sync()
            
            # Mark all cards as synced
            synced_count = mark_flashcards_as_synced(user_id)
            
            return {
                "status": "success",
                "message": f"Successfully synced {synced_count} cards to AnkiWeb",
                "synced_count": synced_count
            }
        except Exception as e:
            logger.warning(f"AnkiWeb sync failed: {e}")
            return {
                "status": "failed",
                "message": f"AnkiWeb sync failed: {str(e)}",
                "unsynced_count": unsynced_count
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retry sync failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Retry sync failed: {str(e)}")


@router.get("/flashcards/status/{task_id}", response_model=FlashcardTaskStatusResponse, status_code=200)
async def get_flashcard_task_status(
    task_id: str = Path(..., description="Task ID"),
    user_id: str = Query(..., description="User ID (UUID)")
) -> FlashcardTaskStatusResponse:
    """
    Get the status of a flashcard generation task.
    
    Args:
        task_id: Task ID returned from /flashcards/generate
        user_id: User ID (UUID) for authorization
        
    Returns:
        FlashcardTaskStatusResponse with current progress and status
        
    Raises:
        HTTPException: If task not found or access denied
    """
    try:
        # Validate user exists
        if not validate_user_exists(user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found. Please sign up first.",
            )
        
        task_service = get_flashcard_task_service()
        task = await task_service.get_task(task_id)
        
        if not task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )
        
        # Verify task belongs to user
        if task.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied",
            )
        
        return FlashcardTaskStatusResponse(**task.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting flashcard task status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get task status: {str(e)}",
        )


@router.get("/flashcards/download/{task_id}")
async def download_flashcards(
    task_id: str = Path(..., description="Task ID"),
    user_id: str = Query(..., description="User ID (UUID)")
) -> StreamingResponse:
    """
    Download the generated flashcard CSV file.
    
    This endpoint can only be called when the task status is "completed".
    
    Args:
        task_id: Task ID returned from /flashcards/generate
        user_id: User ID (UUID) for authorization
        
    Returns:
        StreamingResponse with CSV file
        
    Raises:
        HTTPException: If task not found, not completed, or access denied
    """
    try:
        # Validate user exists
        if not validate_user_exists(user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found. Please sign up first.",
            )
        
        task_service = get_flashcard_task_service()
        task = await task_service.get_task(task_id)
        
        if not task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )
        
        # Verify task belongs to user
        if task.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied",
            )
        
        # Check if task is completed
        if task.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Task is not completed yet. Current status: {task.status}",
            )
        
        if not task.apkg_bytes or not task.filename:
            raise HTTPException(
                status_code=500,
                detail="Task completed but APKG file is missing",
            )
        
        # Return APKG file
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
        logger.error(f"Error downloading flashcards: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download flashcards: {str(e)}",
        )


@router.post("/flashcards/cancel/{task_id}", status_code=200)
async def cancel_flashcard_task(
    task_id: str = Path(..., description="Task ID"),
    user_id: str = Query(..., description="User ID (UUID)")
) -> dict:
    """
    Cancel a running flashcard generation task.
    
    Args:
        task_id: Task ID returned from /flashcards/generate
        user_id: User ID (UUID) for authorization
        
    Returns:
        Dict with success status
        
    Raises:
        HTTPException: If task not found or access denied
    """
    try:
        # Validate user exists
        if not validate_user_exists(user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found. Please sign up first.",
            )
        
        task_service = get_flashcard_task_service()
        task = await task_service.get_task(task_id)
        
        if not task:
            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )
        
        # Verify task belongs to user
        if task.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied",
            )
        
        # Cancel task
        cancelled = await task_service.cancel_task(task_id)
        
        if not cancelled:
            raise HTTPException(
                status_code=400,
                detail="Task cannot be cancelled (may already be completed or failed)",
            )
        
        logger.info(f"Cancelled flashcard generation task {task_id}")
        
        return {"success": True, "message": "Task cancelled"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling flashcard task: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel task: {str(e)}",
        )


@router.get("/flashcards/active/{course_material_id}", response_model=Optional[FlashcardTaskStatusResponse], status_code=200)
async def get_active_flashcard_task(
    course_material_id: str = Path(..., description="Course material ID (UUID)"),
    user_id: str = Query(..., description="User ID (UUID)")
) -> Optional[FlashcardTaskStatusResponse]:
    """
    Get the active (pending or running) flashcard generation task for a course material.
    
    This endpoint allows the frontend to check if there's an active task
    when the page loads, so it can restore the polling state.
    
    Args:
        course_material_id: Course material ID (UUID)
        user_id: User ID (UUID) for authorization
        
    Returns:
        FlashcardTaskStatusResponse if active task exists, None otherwise
        
    Raises:
        HTTPException: If validation fails
    """
    try:
        # Validate user exists
        if not validate_user_exists(user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found. Please sign up first.",
            )
        
        task_service = get_flashcard_task_service()
        task = await task_service.get_active_task_for_material(course_material_id, user_id)
        
        if not task:
            # Return None (will be serialized as null in JSON)
            return None
        
        return FlashcardTaskStatusResponse(**task.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting active flashcard task: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get active task: {str(e)}",
        )


@router.get("/flashcards/{course_material_id}", status_code=200)
async def get_flashcards(
    course_material_id: str = Path(..., description="Course material ID (UUID)"),
    user_id: str = Query(..., description="User ID (UUID)")
) -> dict:
    """
    Get all flashcards for a course material from Supabase.
    
    This endpoint retrieves flashcards that were previously generated
    and saved to the database, allowing users to access their flashcards
    at any time without needing the original task.
    
    Args:
        course_material_id: Course material ID (UUID)
        user_id: User ID (UUID) for authorization
        
    Returns:
        Dict with flashcards list:
        {
            "flashcards": [
                {
                    "id": "...",
                    "front": "...",
                    "back": "...",
                    "source_page_analysis_id": "...",
                    "created_at": "...",
                    "course_id": "...",
                    "user_id": "..."
                },
                ...
            ]
        }
        
    Raises:
        HTTPException: If validation fails or flashcards cannot be retrieved
    """
    try:
        # Validate user exists
        if not validate_user_exists(user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found. Please sign up first.",
            )
        
        # Validate that course material belongs to user and get file info
        client = get_supabase_client()
        material_response = (
            client.table("course_materials")
            .select("id, user_id, file_name, course_id")
            .eq("id", course_material_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        
        if not material_response.data:
            raise HTTPException(
                status_code=404,
                detail="Course material not found or access denied",
            )
        
        material = material_response.data
        course_id = material.get("course_id")
        file_name = material.get("file_name", "material")
        
        # Get course title to construct deck_name
        course_response = (
            client.table("courses")
            .select("title")
            .eq("id", course_id)
            .single()
            .execute()
        )
        
        course_title = course_response.data.get("title", "course") if course_response.data else "course"
        
        # Construct deck name (matches format used during generation)
        deck_name = f"{course_title}::{file_name.replace('.pdf', '')}"
        
        # Get flashcards from flashcard_cache table (new Anki-aligned storage)
        flashcards = get_cached_flashcards_for_material(deck_name, user_id)
        
        return {
            "flashcards": flashcards,
            "count": len(flashcards)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting flashcards: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get flashcards: {str(e)}",
        )


@router.get("/flashcards/{course_material_id}/download")
async def download_flashcards_from_db(
    course_material_id: str = Path(..., description="Course material ID (UUID)"),
    user_id: str = Query(..., description="User ID (UUID)")
) -> StreamingResponse:
    """
    Download flashcards for a course material as Anki .apkg file from Supabase.
    
    This endpoint loads flashcards directly from the database and generates
    an .apkg file on-the-fly with embedded images. This allows users to download
    flashcards at any time without needing the original task.
    
    Args:
        course_material_id: Course material ID (UUID)
        user_id: User ID (UUID) for authorization
        
    Returns:
        StreamingResponse with .apkg file
        
    Raises:
        HTTPException: If flashcards not found, access denied, or download fails
    """
    try:
        # Validate user exists
        if not validate_user_exists(user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found. Please sign up first.",
            )
        
        # Validate that course material belongs to user and get filename
        client = get_supabase_client()
        material_response = (
            client.table("course_materials")
            .select("id, user_id, file_name, course_id")
            .eq("id", course_material_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        
        if not material_response.data:
            raise HTTPException(
                status_code=404,
                detail="Course material not found or access denied",
            )
        
        material = material_response.data
        course_id = material.get("course_id")
        
        # Get course title for filename
        course_response = (
            client.table("courses")
            .select("title")
            .eq("id", course_id)
            .single()
            .execute()
        )
        
        course_title = course_response.data.get("title", "course") if course_response.data else "course"
        file_name = material.get("file_name", "material")
        
        # Construct deck name (matches format used during generation)
        deck_name = f"{course_title}::{file_name.replace('.pdf', '')}"
        
        # Get flashcards from flashcard_cache table (new Anki-aligned storage)
        flashcards = get_cached_flashcards_for_material(deck_name, user_id)
        
        if not flashcards:
            raise HTTPException(
                status_code=404,
                detail="No flashcards found for this material. Please generate flashcards first.",
            )
        
        # Convert to format expected by build_anki_apkg
        cards_for_apkg = []
        for card in flashcards:
            cards_for_apkg.append({
                "front": card.get("front", ""),
                "back": card.get("back", ""),
                "tags": card.get("tags", [])  # Tags are now available from flashcard_cache
            })
        
        # Build .apkg with embedded images
        import re
        lecture_name = file_name.replace('.pdf', '')
        
        # Use deck_name format for filename, replacing :: with - for filesystem compatibility
        # Only remove characters that are invalid in filenames: / \ : * ? " < > |
        safe_deck_name = re.sub(r'[/\\:*?"<>|]', '', f"{course_title} - {lecture_name}").strip()[:100]
        
        apkg_bytes = build_anki_apkg(cards_for_apkg, deck_name=deck_name)
        filename = f"{safe_deck_name}.apkg"
        
        # Return APKG file
        return StreamingResponse(
            io.BytesIO(apkg_bytes),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "application/zip"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading flashcards from database: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download flashcards: {str(e)}",
        )


@router.put("/materials/{material_id}", response_model=MaterialResponse, status_code=200)
async def update_material_endpoint(
    material_id: str = Path(..., description="Material ID (UUID)"),
    user_id: str = Query(..., description="User ID (UUID)"),
    material_update: MaterialUpdateRequest = ...
) -> MaterialResponse:
    """
    Update course material data.
    
    Currently supports updating the file_name field.
    Validates that the material exists and belongs to the user.
    
    Args:
        material_id: Material ID (UUID)
        user_id: User ID (UUID) - required for authorization
        material_update: MaterialUpdateRequest with fields to update
        
    Returns:
        MaterialResponse with updated material data
        
    Raises:
        HTTPException: If material not found or access denied
    """
    # Validate user exists
    if not validate_user_exists(user_id):
        raise HTTPException(
            status_code=404,
            detail="User not found. Please sign up first.",
        )
    
    # Validate that material exists and belongs to user
    client = get_supabase_client()
    try:
        material_response = (
            client.table("course_materials")
            .select("*")
            .eq("id", material_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        
        if not material_response.data:
            raise HTTPException(
                status_code=404,
                detail="Course material not found or access denied",
            )
        
        # Build update dict (only include non-None fields)
        update_data = {}
        if material_update.file_name is not None:
            # Validate filename is not empty
            if not material_update.file_name.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Filename cannot be empty"
                )
            update_data["file_name"] = material_update.file_name.strip()
        
        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No fields provided for update"
            )
        
        # Update material
        updated_response = (
            client.table("course_materials")
            .update(update_data)
            .eq("id", material_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        if updated_response.data and len(updated_response.data) > 0:
            return MaterialResponse(**updated_response.data[0])
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to update material"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating material: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update material: {str(e)}"
        )


@router.delete("/materials/{material_id}", status_code=200)
async def delete_material_endpoint(
    material_id: str = Path(..., description="Material ID (UUID)"),
    user_id: str = Query(..., description="User ID (UUID)"),
) -> dict:
    """
    Delete a course material and all associated data.
    
    This endpoint:
    - Validates that the material exists and belongs to the user
    - Deletes flashcards associated ONLY with this specific material (via page_analyses)
    - Deletes any stored Anki APKG files specific to this material
    - Deletes the PDF file from Supabase Storage
    - Deletes the material record from database (cascades handle page_analyses, slide_snippets)
    
    Args:
        material_id: Material ID (UUID)
        user_id: User ID (UUID) - required for authorization
        
    Returns:
        Success response with status message
        
    Raises:
        HTTPException: If material not found, access denied, or deletion fails
    """
    # Validate user exists
    if not validate_user_exists(user_id):
        raise HTTPException(
            status_code=404,
            detail="User not found. Please sign up first.",
        )
    
    try:
        delete_course_material(material_id, user_id)
        return {"status": "success", "message": "Material deleted successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error deleting material: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete material: {str(e)}"
        )


@router.post("/quiz/submit", response_model=QuizResult, status_code=200)
async def submit_quiz(
    request: QuizSubmit = Body(...)
) -> QuizResult:
    """
    Submit quiz answers and get results.
    
    After submission, generates tutor feedback based on the results.
    
    Args:
        request: QuizSubmit with quiz_id, answers, and user_id
        
    Returns:
        QuizResult with score, correct_count, total_questions, question_results, and tutor_feedback
        
    Raises:
        HTTPException: If quiz not found, already submitted, or submission fails
    """
    try:
        # Validate user exists
        if not validate_user_exists(request.user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found. Please sign up first."
            )
        
        # Submit quiz results
        result = submit_quiz_results(
            quiz_id=request.quiz_id,
            user_id=request.user_id,
            answers=request.answers
        )
        
        logger.info(
            f"Quiz submitted: {request.quiz_id} "
            f"(user: {request.user_id}, score: {result.score:.2%})"
        )
        
        # Generate tutor feedback based on quiz results
        try:
            # Get quiz data to find course_material_id
            quiz_record = get_quiz(request.quiz_id, request.user_id)
            if quiz_record:
                course_material_id = quiz_record["course_material_id"]
                topic_name = quiz_record["topic_name"]
                quiz_data_dict = quiz_record["quiz_data"]
                
                # Get or create study conversation for context
                conversation = get_or_create_study_conversation(
                    user_id=request.user_id,
                    course_material_id=course_material_id,
                    course_id=None,
                )
                conversation_id = conversation["id"]
                thread_id = str(conversation_id)
                
                # Build feedback prompt text with wrong/correct questions
                wrong_questions = [qr for qr in result.question_results if not qr.correct]
                correct_questions = [qr for qr in result.question_results if qr.correct]
                
                # Format wrong questions text
                wrong_questions_text = ""
                if wrong_questions:
                    wrong_questions_text = "Falsch beantwortete Fragen:\n"
                    for qr in wrong_questions:
                        # Find question details from quiz_data
                        question_data = next(
                            (q for q in quiz_data_dict.get("questions", []) if q.get("id") == qr.question_id),
                            None
                        )
                        if question_data:
                            wrong_questions_text += f"- Frage: {question_data.get('question', 'Unbekannt')}\n"
                            wrong_questions_text += f"  Student-Antwort: {qr.user_answer}, Richtige Antwort: {qr.correct_answer}\n"
                            wrong_questions_text += f"  Erklärung: {question_data.get('explanation', 'Keine Erklärung verfügbar')}\n\n"
                
                # Format correct questions text
                correct_questions_text = ""
                if correct_questions:
                    correct_questions_text = f"Richtig beantwortete Fragen ({len(correct_questions)}): Gut gemacht!"
                
                # Load feedback prompt from Langfuse
                try:
                    feedback_prompt_text = get_tutor_prompt(
                        "tutor-agent/quiz-feedback-de",
                        topic_name=topic_name,
                        correct_count=result.correct_count,
                        total_questions=result.total_questions,
                        score_percent=f"{(result.score * 100):.0f}",
                        wrong_questions_text=wrong_questions_text,
                        correct_questions_text=correct_questions_text
                    )
                except Exception as prompt_error:
                    logger.warning(f"Failed to load feedback prompt from Langfuse: {prompt_error}, using fallback")
                    # Fallback prompt
                    feedback_prompt_text = f"""Der Student hat gerade ein Quiz zum Thema "{topic_name}" abgeschlossen.

Ergebnis: {result.correct_count} von {result.total_questions} Fragen richtig beantwortet ({(result.score * 100):.0f}%)

{wrong_questions_text}

{correct_questions_text}

Gib dem Studenten konstruktives Feedback:
1. Erkenne die Leistung an (auch bei niedrigem Score)
2. Erkläre die falsch beantworteten Fragen kurz und verständlich
3. Gib Tipps, wie der Student diese Konzepte besser verstehen kann
4. Motiviere für die nächsten Schritte
5. Halte das Feedback prägnant (3-5 Sätze)"""
                
                # Initialize Tutor Agent and generate feedback
                # Use LLM with explicit run_name for Langfuse tracking
                llm = get_gemini_model().with_config({
                    "run_name": "tutor-agent/quiz-feedback-generation"
                })
                agent = TutorAgent(llm=llm, checkpointer=_checkpointer)
                
                # Set state for agent (material_id, user_id)
                agent_state = {
                    "messages": [HumanMessage(content=feedback_prompt_text)],
                    "material_id": course_material_id,
                    "user_id": request.user_id,
                    "current_page": None  # Not needed for feedback
                }
                
                # Prepare config with Langfuse metadata for feedback generation
                from app.services.observability import create_callback_handler
                callback_handler = create_callback_handler()
                
                agent_config = {
                    "configurable": {
                        "thread_id": thread_id,
                        "user_id": request.user_id
                    }
                }
                
                if callback_handler:
                    agent_config["callbacks"] = [callback_handler]
                    agent_config["metadata"] = {
                        "langfuse_user_id": request.user_id,
                        "langfuse_session_id": course_material_id,
                        "operation": "quiz_feedback_generation",
                        "quiz_id": request.quiz_id,
                        "topic_name": topic_name,
                        "score": result.score,
                        "correct_count": result.correct_count,
                        "total_questions": result.total_questions,
                        "score_percent": f"{(result.score * 100):.0f}",
                        "agent_name": "TutorAgent",
                        "run_name": "tutor-agent/quiz-feedback-generation"
                    }
                    logger.info(
                        f"🟡 Langfuse: Generating tutor feedback for quiz {request.quiz_id} "
                        f"(run_name: tutor-agent/quiz-feedback-generation) "
                        f"with metadata: user_id={request.user_id}, session_id={course_material_id}, "
                        f"score={result.score:.2%}, topic={topic_name}"
                    )
                
                # Run agent to generate feedback with Langfuse tracing
                langfuse_client = get_langfuse_client()
                graph_span_ctx = None
                graph_span = None
                if langfuse_client and settings.LANGFUSE_ENABLED:
                    try:
                        graph_span_ctx = langfuse_client.start_as_current_observation(
                            as_type="span",
                            name="tutor-agent/graph-execution-quiz-feedback",
                            input={
                                "user_id": request.user_id,
                                "quiz_id": request.quiz_id,
                                "course_material_id": course_material_id,
                                "score": result.score
                            }
                        )
                        graph_span = graph_span_ctx.__enter__()
                        logger.info(f"🟡 Langfuse: Started graph execution span 'tutor-agent/graph-execution-quiz-feedback'")
                    except Exception as e:
                        logger.warning(f"🔴 Langfuse: Failed to start graph execution span: {e}")
                        graph_span_ctx = None
                        graph_span = None
                
                try:
                    agent_result = agent.graph.invoke(agent_state, config=agent_config)
                    
                    if callback_handler:
                        logger.info(
                            f"🟢 Langfuse: Tutor feedback generation completed "
                            f"(run_name: tutor-agent/quiz-feedback-generation) - "
                            f"data tracked by CallbackHandler"
                        )
                    
                    # Update graph execution span with success
                    if graph_span:
                        try:
                            graph_span.update(output={"status": "completed"})
                            logger.info("🟢 Langfuse: Graph execution span updated with success")
                        except Exception as e:
                            logger.warning(f"🔴 Langfuse: Failed to update graph execution span: {e}")
                except Exception as e:
                    # Update graph execution span with error
                    if graph_span:
                        try:
                            graph_span.update(output={"status": "error", "error": str(e)})
                            logger.warning("🔴 Langfuse: Graph execution span updated with error")
                        except Exception:
                            pass
                    raise
                finally:
                    # Close graph execution span
                    if graph_span_ctx:
                        try:
                            exc_info = sys.exc_info()
                            graph_span_ctx.__exit__(*exc_info)
                            logger.info("🟢 Langfuse: Graph execution span closed")
                        except Exception as e:
                            logger.warning(f"🔴 Langfuse: Error closing graph execution span: {e}")
                
                # Extract feedback from agent response
                feedback_messages = agent_result.get("messages", [])
                if feedback_messages:
                    last_message = feedback_messages[-1]
                    if hasattr(last_message, "content"):
                        # Extract content properly - handle string, list, or object formats
                        content = last_message.content
                        tutor_feedback = None
                        
                        if isinstance(content, str):
                            # Simple string content
                            tutor_feedback = content
                        elif isinstance(content, list):
                            # List format (e.g., multi-modal content)
                            try:
                                # Extract text from list items
                                text_parts = []
                                for part in content:
                                    if isinstance(part, dict):
                                        # Try common text fields
                                        text = part.get("text") or part.get("content") or part.get("text_content")
                                        if text:
                                            text_parts.append(str(text))
                                    elif isinstance(part, str):
                                        text_parts.append(part)
                                    else:
                                        text_parts.append(str(part))
                                tutor_feedback = "".join(text_parts) if text_parts else None
                            except Exception as e:
                                logger.warning(f"Failed to extract text from list content: {e}")
                                tutor_feedback = str(content)  # Fallback
                        elif isinstance(content, dict):
                            # Object format - try to extract text
                            tutor_feedback = content.get("text") or content.get("content") or content.get("text_content")
                            if not tutor_feedback:
                                # Fallback: convert to JSON string
                                import json
                                tutor_feedback = json.dumps(content, ensure_ascii=False)
                        else:
                            # Other types - convert to string
                            tutor_feedback = str(content) if content else None
                        
                        # Only add feedback if we successfully extracted a non-empty string
                        if tutor_feedback and tutor_feedback.strip():
                            # Add feedback to result - use model_copy to preserve all fields
                            result = result.model_copy(update={"tutor_feedback": tutor_feedback})
                            logger.info(f"Tutor feedback generated for quiz {request.quiz_id} (length: {len(tutor_feedback)})")
                        else:
                            logger.warning(f"Tutor feedback is empty or could not be extracted for quiz {request.quiz_id}")
                else:
                    logger.warning(f"No feedback generated for quiz {request.quiz_id}")
        
        except Exception as e:
            # Don't fail quiz submission if feedback generation fails
            logger.error(f"Failed to generate tutor feedback: {str(e)}", exc_info=True)
            # Continue without feedback
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting quiz: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit quiz: {str(e)}"
        )


@router.get("/quiz/{quiz_id}", response_model=QuizResponse, status_code=200)
async def get_quiz_endpoint(
    quiz_id: str = Path(..., description="Quiz ID (UUID)"),
    user_id: str = Query(..., description="User ID (UUID)")
) -> QuizResponse:
    """
    Get quiz data by ID.
    
    Args:
        quiz_id: Quiz ID (UUID)
        user_id: User ID for authorization (UUID)
        
    Returns:
        QuizResponse with full quiz data
        
    Raises:
        HTTPException: If quiz not found or access denied
    """
    try:
        # Validate user exists
        if not validate_user_exists(user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found. Please sign up first."
            )
        
        # Get quiz
        quiz_record = get_quiz(quiz_id, user_id)
        if not quiz_record:
            raise HTTPException(
                status_code=404,
                detail=f"Quiz not found: {quiz_id}"
            )
        
        # Parse quiz_data from JSONB
        quiz_data_dict = quiz_record["quiz_data"]
        from app.models.schemas import QuizData
        quiz_data = QuizData(**quiz_data_dict)
        
        return QuizResponse(
            id=quiz_record["id"],
            course_material_id=quiz_record["course_material_id"],
            user_id=quiz_record["user_id"],
            topic_name=quiz_record["topic_name"],
            start_page=quiz_record["start_page"],
            end_page=quiz_record["end_page"],
            quiz_data=quiz_data,
            created_at=quiz_record["created_at"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quiz: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get quiz: {str(e)}"
        )


@router.post("/study/snippets")
async def upload_snippet(
    file: UploadFile = File(...),
    course_material_id: str = Form(...),
    page_number: int = Form(...),
    user_id: str = Form(...)
):
    """
    Upload a new slide snippet.
    """
    try:
        logger.info(f"Uploading snippet: material_id={course_material_id}, page={page_number}, user_id={user_id}")
        
        # Validate user
        if not validate_user_exists(user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
            
        # Read file
        file_bytes = await file.read()
        logger.info(f"Read {len(file_bytes)} bytes from file")
        
        # Create snippet
        snippet = create_snippet(
            file_bytes=file_bytes,
            course_material_id=course_material_id,
            page_number=page_number,
            user_id=user_id
        )
        
        logger.info(f"Snippet created successfully: {snippet.get('id', 'unknown')}")
        return snippet
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading snippet: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload snippet: {str(e)}"
        )


@router.get("/study/snippets/{material_id}")
async def get_snippets(
    material_id: str,
    user_id: str = Query(...)
):
    """
    Get all snippets for a material.
    """
    try:
        snippets = get_snippets_for_material(material_id, user_id)
        return snippets
    except Exception as e:
        logger.error(f"Error fetching snippets: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch snippets: {str(e)}"
        )


@router.delete("/study/snippets/{snippet_id}")
async def remove_snippet(
    snippet_id: str,
    user_id: str = Query(...)
):
    """
    Delete a snippet.
    """
    try:
        delete_snippet(snippet_id, user_id)
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting snippet: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete snippet: {str(e)}"
        )


# =============================================================================
# Anki Study History
# =============================================================================

@router.get("/anki/study-history")
async def get_anki_study_history(
    user_id: str = Query(..., description="User ID"),
    days: int = Query(90, description="Number of days of history to retrieve", ge=1, le=365),
    cache_only: bool = Query(False, description="If true, only return cached data (fast)"),
):
    """
    Get Anki study history for a user.
    
    Returns comprehensive daily study statistics including:
    - Cards reviewed per day
    - Time spent studying
    - Button press breakdown (Again/Hard/Good/Easy)
    - Card type breakdown (New/Review/Relearn)
    
    Use cache_only=true for instant response with cached data.
    Use cache_only=false (default) to fetch fresh data from Anki and sync to database.
    """
    try:
        # Validate user exists
        if not validate_user_exists(user_id):
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        # Helper to format cached data
        def format_cached_data(cached_data):
            return {
                "status": "success",
                "source": "cache",
                "days_requested": days,
                "data": [
                    {
                        "date": record["study_date"],
                        "cards_reviewed": record["cards_reviewed"],
                        "time_spent_seconds": record["time_spent_seconds"],
                        "again_count": record["again_count"],
                        "hard_count": record["hard_count"],
                        "good_count": record["good_count"],
                        "easy_count": record["easy_count"],
                        "new_cards": record["new_cards"],
                        "review_cards": record["review_cards"],
                        "relearn_cards": record["relearn_cards"],
                        "avg_time_per_card_ms": record["avg_time_per_card_ms"],
                    }
                    for record in cached_data
                ]
            }
        
        # If cache_only, return cached data immediately (fast path)
        if cache_only:
            cached_data = get_study_history(user_id, days=days)
            return format_cached_data(cached_data)
        
        # Otherwise, try to get fresh data from Anki
        anki_available = False
        fresh_data = []
        
        try:
            client = AnkiClient()
            if client.is_running():
                fresh_data = client.get_detailed_study_history(days=days)
                anki_available = True
                
                # Sync to database for future offline access
                if fresh_data:
                    sync_result = sync_anki_study_history(user_id, fresh_data)
                    logger.info(f"Synced {sync_result['synced']} study history records for user {user_id}")
        except AnkiConnectionError as e:
            logger.warning(f"Anki not available: {e}")
        except Exception as e:
            logger.error(f"Error fetching from Anki: {e}")
        
        # If we got fresh data from Anki, convert and return it
        if anki_available and fresh_data:
            return {
                "status": "success",
                "source": "anki",
                "days_requested": days,
                "data": [
                    {
                        "date": stats.date,
                        "cards_reviewed": stats.cards_reviewed,
                        "time_spent_seconds": stats.time_spent_seconds,
                        "again_count": stats.again_count,
                        "hard_count": stats.hard_count,
                        "good_count": stats.good_count,
                        "easy_count": stats.easy_count,
                        "new_cards": stats.new_cards,
                        "review_cards": stats.review_cards,
                        "relearn_cards": stats.relearn_cards,
                        "avg_time_per_card_ms": stats.avg_time_per_card_ms,
                    }
                    for stats in fresh_data
                ]
            }
        
        # Fall back to cached data from database
        cached_data = get_study_history(user_id, days=days)
        return format_cached_data(cached_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting study history: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get study history: {str(e)}"
        )


# =============================================================================
# Anki Sync Management
# =============================================================================

@router.get("/anki/sync-status")
async def get_anki_sync_status():
    """
    Check the current sync status with AnkiWeb.
    
    Returns:
    - status: "ok" | "full_sync_required" | "not_logged_in" | "not_connected" | "error"
    - message: Human-readable status message
    - can_sync: Whether normal sync is possible
    - action_required: What action the user needs to take (if any)
    """
    try:
        client = AnkiClient()
        
        # First check if Anki is running
        if not client.is_running():
            return {
                "status": "not_connected",
                "message": "Anki is not running. Please start the Docker container.",
                "can_sync": False,
                "action_required": "start_anki"
            }
        
        # Check sync status
        sync_status = client.get_sync_status()
        
        # Add action_required based on status
        action_required = None
        if sync_status["status"] == "full_sync_required":
            action_required = "resolve_conflict"
        elif sync_status["status"] == "not_logged_in":
            action_required = "login_ankiweb"
        
        return {
            **sync_status,
            "action_required": action_required
        }
        
    except Exception as e:
        logger.error(f"Error checking sync status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check sync status: {str(e)}"
        )


@router.post("/anki/sync")
async def trigger_anki_sync():
    """
    Trigger a normal sync with AnkiWeb.
    
    This will fail if a full sync is required (conflict).
    Use GET /anki/sync-status first to check, and POST /anki/force-sync
    to resolve conflicts.
    """
    try:
        client = AnkiClient()
        
        if not client.is_running():
            raise HTTPException(
                status_code=503,
                detail="Anki is not running. Please start the Docker container."
            )
        
        # Attempt sync
        client.sync()
        
        return {
            "status": "success",
            "message": "Sync completed successfully"
        }
        
    except AnkiError as e:
        error_msg = str(e)
        if "Sync status 2" in error_msg:
            raise HTTPException(
                status_code=409,  # Conflict
                detail="Full sync required. Use POST /anki/force-sync with mode='upload' or 'download' to resolve."
            )
        raise HTTPException(
            status_code=500,
            detail=f"Sync failed: {error_msg}"
        )
    except AnkiConnectionError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Anki: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error during sync: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Sync failed: {str(e)}"
        )


class ForceSyncRequest(BaseModel):
    mode: str = Field(
        ...,
        description="Sync direction: 'upload' (local→server) or 'download' (server→local)"
    )


@router.post("/anki/force-sync")
async def force_anki_sync(request: ForceSyncRequest):
    """
    Force a full sync in a specific direction to resolve conflicts.
    
    Args:
        mode: 
            - "upload": Overwrite AnkiWeb with local Docker Anki data
            - "download": Overwrite local Docker Anki with AnkiWeb data
    
    ⚠️  WARNING: This is destructive! One side's data will be lost.
    
    - Use "upload" if you want to KEEP the generated flashcards from this app
    - Use "download" if you want to KEEP changes from your phone/other devices
    """
    try:
        if request.mode not in ("upload", "download"):
            raise HTTPException(
                status_code=400,
                detail="Mode must be 'upload' or 'download'"
            )
        
        client = AnkiClient()
        
        if not client.is_running():
            raise HTTPException(
                status_code=503,
                detail="Anki is not running. Please start the Docker container."
            )
        
        # Attempt force sync
        result = client.force_sync(request.mode)
        
        if result["success"]:
            return {
                "status": "success",
                "message": result["message"]
            }
        else:
            # Check if the custom addon is not installed
            if "not available" in result["message"].lower():
                raise HTTPException(
                    status_code=501,  # Not Implemented
                    detail=(
                        "Force sync not available via API. The Docker container needs "
                        "to be restarted to load the custom addon. "
                        "Alternatively, resolve the conflict manually via VNC at localhost:5900"
                    )
                )
            raise HTTPException(
                status_code=500,
                detail=result["message"]
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during force sync: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Force sync failed: {str(e)}"
        )


class AnkiWebLoginRequest(BaseModel):
    email: str = Field(..., description="AnkiWeb account email")
    password: str = Field(..., description="AnkiWeb account password")


@router.post("/anki/login")
async def login_ankiweb(login_request: AnkiWebLoginRequest, request: Request):
    """
    Login to AnkiWeb with email and password.
    
    This authenticates with AnkiWeb and stores the credentials
    so future syncs work automatically. The password is NOT stored,
    only the authentication token (hkey).
    
    Rate limited to 5 attempts per 15 minutes per IP address.
    """
    # Check rate limit
    client_ip = get_client_ip(request)
    is_limited, remaining = ankiweb_login_limiter.is_rate_limited(client_ip)
    
    if is_limited:
        retry_after = ankiweb_login_limiter.get_retry_after(client_ip)
        logger.warning(f"Rate limit exceeded for AnkiWeb login from IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts. Please try again in {retry_after // 60} minutes.",
            headers={"Retry-After": str(retry_after)}
        )
    
    # Record this attempt (before checking success/failure)
    ankiweb_login_limiter.record_request(client_ip)
    
    try:
        client = AnkiClient()
        
        if not client.is_running():
            raise HTTPException(
                status_code=503,
                detail="Anki is not running. Please start the Docker container."
            )
        
        # Call the loginAnkiWeb action from our custom addon
        result = client._request("loginAnkiWeb", {
            "email": login_request.email,
            "password": login_request.password
        })
        
        if "error" in result:
            raise HTTPException(
                status_code=401,
                detail=result["error"]
            )
        
        # Clear status cache so next check reflects the new login
        _clear_ankiweb_status_cache()
        
        return {
            "status": "success",
            "message": result.get("message", "Logged in to AnkiWeb"),
            "username": result.get("username", login_request.email)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error during AnkiWeb login: {error_msg}", exc_info=True)
        
        # Check for "unsupported action" which means addon needs to be reloaded
        if "unsupported action" in error_msg.lower():
            raise HTTPException(
                status_code=501,
                detail="AnkiWeb login not available. Please restart the Anki Docker container to load the updated addon."
            )
        
        raise HTTPException(
            status_code=500,
            detail=f"Login failed: {error_msg}"
        )


@router.get("/anki/login-status")
async def get_ankiweb_login_status():
    """
    Get the current AnkiWeb login status.
    
    Returns cached result if available (30s TTL) to avoid slow Docker/AnkiConnect checks.
    
    Returns:
    - status: "logged_in" | "not_logged_in" | "not_connected"
    - username: The logged in email (if logged in)
    """
    # Check cache first
    cache_age = time.time() - _ankiweb_status_cache["timestamp"]
    if _ankiweb_status_cache["data"] is not None and cache_age < ANKIWEB_STATUS_CACHE_TTL:
        return _ankiweb_status_cache["data"]
    
    try:
        client = AnkiClient()
        
        if not client.is_running():
            result = {
                "status": "not_connected",
                "username": None,
                "message": "Anki is not running"
            }
            # Cache not_connected for shorter time (5s) to allow quick retry
            _ankiweb_status_cache["data"] = result
            _ankiweb_status_cache["timestamp"] = time.time() - ANKIWEB_STATUS_CACHE_TTL + 5
            return result
        
        # Call the getAnkiWebUsername action from our custom addon
        api_result = client._request("getAnkiWebUsername", {})
        
        if "error" in api_result:
            result = {
                "status": "error",
                "username": None,
                "message": api_result["error"]
            }
            # Don't cache errors
            return result
        
        result = {
            "status": api_result.get("status", "not_logged_in"),
            "username": api_result.get("username"),
            "message": "Connected to AnkiWeb" if api_result.get("status") == "logged_in" else "Not logged in to AnkiWeb"
        }
        
        # Cache the successful result
        _ankiweb_status_cache["data"] = result
        _ankiweb_status_cache["timestamp"] = time.time()
        return result
        
    except Exception as e:
        logger.error(f"Error checking AnkiWeb login status: {str(e)}", exc_info=True)
        # Don't cache errors
        return {
            "status": "error",
            "username": None,
            "message": f"Error checking status: {str(e)}"
        }


@router.post("/anki/logout")
async def logout_ankiweb():
    """
    Logout from AnkiWeb by clearing stored credentials.
    """
    try:
        client = AnkiClient()
        
        if not client.is_running():
            raise HTTPException(
                status_code=503,
                detail="Anki is not running. Please start the Docker container."
            )
        
        # Call the logoutAnkiWeb action from our custom addon
        result = client._request("logoutAnkiWeb", {})
        
        if "error" in result:
            raise HTTPException(
                status_code=500,
                detail=result["error"]
            )
        
        # Clear status cache so next check reflects the logout
        _clear_ankiweb_status_cache()
        
        return {
            "status": "success",
            "message": result.get("message", "Logged out from AnkiWeb")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during AnkiWeb logout: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Logout failed: {str(e)}"
        )
