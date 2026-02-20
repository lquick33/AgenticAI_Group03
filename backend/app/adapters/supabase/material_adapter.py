"""
Supabase Material adapter.

Implements MaterialRepository using Supabase Postgres.

Extracted from app.services.storage (lines 98–248, 336–405, 812–984, 2619–2837).
"""

import json
import logging
from time import time
from typing import Dict, List, Optional, Any, Tuple

from supabase import Client

from app.adapters.supabase.client import retry_on_resource_unavailable

logger = logging.getLogger(__name__)


# =============================================================================
# In-Memory Caches (co-located with the adapter that owns them)
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
        """Get cached classification. Returns None if missing or expired."""
        if material_id in self._cache:
            data, timestamp = self._cache[material_id]
            if time() - timestamp < self._ttl:
                return data
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
        """Get cached summary. Returns None if missing or expired."""
        key = f"{material_id}:{user_id}"
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time() - timestamp < self._ttl:
                return data
            del self._cache[key]
        return None

    def set(
        self, material_id: str, user_id: str, summary: Dict[str, Any]
    ) -> None:
        """Cache a summary."""
        key = f"{material_id}:{user_id}"
        self._cache[key] = (summary, time())

    def invalidate(self, material_id: str) -> None:
        """Remove all cached summaries for a material."""
        keys_to_delete = [
            k for k in self._cache.keys() if k.startswith(f"{material_id}:")
        ]
        for key in keys_to_delete:
            del self._cache[key]

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()


# -- Internal retryable queries ------------------------------------------------


@retry_on_resource_unavailable(max_retries=3, base_delay=0.1, max_delay=2.0)
def _query_course_material_summary(
    client: Client, course_material_id: str, user_id: str
) -> Optional[str]:
    """Internal function to query course material summary (with retry logic)."""
    response = (
        client.table("course_materials")
        .select("summary")
        .eq("id", course_material_id)
        .eq("user_id", user_id)
        .execute()
    )
    if response.data and len(response.data) > 0:
        return response.data[0].get("summary")
    return None


# =============================================================================
# Adapter
# =============================================================================


class SupabaseMaterialAdapter:
    """
    Concrete MaterialRepository backed by Supabase Postgres.

    Handles material CRUD, processing status, summary/classification management,
    and cascading deletion of associated resources.
    """

    def __init__(self, client: Client) -> None:
        self._client = client
        self._classification_cache = ClassificationCache()
        self._summary_cache = SummaryCache()

    # -- MaterialRepository Protocol -------------------------------------------

    def create(
        self,
        course_id: str,
        filename: str,
        file_path: str,
        user_id: str,
        page_count: int,
        file_type: str = "pdf",
    ) -> dict:
        """
        Create a course_material record in the database.

        Returns:
            Created course_material record as dict
        """
        try:
            response = (
                self._client.table("course_materials")
                .insert(
                    {
                        "course_id": course_id,
                        "user_id": user_id,
                        "file_name": filename,
                        "file_path": file_path,
                        "file_type": file_type,
                        "page_count": page_count,
                        "processing_status": "uploading",
                    }
                )
                .execute()
            )

            if response.data and len(response.data) > 0:
                return response.data[0]
            else:
                raise Exception("Failed to create course_material record")
        except Exception as e:
            raise Exception(f"Failed to create course_material: {str(e)}")

    def update_status(
        self,
        material_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update the processing status of a course material.

        Args:
            material_id: Course material ID
            status: New status ("uploading", "processing", "completed", "error")
            error_message: Optional error message if status is "error"
        """
        update_data: Dict[str, Any] = {"processing_status": status}
        if error_message:
            update_data["error_message"] = error_message

        try:
            (
                self._client.table("course_materials")
                .update(update_data)
                .eq("id", material_id)
                .execute()
            )
        except Exception as e:
            raise Exception(f"Failed to update processing status: {str(e)}")

    def update_summary(self, material_id: str, summary: str) -> None:
        """
        Update the global summary field of a course material.

        Args:
            material_id: Course material ID
            summary: JSON-encoded summary string
        """
        try:
            (
                self._client.table("course_materials")
                .update({"summary": summary})
                .eq("id", material_id)
                .execute()
            )
        except Exception as e:
            raise Exception(
                f"Failed to update course material summary: {str(e)}"
            )

    def update_filename(self, material_id: str, filename: str) -> None:
        """
        Update the file_name field in the course_materials table.

        Args:
            material_id: Course material ID
            filename: New filename (without file extension)
        """
        try:
            (
                self._client.table("course_materials")
                .update({"file_name": filename})
                .eq("id", material_id)
                .execute()
            )
            logger.info(
                f"Updated filename for material {material_id} to: {filename}"
            )
        except Exception as e:
            raise Exception(
                f"Failed to update course material filename: {str(e)}"
            )

    def get_filename(
        self, material_id: str, user_id: str
    ) -> Optional[str]:
        """Get the current filename of a course material."""
        try:
            response = (
                self._client.table("course_materials")
                .select("file_name")
                .eq("id", material_id)
                .eq("user_id", user_id)
                .single()
                .execute()
            )
            if response.data:
                return response.data.get("file_name")
            return None
        except Exception as e:
            logger.warning(
                f"Failed to get course material filename: {str(e)}"
            )
            return None

    def get_for_naming(
        self,
        course_id: str,
        user_id: str,
        exclude_material_id: Optional[str] = None,
    ) -> List[dict]:
        """
        Get existing course materials to detect naming patterns.

        Args:
            course_id: Course ID
            user_id: User ID for authorization
            exclude_material_id: Material ID to exclude (the one being renamed)

        Returns:
            List of material dicts with file_name field
        """
        try:
            query = (
                self._client.table("course_materials")
                .select("id, file_name")
                .eq("course_id", course_id)
                .eq("user_id", user_id)
            )

            if exclude_material_id:
                query = query.neq("id", exclude_material_id)

            response = query.order("created_at", ascending=True).execute()
            return response.data if response.data else []
        except Exception as e:
            logger.warning(
                f"Failed to get course materials for naming pattern: {str(e)}"
            )
            return []

    def get_summary(
        self, course_material_id: str, user_id: str
    ) -> Optional[dict]:
        """
        Get the summary field from a course_material record (with caching).

        Summaries are cached for 10 minutes since they rarely change.

        Returns:
            Parsed summary as dict, or None if not found or empty
        """
        # Check cache first
        cached = self._summary_cache.get(course_material_id, user_id)
        if cached is not None:
            logger.debug(
                f"Summary cache HIT for material {course_material_id[:8]}..."
            )
            return cached

        try:
            summary_text = _query_course_material_summary(
                self._client, course_material_id, user_id
            )

            if not summary_text:
                return None

            # Try to parse as JSON
            try:
                result = json.loads(summary_text)
            except json.JSONDecodeError:
                result = {
                    "summary_text": summary_text,
                    "format": "plain_text",
                }

            # Cache the result
            self._summary_cache.set(course_material_id, user_id, result)
            logger.debug(
                f"Summary cache MISS for material "
                f"{course_material_id[:8]}... (now cached)"
            )
            return result
        except Exception as e:
            raise Exception(
                f"Failed to get course material summary: {str(e)}"
            )

    def get_classification(
        self, material_id: str, user_id: str
    ) -> Optional[dict]:
        """
        Get classification for a material (with caching).

        Classifications are cached for 1 hour since they rarely change.

        Returns:
            Dict with classification keys, or None if not classified
        """
        cache_key = f"{material_id}:{user_id}"
        cached = self._classification_cache.get(cache_key)
        if cached is not None:
            logger.debug(
                f"Classification cache HIT for material {material_id[:8]}..."
            )
            return cached

        try:
            response = (
                self._client.table("course_materials")
                .select(
                    "classification, classification_confidence, "
                    "classification_reasoning, classification_override"
                )
                .eq("id", material_id)
                .eq("user_id", user_id)
                .single()
                .execute()
            )

            if response.data and response.data.get("classification"):
                self._classification_cache.set(cache_key, response.data)
                logger.debug(
                    f"Classification cache MISS for material "
                    f"{material_id[:8]}... (now cached)"
                )
                return response.data
            return None
        except Exception as e:
            logger.error(f"Error getting classification: {e}")
            return None

    def update_classification(
        self,
        material_id: str,
        classification: str,
        confidence: float,
        reasoning: str,
        override: bool = False,
    ) -> None:
        """
        Update classification for a material.

        Invalidates the classification cache for this material.
        """
        try:
            (
                self._client.table("course_materials")
                .update(
                    {
                        "classification": classification,
                        "classification_confidence": confidence,
                        "classification_reasoning": reasoning,
                        "classification_override": override,
                    }
                )
                .eq("id", material_id)
                .execute()
            )

            # Invalidate cache for all user variants of this material
            for key in list(self._classification_cache._cache.keys()):
                if key.startswith(f"{material_id}:"):
                    self._classification_cache.invalidate(key)

            logger.info(
                f"Updated classification for material {material_id}: "
                f"{classification}"
            )
        except Exception as e:
            logger.error(f"Error updating classification: {e}")
            raise

    def delete(
        self,
        material_id: str,
        user_id: str,
        get_all_page_analyses_fn=None,
    ) -> None:
        """
        Delete a course material and all associated data.

        Steps:
            1. Retrieves material record (validates ownership)
            2. Deletes flashcards specific to this material (via page_analyses)
            3. Deletes any stored Anki APKG files
            4. Deletes the PDF file from Supabase Storage
            5. Deletes the material record (cascading page_analyses, snippets)

        Args:
            material_id: Course material ID (UUID)
            user_id: User ID (UUID) for authorization
            get_all_page_analyses_fn: Optional callable to get page analyses
                (defaults to SupabasePageAnalysisAdapter if not provided)

        Raises:
            ValueError: If material not found or access denied
            Exception: If deletion fails
        """
        try:
            # Get material record to validate ownership
            material_response = (
                self._client.table("course_materials")
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

            # 1. Delete flashcards specific to this material
            try:
                if get_all_page_analyses_fn:
                    page_analyses = get_all_page_analyses_fn(
                        material_id, user_id
                    )
                else:
                    # Fallback: query page analyses directly
                    pa_response = (
                        self._client.table("page_analyses")
                        .select("id")
                        .eq("course_material_id", material_id)
                        .eq("user_id", user_id)
                        .execute()
                    )
                    page_analyses = pa_response.data or []

                page_analysis_ids = [
                    pa.get("id") for pa in page_analyses if pa.get("id")
                ]

                if page_analysis_ids:
                    flashcards_response = (
                        self._client.table("flashcards")
                        .select("id")
                        .eq("user_id", user_id)
                        .in_("source_page_analysis_id", page_analysis_ids)
                        .execute()
                    )

                    if flashcards_response.data:
                        flashcard_ids = [
                            fc.get("id")
                            for fc in flashcards_response.data
                            if fc.get("id")
                        ]
                        if flashcard_ids:
                            (
                                self._client.table("flashcards")
                                .delete()
                                .in_("id", flashcard_ids)
                                .execute()
                            )
                            logger.info(
                                f"✅ Deleted {len(flashcard_ids)} flashcards "
                                f"for material {material_id}"
                            )
            except Exception as e:
                logger.warning(
                    f"Failed to delete flashcards for material "
                    f"{material_id}: {e}"
                )

            # 2. Delete any stored Anki APKG files
            try:
                user_folder = f"{user_id}/"
                try:
                    files_response = self._client.storage.from_(
                        "course_materials"
                    ).list(user_folder)

                    if files_response:
                        apkg_files_to_delete = []
                        for file_info in files_response:
                            file_name = file_info.get("name", "")
                            if file_name.endswith(".apkg") and (
                                material_id in file_name
                                or "flashcards_" in file_name.lower()
                            ):
                                apkg_path = (
                                    f"{user_folder}{file_name}"
                                    if not file_name.startswith(user_folder)
                                    else file_name
                                )
                                apkg_files_to_delete.append(apkg_path)

                        if apkg_files_to_delete:
                            self._client.storage.from_(
                                "course_materials"
                            ).remove(apkg_files_to_delete)
                            logger.info(
                                f"✅ Deleted {len(apkg_files_to_delete)} "
                                f"APKG files for material {material_id}"
                            )
                except Exception as e:
                    logger.debug(
                        f"No APKG files found or listing failed for "
                        f"material {material_id}: {e}"
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to delete APKG files for material "
                    f"{material_id}: {e}"
                )

            # 3. Delete the PDF file from Supabase Storage
            if file_path:
                try:
                    self._client.storage.from_("course_materials").remove(
                        [file_path]
                    )
                    logger.info(
                        f"✅ Deleted PDF file from storage: {file_path}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to delete PDF file from storage "
                        f"{file_path}: {e}"
                    )

            # 4. Delete material record (cascades page_analyses, snippets)
            delete_response = (
                self._client.table("course_materials")
                .delete()
                .eq("id", material_id)
                .eq("user_id", user_id)
                .execute()
            )

            if not delete_response.data:
                raise ValueError(
                    "Failed to delete material record from database"
                )

            logger.info(
                f"✅ Successfully deleted course material {material_id}"
            )

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Error deleting course material {material_id}: {str(e)}",
                exc_info=True,
            )
            raise Exception(
                f"Failed to delete course material: {str(e)}"
            )
