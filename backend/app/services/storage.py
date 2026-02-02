"""
Supabase Storage and Database Service

Handles file uploads to Supabase Storage and database operations
for course materials and page analyses.
"""

import json
import logging
from time import time, sleep
from typing import Dict, Optional, List, Any, Tuple, TypeVar, Callable
from functools import wraps
import errno

from supabase import create_client, Client

from app.core.config import settings
from app.models.schemas import SlideAnalysis

logger = logging.getLogger(__name__)


# =============================================================================
# Retry Logic for Transient Network Errors
# =============================================================================

T = TypeVar('T')

def retry_on_resource_unavailable(
    max_retries: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    exponential_base: float = 2.0
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator that retries a function on transient network errors.
    
    Handles [Errno 35] Resource temporarily unavailable (EAGAIN/EWOULDBLOCK)
    which can occur with long-running HTTP clients when connection pools
    become stale or exhausted.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_str = str(e)
                    # Check for EAGAIN/EWOULDBLOCK errors (Errno 35 on macOS, 11 on Linux)
                    is_resource_unavailable = (
                        "Resource temporarily unavailable" in error_str or
                        f"[Errno {errno.EAGAIN}]" in error_str or
                        f"[Errno {errno.EWOULDBLOCK}]" in error_str or
                        "[Errno 35]" in error_str  # macOS-specific
                    )
                    
                    if is_resource_unavailable and attempt < max_retries:
                        delay = min(base_delay * (exponential_base ** attempt), max_delay)
                        logger.warning(
                            f"Transient error in {func.__name__} (attempt {attempt + 1}/{max_retries + 1}): "
                            f"{error_str}. Retrying in {delay:.2f}s..."
                        )
                        sleep(delay)
                        last_exception = e
                    else:
                        # Not a retryable error or max retries exceeded
                        raise
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            
        return wrapper
    return decorator


# Initialize Supabase client (singleton)
_supabase_client: Optional[Client] = None


# =============================================================================
# In-Memory Caches for Performance
# =============================================================================

class ClassificationCache:
    """
    In-memory TTL cache for material classifications.
    
    Classifications rarely change (only on manual override), so caching them
    significantly reduces database queries during flashcard generation.
    
    TTL: 1 hour by default (3600 seconds)
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        self._cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
        self._ttl = ttl_seconds
    
    def get(self, material_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached classification for a material.
        
        Returns:
            Classification dict or None if not cached or expired
        """
        if material_id in self._cache:
            data, timestamp = self._cache[material_id]
            if time() - timestamp < self._ttl:
                return data
            # Expired - remove from cache
            del self._cache[material_id]
        return None
    
    def set(self, material_id: str, classification: Dict[str, Any]) -> None:
        """Cache a classification for a material."""
        self._cache[material_id] = (classification, time())
    
    def invalidate(self, material_id: str) -> None:
        """Remove a material's classification from cache."""
        if material_id in self._cache:
            del self._cache[material_id]
    
    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()


# Singleton cache instance
_classification_cache = ClassificationCache()


class PageAnalysisCache:
    """
    In-memory TTL cache for page analyses.
    
    Page analyses are frequently accessed during chat sessions, so caching them
    reduces database queries significantly.
    
    TTL: 5 minutes by default (300 seconds)
    """
    
    def __init__(self, ttl_seconds: int = 300):
        self._cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
        self._ttl = ttl_seconds
    
    def get(self, material_id: str, page_number: int, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached page analysis.
        
        Returns:
            Page analysis dict or None if not cached or expired
        """
        key = f"{material_id}:{page_number}:{user_id}"
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time() - timestamp < self._ttl:
                return data
            # Expired - remove from cache
            del self._cache[key]
        return None
    
    def set(self, material_id: str, page_number: int, user_id: str, analysis: Dict[str, Any]) -> None:
        """Cache a page analysis."""
        key = f"{material_id}:{page_number}:{user_id}"
        self._cache[key] = (analysis, time())
    
    def invalidate(self, material_id: str, page_number: int, user_id: str) -> None:
        """Remove a page analysis from cache."""
        key = f"{material_id}:{page_number}:{user_id}"
        if key in self._cache:
            del self._cache[key]
    
    def invalidate_material(self, material_id: str) -> None:
        """Remove all cached analyses for a material."""
        keys_to_delete = [k for k in self._cache.keys() if k.startswith(f"{material_id}:")]
        for key in keys_to_delete:
            del self._cache[key]
    
    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()


# Singleton cache instance
_page_analysis_cache = PageAnalysisCache()


class SummaryCache:
    """
    In-memory TTL cache for course material summaries.
    
    Summaries are accessed frequently during chat sessions.
    
    TTL: 10 minutes by default (600 seconds)
    """
    
    def __init__(self, ttl_seconds: int = 600):
        self._cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
        self._ttl = ttl_seconds
    
    def get(self, material_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached summary.
        
        Returns:
            Summary dict or None if not cached or expired
        """
        key = f"{material_id}:{user_id}"
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time() - timestamp < self._ttl:
                return data
            # Expired - remove from cache
            del self._cache[key]
        return None
    
    def set(self, material_id: str, user_id: str, summary: Dict[str, Any]) -> None:
        """Cache a summary."""
        key = f"{material_id}:{user_id}"
        self._cache[key] = (summary, time())
    
    def invalidate(self, material_id: str) -> None:
        """Remove all cached summaries for a material."""
        keys_to_delete = [k for k in self._cache.keys() if k.startswith(f"{material_id}:")]
        for key in keys_to_delete:
            del self._cache[key]
    
    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()


# Singleton cache instance
_summary_cache = SummaryCache()


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


@retry_on_resource_unavailable(max_retries=3, base_delay=0.1, max_delay=2.0)
def _query_user_exists(client: Client, user_id: str) -> bool:
    """
    Internal function to query if user exists (with retry logic).
    
    Separated to allow the retry decorator to work on just the network call.
    """
    response = client.table("profiles").select("id").eq(
        "id", user_id
    ).execute()
    return response.data and len(response.data) > 0


def validate_user_exists(user_id: str) -> bool:
    """
    Validate that user exists in profiles table.
    
    Note: Thanks to the SQL trigger, profiles are automatically synced
    with auth.users, so this check works reliably.
    
    Includes automatic retry logic for transient network errors.
    
    Args:
        user_id: User ID to validate
        
    Returns:
        True if user exists, False otherwise
        
    Raises:
        Exception: If database query fails after retries
    """
    client = get_supabase_client()
    
    try:
        return _query_user_exists(client, user_id)
    except Exception as e:
        raise Exception(f"Failed to validate user: {str(e)}")


@retry_on_resource_unavailable(max_retries=3, base_delay=0.1, max_delay=2.0)
def _query_course(client: Client, user_id: str, course_id: str) -> Optional[dict]:
    """Internal function to query course (with retry logic)."""
    response = client.table("courses").select("*").eq(
        "id", course_id
    ).eq("user_id", user_id).execute()
    return response.data[0] if response.data and len(response.data) > 0 else None


def get_course(
    user_id: str,
    course_id: str
) -> dict:
    """
    Get existing course and validate it belongs to user.
    
    Course must be created beforehand (e.g., via web app).
    This function only validates and retrieves existing courses.
    
    Includes automatic retry logic for transient network errors.
    
    Args:
        user_id: User ID
        course_id: Course ID (required)
        
    Returns:
        Course record as dict
        
    Raises:
        ValueError: If course doesn't exist or doesn't belong to user
        Exception: If database operation fails after retries
    """
    client = get_supabase_client()
    
    try:
        result = _query_course(client, user_id, course_id)
        
        if result:
            return result
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
            "is_chapter_heading": analysis_dict.get("is_chapter_heading", False),
            "chapter_title": analysis_dict.get("chapter_title"),
            "raw_analysis": analysis_dict  # Store full JSON as JSONB
        }).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        else:
            raise Exception("Failed to save page_analysis")
    
    except Exception as e:
        raise Exception(f"Failed to save page analysis: {str(e)}")


@retry_on_resource_unavailable(max_retries=3, base_delay=0.1, max_delay=2.0)
def _query_page_analysis(client: Client, course_material_id: str, page_number: int) -> Optional[dict]:
    """Internal function to query page analysis (with retry logic)."""
    response = client.table("page_analyses").select(
        "id, summary, key_terms, exam_questions, diagram_description, raw_analysis, "
        "course_materials!inner(user_id)"
    ).eq(
        "course_material_id", course_material_id
    ).eq(
        "page_number", page_number
    ).execute()
    return response.data[0] if response.data and len(response.data) > 0 else None


def get_page_analysis(
    course_material_id: str,
    page_number: int,
    user_id: str
) -> dict:
    """
    Get page analysis data from the page_analyses table (with in-memory caching).
    
    Page analyses are cached for 5 minutes since they rarely change after creation.
    Includes automatic retry logic for transient network errors.
    
    Args:
        course_material_id: Course material ID
        page_number: Page number (1-indexed)
        user_id: User ID for authorization (RLS) - used for validation only
        
    Returns:
        Page analysis record as dict with summary, key_terms, exam_questions, diagram_description
        
    Raises:
        ValueError: If page analysis not found or access denied
        Exception: If database operation fails after retries
    """
    # Check cache first
    cached = _page_analysis_cache.get(course_material_id, page_number, user_id)
    if cached is not None:
        logger.debug(f"Page analysis cache HIT for material {course_material_id[:8]}... page {page_number}")
        return cached
    
    client = get_supabase_client()
    
    try:
        # OPTIMIZED: Single query with JOIN to validate ownership and fetch data
        # Uses Supabase's foreign key relationship syntax: table!inner(columns)
        # The !inner ensures we only get results where the join succeeds
        analysis = _query_page_analysis(client, course_material_id, page_number)
        
        if not analysis:
            raise ValueError(
                f"Page analysis not found for course_material_id={course_material_id}, page_number={page_number}"
            )
        
        # Extract the material owner's user_id from the joined data
        material_data = analysis.get("course_materials", {})
        material_user_id = material_data.get("user_id") if material_data else None
        
        # Validate that the requesting user_id matches the material's user_id
        # This ensures proper authorization even when using service key
        if material_user_id != user_id:
            raise ValueError(
                f"Access denied: user_id {user_id} does not match course material owner {material_user_id}"
            )
        
        result = {
            "summary": analysis.get("summary", ""),
            "key_terms": analysis.get("key_terms", []),
            "exam_questions": analysis.get("exam_questions", []),
            "diagram_description": analysis.get("diagram_description"),
            "raw_analysis": analysis.get("raw_analysis", {})
        }
        
        # Cache the result
        _page_analysis_cache.set(course_material_id, page_number, user_id, result)
        logger.debug(f"Page analysis cache MISS for material {course_material_id[:8]}... page {page_number} (now cached)")
        
        return result
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
        # OPTIMIZED: Single query with JOIN to validate ownership and fetch data
        logger.info(f"🟡 Querying page_analyses: material={course_material_id}, user={user_id}, pages={start_page}-{end_page}")
        
        response = client.table("page_analyses").select(
            "page_number, summary, key_terms, exam_questions, diagram_description, raw_analysis, "
            "course_materials!inner(user_id)"
        ).eq(
            "course_material_id", course_material_id
        ).gte(
            "page_number", start_page
        ).lte(
            "page_number", end_page
        ).order(
            "page_number", desc=False
        ).execute()
        
        if not response.data:
            # Check if material exists but has no analyses in range
            # vs material doesn't exist or access denied
            material_check = client.table("course_materials").select(
                "user_id"
            ).eq("id", course_material_id).execute()
            
            if not material_check.data:
                raise ValueError(f"Course material not found: {course_material_id}")
            
            material_user_id = material_check.data[0].get("user_id")
            if material_user_id != user_id:
                raise ValueError(
                    f"Access denied: user_id {user_id} does not match course material owner {material_user_id}"
                )
            
            # Material exists, user authorized, just no analyses in range
            logger.warning(f"⚠️ No page analyses found for range {start_page}-{end_page}")
            return []
        
        # Validate ownership from the first result's joined data
        first_result = response.data[0]
        material_data = first_result.get("course_materials", {})
        material_user_id = material_data.get("user_id") if material_data else None
        
        if material_user_id != user_id:
            raise ValueError(
                f"Access denied: user_id {user_id} does not match course material owner {material_user_id}"
            )
        
        # Remove the joined course_materials data from results
        result = []
        for item in response.data:
            clean_item = {k: v for k, v in item.items() if k != "course_materials"}
            result.append(clean_item)
        
        logger.info(f"🟢 Query returned {len(result)} page analyses")
        if result:
            page_numbers = [r.get('page_number') for r in result]
            logger.debug(f"Page numbers found: {page_numbers}")
        
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
        # OPTIMIZED: Single query with JOIN to validate ownership and fetch ID
        response = client.table("page_analyses").select(
            "id, course_materials!inner(user_id)"
        ).eq(
            "course_material_id", course_material_id
        ).eq(
            "page_number", page_number
        ).execute()
        
        if not response.data or len(response.data) == 0:
            return None
        
        analysis = response.data[0]
        
        # Validate ownership from joined data
        material_data = analysis.get("course_materials", {})
        material_user_id = material_data.get("user_id") if material_data else None
        
        if material_user_id != user_id:
            return None
        
        return analysis.get("id")
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


@retry_on_resource_unavailable(max_retries=3, base_delay=0.1, max_delay=2.0)
def _query_course_material_summary(client: Client, course_material_id: str, user_id: str) -> Optional[str]:
    """Internal function to query course material summary (with retry logic)."""
    response = client.table("course_materials").select(
        "summary"
    ).eq(
        "id", course_material_id
    ).eq(
        "user_id", user_id
    ).execute()
    if response.data and len(response.data) > 0:
        return response.data[0].get("summary")
    return None


def get_course_material_summary(
    course_material_id: str,
    user_id: str
) -> Optional[dict]:
    """
    Get the summary field from a course_material record (with in-memory caching).
    
    The summary is stored as a TEXT field containing JSON-encoded data
    with an overview of the lecture topics and concepts.
    
    Summaries are cached for 10 minutes since they rarely change after creation.
    Includes automatic retry logic for transient network errors.
    
    Args:
        course_material_id: Course material ID
        user_id: User ID for authorization (RLS)
        
    Returns:
        Parsed summary as dict, or None if not found or empty
        
    Raises:
        Exception: If database operation fails after retries
    """
    # Check cache first
    cached = _summary_cache.get(course_material_id, user_id)
    if cached is not None:
        logger.debug(f"Summary cache HIT for material {course_material_id[:8]}...")
        return cached
    
    client = get_supabase_client()
    
    try:
        summary_text = _query_course_material_summary(client, course_material_id, user_id)
        
        if not summary_text:
            return None
        
        # Try to parse as JSON
        try:
            result = json.loads(summary_text)
        except json.JSONDecodeError:
            # If not valid JSON, return as plain text in a structured format
            result = {
                "summary_text": summary_text,
                "format": "plain_text"
            }
        
        # Cache the result
        _summary_cache.set(course_material_id, user_id, result)
        logger.debug(f"Summary cache MISS for material {course_material_id[:8]}... (now cached)")
        
        return result
    except Exception as e:
        raise Exception(f"Failed to get course material summary: {str(e)}")


def search_page_analyses(
    user_id: str,
    query: str,
    language: str = "auto",
    limit: int = 10
) -> List[dict]:
    """
    Search across all page_analyses for a user using full-text search.
    
    Uses PostgreSQL full-text search with German and English language support.
    Returns matching pages with course/material context, ranked by relevance.
    
    Args:
        user_id: User ID for authorization (RLS)
        query: Search query string
        language: Language for search - "de", "en", or "auto" (searches both)
        limit: Maximum number of results to return
        
    Returns:
        List of matching pages with context:
        - course_id, course_title, course_color
        - material_id, material_name
        - page_number, summary, key_terms
        - rank (relevance score)
        
    Raises:
        Exception: If database operation fails
    """
    client = get_supabase_client()
    
    if not query or not query.strip():
        return []
    
    # Sanitize query for PostgreSQL tsquery
    sanitized_query = query.strip()
    
    try:
        # ============================================================
        # TIER 1: Fast chapter heading search (indexed, very fast)
        # ============================================================
        # First, try to find an explicit chapter heading matching the query
        # This is ~10x faster than full-text search and more accurate
        # Note: Gracefully skips if columns don't exist yet (pre-migration)
        
        query_lower = sanitized_query.lower()
        stem = query_lower[:min(len(query_lower), 6)] if len(query_lower) >= 4 else query_lower
        
        tier1_results = None
        try:
            select_fields_chapter = (
                "id, page_number, summary, key_terms, chapter_title, course_material_id, "
                "course_materials(id, file_name, course_id, courses(id, title, color_code))"
            )
            
            # Search chapter headings with stem-based ILIKE for cross-language matching
            chapter_response = (
                client.table("page_analyses")
                .select(select_fields_chapter)
                .eq("user_id", user_id)
                .eq("is_chapter_heading", True)
                .ilike("chapter_title", f"%{stem}%")
                .execute()
            )
            tier1_results = chapter_response.data
        except Exception as tier1_error:
            # Tier 1 failed (likely columns don't exist yet) - fall through to Tier 2
            logger.debug(f"Tier 1 search skipped (columns may not exist): {tier1_error}")
            tier1_results = None
        
        if tier1_results:
            # Found chapter heading match(es) - format and return
            chapter_results = []
            for pa in tier1_results:
                material = pa.get("course_materials") or {}
                course = material.get("courses") or {}
                
                chapter_results.append({
                    "id": pa.get("id"),
                    "page_number": pa.get("page_number"),
                    "summary": pa.get("summary"),
                    "key_terms": pa.get("key_terms"),
                    "chapter_title": pa.get("chapter_title"),
                    "is_chapter_heading": True,
                    "material_id": pa.get("course_material_id"),
                    "material_name": material.get("file_name"),
                    "course_id": material.get("course_id"),
                    "course_title": course.get("title"),
                    "course_color": course.get("color_code"),
                    "rank": 100,  # High rank for explicit chapter matches
                    "material": {
                        "id": pa.get("course_material_id"),
                        "name": material.get("file_name")
                    },
                    "course": {
                        "id": material.get("course_id"),
                        "title": course.get("title"),
                        "color": course.get("color_code")
                    }
                })
            
            # Sort by page number (prefer lower page numbers for multiple matches)
            chapter_results.sort(key=lambda x: x["page_number"])
            return chapter_results[:limit]
        
        # ============================================================
        # TIER 2: Full search (fallback when no chapter heading found)
        # ============================================================
        # Build the search query based on language
        # Using raw SQL via RPC for complex full-text search with joins
        
        if language == "de":
            search_sql = """
                SELECT 
                    pa.id,
                    pa.page_number,
                    pa.summary,
                    pa.key_terms,
                    cm.id as material_id,
                    cm.file_name as material_name,
                    c.id as course_id,
                    c.title as course_title,
                    c.color_code as course_color,
                    ts_rank(pa.search_vector_de, plainto_tsquery('german', $1)) as rank
                FROM page_analyses pa
                JOIN course_materials cm ON pa.course_material_id = cm.id
                JOIN courses c ON cm.course_id = c.id
                WHERE pa.user_id = $2
                AND pa.search_vector_de @@ plainto_tsquery('german', $1)
                ORDER BY rank DESC
                LIMIT $3
            """
        elif language == "en":
            search_sql = """
                SELECT 
                    pa.id,
                    pa.page_number,
                    pa.summary,
                    pa.key_terms,
                    cm.id as material_id,
                    cm.file_name as material_name,
                    c.id as course_id,
                    c.title as course_title,
                    c.color_code as course_color,
                    ts_rank(pa.search_vector_en, plainto_tsquery('english', $1)) as rank
                FROM page_analyses pa
                JOIN course_materials cm ON pa.course_material_id = cm.id
                JOIN courses c ON cm.course_id = c.id
                WHERE pa.user_id = $2
                AND pa.search_vector_en @@ plainto_tsquery('english', $1)
                ORDER BY rank DESC
                LIMIT $3
            """
        else:
            # Auto mode: search both German and English, take best rank
            search_sql = """
                SELECT DISTINCT ON (pa.id)
                    pa.id,
                    pa.page_number,
                    pa.summary,
                    pa.key_terms,
                    cm.id as material_id,
                    cm.file_name as material_name,
                    c.id as course_id,
                    c.title as course_title,
                    c.color_code as course_color,
                    GREATEST(
                        COALESCE(ts_rank(pa.search_vector_de, plainto_tsquery('german', $1)), 0),
                        COALESCE(ts_rank(pa.search_vector_en, plainto_tsquery('english', $1)), 0)
                    ) as rank
                FROM page_analyses pa
                JOIN course_materials cm ON pa.course_material_id = cm.id
                JOIN courses c ON cm.course_id = c.id
                WHERE pa.user_id = $2
                AND (
                    pa.search_vector_de @@ plainto_tsquery('german', $1)
                    OR pa.search_vector_en @@ plainto_tsquery('english', $1)
                )
                ORDER BY pa.id, rank DESC
            """
        
        # OPTIMIZED APPROACH: Use database-level filtering with JOINs
        # This is ~4x faster than fetching all data and filtering in Python
        # - Two queries: one for summary ILIKE, one for key_terms contains
        # - Results are merged to ensure comprehensive coverage
        # - JOINs get all related data in single round-trip per query
        
        # query_lower and stem already defined in Tier 1 above
        query_terms = query_lower.split()
        
        select_fields = (
            "id, page_number, summary, key_terms, course_material_id, "
            "course_materials(id, file_name, course_id, courses(id, title, color_code))"
        )
        
        # Query 1: Search summary with ILIKE using stem
        response1 = (
            client.table("page_analyses")
            .select(select_fields)
            .eq("user_id", user_id)
            .ilike("summary", f"%{stem}%")
            .execute()
        )
        
        # Query 2: Search key_terms with array contains for original term
        # This catches pages where key_terms mention the topic but summary doesn't
        # Try both original term and a capitalized version for German nouns
        term_capitalized = sanitized_query.capitalize() if sanitized_query else ""
        # Also try without last char for singular/plural (e.g., Klassendiagramm vs Klassendiagramme)
        term_base = sanitized_query[:-1] if len(sanitized_query) > 4 else sanitized_query
        term_base_cap = term_base.capitalize()
        
        # Build filter with original and base forms
        key_terms_filter = f'key_terms.cs.{{"{term_capitalized}"}}'
        if term_base_cap != term_capitalized:
            key_terms_filter += f',key_terms.cs.{{"{term_base_cap}"}}'
        
        response2 = (
            client.table("page_analyses")
            .select(select_fields)
            .eq("user_id", user_id)
            .or_(key_terms_filter)
            .execute()
        )
        
        # Merge results by id (deduplicate)
        merged = {}
        for r in (response1.data or []):
            merged[r["id"]] = r
        for r in (response2.data or []):
            if r["id"] not in merged:
                merged[r["id"]] = r
        
        if not merged:
            return []
        
        response_data = list(merged.values())
        
        # Score results using Python for refined relevance ranking
        # Use stem-based matching for cross-language support (works for any language mix)
        
        def extract_stems(text: str, min_len: int = 4) -> set:
            """Extract short stems from text for cross-language matching."""
            words = text.lower().replace("-", " ").split()
            stems = set()
            for word in words:
                # Remove common suffixes for better stem matching
                clean = word.rstrip("s").rstrip("e").rstrip("n")  # handles plurals (en/de)
                if len(clean) >= min_len:
                    # Take first 4-6 chars as stem (catches shared roots like sequenz/sequence)
                    stems.add(clean[:min(len(clean), 6)])
            return stems
        
        query_stems = extract_stems(query_lower)
        
        results = []
        for pa in response_data:
            summary = (pa.get("summary") or "").lower()
            key_terms = [kt.lower() for kt in (pa.get("key_terms") or [])]
            key_terms_text = " ".join(key_terms)
            key_terms_stems = extract_stems(key_terms_text)
            
            # Calculate relevance score with bidirectional and stem-based matching
            score = 0
            for term in query_terms:
                # Summary match (bidirectional for word stems)
                if term in summary or any(word.startswith(term[:min(len(term), 6)]) for word in summary.split() if len(word) >= 4):
                    score += 2
                # Key term match (bidirectional - term in kt OR kt in term)
                if any(term in kt or kt in term for kt in key_terms):
                    score += 3
                # Stem-based cross-language matching (e.g., "sequenz" matches "sequen" from "sequence")
                elif query_stems & key_terms_stems:
                    score += 3
                if term in key_terms_text:
                    score += 1
            
            if score > 0:
                # Extract joined data from nested structure
                material = pa.get("course_materials") or {}
                course = material.get("courses") or {}
                
                results.append({
                    "id": pa.get("id"),
                    "page_number": pa.get("page_number"),
                    "summary": pa.get("summary"),
                    "key_terms": pa.get("key_terms"),
                    "material_id": pa.get("course_material_id"),
                    "material_name": material.get("file_name"),
                    "course_id": material.get("course_id"),
                    "course_title": course.get("title"),
                    "course_color": course.get("color_code"),
                    "rank": score,
                    "material": {
                        "id": pa.get("course_material_id"),
                        "name": material.get("file_name")
                    },
                    "course": {
                        "id": material.get("course_id"),
                        "title": course.get("title"),
                        "color": course.get("color_code")
                    }
                })
        
        # Sort by rank descending and limit
        results.sort(key=lambda x: x["rank"], reverse=True)
        return results[:limit]
        
    except Exception as e:
        logger.error(f"Failed to search page analyses: {str(e)}")
        raise Exception(f"Failed to search page analyses: {str(e)}")


def search_page_analyses_multi(
    user_id: str,
    queries: List[str],
    language: str = "auto",
    limit: int = 10
) -> List[dict]:
    """
    Search across all page_analyses for a user using multiple keywords (OR logic).
    
    This function runs searches for each keyword and combines results with
    deduplication and relevance score aggregation. A page that matches multiple
    keywords gets a higher combined score.
    
    Args:
        user_id: User ID for authorization (RLS)
        queries: List of search query strings (keywords)
        language: Language for search - "de", "en", or "auto" (searches both)
        limit: Maximum number of results to return
        
    Returns:
        List of matching pages with context, deduplicated and ranked by combined relevance
    """
    if not queries:
        return []
    
    # Remove empty queries and duplicates while preserving order
    clean_queries = []
    seen = set()
    for q in queries:
        q_clean = q.strip().lower()
        if q_clean and q_clean not in seen:
            clean_queries.append(q.strip())
            seen.add(q_clean)
    
    if not clean_queries:
        return []
    
    # If only one query, use the original function
    if len(clean_queries) == 1:
        return search_page_analyses(user_id, clean_queries[0], language, limit)
    
    try:
        # Run search for each keyword and collect results
        all_results: dict = {}  # page_id -> result dict with aggregated score
        
        for query in clean_queries:
            try:
                results = search_page_analyses(
                    user_id=user_id,
                    query=query,
                    language=language,
                    limit=limit * 2  # Get more results per query for better coverage
                )
                
                for r in results:
                    page_id = r.get("id")
                    if not page_id:
                        continue
                    
                    if page_id in all_results:
                        # Page already found - aggregate scores
                        existing = all_results[page_id]
                        existing["rank"] = (existing.get("rank", 0) or 0) + (r.get("rank", 0) or 0)
                        existing["matched_queries"] = existing.get("matched_queries", 1) + 1
                    else:
                        # New page - add to results
                        r["matched_queries"] = 1
                        all_results[page_id] = r
                        
            except Exception as e:
                logger.warning(f"Search failed for query '{query}': {e}")
                continue
        
        if not all_results:
            return []
        
        # Convert to list and sort by:
        # 1. Number of matched queries (more = better)
        # 2. Aggregated rank score
        results_list = list(all_results.values())
        results_list.sort(
            key=lambda x: (
                x.get("matched_queries", 1),
                x.get("rank", 0) or 0
            ),
            reverse=True
        )
        
        return results_list[:limit]
        
    except Exception as e:
        logger.error(f"Failed to search page analyses with multiple queries: {str(e)}")
        raise Exception(f"Failed to search page analyses: {str(e)}")


def search_page_analyses_hybrid(
    user_id: str,
    query: str,
    query_embedding: List[float],
    language: str = "auto",
    limit: int = 10,
    vector_weight: float = 0.6,
    keyword_weight: float = 0.4
) -> List[dict]:
    """
    Hybrid search combining vector similarity and keyword full-text search.
    
    Uses Reciprocal Rank Fusion (RRF) to combine results from both search methods.
    This provides the best of both worlds:
    - Vector search catches semantically similar content
    - Keyword search catches exact term matches
    
    Args:
        user_id: User ID for authorization (RLS)
        query: Search query string for keyword search
        query_embedding: Query embedding vector for similarity search
        language: Language for FTS - "de", "en", or "auto"
        limit: Maximum number of results to return
        vector_weight: Weight for vector search results (default 0.6)
        keyword_weight: Weight for keyword search results (default 0.4)
        
    Returns:
        List of matching pages with combined relevance scores
    """
    if not query or not query.strip():
        return []
    
    client = get_supabase_client()
    
    try:
        # Fetch more results from each method for better fusion
        fetch_limit = limit * 3
        
        # 1. Vector similarity search (if embedding provided and available)
        vector_results = []
        if query_embedding and len(query_embedding) > 0:
            try:
                # Convert embedding to string format for pgvector
                embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"
                
                # Call the RPC function for vector search
                response = client.rpc(
                    "search_pages_by_embedding",
                    {
                        "p_user_id": user_id,
                        "p_query_embedding": embedding_str,
                        "p_limit": fetch_limit
                    }
                ).execute()
                
                if response.data:
                    vector_results = response.data
                    logger.debug(f"Vector search returned {len(vector_results)} results")
                    
            except Exception as e:
                # Vector search failed (maybe no embeddings yet) - continue with keyword only
                logger.debug(f"Vector search skipped: {e}")
        
        # 2. Keyword full-text search
        keyword_results = search_page_analyses(
            user_id=user_id,
            query=query,
            language=language,
            limit=fetch_limit
        )
        logger.debug(f"Keyword search returned {len(keyword_results)} results")
        
        # 3. Reciprocal Rank Fusion (RRF)
        # RRF score = sum(1 / (k + rank)) for each result list
        # k is a constant (typically 60) to prevent high-ranked items from dominating
        K = 60
        
        # Build score map: page_id -> (rrf_score, result_data)
        fusion_scores: dict = {}
        
        # Add vector results with their RRF contribution
        for rank, result in enumerate(vector_results):
            page_id = result.get("id")
            if not page_id:
                continue
            
            rrf_contribution = vector_weight * (1.0 / (K + rank + 1))
            
            if page_id in fusion_scores:
                fusion_scores[page_id]["rrf_score"] += rrf_contribution
                fusion_scores[page_id]["vector_rank"] = rank + 1
            else:
                fusion_scores[page_id] = {
                    "rrf_score": rrf_contribution,
                    "vector_rank": rank + 1,
                    "keyword_rank": None,
                    "data": result
                }
        
        # Add keyword results with their RRF contribution
        for rank, result in enumerate(keyword_results):
            page_id = result.get("id")
            if not page_id:
                continue
            
            rrf_contribution = keyword_weight * (1.0 / (K + rank + 1))
            
            if page_id in fusion_scores:
                fusion_scores[page_id]["rrf_score"] += rrf_contribution
                fusion_scores[page_id]["keyword_rank"] = rank + 1
                # Prefer keyword result data if we have both (has more fields)
                if "material_id" in result:
                    fusion_scores[page_id]["data"] = result
            else:
                fusion_scores[page_id] = {
                    "rrf_score": rrf_contribution,
                    "vector_rank": None,
                    "keyword_rank": rank + 1,
                    "data": result
                }
        
        if not fusion_scores:
            return []
        
        # 4. Sort by RRF score and build final results
        sorted_results = sorted(
            fusion_scores.values(),
            key=lambda x: x["rrf_score"],
            reverse=True
        )
        
        # Build output with combined rank
        final_results = []
        for entry in sorted_results[:limit]:
            result = entry["data"].copy()
            result["rank"] = entry["rrf_score"]
            result["vector_rank"] = entry["vector_rank"]
            result["keyword_rank"] = entry["keyword_rank"]
            final_results.append(result)
        
        return final_results
        
    except Exception as e:
        logger.error(f"Failed hybrid search: {str(e)}")
        # Fall back to keyword-only search
        return search_page_analyses(user_id, query, language, limit)


def check_embeddings_available(user_id: str) -> bool:
    """
    Check if any embeddings are available for a user's materials.
    
    Used to determine whether to use hybrid search or keyword-only.
    
    Args:
        user_id: User ID
        
    Returns:
        True if at least one page has embeddings
    """
    client = get_supabase_client()
    
    try:
        response = (
            client.table("page_analyses")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("embedding_status", "completed")
            .limit(1)
            .execute()
        )
        return (response.count or 0) > 0
    except Exception:
        return False


def get_user_course_counts(user_id: str) -> tuple[int, int]:
    """
    Get course and material counts for a user (lightweight query for Quick Chat initiate).
    
    Args:
        user_id: User ID for authorization (RLS)
        
    Returns:
        Tuple of (course_count, material_count)
    """
    client = get_supabase_client()
    
    try:
        # Count courses
        courses_response = (
            client.table("courses")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        course_count = courses_response.count or 0
        
        if course_count == 0:
            return (0, 0)
        
        # Count completed materials for this user's courses
        # Use a subquery via RPC or just get course IDs first
        course_ids = [c["id"] for c in (courses_response.data or [])]
        
        materials_response = (
            client.table("course_materials")
            .select("id", count="exact")
            .in_("course_id", course_ids)
            .eq("processing_status", "completed")
            .execute()
        )
        material_count = materials_response.count or 0
        
        return (course_count, material_count)
        
    except Exception as e:
        logger.error(f"Failed to get user course counts: {str(e)}")
        return (0, 0)  # Fail gracefully for counts


def get_user_courses_with_materials(user_id: str) -> List[dict]:
    """
    Get all courses and their materials for a user.
    
    Used by Quick Chat to show available courses/lectures.
    
    Args:
        user_id: User ID for authorization (RLS)
        
    Returns:
        List of courses with their materials:
        - course_id, course_title, course_color, course_description
        - materials: list of {material_id, material_name, page_count, has_summary}
        
    Raises:
        Exception: If database operation fails
    """
    client = get_supabase_client()
    
    try:
        # Get all courses for user
        courses_response = (
            client.table("courses")
            .select("id, title, description, color_code, exam_date")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
        )
        
        if not courses_response.data:
            return []
        
        course_ids = [c["id"] for c in courses_response.data]
        
        # Get all materials for these courses
        materials_response = (
            client.table("course_materials")
            .select("id, course_id, file_name, page_count, processing_status, summary")
            .in_("course_id", course_ids)
            .eq("processing_status", "completed")
            .order("created_at", desc=False)
            .execute()
        )
        
        # Group materials by course
        materials_by_course: Dict[str, list] = {}
        for m in (materials_response.data or []):
            course_id = m.get("course_id")
            if course_id not in materials_by_course:
                materials_by_course[course_id] = []
            materials_by_course[course_id].append({
                "material_id": m.get("id"),
                "material_name": m.get("file_name"),
                "page_count": m.get("page_count"),
                "has_summary": bool(m.get("summary"))
            })
        
        # Build result
        results = []
        for course in courses_response.data:
            results.append({
                "course_id": course.get("id"),
                "course_title": course.get("title"),
                "course_description": course.get("description"),
                "course_color": course.get("color_code"),
                "exam_date": course.get("exam_date"),
                "materials": materials_by_course.get(course.get("id"), [])
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to get user courses with materials: {str(e)}")
        raise Exception(f"Failed to get user courses with materials: {str(e)}")


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


def get_messages_for_pages_batch(
    page_ids: List[str],
    user_id: str
) -> Dict[str, List[dict]]:
    """
    Batch fetch messages for multiple pages in a single query.
    
    Performance optimization: Replaces N+1 queries with 2 queries total.
    Used during flashcard generation to prefetch all messages upfront.
    
    Args:
        page_ids: List of page analysis IDs (UUIDs)
        user_id: User ID for authorization (RLS)
        
    Returns:
        Dict mapping page_id -> list of message dicts
        Messages are ordered chronologically (oldest first) within each page
        
    Raises:
        Exception: If database operation fails
    """
    if not page_ids:
        return {}
    
    client = get_supabase_client()
    
    try:
        # Query all messages for the given page IDs in a single query
        response = (
            client.table("messages")
            .select("id, role, content, created_at, context_page_id, conversation_id")
            .in_("context_page_id", page_ids)
            .execute()
        )
        
        if not response.data:
            return {}
        
        # Get all unique conversation IDs
        conversation_ids = list(set(
            msg.get("conversation_id") for msg in response.data 
            if msg.get("conversation_id")
        ))
        
        if not conversation_ids:
            return {}
        
        # Validate ownership for all conversations in a single query
        conv_response = (
            client.table("conversations")
            .select("id")
            .in_("id", conversation_ids)
            .eq("user_id", user_id)
            .execute()
        )
        
        valid_conversation_ids = {conv["id"] for conv in (conv_response.data or [])}
        
        # Group messages by page_id, filtering for valid conversations
        messages_by_page: Dict[str, List[dict]] = {}
        
        for msg in response.data:
            if msg.get("conversation_id") not in valid_conversation_ids:
                continue
            
            page_id = msg.get("context_page_id")
            if page_id:
                if page_id not in messages_by_page:
                    messages_by_page[page_id] = []
                messages_by_page[page_id].append(msg)
        
        # Sort messages within each page by created_at (oldest first)
        for page_id in messages_by_page:
            messages_by_page[page_id].sort(key=lambda x: x.get("created_at", ""))
        
        return messages_by_page
    
    except Exception as e:
        raise Exception(f"Failed to batch fetch messages for pages: {str(e)}")


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
        
        # OPTIMIZED: Prepare all updates and execute in batches
        # Group updates by new deck name to minimize queries
        updates_by_id = {}
        for record in response.data:
            old_deck = record["deck_name"]
            new_deck = old_deck.replace(old_prefix, new_prefix, 1)
            updates_by_id[record["id"]] = new_deck
        
        # Execute updates in a single loop but using upsert pattern for efficiency
        # Note: Supabase doesn't support batch UPDATE with different values per row,
        # so we update in chunks to reduce connection overhead
        count = 0
        ids = list(updates_by_id.keys())
        
        # Update in batches of 50 to balance between connection overhead and atomicity
        batch_size = 50
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i + batch_size]
            for record_id in batch_ids:
                new_deck = updates_by_id[record_id]
                client.table("flashcard_cache").update(
                    {"deck_name": new_deck}
                ).eq("id", record_id).execute()
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
        # OPTIMIZED: Collect all inserts first, then batch insert
        to_insert = anki_note_ids - cached_note_ids
        insert_records = []
        
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
            
            insert_records.append({
                "user_id": user_id,
                "anki_note_id": note_id,
                "deck_name": deck_name,
                "front": front,
                "back": back,
                "tags": anki_note.get("tags", []),
                "anki_mod": anki_note.get("mod"),
                "course_id": course_id,
            })
        
        # Batch insert all new records
        if insert_records:
            try:
                # Insert in batches of 100 to avoid payload limits
                batch_size = 100
                for i in range(0, len(insert_records), batch_size):
                    batch = insert_records[i:i + batch_size]
                    client.table("flashcard_cache").insert(batch).execute()
                    stats["inserted"] += len(batch)
                logger.info(f"Batch inserted {stats['inserted']} new cards")
            except Exception as e:
                stats["errors"].append(f"Batch insert failed: {e}")
                logger.error(f"Batch insert failed: {e}")
        
        # 2. Find notes to UPDATE (mod timestamp changed)
        # Note: Updates still need to be individual as each has different values
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
    Get classification for a material (with in-memory caching).
    
    Classifications are cached for 1 hour since they rarely change.
    Cache is invalidated when classification is updated.
    
    Args:
        material_id: Course material ID
        user_id: User ID
        
    Returns:
        Dict with keys: classification, classification_confidence, 
        classification_reasoning, classification_override
        or None if not classified
    """
    # Check cache first
    cache_key = f"{material_id}:{user_id}"
    cached = _classification_cache.get(cache_key)
    if cached is not None:
        logger.debug(f"Classification cache HIT for material {material_id[:8]}...")
        return cached
    
    # Cache miss - fetch from database
    client = get_supabase_client()
    try:
        response = client.table("course_materials").select(
            "classification, classification_confidence, classification_reasoning, classification_override"
        ).eq("id", material_id).eq("user_id", user_id).single().execute()
        
        if response.data and response.data.get("classification"):
            # Cache the result
            _classification_cache.set(cache_key, response.data)
            logger.debug(f"Classification cache MISS for material {material_id[:8]}... (now cached)")
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
    
    Invalidates the classification cache for this material.
    
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
        
        # Invalidate cache for all user variants of this material
        # Since we don't know the user_id here, we'll clear any cached entry
        # that starts with this material_id
        for key in list(_classification_cache._cache.keys()):
            if key.startswith(f"{material_id}:"):
                _classification_cache.invalidate(key)
        
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

