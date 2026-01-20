"""
API Endpoints

FastAPI route handlers for PDF upload and processing.
"""

import io
import json
import logging
import sys
import traceback
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Form, BackgroundTasks, Path, Body
from fastapi.responses import StreamingResponse
from pdf2image import convert_from_bytes
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
)
from app.services.pdf_processor import process_pdf_background
from app.services.storage import (
    upload_pdf_to_storage,
    create_course_material,
    validate_user_exists,
    get_course,
    get_supabase_client,
    get_page_analysis,
    get_page_analysis_id,
)
from app.agents.flashcards import FlashcardGeneratorAgent
from app.services.flashcard_service import build_anki_csv
from app.services.flashcard_task_service import get_flashcard_task_service
from app.services.session_storage import (
    get_or_create_study_conversation,
    update_conversation_progress,
    append_messages,
    load_conversation_with_messages,
)
from langfuse import get_client, propagate_attributes
from app.core.config import settings
import os

logger = logging.getLogger(__name__)

router = APIRouter()


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
        
        # Convert PDF to images
        try:
            logger.info("Converting PDF to images...")
            images = convert_from_bytes(
                file_bytes,
                dpi=300,
                fmt='jpeg'
            )
            logger.info(f"Converted {len(images)} pages to images")
        except Exception as e:
            logger.error(f"Failed to convert PDF: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=400,
                detail=f"Failed to convert PDF to images: {str(e)}"
            )
        
        page_count = len(images)
        
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
        
        # Get page count for response (quick check without full processing)
        try:
            logger.info("Getting page count from PDF...")
            images = convert_from_bytes(
                file_bytes,
                dpi=300,
                fmt='jpeg'
            )
            page_count = len(images)
            logger.info(f"PDF has {page_count} pages")
        except Exception as e:
            logger.error(f"Failed to get page count: {str(e)}", exc_info=True)
            # Continue anyway, background task will handle it
            page_count = 0
        
        # Start background processing task
        logger.info(f"Starting background processing task for material {material_id}")
        background_tasks.add_task(
            process_pdf_background,
            material_id=material_id,
            file_bytes=file_bytes,
            user_id=user_id,
            max_concurrent=5  # Process 5 pages in parallel
        )
        
        # Return immediately with queued status
        return UploadResponse(
            message="PDF upload successful. Processing started in background.",
            course_material_id=material_id,
            page_count=page_count,
            pages_analyzed=0,  # Will be updated by background task
            status="queued",
            error_message=None
        )
    
    except HTTPException:
        raise
    except Exception as e:
        # Log the full error with traceback
        logger.error(f"Unexpected error during PDF processing: {str(e)}", exc_info=True)
        logger.error(f"Traceback: {traceback.format_exc()}")
        
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
                    
                    # #region agent log
                    import json
                    log_path = r"c:\App\AAI\AgenticAI_Group03\.cursor\debug.log"
                    try:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "pre-fix",
                                "hypothesisId": "H1",
                                "location": "endpoints.py:fix_incomplete_tool_calls(entry)",
                                "message": "Starting message validation",
                                "data": {
                                    "messageCount": len(messages),
                                    "messageTypes": [type(msg).__name__ for msg in messages]
                                },
                                "timestamp": int(__import__("time").time() * 1000)
                            }) + "\n")
                    except Exception:
                        pass
                    # #endregion agent log
                    
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
                                
                                # #region agent log
                                try:
                                    with open(log_path, "a", encoding="utf-8") as f:
                                        f.write(json.dumps({
                                            "sessionId": "debug-session",
                                            "runId": "pre-fix",
                                            "hypothesisId": "H1",
                                            "location": "endpoints.py:fix_incomplete_tool_calls(complete_pair)",
                                            "message": "Found complete tool call pair",
                                            "data": {
                                                "toolCallCount": len(tool_call_ids),
                                                "toolMessageCount": len(found_tool_messages)
                                            },
                                            "timestamp": int(__import__("time").time() * 1000)
                                        }) + "\n")
                                except Exception:
                                    pass
                                # #endregion agent log
                            else:
                                # Incomplete tool call pair - remove the AIMessage
                                # #region agent log
                                try:
                                    with open(log_path, "a", encoding="utf-8") as f:
                                        f.write(json.dumps({
                                            "sessionId": "debug-session",
                                            "runId": "pre-fix",
                                            "hypothesisId": "H1",
                                            "location": "endpoints.py:fix_incomplete_tool_calls(incomplete_pair)",
                                            "message": "Removing incomplete tool call pair",
                                            "data": {
                                                "expectedToolCalls": len(tool_call_ids),
                                                "foundToolMessages": len(found_tool_messages),
                                                "missingToolCallIds": list(tool_call_ids - found_tool_call_ids)
                                            },
                                            "timestamp": int(__import__("time").time() * 1000)
                                        }) + "\n")
                                except Exception:
                                    pass
                                # #endregion agent log
                                
                                logger.warning(
                                    f"Incomplete tool call pair detected at index {i}: AIMessage has {len(tool_call_ids)} tool_calls, "
                                    f"but only {len(found_tool_messages)} ToolMessages found. Removing incomplete AIMessage to prevent API error."
                                )
                                i += 1  # Skip the incomplete AIMessage
                        elif isinstance(msg, ToolMessage):
                            # Orphaned ToolMessage (no preceding AIMessage with tool_calls)
                            # Remove it to prevent API errors
                            # #region agent log
                            try:
                                with open(log_path, "a", encoding="utf-8") as f:
                                    f.write(json.dumps({
                                        "sessionId": "debug-session",
                                        "runId": "pre-fix",
                                        "hypothesisId": "H1",
                                        "location": "endpoints.py:fix_incomplete_tool_calls(orphaned_tool)",
                                        "message": "Removing orphaned ToolMessage",
                                        "data": {
                                            "toolCallId": getattr(msg, "tool_call_id", None)
                                        },
                                        "timestamp": int(__import__("time").time() * 1000)
                                    }) + "\n")
                            except Exception:
                                pass
                            # #endregion agent log
                            
                            logger.warning(f"Orphaned ToolMessage detected at index {i}, removing to prevent API error.")
                            i += 1
                        else:
                            # Regular message (HumanMessage, AIMessage without tool_calls, SystemMessage)
                            fixed_messages.append(msg)
                            i += 1
                    
                    # #region agent log
                    try:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "pre-fix",
                                "hypothesisId": "H1",
                                "location": "endpoints.py:fix_incomplete_tool_calls(exit)",
                                "message": "Message validation complete",
                                "data": {
                                    "originalCount": len(messages),
                                    "fixedCount": len(fixed_messages),
                                    "removedCount": len(messages) - len(fixed_messages)
                                },
                                "timestamp": int(__import__("time").time() * 1000)
                            }) + "\n")
                    except Exception:
                        pass
                    # #endregion agent log
                    
                    return fixed_messages

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
                            initial_human_content = (
                                "The student has reopened the study reader, but you already sent them a welcome back message recently.\n\n"
                                f"- Current page: {request.page_number}\n"
                                f"- Page summary: {summary}\n\n"
                                "GREETING INSTRUCTIONS (German):\n"
                                "Begrüße den Studenten kurz und freundlich, aber NICHT mit einer erneuten 'Welcome Back' Nachricht.\n"
                                "Formuliere eine normale, kurze Nachricht zur aktuellen Folie, etwa so:\n"
                                f"\"Du bist gerade auf Folie {request.page_number}. [KURZE BESCHREIBUNG DER FOLIE BASIEREND AUF DER ZUSAMMENFASSUNG]. "
                                "Gibt es etwas Spezielles, das du über diese Folie wissen möchtest?\"\n"
                                "Halte die Nachricht kurz (1-2 Sätze) und fokussiere dich auf die aktuelle Folie."
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

                            initial_human_content = (
                                "The student is returning to this study session after closing and reopening the study reader.\n\n"
                                f"- They have already worked through approximately {completed_pages} "
                                f"of {total_pages_safe} pages in this material.\n"
                                "- You have access to the previous chat history in the messages above.\n"
                                f"{topics_instructions}\n\n"
                                "GREETING INSTRUCTIONS (German):\n"
                                "Begrüße den Studenten freundlich als Rückkehrer mit einer persönlichen Nachricht.\n"
                                "Formuliere etwa so (sinngemäß, nicht wortwörtlich, aber sehr ähnlich):\n"
                                f"\"Hi! Schön, dass du wieder da bist. Wir haben jetzt {completed_pages} von {total_pages_safe} "
                                "Seiten abgearbeitet und dabei folgende Themen behandelt: [NENNE HIER DIE 2–5 WICHTIGSTEN THEMEN "
                                "AUS DEM CHAT-VERLAUF, DIE WIRKLICH BEREITS BESPROCHEN WURDEN]. "
                                "Kannst du dich an alles erinnern oder soll ich dir nochmal eine kurze Zusammenfassung geben?\"\n"
                                "WICHTIG: Nutze wirklich nur den Chat-Verlauf als Grundlage für die Themenliste –\n"
                                "Themen, die lediglich als zukünftige Inhalte angekündigt wurden, sollen NICHT erwähnt werden.\n"
                                "Halte die Nachricht persönlich, freundlich und kurz (2-3 Sätze)."
                            )
                    else:
                        # First visit for this material (no previous chat history)
                        total_pages_safe = total_pages or "unbekannt"
                        initial_human_content = (
                        "This is the student's first visit to this study session for this lecture material.\n\n"
                        "IMPORTANT: Before greeting the student, use the get_course_material_summary tool to retrieve "
                        "the overall summary of this lecture material. This will give you context about the main topics "
                        "and concepts covered in this lecture.\n\n"
                        "Use the following information:\n"
                        f"- Current page: {request.page_number}\n"
                        f"- Total pages (if known): {total_pages_safe}\n"
                        f"- Page summary: {summary}\n\n"
                        "GREETING INSTRUCTIONS (German):\n"
                        "1. First, call the get_course_material_summary tool to get the overall lecture summary.\n"
                        "2. Then, begrüße den Studenten mit einer freundlichen, motivierenden ersten Nachricht.\n"
                        "3. Formuliere etwa so (sinngemäß, nicht wortwörtlich):\n"
                        "\"Hallo! Heute schauen wir uns diese Vorlesung bzw. diesen Foliensatz an. "
                        "Die Kernthemen sind: [NUTZE DIE ZUSAMMENFASSUNG AUS DEM TOOL, um die wichtigsten Themen "
                        "in 1–2 Sätzen zu benennen]. Wenn du bereit bist zu starten, blättere gerne eine Seite weiter "
                        "oder stell mir direkt eine Frage zu dieser Einführungsfolie.\"\n"
                        "Halte die Antwort kurz, freundlich und einladend. Nutze die Informationen aus dem Tool, "
                        "um eine informierte Begrüßung zu geben."
                    )

                    # Fix incomplete tool call pairs in base_messages before adding new messages
                    # This ensures message ordering is valid before adding new HumanMessage
                    base_messages = fix_incomplete_tool_calls(base_messages)
                    
                    # #region agent log
                    try:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "pre-fix",
                                "hypothesisId": "H5",
                                "location": "endpoints.py:initiate_chat(is_initial_open_validation)",
                                "message": "Validating base_messages before adding new HumanMessage",
                                "data": {
                                    "baseMessageCount": len(base_messages),
                                    "lastMessageType": type(base_messages[-1]).__name__ if base_messages else None
                                },
                                "timestamp": int(__import__("time").time() * 1000)
                            }) + "\n")
                    except Exception:
                        pass
                    # #endregion agent log
                    
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
                    }
                else:
                    # This is just a page change within an ongoing session
                    # Use existing LangGraph state if available, otherwise bootstrap
                    if is_new_thread:
                        # LangGraph state is empty, but we might have bootstrapped messages
                        # Fix incomplete tool call pairs in base_messages before adding new messages
                        base_messages = fix_incomplete_tool_calls(base_messages)
                        
                        # #region agent log
                        try:
                            with open(log_path, "a", encoding="utf-8") as f:
                                f.write(json.dumps({
                                    "sessionId": "debug-session",
                                    "runId": "pre-fix",
                                    "hypothesisId": "H5",
                                    "location": "endpoints.py:initiate_chat(is_new_thread_validation)",
                                    "message": "Validating base_messages for new thread before adding new HumanMessage",
                                    "data": {
                                        "baseMessageCount": len(base_messages),
                                        "lastMessageType": type(base_messages[-1]).__name__ if base_messages else None
                                    },
                                    "timestamp": int(__import__("time").time() * 1000)
                                }) + "\n")
                        except Exception:
                            pass
                        # #endregion agent log
                        
                        initial_state = {
                            "messages": base_messages
                            + [
                                SystemMessage(content=system_message),
                                HumanMessage(
                                    content=(
                                        "The student has navigated to a new slide.\n"
                                        f"- Current page: {request.page_number}\n"
                                        f"- Page summary: {summary}\n\n"
                                        "Continue the conversation naturally auf Deutsch, knüpfe locker an das "
                                        "bisher Gesagte an und erkläre die neue Folie im Kontext der bisherigen Themen."
                                    )
                                ),
                            ],
                            "current_page": request.page_number,
                            "material_id": request.material_id,
                            "user_id": request.user_id,
                        }
                    else:
                        # Existing thread in this backend process: load existing messages from snapshot
                        existing_messages = snapshot.values.get("messages", [])
                        
                        # Fix incomplete tool call pairs to prevent Gemini API errors
                        # Gemini requires: AIMessage with tool_calls -> ToolMessages -> (optional) AIMessage -> HumanMessage
                        existing_messages = fix_incomplete_tool_calls(existing_messages)

                        # For simple page changes within an ongoing conversation, we use a lighter hint
                        page_change_human = HumanMessage(
                            content=(
                                "The student has navigated to a new slide.\n"
                                f"- Current page: {request.page_number}\n"
                                f"- Page summary: {summary}\n\n"
                                "Continue the ongoing conversation natürlich auf Deutsch, knüpfe locker an das "
                                "bisher Gesagte an und erkläre die neue Folie im Kontext der bisherigen Themen."
                            )
                        )

                        # Validate that adding HumanMessage won't break message ordering
                        # If last message is AIMessage with tool_calls, we need ToolMessages first
                        validated_messages = fix_incomplete_tool_calls(existing_messages)
                        
                        # #region agent log
                        import json
                        log_path = r"c:\App\AAI\AgenticAI_Group03\.cursor\debug.log"
                        try:
                            with open(log_path, "a", encoding="utf-8") as f:
                                f.write(json.dumps({
                                    "sessionId": "debug-session",
                                    "runId": "pre-fix",
                                    "hypothesisId": "H4",
                                    "location": "endpoints.py:initiate_chat(existing_thread_validation)",
                                    "message": "Validating existing messages before adding new HumanMessage",
                                    "data": {
                                        "originalCount": len(existing_messages),
                                        "validatedCount": len(validated_messages),
                                        "lastMessageType": type(validated_messages[-1]).__name__ if validated_messages else None
                                    },
                                    "timestamp": int(__import__("time").time() * 1000)
                                }) + "\n")
                        except Exception:
                            pass
                        # #endregion agent log
                        
                        initial_state = {
                            "messages": validated_messages
                            + [
                                SystemMessage(content=system_message),
                                page_change_human,
                            ],
                            "current_page": request.page_number,
                            "material_id": request.material_id,
                            "user_id": request.user_id,
                        }
                
                # Prepare buffer for assistant response text for persistence
                assistant_response_chunks: list[str] = []
                last_sent_content = ""  # Track what we've already sent for incremental updates
                
                # Stream agent response with incremental content updates
                logger.info(f"Starting agent stream for page {request.page_number}")
                try:
                    async for chunk in agent.graph.astream(initial_state, config):
                        chunk_data = {}
                        for node_name, node_data in chunk.items():
                            if "messages" in node_data:
                                messages = []
                                for msg in node_data["messages"]:
                                    # Extract tool responses (ToolMessage contains tool results)
                                    if isinstance(msg, ToolMessage):
                                        tool_call_id = getattr(msg, "tool_call_id", None) or getattr(msg, "name", None) or ""
                                        tool_content = getattr(msg, "content", "")
                                        
                                        if tool_call_id and tool_content:
                                            # Send tool response event
                                            tool_response_event = {
                                                "type": "tool_response",
                                                "tool_call_id": tool_call_id,
                                                "result": tool_content,
                                                "message_id": f"msg-{len(assistant_response_chunks)}"
                                            }
                                            yield f"data: {json.dumps(tool_response_event)}\n\n"
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
                                                        "message_id": f"msg-{len(assistant_response_chunks)}"
                                                    }
                                                    yield f"data: {json.dumps(tool_event)}\n\n"

                                        # Handle assistant messages with incremental streaming
                                        if role == "assistant" and msg.content:
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
                                        else:
                                            # Non-assistant messages: send normally
                                            messages.append({
                                                "role": role,
                                                "content": msg.content,
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
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    logger.error(f"Error in agent stream: {str(e)}", exc_info=True)
                    
                    # Trace als Error markieren
                    if trace:
                        logger.warning(f"🟡 Langfuse: Updating trace 'tutor-agent-initiate' with ERROR status: {str(e)}")
                        trace.update(level="ERROR", status_message=str(e))
                        logger.warning("🔴 Langfuse: Trace 'tutor-agent-initiate' marked as ERROR")
                    
                    error_data = {"error": str(e)}
                    yield f"data: {json.dumps(error_data)}\n\n"
                    yield "data: [DONE]\n\n"
                
                finally:
                    # Cleanup Langfuse tracing
                    # WICHTIG: Kein flush() hier! Das blockiert den Stream-Exit.
                    exc_info = sys.exc_info()  # Holt die aktuelle Exception, falls vorhanden
                    
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
                
                # Add user message to existing thread and preserve state
                initial_state = {
                    "messages": [HumanMessage(content=request.message)],
                    "material_id": material_id,
                    "user_id": user_id
                }
                
                # Only add current_page if it exists in previous state or metadata
                if current_page is not None:
                    initial_state["current_page"] = current_page

                # Prepare buffer for assistant response text for persistence
                assistant_response_chunks: list[str] = []
                last_sent_content = ""  # Track what we've already sent for incremental updates

                # Stream agent response with incremental content updates
                async for chunk in agent.graph.astream(initial_state, config):
                    chunk_data = {}
                    for node_name, node_data in chunk.items():
                        if "messages" in node_data:
                            messages = []
                            for msg in node_data["messages"]:
                                # Extract tool responses (ToolMessage contains tool results)
                                if isinstance(msg, ToolMessage):
                                    tool_call_id = getattr(msg, "tool_call_id", None) or getattr(msg, "name", None) or ""
                                    tool_content = getattr(msg, "content", "")
                                    
                                    if tool_call_id and tool_content:
                                        # Send tool response event
                                        tool_response_event = {
                                            "type": "tool_response",
                                            "tool_call_id": tool_call_id,
                                            "result": tool_content,
                                            "message_id": f"msg-{len(assistant_response_chunks)}"
                                        }
                                        yield f"data: {json.dumps(tool_response_event)}\n\n"
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
                                                    "message_id": f"msg-{len(assistant_response_chunks)}"
                                                }
                                                yield f"data: {json.dumps(tool_event)}\n\n"

                                    # Handle assistant messages with incremental streaming
                                    if role == "assistant" and msg.content:
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
                                    else:
                                        # Non-assistant messages: send normally
                                        messages.append({
                                            "role": role,
                                            "content": msg.content
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
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Error in agent stream: {str(e)}", exc_info=True)
                
                # Trace als Error markieren
                if trace:
                    logger.warning(f"🟡 Langfuse: Updating trace 'tutor-agent-message' with ERROR status: {str(e)}")
                    trace.update(level="ERROR", status_message=str(e))
                    logger.warning("🔴 Langfuse: Trace 'tutor-agent-message' marked as ERROR")
                
                error_data = {"error": str(e)}
                yield f"data: {json.dumps(error_data)}\n\n"
                yield "data: [DONE]\n\n"
                
            finally:
                # Cleanup - KEIN FLUSH
                exc_info = sys.exc_info()
                
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
    user_id: str = Query(..., description="User ID (UUID)")
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
        
    Returns:
        FlashcardTaskResponse with task_id and status
        
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
        
        client = get_supabase_client()
        
        # Get course material and validate ownership
        material_response = (
            client.table("course_materials")
            .select("id, course_id, user_id")
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
        
        # Create background task
        task_service = get_flashcard_task_service()
        task_id = await task_service.create_task(
            course_material_id=course_material_id,
            user_id=user_id,
            course_id=course_id,
        )
        
        logger.info(f"Created flashcard generation task {task_id} for material {course_material_id}")
        
        return FlashcardTaskResponse(
            task_id=task_id,
            status="pending",
            message="Flashcard generation started. Use the task_id to check progress."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating flashcard generation task: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start flashcard generation: {str(e)}",
        )


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
        
        if not task.csv_bytes or not task.filename:
            raise HTTPException(
                status_code=500,
                detail="Task completed but CSV file is missing",
            )
        
        # Return CSV file
        return StreamingResponse(
            io.BytesIO(task.csv_bytes),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{task.filename}"',
                "Content-Type": "text/csv; charset=utf-8"
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
