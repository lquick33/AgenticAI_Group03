"""
API Endpoints

FastAPI route handlers for PDF upload and processing.
"""

import io
import logging
import traceback
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Form, BackgroundTasks, Path
from pdf2image import convert_from_bytes
from PIL import Image

from app.models.schemas import UploadResponse, ErrorResponse, CourseResponse, CourseUpdateRequest
from app.services.pdf_processor import process_pdf_background
from app.services.storage import (
    upload_pdf_to_storage,
    create_course_material,
    validate_user_exists,
    get_course,
    get_supabase_client
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
