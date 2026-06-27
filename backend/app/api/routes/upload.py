# from fastapi import APIRouter, UploadFile, File, Response, Request, HTTPException, Query
# from pydantic import BaseModel
# from app.services.dataset_service import handle_upload, load_dataframe
# from app.core.session import get_session
# from app.core.config import settings

# router = APIRouter()


# class SelectDatasetRequest(BaseModel):
#     filename: str



# @router.post("/upload")
# async def upload_dataset(file: UploadFile = File(...), response: Response = None):
#     """
#     Upload a CSV or XLSX file.
#     Returns dataset metadata and stores session in a secure backend cookie.
#     """
#     session = await handle_upload(file)
#     response.set_cookie(
#         key="session_id",
#         value=session.session_id,
#         httponly=True,
#         samesite="lax",
#         max_age=settings.SESSION_TTL_MINUTES * 60,
#     )
#     return {
#         "filename": session.filename,
#         "row_count": session.row_count,
#         "column_count": len(session.columns),
#         "columns": session.columns,
#         "dtypes": session.dtypes,
#         "sample": session.sample_rows,
#     }


# @router.post("/upload/select")
# async def select_dataset(req: SelectDatasetRequest, response: Response):
#     """
#     Switch the active dataset session to the one matching the given filename.
#     """
#     from app.core.session import _store
#     # Find session with matching filename
#     target_session = None
#     for session in _store.values():
#         if session.filename == req.filename:
#             target_session = session
#             break

#     if not target_session:
#         raise HTTPException(
#             status_code=404,
#             detail=f"Dataset {req.filename} session not found. Please upload it again.",
#         )

#     response.set_cookie(
#         key="session_id",
#         value=target_session.session_id,
#         httponly=True,
#         samesite="lax",
#         max_age=settings.SESSION_TTL_MINUTES * 60,
#     )
#     return {
#         "filename": target_session.filename,
#         "row_count": target_session.row_count,
#         "column_count": len(target_session.columns),
#         "columns": target_session.columns,
#         "dtypes": target_session.dtypes,
#         "sample": target_session.sample_rows,
#     }


# @router.get("/upload/preview")
# async def preview_dataset(
#     request: Request,
#     page: int = Query(1, ge=1),
#     page_size: int = Query(100, ge=1, le=500),
# ):
#     """
#     Return a paginated slice of the uploaded dataset as JSON rows.
#     Used by the frontend dataset viewer panel.
#     """
#     session_id = request.cookies.get("session_id")
#     if not session_id:
#         raise HTTPException(status_code=401, detail="No active session")
#     session = get_session(session_id)
#     if not session:
#         raise HTTPException(status_code=404, detail="Session not found")

#     df = load_dataframe(session)
#     total = len(df)
#     start = (page - 1) * page_size
#     end = min(start + page_size, total)
#     slice_df = df.iloc[start:end].fillna("")

#     return {
#         "filename": session.filename,
#         "columns": session.columns,
#         "total_rows": total,
#         "page": page,
#         "page_size": page_size,
#         "rows": slice_df.to_dict(orient="records"),
#     }








import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Response, Request, HTTPException, Query, Header
from pydantic import BaseModel
from app.services.dataset_service import handle_upload, load_dataframe
from app.core.session import get_session
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


class SelectDatasetRequest(BaseModel):
    filename: str


@router.post("/upload")
async def upload_dataset(file: UploadFile = File(...), response: Response = None):
    """
    Upload a CSV or XLSX file.
    Returns dataset metadata and stores session in a secure backend cookie.
    
    Returns:
      - 200 OK with dataset metadata
      - 400 Bad Request if file type not supported
      - 422 Unprocessable Entity if file can't be parsed
      - 500 Internal Server Error if Azure upload fails
    """
    try:
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
    
    except HTTPException:
        # Re-raise HTTPException (already has proper status code)
        raise
    
    except RuntimeError as e:
        # Dataset initialization failed
        logger.error(f"[Upload] RuntimeError: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Dataset error: {str(e)}")
    
    except Exception as e:
        # Catch any unexpected errors
        logger.error(f"[Upload] Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload/select")
async def select_dataset(req: SelectDatasetRequest, response: Response):
    """
    Switch the active dataset session to the one matching the given filename.
    
    Returns:
      - 200 OK with dataset metadata
      - 404 Not Found if dataset session not found
    """
    try:
        from app.core.session import _store
        
        # Find session with matching filename
        target_session = None
        for session in _store.values():
            if session.filename == req.filename:
                target_session = session
                break

        if not target_session:
            from app.core.session import get_sessions_dir, get_session
            try:
                for p in get_sessions_dir().glob("*.json"):
                    session_id = p.stem
                    if session_id not in _store:
                        session = get_session(session_id)
                        if session and session.filename == req.filename:
                            target_session = session
                            break
            except Exception as e:
                logger.warning(f"Failed to restore session from disk for filename lookup: {e}")

        if not target_session:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset '{req.filename}' session not found. Please upload it again.",
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
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"[Select Dataset] Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Selection failed: {str(e)}")


@router.get("/upload/preview")
async def preview_dataset(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
):
    """
    Return a paginated slice of the uploaded dataset as JSON rows.
    Used by the frontend dataset viewer panel.
    
    Returns:
      - 200 OK with paginated dataset rows
      - 401 Unauthorized if no active session
      - 404 Not Found if session doesn't exist
      - 500 Internal Server Error if dataset can't be loaded from cache/Azure
    """
    try:
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No active session. Please upload a dataset first.")
        
        session = get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found. Please re-upload your dataset.")

        # Load dataframe — may raise RuntimeError if cache is missing and Azure download fails
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
    
    except HTTPException:
        raise
    
    except RuntimeError as e:
        # Dataset cache missing and Azure download failed
        logger.error(f"[Preview] RuntimeError (dataset unavailable): {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Dataset unavailable: {str(e)} Please re-upload your dataset."
        )
    
    except Exception as e:
        logger.error(f"[Preview] Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")


@router.post("/upload/download")
async def download_cleaned_dataset(request: Request, authorization: str | None = Header(None)):
    """
    Download the current (possibly cleaned/modified) dataset from session.
    Saves the cleaned version back to Azure Vault in the same project/folder,
    and returns the file bytes to trigger a local browser download.
    """
    try:
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=401, detail="No active session. Please upload a dataset first.")

        session = get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found. Please re-upload your dataset.")

        # 1. Load the current dataframe from kernel/cache
        df = load_dataframe(session)

        # 2. Get file extension and set proper MIME types & conversion
        filename = session.filename or "dataset.csv"
        import os
        base, ext = os.path.splitext(filename)
        ext = ext.lower()

        # We'll name it cleaned_<original_name>
        cleaned_filename = f"cleaned_{base}{ext}"

        import io
        file_buf = io.BytesIO()
        if ext in (".xlsx", ".xls"):
            # Excel format
            df.to_excel(file_buf, index=False)
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            # Fallback to CSV
            df.to_csv(file_buf, index=False)
            content_type = "text/csv"

        file_bytes = file_buf.getvalue()

        # 3. Upload the cleaned file to Azure Vault under the same project and folder
        from app.api.routes.vault import _get_authed_vault
        vault = _get_authed_vault(authorization)
        try:
            file_data = await vault.upload_file_complete(
                filename=cleaned_filename,
                file_bytes=file_bytes,
                project_id=session.vault_project_id,
                folder_id=session.vault_folder_id,
                content_type=content_type,
            )
            # Confirm file upload status as completed
            file_id = file_data.get("id")
            if file_id:
                await vault.update_upload_status(file_id, {"upload_status": "completed"})
                logger.info(f"[Download] Successfully uploaded cleaned file '{cleaned_filename}' and confirmed upload status to Azure Vault (id={file_id}, project={session.vault_project_id}, folder={session.vault_folder_id})")
            else:
                logger.warning(f"[Download] Uploaded cleaned file '{cleaned_filename}' but no ID returned to confirm status.")
        except Exception as e:
            logger.error(f"[Download] Failed uploading/confirming cleaned file to Azure Vault: {str(e)}")

        # 4. Return as attachment for local download
        return Response(
            content=file_bytes,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{cleaned_filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Download] Cleaned download failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to download dataset: {str(e)}")