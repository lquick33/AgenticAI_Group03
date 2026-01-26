"""
Service for managing slide snippets (user-created image crops).
"""

import time
import logging
from typing import List, Optional

from app.services.storage import get_supabase_client
from app.core.config import settings

logger = logging.getLogger(__name__)

def create_snippet(
    file_bytes: bytes,
    course_material_id: str,
    page_number: int,
    user_id: str
) -> dict:
    """
    Create a new slide snippet.
    
    1. Uploads image to Supabase Storage.
    2. Inserts record into slide_snippets table.
    
    Args:
        file_bytes: Image file bytes
        course_material_id: Course material ID
        page_number: Page number (1-indexed)
        user_id: User ID
        
    Returns:
        Created snippet record
    """
    client = get_supabase_client()
    
    # Check if a snippet already exists for this page to cleanup old image
    try:
        existing = client.table("slide_snippets").select("image_path").eq(
            "course_material_id", course_material_id
        ).eq(
            "page_number", page_number
        ).eq(
            "user_id", user_id
        ).execute()
        
        if existing.data and len(existing.data) > 0:
            old_image_path = existing.data[0]["image_path"]
            logger.info(f"Deleting old snippet image: {old_image_path}")
            try:
                client.storage.from_("course_materials").remove([old_image_path])
            except Exception as e:
                logger.warning(f"Failed to delete old snippet image: {e}")
    except Exception as e:
        logger.warning(f"Failed to check for existing snippets: {e}")
    
    # 1. Upload to Storage
    # Use course_materials bucket with clear path structure
    # Path: {user_id}/snippets/{course_material_id}/{filename}
    timestamp = int(time.time() * 1000)
    filename = f"page_{page_number}_{timestamp}.png"
    storage_path = f"{user_id}/snippets/{course_material_id}/{filename}"
    
    bucket_name = "course_materials"
    try:
        client.storage.from_(bucket_name).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": "image/png", "upsert": "true"}
        )
        logger.info(f"✅ Uploaded snippet to {bucket_name}/{storage_path}")
    except Exception as e:
        logger.error(f"Storage upload failed: {str(e)}")
        raise Exception(f"Failed to upload snippet image: {str(e)}")
        
    # 2. Insert or update into DB (using upsert)
    try:
        # Use upsert - Supabase will automatically handle the unique constraint
        # on (course_material_id, page_number, user_id)
        data = {
            "course_material_id": course_material_id,
            "user_id": user_id,
            "page_number": page_number,
            "image_path": storage_path
        }
        
        # Upsert without explicit on_conflict - let Supabase use the unique constraint
        response = client.table("slide_snippets").upsert(data).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        else:
            logger.error(f"DB upsert returned no data. Response: {response}")
            raise Exception("Failed to save snippet record (no data returned)")
            
    except Exception as e:
        logger.error(f"DB upsert failed: {str(e)}", exc_info=True)
        # Try to cleanup storage if DB insert fails
        try:
            client.storage.from_("course_materials").remove([storage_path])
        except:
            pass
        raise Exception(f"Failed to save snippet metadata: {str(e)}")


def get_snippets_for_material(
    course_material_id: str,
    user_id: str
) -> List[dict]:
    """
    Get all snippets for a course material.
    
    Args:
        course_material_id: Course material ID
        user_id: User ID
        
    Returns:
        List of snippet records
    """
    client = get_supabase_client()
    
    try:
        response = client.table("slide_snippets").select("*").eq(
            "course_material_id", course_material_id
        ).eq(
            "user_id", user_id
        ).order("page_number").execute()
        
        return response.data or []
    except Exception as e:
        raise Exception(f"Failed to fetch snippets: {str(e)}")


def get_snippet_public_url(image_path: str) -> str:
    """
    Get accessible URL for a snippet image.
    
    Creates a signed URL from the course_materials bucket.
    Note: For APKG generation, we download images directly instead of using URLs.
    
    Args:
        image_path: Storage path (format: {user_id}/snippets/{material_id}/{filename})
        
    Returns:
        Signed URL string
        
    Raises:
        Exception: If URL generation fails
    """
    logger.info(f"🔍 get_snippet_public_url called with image_path: {image_path}")
    client = get_supabase_client()
    
    bucket_name = "course_materials"
    try:
        # Create signed URL valid for 10 years (for backwards compatibility with any CSV exports)
        response = client.storage.from_(bucket_name).create_signed_url(image_path, 315360000)
        
        # Supabase storage-py returns a dict with 'signedURL' key
        if isinstance(response, dict) and "signedURL" in response:
            url = response["signedURL"]
            logger.info(f"✅ Created signed URL for {image_path[:50]}...")
            return url
        else:
            logger.error(f"❌ Unexpected response format from create_signed_url: {response}")
            raise Exception(f"Unexpected response format: {response}")
    except Exception as e:
        logger.error(f"❌ Error creating signed URL: {e}", exc_info=True)
        raise


def download_snippet_image(image_path: str) -> bytes:
    """
    Download snippet image bytes from Supabase Storage.
    
    This is used for embedding images directly in .apkg files instead of using URLs.
    
    Args:
        image_path: Storage path of the image (format: {user_id}/snippets/{material_id}/{filename})
        
    Returns:
        Image bytes
        
    Raises:
        Exception: If download fails
    """
    logger.info(f"🔍 download_snippet_image called with image_path: {image_path}")
    client = get_supabase_client()
    
    bucket_name = "course_materials"
    try:
        image_bytes = client.storage.from_(bucket_name).download(image_path)
        logger.info(f"✅ Downloaded image from {bucket_name} ({len(image_bytes)} bytes)")
        return image_bytes
    except Exception as e:
        logger.error(f"❌ Failed to download snippet image: {e}")
        raise Exception(f"Failed to download snippet image: {str(e)}")


def delete_snippet(
    snippet_id: str,
    user_id: str
) -> None:
    """
    Delete a snippet.
    
    Args:
        snippet_id: Snippet ID
        user_id: User ID (for authorization)
    """
    client = get_supabase_client()
    
    try:
        # Get image path first
        response = client.table("slide_snippets").select("image_path").eq(
            "id", snippet_id
        ).eq(
            "user_id", user_id
        ).single().execute()
        
        if not response.data:
            raise ValueError("Snippet not found or access denied")
            
        image_path = response.data["image_path"]
        
        # Delete from DB
        client.table("slide_snippets").delete().eq(
            "id", snippet_id
        ).eq(
            "user_id", user_id
        ).execute()
        
        # Delete from Storage
        try:
            client.storage.from_("course_materials").remove([image_path])
            logger.info(f"✅ Deleted snippet image: {image_path}")
        except Exception as e:
            logger.warning(f"Failed to delete snippet image from storage: {e}")
        
    except Exception as e:
        raise Exception(f"Failed to delete snippet: {str(e)}")
