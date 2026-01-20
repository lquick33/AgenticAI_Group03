"""
Supabase Storage and Database Service

Handles file uploads to Supabase Storage and database operations
for course materials and page analyses.
"""

import json
from typing import Optional

from supabase import create_client, Client

from app.core.config import settings
from app.models.schemas import SlideAnalysis


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
        A list of dicts with keys: page_number, summary, key_terms,
        exam_questions (if available)

    Raises:
        Exception: If database operation fails
    """
    client = get_supabase_client()

    try:
        response = (
            client.table("page_analyses")
            .select("page_number, summary, key_terms, exam_questions")
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

