from fastapi import APIRouter, UploadFile, File, Response, Request, HTTPException, Query
from pydantic import BaseModel
from app.services.dataset_service import handle_upload, load_dataframe
from app.core.session import get_session
from app.core.config import settings

router = APIRouter()


class SelectDatasetRequest(BaseModel):
    filename: str



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


@router.post("/upload/select")
async def select_dataset(req: SelectDatasetRequest, response: Response):
    """
    Switch the active dataset session to the one matching the given filename.
    """
    from app.core.session import _store
    # Find session with matching filename
    target_session = None
    for session in _store.values():
        if session.filename == req.filename:
            target_session = session
            break

    if not target_session:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset {req.filename} session not found. Please upload it again.",
        )

    response.set_cookie(
        key="session_id",
        value=target_session.session_id,
        httponly=True,
        samesite="lax",
        max_age=settings.SESSION_TTL_MINUTES * 60,
    )
    return {
        "filename": target_session.filename,
        "row_count": target_session.row_count,
        "column_count": len(target_session.columns),
        "columns": target_session.columns,
        "dtypes": target_session.dtypes,
        "sample": target_session.sample_rows,
    }


@router.get("/upload/preview")
async def preview_dataset(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
):
    """
    Return a paginated slice of the uploaded dataset as JSON rows.
    Used by the frontend dataset viewer panel.
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="No active session")
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    df = load_dataframe(session)
    total = len(df)
    start = (page - 1) * page_size
    end = min(start + page_size, total)
    slice_df = df.iloc[start:end].fillna("")

    return {
        "filename": session.filename,
        "columns": session.columns,
        "total_rows": total,
        "page": page,
        "page_size": page_size,
        "rows": slice_df.to_dict(orient="records"),
    }