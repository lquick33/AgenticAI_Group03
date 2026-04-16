import logging

from fastapi import APIRouter, File, Form, HTTPException, Path, Query, UploadFile
from pdf2image import pdfinfo_from_bytes

from app.adapters.supabase.client import get_supabase_client
from app.core.adapters import get_course, get_file_storage, get_material, get_page_analysis
from app.models.schemas import (
    MaterialResponse,
    MaterialUpdateRequest,
    PageAnalysisDataResponse,
    UploadResponse,
)
from app.services.pdf_processor import process_pdf_task

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload", response_model=UploadResponse, status_code=200)
async def upload_pdf(
    file: UploadFile = File(...),
    user_id: str | None = Form(None),
    userId: str | None = Form(None),
    course_id: str | None = Form(None),
    courseId: str | None = Form(None),
) -> UploadResponse:
    """
    Upload a PDF and queue asynchronous processing.

    Supports both snake_case and camelCase form fields for compatibility.
    """
    resolved_user_id = user_id or userId
    resolved_course_id = course_id or courseId

    if not resolved_user_id or not resolved_course_id:
        raise HTTPException(
            status_code=400,
            detail="user_id (or userId) and course_id (or courseId) are required.",
        )

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    try:
        if not get_course().validate_user_exists(resolved_user_id):
            raise HTTPException(
                status_code=404, detail="User not found. Please sign up first."
            )

        # Validate that course belongs to user.
        try:
            get_course().get(user_id=resolved_user_id, course_id=resolved_course_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        try:
            page_count = int(pdfinfo_from_bytes(file_bytes)["Pages"])
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail=f"Failed to read PDF info: {exc}"
            ) from exc

        if page_count <= 0:
            raise HTTPException(status_code=400, detail="PDF contains no pages")

        storage_path = get_file_storage().upload(
            file_bytes=file_bytes,
            filename=file.filename,
            user_id=resolved_user_id,
        )

        material = get_material().create(
            course_id=resolved_course_id,
            filename=file.filename,
            file_path=storage_path,
            user_id=resolved_user_id,
            page_count=page_count,
            file_type="pdf",
        )

        process_pdf_task.delay(
            material_id=material["id"],
            user_id=resolved_user_id,
            course_id=resolved_course_id,
            file_path=storage_path,
            max_concurrent=5,
        )

        return UploadResponse(
            message="PDF upload successful. Processing started in background.",
            course_material_id=material["id"],
            page_count=page_count,
            pages_analyzed=0,
            status="queued",
            error_message=None,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error processing upload: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process file: {exc}")


@router.get("/page-analysis", response_model=PageAnalysisDataResponse, status_code=200)
async def get_page_analysis_endpoint(
    course_material_id: str = Query(...),
    user_id: str = Query(...),
    page_number: int | None = Query(None),
    page: int | None = Query(None),
) -> PageAnalysisDataResponse:
    resolved_page = page_number if page_number is not None else page
    if resolved_page is None:
        raise HTTPException(status_code=400, detail="page_number (or page) is required.")

    try:
        if not get_course().validate_user_exists(user_id):
            raise HTTPException(
                status_code=404, detail="User not found. Please sign up first."
            )

        analysis = get_page_analysis().get(
            course_material_id=course_material_id,
            page_number=resolved_page,
            user_id=user_id,
        )
        return PageAnalysisDataResponse(**analysis)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error retrieving page analysis: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve: {exc}")


@router.put("/materials/{material_id}", response_model=MaterialResponse, status_code=200)
async def update_material(
    material_update: MaterialUpdateRequest,
    material_id: str = Path(...),
    user_id: str = Query(...),
) -> MaterialResponse:
    try:
        if not get_course().validate_user_exists(user_id):
            raise HTTPException(
                status_code=404, detail="User not found. Please sign up first."
            )

        client = get_supabase_client()
        material_response = (
            client.table("course_materials")
            .select("*")
            .eq("id", material_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        if not material_response.data:
            raise HTTPException(
                status_code=404,
                detail="Course material not found or access denied",
            )

        update_data = {}
        if material_update.file_name is not None:
            if not material_update.file_name.strip():
                raise HTTPException(status_code=400, detail="Filename cannot be empty")
            update_data["file_name"] = material_update.file_name.strip()

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided for update")

        updated_response = (
            client.table("course_materials")
            .update(update_data)
            .eq("id", material_id)
            .eq("user_id", user_id)
            .execute()
        )
        if updated_response.data and len(updated_response.data) > 0:
            return MaterialResponse(**updated_response.data[0])
        raise HTTPException(status_code=500, detail="Failed to update material")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error updating material %s: %s", material_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update material: {exc}")


@router.delete("/materials/{material_id}", status_code=200)
async def delete_material(
    material_id: str = Path(...),
    user_id: str = Query(...),
):
    try:
        if not get_course().validate_user_exists(user_id):
            raise HTTPException(
                status_code=404, detail="User not found. Please sign up first."
            )

        get_material().delete(material_id, user_id)
        return {"status": "success", "message": "Material deleted successfully"}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error deleting material %s: %s", material_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete material: {exc}")
