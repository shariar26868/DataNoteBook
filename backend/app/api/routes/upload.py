from fastapi import APIRouter, UploadFile, File, Response
from app.services.dataset_service import handle_upload
from app.core.config import settings

router = APIRouter()


@router.post("/upload")
async def upload_dataset(file: UploadFile = File(...), response: Response = None):
    """
    Upload a CSV or XLSX file.
    Returns dataset metadata and stores session in a secure backend cookie.
    """
    session = await handle_upload(file)
    response.set_cookie(
        key="session_id",
        value=session.session_id,
        httponly=True,
        samesite="lax",
        max_age=settings.SESSION_TTL_MINUTES * 60,
    )
    return {
        "filename": session.filename,
        "row_count": session.row_count,
        "column_count": len(session.columns),
        "columns": session.columns,
        "dtypes": session.dtypes,
        "sample": session.sample_rows,
    }