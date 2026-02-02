"""
PDF Background Processing Service

Handles asynchronous background processing of PDF files with parallel page analysis.
"""

import asyncio
import logging
from typing import List

from pdf2image import convert_from_bytes
from PIL import Image

from app.core.config import settings
from app.services.analyzer import analyze_pdf_page, generate_material_summary, generate_material_filename, detect_naming_pattern, image_bytes_to_base64
from app.services.storage import (
    update_processing_status,
    save_page_analysis,
    get_all_page_analyses_for_material,
    update_course_material_summary,
    update_course_material_filename,
    get_page_analysis,
    get_course_materials_for_naming,
    get_course_material_filename,
)
from app.services.embedding_service import (
    generate_embeddings_for_material_async,
    check_embedding_availability,
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


def extract_page_image(pdf_bytes: bytes, page_number: int) -> str:
    """
    Extract a specific page from a PDF as a base64 encoded image string.
    
    Args:
        pdf_bytes: Raw PDF file bytes
        page_number: Page number to extract (1-indexed)
        
    Returns:
        Base64 data URI string of the page image
        
    Raises:
        ValueError: If page extraction fails
    """
    try:
        # Convert specific page to image
        # first_page and last_page are 1-indexed
        images = convert_from_bytes(
            pdf_bytes,
            first_page=page_number,
            last_page=page_number,
            dpi=settings.PDF_PROCESSING_DPI,
            fmt='jpeg'
        )
        
        if not images:
            raise ValueError(f"Page {page_number} not found in PDF")
            
        # Get the single image
        image = images[0]
        
        # Convert to bytes
        image_bytes = pil_image_to_bytes(image)
        
        # Convert to base64 data URI
        return image_bytes_to_base64(image_bytes)
        
    except Exception as e:
        raise ValueError(f"Failed to extract page {page_number}: {str(e)}")


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
            
            # Analyze page (async) with Langfuse tracking parameters
            analysis = await analyze_pdf_page(
                image_bytes,
                api_key=None,  # Uses settings if None
                material_id=material_id,
                user_id=user_id,
                page_number=page_number
            )
            
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
    course_id: str,
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
                dpi=settings.PDF_PROCESSING_DPI,
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
        
        # Process pages in parallel, handling completions as they arrive
        logger.info(f"Processing {page_count} pages with max {max_concurrent} concurrent requests")
        
        # Track results and filename generation status
        results = {}  # page_number -> (success, error_message)
        pages_analyzed = 0
        errors = []
        filename_generated = False  # Flag to track if filename has been generated
        
        # Process pages as they complete (not waiting for all to finish)
        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                # process_single_page always returns a tuple (page_number, success, error_msg)
                page_num, success, error_msg = result
                results[page_num] = (success, error_msg)
                
                if success:
                    pages_analyzed += 1
                    
                    # Generate filename immediately when page 1 completes
                    if page_num == 1 and not filename_generated:
                        filename_generated = True
                        try:
                            logger.info(f"Page 1 analyzed, generating filename immediately for material {material_id}")
                            
                            # Get page 1 analysis
                            page_one_analysis = get_page_analysis(
                                course_material_id=material_id,
                                page_number=1,
                                user_id=user_id
                            )
                            
                            if page_one_analysis and page_one_analysis.get("summary"):
                                page_one_summary = page_one_analysis.get("summary")
                                
                                # Get existing materials to detect pattern
                                existing_materials = get_course_materials_for_naming(
                                    course_id=course_id,
                                    user_id=user_id,
                                    exclude_material_id=material_id
                                )
                                existing_filenames = [m.get("file_name", "") for m in existing_materials if m.get("file_name")]
                                
                                # Detect pattern
                                naming_pattern = detect_naming_pattern(existing_filenames)
                                
                                # Generate filename
                                new_filename = await generate_material_filename(
                                    page_one_summary=page_one_summary,
                                    api_key=None,
                                    material_id=material_id,
                                    user_id=user_id,
                                    course_id=course_id,
                                    existing_pattern=naming_pattern
                                )
                                
                                # Update filename immediately
                                update_course_material_filename(material_id, new_filename)
                                logger.info(f"Immediate filename generation: Updated material {material_id} to: {new_filename}")
                            else:
                                logger.warning(f"Page 1 analysis missing summary for material {material_id}, will retry at end")
                                filename_generated = False  # Allow fallback to retry
                        except Exception as filename_error:
                            logger.warning(f"Immediate filename generation failed: {filename_error}", exc_info=True)
                            filename_generated = False  # Allow fallback to retry
                else:
                    errors.append(error_msg)
            except Exception as e:
                # Handle exceptions from as_completed iteration (shouldn't happen, but safety check)
                error_msg = f"Error processing page result: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg, exc_info=True)
        
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
                    summary_json = await generate_material_summary(
                        page_data,
                        api_key=None,  # Uses settings if None
                        material_id=material_id,
                        user_id=user_id
                    )
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
            
            # Classify material if at least one page succeeded.
            # This is best-effort only: failures here must not overwrite the main status.
            try:
                logger.info(
                    f"Classifying material {material_id} based on {pages_analyzed} analyzed pages"
                )
                from app.services.classifier import classify_material
                from app.services.storage import update_material_classification
                
                classification_result = await classify_material(
                    material_id=material_id,
                    user_id=user_id,
                    course_id=course_id
                )
                
                # Store classification in database
                update_material_classification(
                    material_id=material_id,
                    classification=classification_result["category"],
                    confidence=classification_result["confidence"],
                    reasoning=classification_result["reasoning"],
                    override=False
                )
                logger.info(
                    f"Successfully classified material {material_id} as: {classification_result['category']} "
                    f"(confidence: {classification_result['confidence']})"
                )
            except Exception as classification_error:
                logger.error(
                    f"Failed to classify material {material_id}: {classification_error}",
                    exc_info=True,
                )
                # Don't fail the whole process if classification fails
                # Material will be classified later when flashcards are generated (fallback)

        # Update final status in course_materials
        update_processing_status(material_id, status, error_message)
        logger.info(f"Background processing completed for material {material_id}: {status}")
        
        # Generate and update filename based on page 1 summary if processing completed successfully
        # Only run if filename wasn't already generated immediately after page 1 (fallback)
        if status == "completed" and pages_analyzed > 0 and not filename_generated:
            try:
                # Check if filename was already generated (doesn't match original upload filename pattern)
                current_filename = get_course_material_filename(material_id, user_id)
                # If filename looks like it was already generated (doesn't contain .pdf or looks professional), skip
                if current_filename and not current_filename.endswith('.pdf') and not current_filename.startswith('uploaded'):
                    logger.info(f"Filename already generated for material {material_id}: {current_filename}, skipping fallback")
                else:
                    logger.info(
                        f"Generating professional filename for material {material_id} "
                        f"based on page 1 summary (fallback)"
                    )
                    # Get page 1 analysis
                    page_one_analysis = get_page_analysis(
                        course_material_id=material_id,
                        page_number=1,
                        user_id=user_id
                    )
                    
                    if page_one_analysis and page_one_analysis.get("summary"):
                        page_one_summary = page_one_analysis.get("summary")
                        
                        # Get existing materials to detect pattern
                        existing_materials = get_course_materials_for_naming(
                            course_id=course_id,
                            user_id=user_id,
                            exclude_material_id=material_id
                        )
                        existing_filenames = [m.get("file_name", "") for m in existing_materials if m.get("file_name")]
                        
                        # Detect pattern
                        naming_pattern = detect_naming_pattern(existing_filenames)
                        
                        # Generate professional filename
                        new_filename = await generate_material_filename(
                            page_one_summary=page_one_summary,
                            api_key=None,  # Uses settings if None
                            material_id=material_id,
                            user_id=user_id,
                            course_id=course_id,
                            existing_pattern=naming_pattern
                        )
                        # Update filename in database
                        update_course_material_filename(material_id, new_filename)
                        logger.info(f"Successfully updated filename for material {material_id} to: {new_filename}")
                    else:
                        logger.warning(
                            f"No page 1 summary found for material {material_id} when generating filename"
                        )
            except Exception as filename_error:
                logger.error(
                    f"Failed to generate or update filename for {material_id}: "
                    f"{filename_error}",
                    exc_info=True,
                )
                # Don't fail the whole process if filename generation fails
        
        # Generate embeddings in the background (for semantic search)
        # This runs after all other processing is complete, so it doesn't block the user
        if status == "completed" and pages_analyzed > 0:
            if check_embedding_availability():
                try:
                    logger.info(f"Starting background embedding generation for material {material_id}")
                    # Run embedding generation asynchronously - don't await to not block
                    asyncio.create_task(
                        _generate_embeddings_background(material_id)
                    )
                except Exception as embed_error:
                    # Log but don't fail - embeddings are optional enhancement
                    logger.warning(
                        f"Failed to start embedding generation for {material_id}: {embed_error}"
                    )
            else:
                logger.debug(
                    f"Skipping embedding generation for {material_id}: OpenAI API key not configured"
                )
        
    except Exception as e:
        # Unexpected error during processing
        error_msg = f"Unexpected error during background processing: {str(e)}"
        logger.error(error_msg, exc_info=True)
        try:
            update_processing_status(material_id, "error", error_msg)
        except Exception as update_error:
            logger.error(f"Failed to update error status: {str(update_error)}", exc_info=True)


async def _generate_embeddings_background(material_id: str) -> None:
    """
    Background task to generate embeddings for a material.
    
    This runs after PDF processing completes and doesn't block the user.
    Embeddings enable semantic search in QuickChat.
    
    Args:
        material_id: Course material ID
    """
    try:
        pages_processed = await generate_embeddings_for_material_async(material_id)
        logger.info(
            f"Background embedding generation completed for material {material_id}: "
            f"{pages_processed} pages embedded"
        )
    except Exception as e:
        # Log error but don't propagate - this is a background enhancement
        logger.error(
            f"Background embedding generation failed for material {material_id}: {e}",
            exc_info=True
        )
