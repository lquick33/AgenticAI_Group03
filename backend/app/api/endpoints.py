"""
API Endpoints

FastAPI route handlers for PDF upload and processing.
"""

import io
import json
import logging
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
    ChatMessageRequest
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
from app.services.session_storage import (
    get_or_create_study_conversation,
    update_conversation_progress,
    append_messages,
    load_conversation_with_messages,
)

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

                    initial_state = {
                        "messages": existing_messages
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
                                # Skip tool messages entirely for UI and persistence
                                if isinstance(msg, ToolMessage):
                                    continue

                                if hasattr(msg, "content"):
                                    role = "assistant"
                                    if isinstance(msg, SystemMessage):
                                        role = "system"
                                    elif isinstance(msg, HumanMessage):
                                        role = "user"
                                    elif isinstance(msg, AIMessage):
                                        role = "assistant"

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

                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Error in agent stream: {str(e)}", exc_info=True)
                error_data = {"error": str(e)}
                yield f"data: {json.dumps(error_data)}\n\n"
                yield "data: [DONE]\n\n"
        
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
                            # Skip tool messages entirely for UI and persistence
                            if isinstance(msg, ToolMessage):
                                continue

                            if hasattr(msg, "content"):
                                role = "assistant"
                                if isinstance(msg, SystemMessage):
                                    role = "system"
                                elif isinstance(msg, HumanMessage):
                                    role = "user"
                                elif isinstance(msg, AIMessage):
                                    role = "assistant"

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

            yield "data: [DONE]\n\n"
        
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
