import logging
from typing import List

from fastapi import APIRouter, HTTPException, Path, Query

from app.adapters.supabase.client import get_supabase_client
from app.core.adapters import get_course
from app.models.schemas import CourseResponse, CourseUpdateRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/courses", response_model=List[CourseResponse], status_code=200)
async def list_courses(user_id: str = Query(...)) -> List[CourseResponse]:
    try:
        if not get_course().validate_user_exists(user_id):
            raise HTTPException(
                status_code=404, detail="User not found. Please sign up first."
            )

        response = (
            get_supabase_client()
            .table("courses")
            .select("*")
            .eq("user_id", user_id)
            .order("updated_at", desc=False)
            .execute()
        )
        return [CourseResponse(**course) for course in (response.data or [])]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error fetching courses: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch courses: {exc}")


@router.get("/courses/{course_id}", response_model=CourseResponse, status_code=200)
async def get_single_course(
    course_id: str = Path(...),
    user_id: str = Query(...),
) -> CourseResponse:
    try:
        course_data = get_course().get(user_id=user_id, course_id=course_id)
        return CourseResponse(**course_data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Error fetching course %s: %s", course_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch course: {exc}")


@router.post("/courses", response_model=CourseResponse, status_code=201)
async def create_course(
    course_data: CourseUpdateRequest,
    user_id: str = Query(...),
) -> CourseResponse:
    try:
        if not get_course().validate_user_exists(user_id):
            raise HTTPException(
                status_code=404, detail="User not found. Please sign up first."
            )

        if not course_data.title:
            raise HTTPException(status_code=400, detail="Title is required")

        insert_data = {"user_id": user_id, "title": course_data.title}
        if course_data.description is not None:
            insert_data["description"] = course_data.description
        if course_data.exam_date is not None:
            insert_data["exam_date"] = (
                course_data.exam_date if course_data.exam_date else None
            )
        if course_data.color_code is not None:
            insert_data["color_code"] = course_data.color_code

        response = get_supabase_client().table("courses").insert(insert_data).execute()
        if response.data and len(response.data) > 0:
            return CourseResponse(**response.data[0])

        raise HTTPException(status_code=500, detail="Failed to create course")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error creating course: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create course: {exc}")


@router.put("/courses/{course_id}", response_model=CourseResponse, status_code=200)
async def update_course(
    course_update: CourseUpdateRequest,
    course_id: str = Path(...),
    user_id: str = Query(...),
) -> CourseResponse:
    try:
        # Validate ownership first.
        get_course().get(user_id=user_id, course_id=course_id)

        update_data = {}
        if course_update.title is not None:
            update_data["title"] = course_update.title
        if course_update.description is not None:
            update_data["description"] = course_update.description
        if course_update.exam_date is not None:
            update_data["exam_date"] = (
                course_update.exam_date if course_update.exam_date else None
            )
        if course_update.color_code is not None:
            update_data["color_code"] = course_update.color_code

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided for update")

        response = (
            get_supabase_client()
            .table("courses")
            .update(update_data)
            .eq("id", course_id)
            .eq("user_id", user_id)
            .execute()
        )
        if response.data and len(response.data) > 0:
            return CourseResponse(**response.data[0])

        raise HTTPException(status_code=500, detail="Failed to update course")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error updating course %s: %s", course_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update course: {exc}")
