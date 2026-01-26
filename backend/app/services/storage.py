"""
Supabase Storage and Database Service

Handles file uploads to Supabase Storage and database operations
for course materials and page analyses.
"""

import json
import logging
from typing import Optional, List

from supabase import create_client, Client

from app.core.config import settings
from app.models.schemas import SlideAnalysis

logger = logging.getLogger(__name__)


# Initialize Supabase client (singleton)
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Get or create Supabase client instance.
    
    Returns:
        Configured Supabase client
    """
    global _supabase_client
    
    if _supabase_client is None:
        # Simplified client creation - ClientOptions not needed for basic usage
        _supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )
    
    return _supabase_client


def upload_pdf_to_storage(
    file_bytes: bytes,
    filename: str,
    user_id: str,
    bucket_name: str = "course_materials"
) -> str:
    """
    Upload PDF file to Supabase Storage.
    
    Args:
        file_bytes: PDF file bytes
        filename: Original filename
        user_id: User ID for organizing files
        bucket_name: Storage bucket name (default: "course_materials")
        
    Returns:
        Storage path of uploaded file
        
    Raises:
        Exception: If upload fails
    """
    client = get_supabase_client()
    
    # Create storage path: user_id/filename
    storage_path = f"{user_id}/{filename}"
    
    try:
        # Upload file to storage
        response = client.storage.from_(bucket_name).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"}
        )
        
        # Return the storage path
        return storage_path
    
    except Exception as e:
        raise Exception(f"Failed to upload PDF to storage: {str(e)}")


def download_file_from_storage(
    path: str,
    bucket_name: str = "course_materials"
) -> bytes:
    """
    Download a file from Supabase Storage.
    
    Args:
        path: Storage path of the file
        bucket_name: Storage bucket name (default: "course_materials")
        
    Returns:
        File content as bytes
        
    Raises:
        Exception: If download fails
    """
    client = get_supabase_client()
    
    try:
        response = client.storage.from_(bucket_name).download(path)
        return response
    except Exception as e:
        raise Exception(f"Failed to download file from storage: {str(e)}")


def create_course_material(
    course_id: str,
    filename: str,
    file_path: str,
    user_id: str,
    page_count: int,
    file_type: str = "pdf"
) -> dict:
    """
    Create a course_material record in the database.
    
    Args:
        course_id: Course ID
        filename: Original filename
        file_path: Storage path
        user_id: User ID
        page_count: Number of pages
        file_type: File type (default: "pdf")
        
    Returns:
        Created course_material record as dict
    """
    client = get_supabase_client()
    
    try:
        response = client.table("course_materials").insert({
            "course_id": course_id,
            "user_id": user_id,
            "file_name": filename,
            "file_path": file_path,
            "file_type": file_type,
            "page_count": page_count,
            "processing_status": "uploading"
        }).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        else:
            raise Exception("Failed to create course_material record")
    
    except Exception as e:
        raise Exception(f"Failed to create course_material: {str(e)}")


def update_processing_status(
    material_id: str,
    status: str,
    error_message: Optional[str] = None
) -> None:
    """
    Update the processing status of a course material.
    
    Args:
        material_id: Course material ID
        status: New status ("uploading", "processing", "completed", "error")
        error_message: Optional error message if status is "error"
    """
    client = get_supabase_client()
    
    update_data = {"processing_status": status}
    if error_message:
        update_data["error_message"] = error_message
    
    try:
        client.table("course_materials").update(update_data).eq(
            "id", material_id
        ).execute()
    
    except Exception as e:
        raise Exception(f"Failed to update processing status: {str(e)}")


def validate_user_exists(user_id: str) -> bool:
    """
    Validate that user exists in profiles table.
    
    Note: Thanks to the SQL trigger, profiles are automatically synced
    with auth.users, so this check works reliably.
    
    Args:
        user_id: User ID to validate
        
    Returns:
        True if user exists, False otherwise
        
    Raises:
        Exception: If database query fails
    """
    client = get_supabase_client()
    
    try:
        response = client.table("profiles").select("id").eq(
            "id", user_id
        ).execute()
        
        return response.data and len(response.data) > 0
    except Exception as e:
        raise Exception(f"Failed to validate user: {str(e)}")


def get_course(
    user_id: str,
    course_id: str
) -> dict:
    """
    Get existing course and validate it belongs to user.
    
    Course must be created beforehand (e.g., via web app).
    This function only validates and retrieves existing courses.
    
    Args:
        user_id: User ID
        course_id: Course ID (required)
        
    Returns:
        Course record as dict
        
    Raises:
        ValueError: If course doesn't exist or doesn't belong to user
        Exception: If database operation fails
    """
    client = get_supabase_client()
    
    try:
        response = client.table("courses").select("*").eq(
            "id", course_id
        ).eq("user_id", user_id).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        else:
            raise ValueError(
                f"Course {course_id} not found or access denied"
            )
    except ValueError:
        raise
    except Exception as e:
        raise Exception(f"Failed to get course: {str(e)}")


def save_page_analysis(
    course_material_id: str,
    page_number: int,
    analysis: SlideAnalysis,
    user_id: str
) -> dict:
    """
    Save page analysis to the page_analyses table.
    
    Args:
        course_material_id: Course material ID
        page_number: Page number (1-indexed)
        analysis: SlideAnalysis object
        user_id: User ID
        
    Returns:
        Created page_analysis record as dict
    """
    client = get_supabase_client()
    
    # Convert analysis to dict for storage
    analysis_dict = analysis.model_dump()
    
    try:
        # Insert or update (handle unique constraint)
        response = client.table("page_analyses").upsert({
            "course_material_id": course_material_id,
            "user_id": user_id,
            "page_number": page_number,
            "summary": analysis_dict["summary"],
            "key_terms": analysis_dict["key_terms"],
            "exam_questions": analysis_dict["exam_questions"],
            "diagram_description": analysis_dict["diagram_description"],
            "raw_analysis": analysis_dict  # Store full JSON as JSONB
        }).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        else:
            raise Exception("Failed to save page_analysis")
    
    except Exception as e:
        raise Exception(f"Failed to save page analysis: {str(e)}")


def get_page_analysis(
    course_material_id: str,
    page_number: int,
    user_id: str
) -> dict:
    """
    Get page analysis data from the page_analyses table.
    
    Args:
        course_material_id: Course material ID
        page_number: Page number (1-indexed)
        user_id: User ID for authorization (RLS) - used for validation only
        
    Returns:
        Page analysis record as dict with summary, key_terms, exam_questions, diagram_description
        
    Raises:
        ValueError: If page analysis not found or access denied
        Exception: If database operation fails
    """
    client = get_supabase_client()
    
    try:
        # First, get the user_id from the course_material to ensure we use the correct one
        # This prevents issues where the state might have a stale user_id
        material_response = client.table("course_materials").select(
            "user_id"
        ).eq("id", course_material_id).single().execute()
        
        if not material_response.data:
            raise ValueError(
                f"Course material not found: {course_material_id}"
            )
        
        material_user_id = material_response.data["user_id"]
        
        # Validate that the requesting user_id matches the material's user_id
        # This ensures proper authorization
        if material_user_id != user_id:
            raise ValueError(
                f"Access denied: user_id {user_id} does not match course material owner {material_user_id}"
            )
        
        # Now query with the correct user_id from the material
        response = client.table("page_analyses").select(
            "id, summary, key_terms, exam_questions, diagram_description, raw_analysis"
        ).eq(
            "course_material_id", course_material_id
        ).eq(
            "page_number", page_number
        ).eq(
            "user_id", material_user_id
        ).execute()
        
        if response.data and len(response.data) > 0:
            analysis = response.data[0]
            return {
                "summary": analysis.get("summary", ""),
                "key_terms": analysis.get("key_terms", []),
                "exam_questions": analysis.get("exam_questions", []),
                "diagram_description": analysis.get("diagram_description"),
                "raw_analysis": analysis.get("raw_analysis", {})
            }
        else:
            raise ValueError(
                f"Page analysis not found for course_material_id={course_material_id}, page_number={page_number}"
            )
    except ValueError:
        raise
    except Exception as e:
        raise Exception(f"Failed to get page analysis: {str(e)}")


def get_page_analyses_for_range(
    course_material_id: str,
    user_id: str,
    start_page: int,
    end_page: int
) -> list[dict]:
    """
    Get page analyses for a specific page range.
    
    Args:
        course_material_id: Course material ID
        user_id: User ID for authorization (RLS)
        start_page: Starting page number (1-indexed, inclusive)
        end_page: Ending page number (1-indexed, inclusive)
        
    Returns:
        List of page analysis records as dicts, each with:
        - page_number: int
        - summary: str
        - key_terms: list[str]
        - exam_questions: list[str]
        - diagram_description: str
        - raw_analysis: dict (optional)
        
    Raises:
        ValueError: If course material not found or access denied
        Exception: If database operation fails
    """
    client = get_supabase_client()
    
    try:
        # Validate course material and user authorization
        material_response = client.table("course_materials").select(
            "user_id"
        ).eq("id", course_material_id).single().execute()
        
        if not material_response.data:
            raise ValueError(
                f"Course material not found: {course_material_id}"
            )
        
        material_user_id = material_response.data["user_id"]
        
        if material_user_id != user_id:
            raise ValueError(
                f"Access denied: user_id {user_id} does not match course material owner {material_user_id}"
            )
        
        # Query page analyses for the range
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"🟡 Querying page_analyses: material={course_material_id}, user={material_user_id}, pages={start_page}-{end_page}")
        
        response = client.table("page_analyses").select(
            "page_number, summary, key_terms, exam_questions, diagram_description, raw_analysis"
        ).eq(
            "course_material_id", course_material_id
        ).eq(
            "user_id", material_user_id
        ).gte(
            "page_number", start_page
        ).lte(
            "page_number", end_page
        ).order(
            "page_number", desc=False
        ).execute()
        
        result = response.data or []
        logger.info(f"🟢 Query returned {len(result)} page analyses")
        if result:
            page_numbers = [r.get('page_number') for r in result]
            logger.debug(f"Page numbers found: {page_numbers}")
        else:
            logger.warning(f"⚠️ No page analyses found for range {start_page}-{end_page}")
        
        return result
    
    except ValueError:
        raise
    except Exception as e:
        raise Exception(f"Failed to get page analyses for range: {str(e)}")


def get_page_analysis_id(
    course_material_id: str,
    page_number: int,
    user_id: str
) -> Optional[str]:
    """
    Get page analysis ID from the page_analyses table.
    
    Args:
        course_material_id: Course material ID
        page_number: Page number (1-indexed)
        user_id: User ID for authorization (RLS) - used for validation only
        
    Returns:
        Page analysis ID (UUID) or None if not found
        
    Raises:
        Exception: If database operation fails
    """
    client = get_supabase_client()
    
    try:
        # First, get the user_id from the course_material to ensure we use the correct one
        material_response = client.table("course_materials").select(
            "user_id"
        ).eq("id", course_material_id).single().execute()
        
        if not material_response.data:
            return None
        
        material_user_id = material_response.data["user_id"]
        
        # Validate that the requesting user_id matches the material's user_id
        if material_user_id != user_id:
            return None
        
        # Now query with the correct user_id from the material
        response = client.table("page_analyses").select(
            "id"
        ).eq(
            "course_material_id", course_material_id
        ).eq(
            "page_number", page_number
        ).eq(
            "user_id", material_user_id
        ).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0].get("id")
        else:
            return None
    except Exception as e:
        raise Exception(f"Failed to get page analysis ID: {str(e)}")


def get_all_page_analyses_for_material(
    course_material_id: str,
    user_id: str
) -> list[dict]:
    """
    Get all page analyses for a given course material.

    This helper is used to aggregate per-page summaries and key terms in
    order to generate a global topics summary for the entire lecture.

    Args:
        course_material_id: Course material ID
        user_id: User ID for authorization (RLS)

    Returns:
        A list of dicts with keys: id, page_number, summary, key_terms,
        exam_questions, diagram_description (if available)

    Raises:
        Exception: If database operation fails
    """
    client = get_supabase_client()

    try:
        response = (
            client.table("page_analyses")
            .select("id, page_number, summary, key_terms, exam_questions, diagram_description")
            .eq("course_material_id", course_material_id)
            .eq("user_id", user_id)
            .order("page_number", desc=False)
            .execute()
        )

        return response.data or []
    except Exception as e:
        raise Exception(f"Failed to get page analyses for material: {str(e)}")


def update_course_material_summary(
    material_id: str,
    summary: str
) -> None:
    """
    Update the global summary field of a course material.

    The summary is expected to be a JSON-encoded string containing a
    structured overview of the lecture topics, but is stored as TEXT
    for maximum flexibility.

    Args:
        material_id: Course material ID
        summary: JSON-encoded summary string
    """
    client = get_supabase_client()

    try:
        client.table("course_materials").update(
            {"summary": summary}
        ).eq("id", material_id).execute()
    except Exception as e:
        raise Exception(f"Failed to update course material summary: {str(e)}")


def update_course_material_filename(
    material_id: str,
    filename: str
) -> None:
    """
    Update the file_name field in the course_materials table.
    
    This function updates the display name of a course material with a
    professionally generated filename based on the lecture content.
    
    Args:
        material_id: Course material ID
        filename: New filename (without file extension)
    """
    client = get_supabase_client()
    
    try:
        client.table("course_materials").update(
            {"file_name": filename}
        ).eq("id", material_id).execute()
        logger.info(f"Updated filename for material {material_id} to: {filename}")
    except Exception as e:
        raise Exception(f"Failed to update course material filename: {str(e)}")


def get_course_material_filename(material_id: str, user_id: str) -> Optional[str]:
    """
    Get the current filename of a course material.
    
    Args:
        material_id: Course material ID
        user_id: User ID for authorization
        
    Returns:
        Current filename or None if not found
    """
    client = get_supabase_client()
    
    try:
        response = client.table("course_materials").select("file_name").eq("id", material_id).eq("user_id", user_id).single().execute()
        if response.data:
            return response.data.get("file_name")
        return None
    except Exception as e:
        logger.warning(f"Failed to get course material filename: {str(e)}")
        return None


def get_course_materials_for_naming(
    course_id: str,
    user_id: str,
    exclude_material_id: Optional[str] = None
) -> List[dict]:
    """
    Get existing course materials to detect naming patterns.
    
    Args:
        course_id: Course ID
        user_id: User ID for authorization
        exclude_material_id: Material ID to exclude from results (the one being renamed)
        
    Returns:
        List of material dicts with file_name field
    """
    client = get_supabase_client()
    
    try:
        query = client.table("course_materials").select("id, file_name").eq("course_id", course_id).eq("user_id", user_id)
        
        if exclude_material_id:
            query = query.neq("id", exclude_material_id)
        
        response = query.order("created_at", ascending=True).execute()
        return response.data if response.data else []
    except Exception as e:
        logger.warning(f"Failed to get course materials for naming pattern: {str(e)}")
        return []


def get_course_material_summary(
    course_material_id: str,
    user_id: str
) -> Optional[dict]:
    """
    Get the summary field from a course_material record.
    
    The summary is stored as a TEXT field containing JSON-encoded data
    with an overview of the lecture topics and concepts.
    
    Args:
        course_material_id: Course material ID
        user_id: User ID for authorization (RLS)
        
    Returns:
        Parsed summary as dict, or None if not found or empty
        
    Raises:
        Exception: If database operation fails
    """
    client = get_supabase_client()
    
    try:
        response = client.table("course_materials").select(
            "summary"
        ).eq(
            "id", course_material_id
        ).eq(
            "user_id", user_id
        ).execute()
        
        if response.data and len(response.data) > 0:
            summary_text = response.data[0].get("summary")
            if not summary_text:
                return None
            
            # Try to parse as JSON
            try:
                return json.loads(summary_text)
            except json.JSONDecodeError:
                # If not valid JSON, return as plain text in a structured format
                return {
                    "summary_text": summary_text,
                    "format": "plain_text"
                }
        else:
            return None
    except Exception as e:
        raise Exception(f"Failed to get course material summary: {str(e)}")


def get_messages_for_page(
    page_analysis_id: str,
    user_id: str
) -> List[dict]:
    """
    Get all messages associated with a specific page analysis.
    
    Messages are filtered by context_page_id and validated to ensure
    they belong to a conversation owned by the user.
    
    Args:
        page_analysis_id: Page analysis ID (UUID)
        user_id: User ID for authorization (RLS)
        
    Returns:
        List of message dicts with keys: id, role, content, created_at, context_page_id
        Ordered chronologically (oldest first)
        
    Raises:
        Exception: If database operation fails
    """
    client = get_supabase_client()
    
    try:
        # Query messages with context_page_id and join with conversations to validate user_id
        # We need to ensure the messages belong to a conversation owned by the user
        response = (
            client.table("messages")
            .select("id, role, content, created_at, context_page_id, conversation_id")
            .eq("context_page_id", page_analysis_id)
            .execute()
        )
        
        if not response.data:
            return []
        
        # Filter messages to only include those from conversations owned by the user
        # We need to check each message's conversation
        conversation_ids = list(set(msg.get("conversation_id") for msg in response.data if msg.get("conversation_id")))
        
        if not conversation_ids:
            return []
        
        # Get conversations to validate ownership
        conv_response = (
            client.table("conversations")
            .select("id")
            .in_("id", conversation_ids)
            .eq("user_id", user_id)
            .execute()
        )
        
        valid_conversation_ids = {conv["id"] for conv in (conv_response.data or [])}
        
        # Filter messages to only those from valid conversations
        filtered_messages = [
            msg for msg in response.data
            if msg.get("conversation_id") in valid_conversation_ids
        ]
        
        # Sort by created_at (oldest first)
        filtered_messages.sort(key=lambda x: x.get("created_at", ""))
        
        return filtered_messages
    except Exception as e:
        raise Exception(f"Failed to get messages for page: {str(e)}")


def save_flashcards(
    flashcards: List[dict],
    user_id: str,
    course_id: str
) -> None:
    """
    Save flashcards to the database.
    
    Args:
        flashcards: List of flashcard dicts with keys:
            - front: Front side text
            - back: Back side text
            - tags: List of tags (will be joined with spaces)
            - source_page_analysis_id: Optional page analysis ID
        user_id: User ID (UUID)
        course_id: Course ID (UUID)
        
    Raises:
        Exception: If database operation fails
    """
    if not flashcards:
        return
    
    client = get_supabase_client()
    
    try:
        records = []
        for card in flashcards:
            # Convert tags list to space-separated string if needed
            tags = card.get("tags", [])
            if isinstance(tags, list):
                tags_str = " ".join(str(tag) for tag in tags)
            else:
                tags_str = str(tags) if tags else ""
            
            record = {
                "course_id": course_id,
                "user_id": user_id,
                "front": card.get("front", ""),
                "back": card.get("back", ""),
            }
            
            if card.get("source_page_analysis_id"):
                record["source_page_analysis_id"] = card["source_page_analysis_id"]
            
            records.append(record)
        
        # Batch insert
        client.table("flashcards").insert(records).execute()
    except Exception as e:
        raise Exception(f"Failed to save flashcards: {str(e)}")


def get_flashcards_for_material(
    course_material_id: str,
    user_id: str
) -> List[dict]:
    """
    Get all flashcards for a course material.
    
    Retrieves flashcards by finding all page analyses for the material
    and then fetching flashcards linked to those page analyses.
    
    Args:
        course_material_id: Course material ID (UUID)
        user_id: User ID (UUID) for authorization
        
    Returns:
        List of flashcard dicts with keys:
            - id: Flashcard ID
            - front: Front side text
            - back: Back side text
            - source_page_analysis_id: Page analysis ID
            - created_at: Creation timestamp
            - course_id: Course ID
            - user_id: User ID
            
    Raises:
        Exception: If database operation fails
    """
    client = get_supabase_client()
    
    try:
        # First, get all page analysis IDs for this material
        page_analyses = get_all_page_analyses_for_material(course_material_id, user_id)
        
        if not page_analyses:
            return []
        
        page_analysis_ids = [pa.get("id") for pa in page_analyses if pa.get("id")]
        
        if not page_analysis_ids:
            return []
        
        # Get all flashcards linked to these page analyses
        response = (
            client.table("flashcards")
            .select("id, front, back, source_page_analysis_id, created_at, course_id, user_id")
            .eq("user_id", user_id)
            .in_("source_page_analysis_id", page_analysis_ids)
            .order("created_at", desc=False)
            .execute()
        )
        
        return response.data if response.data else []
        
    except Exception as e:
        raise Exception(f"Failed to get flashcards for material: {str(e)}")


def delete_course_material(
    material_id: str,
    user_id: str
) -> None:
    """
    Delete a course material and all associated data.
    
    This function:
    1. Gets the material record to retrieve file_path
    2. Deletes flashcards specific to this material (via page_analyses)
    3. Deletes any stored Anki APKG files specific to this material
    4. Deletes the PDF file from Supabase Storage
    5. Deletes the material record from database (cascades handle page_analyses, slide_snippets)
    
    Args:
        material_id: Course material ID (UUID)
        user_id: User ID (UUID) for authorization
        
    Raises:
        ValueError: If material not found or access denied
        Exception: If deletion fails
    """
    client = get_supabase_client()
    
    try:
        # Get material record to retrieve file_path and validate ownership
        material_response = (
            client.table("course_materials")
            .select("*")
            .eq("id", material_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        
        if not material_response.data:
            raise ValueError("Course material not found or access denied")
        
        material = material_response.data
        file_path = material.get("file_path")
        
        # 1. Delete flashcards specific to this material only
        try:
            # Get all page_analyses for this material
            page_analyses = get_all_page_analyses_for_material(material_id, user_id)
            page_analysis_ids = [pa.get("id") for pa in page_analyses if pa.get("id")]
            
            if page_analysis_ids:
                # Get all flashcards linked to these page_analyses
                flashcards_response = (
                    client.table("flashcards")
                    .select("id")
                    .eq("user_id", user_id)
                    .in_("source_page_analysis_id", page_analysis_ids)
                    .execute()
                )
                
                if flashcards_response.data:
                    flashcard_ids = [fc.get("id") for fc in flashcards_response.data if fc.get("id")]
                    if flashcard_ids:
                        # Delete only flashcards linked to this material's page_analyses
                        client.table("flashcards").delete().in_("id", flashcard_ids).execute()
                        logger.info(f"✅ Deleted {len(flashcard_ids)} flashcards for material {material_id}")
        except Exception as e:
            logger.warning(f"Failed to delete flashcards for material {material_id}: {e}")
            # Continue with deletion even if flashcard deletion fails
        
        # 2. Delete any stored Anki APKG files specific to this material
        try:
            # APKG files are typically generated on-the-fly, but check for any stored ones
            # Common patterns: flashcards_{material_id}.apkg or paths containing material_id
            # Since APKG files are usually generated on-demand, we'll try to find and delete
            # any files that might match this material
            
            # List files in user's storage folder to find APKG files
            user_folder = f"{user_id}/"
            try:
                # List files in the user's folder
                files_response = client.storage.from_("course_materials").list(user_folder)
                
                if files_response:
                    # Look for APKG files that might be associated with this material
                    # Pattern: files containing material_id or matching flashcard naming
                    apkg_files_to_delete = []
                    for file_info in files_response:
                        file_name = file_info.get("name", "")
                        # Check if it's an APKG file and might be related to this material
                        if file_name.endswith(".apkg") and (
                            material_id in file_name or 
                            f"flashcards_" in file_name.lower()
                        ):
                            # Construct full path
                            apkg_path = f"{user_folder}{file_name}" if not file_name.startswith(user_folder) else file_name
                            apkg_files_to_delete.append(apkg_path)
                    
                    if apkg_files_to_delete:
                        client.storage.from_("course_materials").remove(apkg_files_to_delete)
                        logger.info(f"✅ Deleted {len(apkg_files_to_delete)} APKG files for material {material_id}")
            except Exception as e:
                # If listing fails (e.g., folder doesn't exist), that's okay
                logger.debug(f"No APKG files found or listing failed for material {material_id}: {e}")
        except Exception as e:
            logger.warning(f"Failed to delete APKG files for material {material_id}: {e}")
            # Continue with deletion even if APKG deletion fails
        
        # 3. Delete the PDF file from Supabase Storage
        if file_path:
            try:
                client.storage.from_("course_materials").remove([file_path])
                logger.info(f"✅ Deleted PDF file from storage: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete PDF file from storage {file_path}: {e}")
                # Continue with DB deletion even if storage deletion fails
        
        # 4. Delete material record from database
        # This will cascade delete page_analyses and slide_snippets
        delete_response = (
            client.table("course_materials")
            .delete()
            .eq("id", material_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        if not delete_response.data:
            raise ValueError("Failed to delete material record from database")
        
        logger.info(f"✅ Successfully deleted course material {material_id}")
        
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Error deleting course material {material_id}: {str(e)}", exc_info=True)
        raise Exception(f"Failed to delete course material: {str(e)}")

