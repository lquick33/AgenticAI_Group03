"""
API Endpoints

FastAPI route handlers for PDF upload and processing.
"""

import io
import json
import logging
import traceback
from typing import Optional, AsyncGenerator
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.agents.tutor import TutorAgent
from app.services.analyzer import get_gemini_model

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Form, BackgroundTasks, Path, Body
from fastapi.responses import StreamingResponse
from pdf2image import convert_from_bytes
from PIL import Image

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
    get_page_analysis
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
        
        # Get course material to find course_material_id
        client = get_supabase_client()
        material_response = client.table("course_materials").select(
            "id, course_id"
        ).eq("id", request.material_id).eq("user_id", request.user_id).single().execute()
        
        if not material_response.data:
            raise HTTPException(
                status_code=404,
                detail="Course material not found or access denied"
            )
        
        course_material_id = material_response.data["id"]
        
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
        agent = TutorAgent(
            llm=llm,
            checkpointer=_checkpointer
        )
        
        # Thread ID: material_id for continuous conversation
        thread_id = request.material_id
        
        # Create system message for page change
        system_message = (
            f"SYSTEM EVENT: User navigated to Page {request.page_number}. "
            f"Summary of Page {request.page_number}: {summary}. "
            f"Please greet the user and explain the content of the slide."
        )
        
        # Create initial message
        initial_message = f"Please help me understand this slide (Page {request.page_number})."
        
        # Stream response
        async def event_generator() -> AsyncGenerator[str, None]:
            # First, inject system message and initial message
            config = {"configurable": {"thread_id": thread_id, "user_id": request.user_id}}
            
            # Check if thread exists
            snapshot = agent.graph.get_state(config)
            is_new_thread = snapshot is None or not snapshot.values or not snapshot.values.get("messages")
            
            # Update state with current page information (according to AGENT_DEVELOPMENT_RULES.md)
            # The agent should always know which page we are currently viewing
            if is_new_thread:
                # New thread: add system message and page change message
                initial_state = {
                    "messages": [
                        SystemMessage(content=system_message),
                        HumanMessage(content=initial_message)
                    ],
                    "current_page": request.page_number,
                    "material_id": request.material_id,
                    "user_id": request.user_id
                }
            else:
                # Existing thread: add page change message and update state
                initial_state = {
                    "messages": [
                        SystemMessage(content=system_message),
                        HumanMessage(content=initial_message)
                    ],
                    "current_page": request.page_number,
                    "material_id": request.material_id,
                    "user_id": request.user_id
                }
            
            # Stream agent response
            logger.info(f"Starting agent stream for page {request.page_number}")
            try:
                async for chunk in agent.graph.astream(initial_state, config):
                    chunk_data = {}
                    for node_name, node_data in chunk.items():
                        if "messages" in node_data:
                            messages = []
                            for msg in node_data["messages"]:
                                if hasattr(msg, "content"):
                                    role = "assistant"
                                    if isinstance(msg, SystemMessage):
                                        role = "system"
                                    elif isinstance(msg, HumanMessage):
                                        role = "user"
                                    
                                    messages.append({
                                        "role": role,
                                        "content": msg.content
                                    })
                            if messages:  # Only add if there are messages
                                chunk_data[node_name] = {"messages": messages}
                    
                    if chunk_data:  # Only yield if there's data
                        logger.debug(f"Yielding chunk: {chunk_data}")
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                
                logger.info(f"Agent stream completed for page {request.page_number}")
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
        agent = TutorAgent(
            llm=llm,
            checkpointer=_checkpointer
        )
        
        # Thread ID: material_id for continuous conversation
        thread_id = request.material_id
        
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
            
            # Add user message to existing thread and preserve state
            initial_state = {
                "messages": [HumanMessage(content=request.message)],
                "material_id": material_id,
                "user_id": user_id
            }
            
            # Only add current_page if it exists in previous state
            if current_page is not None:
                initial_state["current_page"] = current_page
            
            # Stream agent response
            async for chunk in agent.graph.astream(initial_state, config):
                chunk_data = {}
                for node_name, node_data in chunk.items():
                    if "messages" in node_data:
                        messages = []
                        for msg in node_data["messages"]:
                            if hasattr(msg, "content"):
                                role = "assistant"
                                if isinstance(msg, SystemMessage):
                                    role = "system"
                                elif isinstance(msg, HumanMessage):
                                    role = "user"
                                
                                messages.append({
                                    "role": role,
                                    "content": msg.content
                                })
                        chunk_data[node_name] = {"messages": messages}
                
                yield f"data: {json.dumps(chunk_data)}\n\n"
            
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
