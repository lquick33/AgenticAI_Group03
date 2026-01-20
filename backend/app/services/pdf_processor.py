"""
PDF Background Processing Service

Handles asynchronous background processing of PDF files with parallel page analysis.
"""

import asyncio
import logging
from typing import List

from pdf2image import convert_from_bytes
from PIL import Image

from app.services.analyzer import analyze_pdf_page, generate_material_summary
from app.services.storage import (
    update_processing_status,
    save_page_analysis,
    get_all_page_analyses_for_material,
    update_course_material_summary,
)

logger = logging.getLogger(__name__)


def pil_image_to_bytes(image: Image.Image, format: str = "JPEG") -> bytes:
    """
    Convert PIL Image to bytes.
    
    Args:
        image: PIL Image object
        format: Image format (default: JPEG)
        
    Returns:
        Image bytes
    """
    import io
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return buffer.getvalue()


async def process_single_page(
    semaphore: asyncio.Semaphore,
    material_id: str,
    page_number: int,
    image: Image.Image,
    user_id: str
) -> tuple[int, bool, str]:
    """
    Process a single PDF page asynchronously.
    
    Args:
        semaphore: Semaphore to limit concurrent requests
        material_id: Course material ID
        page_number: Page number (1-indexed)
        image: PIL Image object
        user_id: User ID
        
    Returns:
        Tuple of (page_number, success, error_message)
    """
    async with semaphore:
        try:
            logger.info(f"Processing page {page_number} for material {material_id}")
            
            # Convert PIL Image to bytes
            image_bytes = pil_image_to_bytes(image)
            
            # Analyze page (async)
            analysis = await analyze_pdf_page(image_bytes)
            
            # Save to database
            save_page_analysis(
                course_material_id=material_id,
                page_number=page_number,
                analysis=analysis,
                user_id=user_id
            )
            
            logger.info(f"Successfully processed page {page_number}")
            return (page_number, True, "")
            
        except Exception as e:
            error_msg = f"Failed to process page {page_number}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (page_number, False, error_msg)


async def process_pdf_background(
    material_id: str,
    file_bytes: bytes,
    user_id: str,
    max_concurrent: int = 5
) -> None:
    """
    Process PDF in background with parallel page analysis.
    
    This function:
    1. Sets status to 'processing'
    2. Converts PDF to images
    3. Processes pages in parallel (max_concurrent at a time)
    4. Updates status to 'completed' or 'error'
    
    Args:
        material_id: Course material ID
        file_bytes: PDF file bytes
        user_id: User ID
        max_concurrent: Maximum number of concurrent page analyses (default: 5)
    """
    try:
        # Set status to processing
        logger.info(f"Starting background processing for material {material_id}")
        update_processing_status(material_id, "processing")
        
        # Convert PDF to images
        logger.info(f"Converting PDF to images for material {material_id}")
        try:
            images = convert_from_bytes(
                file_bytes,
                dpi=300,
                fmt='jpeg'
            )
            page_count = len(images)
            logger.info(f"Converted {page_count} pages to images")
        except Exception as e:
            error_msg = f"Failed to convert PDF to images: {str(e)}"
            logger.error(error_msg, exc_info=True)
            update_processing_status(material_id, "error", error_msg)
            return
        
        if page_count == 0:
            error_msg = "PDF contains no pages"
            logger.error(error_msg)
            update_processing_status(material_id, "error", error_msg)
            return
        
        # Create semaphore to limit concurrent requests (rate limit protection)
        semaphore = asyncio.Semaphore(max_concurrent)
        
        # Create tasks for all pages
        tasks = [
            process_single_page(
                semaphore=semaphore,
                material_id=material_id,
                page_number=page_num,
                image=image,
                user_id=user_id
            )
            for page_num, image in enumerate(images, start=1)
        ]
        
        # Process all pages in parallel (with semaphore limiting concurrency)
        logger.info(f"Processing {page_count} pages with max {max_concurrent} concurrent requests")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        pages_analyzed = 0
        errors = []
        
        for result in results:
            if isinstance(result, Exception):
                # Task raised an exception
                error_msg = f"Task exception: {str(result)}"
                errors.append(error_msg)
                logger.error(error_msg, exc_info=True)
            else:
                page_num, success, error_msg = result
                if success:
                    pages_analyzed += 1
                else:
                    errors.append(error_msg)
        
        # Update final status
        if pages_analyzed == page_count:
            status = "completed"
            error_message = None
            logger.info(f"Successfully processed all {page_count} pages")
        elif pages_analyzed > 0:
            status = "completed"  # Partially completed
            error_message = f"Some pages failed: {len(errors)}/{page_count} pages had errors"
            logger.warning(f"Partially completed: {pages_analyzed}/{page_count} pages processed")
        else:
            status = "error"
            error_message = f"All pages failed: {', '.join(errors[:5])}"  # Limit error message length
            logger.error(f"All pages failed for material {material_id}")

        # Try to generate a global material summary if at least one page succeeded.
        # This is best-effort only: failures here must not overwrite the main status.
        if pages_analyzed > 0:
            try:
                logger.info(
                    f"Generating global material summary for material {material_id} "
                    f"based on {pages_analyzed} analyzed pages"
                )
                page_data = get_all_page_analyses_for_material(
                    course_material_id=material_id,
                    user_id=user_id,
                )
                if page_data:
                    summary_json = await generate_material_summary(page_data)
                    update_course_material_summary(material_id, summary_json)
                    logger.info(f"Successfully stored global summary for material {material_id}")
                else:
                    logger.warning(
                        f"No page_analyses found for material {material_id} when generating global summary"
                    )
            except Exception as summary_error:
                logger.error(
                    f"Failed to generate or store global material summary for {material_id}: "
                    f"{summary_error}",
                    exc_info=True,
                )

        # Update final status in course_materials
        update_processing_status(material_id, status, error_message)
        logger.info(f"Background processing completed for material {material_id}: {status}")
        
    except Exception as e:
        # Unexpected error during processing
        error_msg = f"Unexpected error during background processing: {str(e)}"
        logger.error(error_msg, exc_info=True)
        try:
            update_processing_status(material_id, "error", error_msg)
        except Exception as update_error:
            logger.error(f"Failed to update error status: {str(update_error)}", exc_info=True)
