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


# =============================================================================
# Flashcard Cache Functions (Anki-aligned storage)
# =============================================================================

def cache_flashcards(
    cards: List[dict],
    anki_note_ids: List[int],
    user_id: str,
    deck_name: str,
    course_id: Optional[str] = None,
    synced_to_ankiweb: bool = False
) -> None:
    """
    Cache flashcards after adding to Anki.
    
    Tags already contain metadata (page:N, source:uuid) - no separate columns needed.
    
    Args:
        cards: List of card dicts with front, back, tags
        anki_note_ids: List of Anki note IDs (from add_notes response)
        user_id: User ID (UUID)
        deck_name: Full deck name (e.g., "Course::Lecture")
        course_id: Optional course ID for faster DB joins
        synced_to_ankiweb: Whether cards have been synced to AnkiWeb
    """
    if not cards or not anki_note_ids:
        return
    
    client = get_supabase_client()
    
    records = []
    for card, note_id in zip(cards, anki_note_ids):
        if note_id:  # Only cache if Anki add succeeded
            records.append({
                "user_id": user_id,
                "anki_note_id": note_id,
                "deck_name": deck_name,
                "front": card["front"],
                "back": card["back"],
                "tags": card.get("tags", []),
                "course_id": course_id,
                "synced_to_ankiweb": synced_to_ankiweb,
            })
    
    if records:
        try:
            client.table("flashcard_cache").upsert(
                records, 
                on_conflict="user_id,anki_note_id"
            ).execute()
        except Exception as e:
            # Log but don't fail - Anki is source of truth, cache is backup
            import logging
            logging.warning(f"Failed to cache flashcards: {e}")


def get_cached_flashcards_for_material(
    deck_name: str,
    user_id: str
) -> List[dict]:
    """
    Get cached flashcards for a specific lecture deck.
    
    Args:
        deck_name: Full deck name (e.g., "Marketing 101::Lecture 3")
        user_id: User ID (UUID)
        
    Returns:
        List of flashcard dicts with front, back, tags, anki_note_id
    """
    client = get_supabase_client()
    
    try:
        response = (
            client.table("flashcard_cache")
            .select("id, anki_note_id, front, back, tags, created_at")
            .eq("user_id", user_id)
            .eq("deck_name", deck_name)
            .order("created_at", desc=False)
            .execute()
        )
        return response.data if response.data else []
    except Exception as e:
        raise Exception(f"Failed to get cached flashcards: {str(e)}")


def get_cached_flashcards_for_course(
    course_id: str,
    user_id: str
) -> List[dict]:
    """
    Get all cached flashcards for a course (all lectures).
    Used as fallback for deduplication when Anki is unavailable.
    
    Args:
        course_id: Course ID (UUID)
        user_id: User ID (UUID)
        
    Returns:
        List of flashcard dicts with front, back, tags
    """
    client = get_supabase_client()
    
    try:
        response = (
            client.table("flashcard_cache")
            .select("id, anki_note_id, deck_name, front, back, tags")
            .eq("user_id", user_id)
            .eq("course_id", course_id)
            .execute()
        )
        return response.data if response.data else []
    except Exception as e:
        raise Exception(f"Failed to get cached flashcards for course: {str(e)}")


def get_cached_flashcards_by_deck_pattern(
    deck_pattern: str,
    user_id: str
) -> List[dict]:
    """
    Get cached flashcards matching a deck name pattern.
    Useful for getting all flashcards in a course hierarchy.
    
    Args:
        deck_pattern: Deck name pattern (e.g., "Marketing 101::%")
        user_id: User ID (UUID)
        
    Returns:
        List of flashcard dicts
    """
    client = get_supabase_client()
    
    try:
        response = (
            client.table("flashcard_cache")
            .select("id, anki_note_id, deck_name, front, back, tags")
            .eq("user_id", user_id)
            .like("deck_name", deck_pattern)
            .execute()
        )
        return response.data if response.data else []
    except Exception as e:
        raise Exception(f"Failed to get cached flashcards by pattern: {str(e)}")


def delete_cached_flashcards_for_deck(
    deck_name: str,
    user_id: str
) -> int:
    """
    Delete cached flashcards for a specific deck.
    
    Args:
        deck_name: Deck name to delete
        user_id: User ID (UUID)
        
    Returns:
        Number of deleted records
    """
    client = get_supabase_client()
    
    try:
        response = (
            client.table("flashcard_cache")
            .delete()
            .eq("user_id", user_id)
            .eq("deck_name", deck_name)
            .execute()
        )
        return len(response.data) if response.data else 0
    except Exception as e:
        raise Exception(f"Failed to delete cached flashcards: {str(e)}")


def update_cached_deck_names(
    old_pattern: str,
    new_prefix: str,
    old_prefix: str,
    user_id: str
) -> int:
    """
    Update deck names in cache when course or material is renamed.
    
    Args:
        old_pattern: Pattern to match (e.g., "Old Course::%")
        new_prefix: New prefix to replace with
        old_prefix: Old prefix to replace
        user_id: User ID (UUID)
        
    Returns:
        Number of updated records
    """
    client = get_supabase_client()
    
    try:
        # Get matching records
        response = (
            client.table("flashcard_cache")
            .select("id, deck_name")
            .eq("user_id", user_id)
            .like("deck_name", old_pattern)
            .execute()
        )
        
        if not response.data:
            return 0
        
        # Update each record with new deck name
        count = 0
        for record in response.data:
            old_deck = record["deck_name"]
            new_deck = old_deck.replace(old_prefix, new_prefix, 1)
            
            client.table("flashcard_cache").update(
                {"deck_name": new_deck}
            ).eq("id", record["id"]).execute()
            count += 1
        
        return count
    except Exception as e:
        raise Exception(f"Failed to update cached deck names: {str(e)}")


def get_unsynced_flashcard_count(user_id: str) -> int:
    """
    Get the count of flashcards that haven't been synced to AnkiWeb.
    
    Args:
        user_id: User ID (UUID)
        
    Returns:
        Count of unsynced flashcards
    """
    client = get_supabase_client()
    
    try:
        response = (
            client.table("flashcard_cache")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("synced_to_ankiweb", False)
            .execute()
        )
        return response.count if response.count else 0
    except Exception as e:
        logger.warning(f"Failed to get unsynced flashcard count: {e}")
        return 0


def mark_flashcards_as_synced(user_id: str) -> int:
    """
    Mark all unsynced flashcards as synced to AnkiWeb.
    Called after a successful AnkiWeb sync.
    
    Args:
        user_id: User ID (UUID)
        
    Returns:
        Number of updated records
    """
    client = get_supabase_client()
    
    try:
        response = (
            client.table("flashcard_cache")
            .update({"synced_to_ankiweb": True})
            .eq("user_id", user_id)
            .eq("synced_to_ankiweb", False)
            .execute()
        )
        return len(response.data) if response.data else 0
    except Exception as e:
        logger.warning(f"Failed to mark flashcards as synced: {e}")
        return 0


def sync_cache_from_anki(
    parent_deck: str,
    user_id: str,
    course_id: Optional[str] = None
) -> dict:
    """
    Sync cache from Anki - pull changes from Anki into flashcard_cache.
    
    This ensures the cache reflects any manual edits/deletions in Anki.
    Should be called before flashcard generation for accurate deduplication.
    
    Args:
        parent_deck: Parent deck name (course) - syncs all sub-decks
        user_id: User ID
        course_id: Optional course ID for new inserts
        
    Returns:
        Dict with sync stats: inserted, updated, deleted, unchanged
    """
    import logging
    logger = logging.getLogger(__name__)
    
    stats = {
        "inserted": 0,
        "updated": 0,
        "deleted": 0,
        "unchanged": 0,
        "errors": []
    }
    
    try:
        from app.services.anki.client import AnkiClient
        anki = AnkiClient()
        
        # Get all notes from Anki
        anki_notes = anki.get_deck_notes_with_info(parent_deck)
        anki_note_map = {note["noteId"]: note for note in anki_notes}
        anki_note_ids = set(anki_note_map.keys())
        
        logger.info(f"Sync: Found {len(anki_notes)} notes in Anki deck '{parent_deck}'")
        
        # Get all cached notes for this deck pattern
        client = get_supabase_client()
        cache_response = (
            client.table("flashcard_cache")
            .select("id, anki_note_id, anki_mod, front, back, tags, deck_name")
            .eq("user_id", user_id)
            .like("deck_name", f"{parent_deck}::%")
            .execute()
        )
        
        cached_notes = cache_response.data or []
        cache_map = {note["anki_note_id"]: note for note in cached_notes}
        cached_note_ids = set(cache_map.keys())
        
        logger.info(f"Sync: Found {len(cached_notes)} notes in cache")
        
        # 1. Find notes to INSERT (in Anki but not in cache)
        to_insert = anki_note_ids - cached_note_ids
        for note_id in to_insert:
            anki_note = anki_note_map[note_id]
            fields = anki_note.get("fields", {})
            front = fields.get("Front", {}).get("value", "")
            back = fields.get("Back", {}).get("value", "")
            
            # Determine deck name from cards
            cards = anki_note.get("cards", [])
            deck_name = parent_deck  # Default
            if cards:
                # Get the deck of the first card
                card_info = anki._request("cardsInfo", {"cards": [cards[0]]})
                if card_info:
                    deck_name = card_info[0].get("deckName", parent_deck)
            
            try:
                client.table("flashcard_cache").insert({
                    "user_id": user_id,
                    "anki_note_id": note_id,
                    "deck_name": deck_name,
                    "front": front,
                    "back": back,
                    "tags": anki_note.get("tags", []),
                    "anki_mod": anki_note.get("mod"),
                    "course_id": course_id,
                }).execute()
                stats["inserted"] += 1
            except Exception as e:
                stats["errors"].append(f"Insert {note_id}: {e}")
        
        # 2. Find notes to UPDATE (mod timestamp changed)
        to_check = anki_note_ids & cached_note_ids
        for note_id in to_check:
            anki_note = anki_note_map[note_id]
            cached_note = cache_map[note_id]
            
            anki_mod = anki_note.get("mod")
            cached_mod = cached_note.get("anki_mod")
            
            if anki_mod != cached_mod:
                # Note was modified in Anki - update cache
                fields = anki_note.get("fields", {})
                front = fields.get("Front", {}).get("value", "")
                back = fields.get("Back", {}).get("value", "")
                
                try:
                    client.table("flashcard_cache").update({
                        "front": front,
                        "back": back,
                        "tags": anki_note.get("tags", []),
                        "anki_mod": anki_mod,
                        "cached_at": "now()",
                    }).eq("id", cached_note["id"]).execute()
                    stats["updated"] += 1
                except Exception as e:
                    stats["errors"].append(f"Update {note_id}: {e}")
            else:
                stats["unchanged"] += 1
        
        # 3. Find notes in cache but not in Anki (possibly deleted)
        # SAFETY: We do NOT auto-delete from cache. Instead, we log for user review.
        # The cache acts as a backup in case cards were accidentally deleted from Anki.
        orphaned = cached_note_ids - anki_note_ids
        if orphaned:
            logger.warning(
                f"⚠️  SYNC WARNING: {len(orphaned)} cards in cache but NOT in Anki. "
                f"These may have been deleted from Anki. Note IDs: {list(orphaned)[:5]}..."
            )
            stats["orphaned_in_cache"] = len(orphaned)
            # Cards are preserved in cache - user can manually review/delete if desired
        
        logger.info(f"Sync complete: {stats}")
        return stats
        
    except Exception as e:
        stats["errors"].append(f"Sync failed: {e}")
        logger.error(f"Sync failed: {e}")
        return stats


def extract_source_from_tags(tags: List[str]) -> Optional[str]:
    """
    Extract page_analysis_id from tags (source:uuid format).
    
    Args:
        tags: List of tag strings
        
    Returns:
        UUID string or None if not found
    """
    if not tags:
        return None
    for tag in tags:
        if tag.startswith("source:"):
            return tag[7:]  # Remove "source:" prefix
    return None


def extract_page_from_tags(tags: List[str]) -> Optional[int]:
    """
    Extract page number from tags (page:N format).
    
    Args:
        tags: List of tag strings
        
    Returns:
        Page number or None if not found
    """
    if not tags:
        return None
    for tag in tags:
        if tag.startswith("page:"):
            try:
                return int(tag[5:])  # Remove "page:" prefix
            except ValueError:
                pass
    return None


# =============================================================================
# Anki Deck Rename Handlers
# =============================================================================

def on_course_renamed(
    course_id: str,
    old_title: str,
    new_title: str,
    user_id: str
) -> dict:
    """
    Handle course rename - update all lecture decks in Anki and cache.
    
    Call this when a course title is changed.
    
    Args:
        course_id: Course ID
        old_title: Previous course title
        new_title: New course title
        user_id: User ID
        
    Returns:
        Dict with counts of updated items
    """
    from pathlib import Path
    import logging
    logger = logging.getLogger(__name__)
    
    result = {
        "anki_decks_renamed": 0,
        "cache_entries_updated": 0,
        "errors": []
    }
    
    try:
        # Get all materials for this course
        client = get_supabase_client()
        materials_response = (
            client.table("course_materials")
            .select("id, file_name")
            .eq("course_id", course_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        materials = materials_response.data or []
        
        # Rename each deck in Anki
        try:
            from app.services.anki.client import AnkiClient
            anki = AnkiClient()
            
            for material in materials:
                lecture_name = Path(material["file_name"]).stem
                old_deck = f"{old_title}::{lecture_name}"
                new_deck = f"{new_title}::{lecture_name}"
                
                try:
                    if anki.rename_deck(old_deck, new_deck):
                        result["anki_decks_renamed"] += 1
                except Exception as e:
                    result["errors"].append(f"Anki rename failed for {old_deck}: {e}")
            
            # Sync changes
            anki.sync()
        except Exception as e:
            result["errors"].append(f"Anki connection failed: {e}")
        
        # Update cache
        try:
            updated = update_cached_deck_names(
                old_pattern=f"{old_title}::%",
                new_prefix=new_title,
                old_prefix=old_title,
                user_id=user_id
            )
            result["cache_entries_updated"] = updated
        except Exception as e:
            result["errors"].append(f"Cache update failed: {e}")
        
        logger.info(f"Course renamed: {old_title} -> {new_title}, "
                   f"Anki: {result['anki_decks_renamed']}, Cache: {result['cache_entries_updated']}")
        
    except Exception as e:
        result["errors"].append(f"Course rename failed: {e}")
    
    return result


def on_material_renamed(
    material_id: str,
    old_file_name: str,
    new_file_name: str,
    user_id: str
) -> dict:
    """
    Handle lecture file rename - update deck name in Anki and cache.
    
    Call this when a course material file name is changed.
    
    Args:
        material_id: Course material ID
        old_file_name: Previous file name
        new_file_name: New file name
        user_id: User ID
        
    Returns:
        Dict with update status
    """
    from pathlib import Path
    import logging
    logger = logging.getLogger(__name__)
    
    result = {
        "anki_deck_renamed": False,
        "cache_entries_updated": 0,
        "errors": []
    }
    
    try:
        # Get course title
        client = get_supabase_client()
        material_response = (
            client.table("course_materials")
            .select("course_id")
            .eq("id", material_id)
            .single()
            .execute()
        )
        
        if not material_response.data:
            result["errors"].append("Material not found")
            return result
        
        course_id = material_response.data["course_id"]
        
        course_response = (
            client.table("courses")
            .select("title")
            .eq("id", course_id)
            .single()
            .execute()
        )
        
        if not course_response.data:
            result["errors"].append("Course not found")
            return result
        
        course_title = course_response.data["title"]
        old_lecture = Path(old_file_name).stem
        new_lecture = Path(new_file_name).stem
        
        old_deck = f"{course_title}::{old_lecture}"
        new_deck = f"{course_title}::{new_lecture}"
        
        # Rename in Anki
        try:
            from app.services.anki.client import AnkiClient
            anki = AnkiClient()
            
            if anki.rename_deck(old_deck, new_deck):
                result["anki_deck_renamed"] = True
                anki.sync()
        except Exception as e:
            result["errors"].append(f"Anki rename failed: {e}")
        
        # Update cache
        try:
            updated = update_cached_deck_names(
                old_pattern=old_deck,
                new_prefix=new_deck,
                old_prefix=old_deck,
                user_id=user_id
            )
            result["cache_entries_updated"] = updated
        except Exception as e:
            result["errors"].append(f"Cache update failed: {e}")
        
        logger.info(f"Material renamed: {old_deck} -> {new_deck}, "
                   f"Anki: {result['anki_deck_renamed']}, Cache: {result['cache_entries_updated']}")
        
    except Exception as e:
        result["errors"].append(f"Material rename failed: {e}")
    
    return result


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


def get_material_classification(
    material_id: str,
    user_id: str
) -> Optional[dict]:
    """
    Get classification for a material.
    
    Args:
        material_id: Course material ID
        user_id: User ID
        
    Returns:
        Dict with keys: classification, classification_confidence, 
        classification_reasoning, classification_override
        or None if not classified
    """
    client = get_supabase_client()
    try:
        response = client.table("course_materials").select(
            "classification, classification_confidence, classification_reasoning, classification_override"
        ).eq("id", material_id).eq("user_id", user_id).single().execute()
        
        if response.data and response.data.get("classification"):
            return response.data
        return None
    except Exception as e:
        logger.error(f"Error getting classification: {e}")
        return None


def update_material_classification(
    material_id: str,
    classification: str,
    confidence: float,
    reasoning: str,
    override: bool = False
) -> None:
    """
    Update classification for a material.
    
    Args:
        material_id: Course material ID
        classification: Classification category (must match enum)
        confidence: Confidence score (0.0-1.0)
        reasoning: LLM reasoning for classification
        override: Whether this is a manual override
    """
    client = get_supabase_client()
    try:
        client.table("course_materials").update({
            "classification": classification,
            "classification_confidence": confidence,
            "classification_reasoning": reasoning,
            "classification_override": override
        }).eq("id", material_id).execute()
        logger.info(f"Updated classification for material {material_id}: {classification}")
    except Exception as e:
        logger.error(f"Error updating classification: {e}")
        raise


# =============================================================================
# Knowledge Tracking Functions
# =============================================================================

def save_deck_mapping(
    user_id: str,
    course_id: str,
    deck_name: str,
    course_material_id: Optional[str] = None
) -> dict:
    """
    Save or update a course-to-deck mapping.
    
    Args:
        user_id: User ID
        course_id: Course ID
        deck_name: Anki deck name (e.g., "Marketing 101::Lecture 1")
        course_material_id: Optional course material ID
        
    Returns:
        The created/updated mapping record
    """
    client = get_supabase_client()
    
    data = {
        "user_id": user_id,
        "course_id": course_id,
        "deck_name": deck_name,
    }
    if course_material_id:
        data["course_material_id"] = course_material_id
    
    try:
        # Upsert based on user_id + deck_name unique constraint
        response = client.table("course_deck_mappings").upsert(
            data,
            on_conflict="user_id,deck_name"
        ).execute()
        
        return response.data[0] if response.data else data
    except Exception as e:
        logger.error(f"Error saving deck mapping: {e}")
        raise


def get_deck_mappings_for_course(user_id: str, course_id: str) -> List[dict]:
    """
    Get all deck mappings for a course.
    
    Args:
        user_id: User ID
        course_id: Course ID
        
    Returns:
        List of deck mapping records
    """
    client = get_supabase_client()
    
    try:
        response = client.table("course_deck_mappings").select("*").eq(
            "user_id", user_id
        ).eq("course_id", course_id).execute()
        
        return response.data or []
    except Exception as e:
        logger.error(f"Error getting deck mappings: {e}")
        return []


def save_knowledge_snapshot(
    user_id: str,
    deck_name: str,
    total_cards: int,
    new_cards: int,
    learning_cards: int,
    young_cards: int,
    mature_cards: int,
    suspended_cards: int = 0,
    avg_ease_factor: Optional[float] = None,
    avg_interval_days: Optional[float] = None,
    retention_rate: Optional[float] = None,
    mastery_score: Optional[float] = None,
    course_id: Optional[str] = None,
    course_material_id: Optional[str] = None,
) -> dict:
    """
    Save a knowledge snapshot for a deck.
    
    Args:
        user_id: User ID
        deck_name: Anki deck name
        total_cards: Total card count
        new_cards: New card count
        learning_cards: Learning card count
        young_cards: Young review card count
        mature_cards: Mature card count
        suspended_cards: Suspended card count
        avg_ease_factor: Average ease factor
        avg_interval_days: Average interval in days
        retention_rate: Retention rate (0-1)
        mastery_score: Mastery score (0-1)
        course_id: Optional course ID
        course_material_id: Optional material ID
        
    Returns:
        The created snapshot record
    """
    client = get_supabase_client()
    
    data = {
        "user_id": user_id,
        "deck_name": deck_name,
        "total_cards": total_cards,
        "new_cards": new_cards,
        "learning_cards": learning_cards,
        "young_cards": young_cards,
        "mature_cards": mature_cards,
        "suspended_cards": suspended_cards,
        "avg_ease_factor": avg_ease_factor,
        "avg_interval_days": avg_interval_days,
        "retention_rate": retention_rate,
        "mastery_score": mastery_score,
    }
    
    if course_id:
        data["course_id"] = course_id
    if course_material_id:
        data["course_material_id"] = course_material_id
    
    try:
        response = client.table("deck_knowledge_snapshots").insert(data).execute()
        return response.data[0] if response.data else data
    except Exception as e:
        logger.error(f"Error saving knowledge snapshot: {e}")
        raise


def get_latest_knowledge_snapshot(
    user_id: str, 
    deck_name: str
) -> Optional[dict]:
    """
    Get the most recent knowledge snapshot for a deck.
    
    Args:
        user_id: User ID
        deck_name: Anki deck name
        
    Returns:
        The latest snapshot record or None
    """
    client = get_supabase_client()
    
    try:
        response = client.table("deck_knowledge_snapshots").select("*").eq(
            "user_id", user_id
        ).eq("deck_name", deck_name).order(
            "captured_at", desc=True
        ).limit(1).execute()
        
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Error getting knowledge snapshot: {e}")
        return None


def get_knowledge_snapshots_for_course(
    user_id: str,
    course_id: str,
    limit: int = 30
) -> List[dict]:
    """
    Get recent knowledge snapshots for all decks in a course.
    
    Args:
        user_id: User ID
        course_id: Course ID
        limit: Maximum snapshots per deck
        
    Returns:
        List of snapshot records
    """
    client = get_supabase_client()
    
    try:
        response = client.table("deck_knowledge_snapshots").select("*").eq(
            "user_id", user_id
        ).eq("course_id", course_id).order(
            "captured_at", desc=True
        ).limit(limit).execute()
        
        return response.data or []
    except Exception as e:
        logger.error(f"Error getting course knowledge snapshots: {e}")
        return []


def save_anki_card_mapping(
    user_id: str,
    anki_note_id: int,
    deck_name: str,
    flashcard_id: Optional[str] = None
) -> dict:
    """
    Save a mapping between an Anki note and an agent-generated flashcard.
    
    Args:
        user_id: User ID
        anki_note_id: Anki note ID
        deck_name: Deck the card was added to
        flashcard_id: Optional flashcard ID from our database
        
    Returns:
        The created mapping record
    """
    client = get_supabase_client()
    
    data = {
        "user_id": user_id,
        "anki_note_id": anki_note_id,
        "deck_name": deck_name,
    }
    if flashcard_id:
        data["flashcard_id"] = flashcard_id
    
    try:
        response = client.table("anki_card_mappings").upsert(
            data,
            on_conflict="user_id,anki_note_id"
        ).execute()
        
        return response.data[0] if response.data else data
    except Exception as e:
        logger.error(f"Error saving Anki card mapping: {e}")
        raise


def get_course_with_materials(user_id: str, course_id: str) -> Optional[dict]:
    """
    Get a course with all its materials.
    
    Args:
        user_id: User ID
        course_id: Course ID
        
    Returns:
        Course dict with 'materials' list, or None if not found
    """
    client = get_supabase_client()
    
    try:
        # Get course
        course_response = client.table("courses").select("*").eq(
            "id", course_id
        ).eq("user_id", user_id).single().execute()
        
        if not course_response.data:
            return None
        
        course = course_response.data
        
        # Get materials
        materials_response = client.table("course_materials").select(
            "id, file_name, file_type, page_count, processing_status"
        ).eq("course_id", course_id).eq("user_id", user_id).order(
            "created_at"
        ).execute()
        
        course["materials"] = materials_response.data or []
        
        return course
    except Exception as e:
        logger.error(f"Error getting course with materials: {e}")
        return None


# =============================================================================
# Anki Study History
# =============================================================================

def upsert_study_history(
    user_id: str,
    study_date: str,
    cards_reviewed: int,
    time_spent_seconds: int = 0,
    again_count: int = 0,
    hard_count: int = 0,
    good_count: int = 0,
    easy_count: int = 0,
    new_cards: int = 0,
    review_cards: int = 0,
    relearn_cards: int = 0,
    avg_time_per_card_ms: int = 0,
) -> Optional[dict]:
    """
    Insert or update a study history entry for a specific date.
    
    Args:
        user_id: User ID
        study_date: Date string in "yyyy-MM-dd" format
        cards_reviewed: Total reviews on this day
        time_spent_seconds: Total study time in seconds
        again_count: "Again" button presses
        hard_count: "Hard" button presses
        good_count: "Good" button presses
        easy_count: "Easy" button presses
        new_cards: New cards learned
        review_cards: Regular reviews
        relearn_cards: Relearning reviews
        avg_time_per_card_ms: Average time per review
        
    Returns:
        The upserted record, or None on error
    """
    client = get_supabase_client()
    
    try:
        data = {
            "user_id": user_id,
            "study_date": study_date,
            "cards_reviewed": cards_reviewed,
            "time_spent_seconds": time_spent_seconds,
            "again_count": again_count,
            "hard_count": hard_count,
            "good_count": good_count,
            "easy_count": easy_count,
            "new_cards": new_cards,
            "review_cards": review_cards,
            "relearn_cards": relearn_cards,
            "avg_time_per_card_ms": avg_time_per_card_ms,
        }
        
        response = client.table("anki_study_history").upsert(
            data,
            on_conflict="user_id,study_date"
        ).execute()
        
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Error upserting study history: {e}")
        return None


def sync_anki_study_history(
    user_id: str,
    stats_list: list,
) -> dict:
    """
    Bulk sync study history from Anki.
    
    Args:
        user_id: User ID
        stats_list: List of DailyStudyStats objects or dicts
        
    Returns:
        Dict with 'synced' count and any 'errors'
    """
    client = get_supabase_client()
    synced = 0
    errors = []
    
    for stats in stats_list:
        try:
            # Handle both DailyStudyStats objects and dicts
            if hasattr(stats, 'date'):
                data = {
                    "user_id": user_id,
                    "study_date": stats.date,
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
            else:
                data = {
                    "user_id": user_id,
                    "study_date": stats["date"],
                    "cards_reviewed": stats["cards_reviewed"],
                    "time_spent_seconds": stats.get("time_spent_seconds", 0),
                    "again_count": stats.get("again_count", 0),
                    "hard_count": stats.get("hard_count", 0),
                    "good_count": stats.get("good_count", 0),
                    "easy_count": stats.get("easy_count", 0),
                    "new_cards": stats.get("new_cards", 0),
                    "review_cards": stats.get("review_cards", 0),
                    "relearn_cards": stats.get("relearn_cards", 0),
                    "avg_time_per_card_ms": stats.get("avg_time_per_card_ms", 0),
                }
            
            client.table("anki_study_history").upsert(
                data,
                on_conflict="user_id,study_date"
            ).execute()
            synced += 1
        except Exception as e:
            errors.append(str(e))
            logger.error(f"Error syncing study history for date {stats}: {e}")
    
    return {"synced": synced, "errors": errors}


def get_study_history(
    user_id: str,
    days: int = 90,
) -> list[dict]:
    """
    Get study history for a user.
    
    Args:
        user_id: User ID
        days: Number of days to retrieve (default 90)
        
    Returns:
        List of study history records sorted by date (oldest first)
    """
    from datetime import datetime, timedelta
    
    client = get_supabase_client()
    
    # Calculate cutoff date
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    try:
        response = client.table("anki_study_history").select(
            "study_date, cards_reviewed, time_spent_seconds, "
            "again_count, hard_count, good_count, easy_count, "
            "new_cards, review_cards, relearn_cards, avg_time_per_card_ms"
        ).eq(
            "user_id", user_id
        ).gte(
            "study_date", cutoff_date
        ).order(
            "study_date", desc=False
        ).execute()
        
        return response.data or []
    except Exception as e:
        logger.error(f"Error getting study history: {e}")
        return []

