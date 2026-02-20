"""
Supabase Course adapter.

Implements CourseRepository using Supabase Postgres.

Extracted from app.services.storage (lines 408–493, 1572–1690, 3077–3113).
"""

import logging
from typing import Dict, List, Optional, Tuple

from supabase import Client

from app.adapters.supabase.client import retry_on_resource_unavailable

logger = logging.getLogger(__name__)


# -- Internal retryable queries ------------------------------------------------


@retry_on_resource_unavailable(max_retries=3, base_delay=0.1, max_delay=2.0)
def _query_user_exists(client: Client, user_id: str) -> bool:
    """Internal function to query if user exists (with retry logic)."""
    response = (
        client.table("profiles").select("id").eq("id", user_id).execute()
    )
    return response.data and len(response.data) > 0


@retry_on_resource_unavailable(max_retries=3, base_delay=0.1, max_delay=2.0)
def _query_course(
    client: Client, user_id: str, course_id: str
) -> Optional[dict]:
    """Internal function to query course (with retry logic)."""
    response = (
        client.table("courses")
        .select("*")
        .eq("id", course_id)
        .eq("user_id", user_id)
        .execute()
    )
    return response.data[0] if response.data and len(response.data) > 0 else None


class SupabaseCourseAdapter:
    """
    Concrete CourseRepository backed by Supabase Postgres.

    Handles course retrieval, user validation, and course-material aggregation.
    """

    def __init__(self, client: Client) -> None:
        self._client = client

    # -- CourseRepository Protocol ---------------------------------------------

    def validate_user_exists(self, user_id: str) -> bool:
        """
        Validate that user exists in profiles table.

        Note: Thanks to the SQL trigger, profiles are automatically synced
        with auth.users, so this check works reliably.

        Args:
            user_id: User ID to validate

        Returns:
            True if user exists, False otherwise

        Raises:
            Exception: If database query fails after retries
        """
        try:
            return _query_user_exists(self._client, user_id)
        except Exception as e:
            raise Exception(f"Failed to validate user: {str(e)}")

    def get(self, user_id: str, course_id: str) -> dict:
        """
        Get existing course and validate it belongs to user.

        Args:
            user_id: User ID
            course_id: Course ID (required)

        Returns:
            Course record as dict

        Raises:
            ValueError: If course doesn't exist or doesn't belong to user
            Exception: If database operation fails after retries
        """
        try:
            result = _query_course(self._client, user_id, course_id)

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

    def get_with_materials(
        self, user_id: str, course_id: str
    ) -> Optional[dict]:
        """
        Get a course with all its materials.

        Args:
            user_id: User ID
            course_id: Course ID

        Returns:
            Course dict with 'materials' list, or None if not found
        """
        try:
            course_response = (
                self._client.table("courses")
                .select("*")
                .eq("id", course_id)
                .eq("user_id", user_id)
                .single()
                .execute()
            )

            if not course_response.data:
                return None

            course = course_response.data

            materials_response = (
                self._client.table("course_materials")
                .select("id, file_name, file_type, page_count, processing_status")
                .eq("course_id", course_id)
                .eq("user_id", user_id)
                .order("created_at")
                .execute()
            )

            course["materials"] = materials_response.data or []

            return course
        except Exception as e:
            logger.error(f"Error getting course with materials: {e}")
            return None

    def get_counts(self, user_id: str) -> Tuple[int, int]:
        """
        Get course and material counts for a user (lightweight query).

        Args:
            user_id: User ID for authorization (RLS)

        Returns:
            Tuple of (course_count, material_count)
        """
        try:
            courses_response = (
                self._client.table("courses")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .execute()
            )
            course_count = courses_response.count or 0

            if course_count == 0:
                return (0, 0)

            course_ids = [c["id"] for c in (courses_response.data or [])]

            materials_response = (
                self._client.table("course_materials")
                .select("id", count="exact")
                .in_("course_id", course_ids)
                .eq("processing_status", "completed")
                .execute()
            )
            material_count = materials_response.count or 0

            return (course_count, material_count)

        except Exception as e:
            logger.error(f"Failed to get user course counts: {str(e)}")
            return (0, 0)

    def get_all_with_materials(self, user_id: str) -> List[dict]:
        """
        Get all courses and their materials for a user.

        Used by Quick Chat to show available courses/lectures.

        Args:
            user_id: User ID for authorization (RLS)

        Returns:
            List of courses with nested materials list

        Raises:
            Exception: If database operation fails
        """
        try:
            courses_response = (
                self._client.table("courses")
                .select("id, title, description, color_code, exam_date")
                .eq("user_id", user_id)
                .order("updated_at", desc=True)
                .execute()
            )

            if not courses_response.data:
                return []

            course_ids = [c["id"] for c in courses_response.data]

            materials_response = (
                self._client.table("course_materials")
                .select("id, course_id, file_name, page_count, processing_status, summary")
                .in_("course_id", course_ids)
                .eq("processing_status", "completed")
                .order("created_at", desc=False)
                .execute()
            )

            # Group materials by course
            materials_by_course: Dict[str, list] = {}
            for m in materials_response.data or []:
                cid = m.get("course_id")
                if cid not in materials_by_course:
                    materials_by_course[cid] = []
                materials_by_course[cid].append({
                    "material_id": m.get("id"),
                    "material_name": m.get("file_name"),
                    "page_count": m.get("page_count"),
                    "has_summary": bool(m.get("summary")),
                })

            results = []
            for course in courses_response.data:
                results.append({
                    "course_id": course.get("id"),
                    "course_title": course.get("title"),
                    "course_description": course.get("description"),
                    "course_color": course.get("color_code"),
                    "exam_date": course.get("exam_date"),
                    "materials": materials_by_course.get(course.get("id"), []),
                })

            return results

        except Exception as e:
            logger.error(f"Failed to get user courses with materials: {str(e)}")
            raise Exception(f"Failed to get user courses with materials: {str(e)}")
