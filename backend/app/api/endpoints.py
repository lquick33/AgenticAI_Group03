"""
API Endpoints

FastAPI route handlers for PDF upload and processing.
"""

import io
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pdf2image import convert_from_bytes
from PIL import Image

from app.models.schemas import UploadResponse, ErrorResponse
from app.services.analyzer import analyze_pdf_page
from app.services.storage import (
    upload_pdf_to_storage,
    create_course_material,
    update_processing_status,
    save_page_analysis
)

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
    file: UploadFile = File(...),
    course_id: Optional[str] = Query(None, description="Course ID (optional)"),
    user_id: str = Query(..., description="User ID (required)")
) -> UploadResponse:
    """
    Upload and process a PDF file.
    
    This endpoint:
    1. Accepts a PDF file upload
    2. Converts PDF pages to images
    3. Analyzes each page using Gemini vision model
    4. Stores results in Supabase database
    
    Args:
        file: PDF file to upload
        course_id: Optional course ID (if None, will need to be created)
        user_id: User ID (required)
        
    Returns:
        UploadResponse with processing status and results
        
    Raises:
        HTTPException: If processing fails
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="File must be a PDF"
        )
    
    try:
        # Read file bytes
        file_bytes = await file.read()
        
        if len(file_bytes) == 0:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty"
            )
        
        # Convert PDF to images
        try:
            images = convert_from_bytes(
                file_bytes,
                dpi=300,
                fmt='jpeg'
            )
        except Exception as e:
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
        
        # Create course_material record (use placeholder course_id if not provided)
        if not course_id:
            # For now, we'll use a placeholder. In production, you'd create a course first
            course_id = "00000000-0000-0000-0000-000000000000"  # Placeholder
        
        try:
            material_record = create_course_material(
                course_id=course_id,
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
        
        # Update status to processing
        try:
            update_processing_status(material_id, "processing")
        except Exception as e:
            # Log error but continue
            print(f"Warning: Failed to update status: {str(e)}")
        
        # Process each page
        pages_analyzed = 0
        errors = []
        
        for page_num, image in enumerate(images, start=1):
            try:
                # Convert PIL Image to bytes
                image_bytes = pil_image_to_bytes(image)
                
                # Analyze page
                analysis = analyze_pdf_page(image_bytes)
                
                # Save to database
                save_page_analysis(
                    course_material_id=material_id,
                    page_number=page_num,
                    analysis=analysis,
                    user_id=user_id
                )
                
                pages_analyzed += 1
                
            except Exception as e:
                error_msg = f"Failed to process page {page_num}: {str(e)}"
                errors.append(error_msg)
                print(f"Error: {error_msg}")
                # Continue with next page
        
        # Update final status
        if pages_analyzed == page_count:
            status = "completed"
            error_message = None
        elif pages_analyzed > 0:
            status = "completed"  # Partially completed
            error_message = f"Some pages failed: {', '.join(errors)}"
        else:
            status = "error"
            error_message = f"All pages failed: {', '.join(errors)}"
        
        try:
            update_processing_status(material_id, status, error_message)
        except Exception as e:
            print(f"Warning: Failed to update final status: {str(e)}")
        
        # Return response
        return UploadResponse(
            message=f"PDF processed: {pages_analyzed}/{page_count} pages analyzed",
            course_material_id=material_id,
            page_count=page_count,
            pages_analyzed=pages_analyzed,
            status=status,
            error_message=error_message if errors else None
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error during PDF processing: {str(e)}"
        )
