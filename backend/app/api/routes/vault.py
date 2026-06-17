from fastapi import APIRouter, HTTPException, Response
from app.schemas.vault import (
    ProjectCreateRequest,
    FolderCreateRequest,
    FileCreateRequest,
    PresignedUrlRequest
)
from app.services.vault_service import get_vault_client
from app.services.dataset_service import handle_vault_file
from app.core.config import settings

router = APIRouter()

@router.post("/project")
async def create_project(req: ProjectCreateRequest):
    """Create a new project via Vault API."""
    vault = get_vault_client()
    try:
        project_data = await vault.create_project(
            name=req.name,
            storage_location=req.storage_location
        )
        return {"success": True, "data": project_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/folder")
async def create_folder(req: FolderCreateRequest):
    """Create a new folder via Vault API."""
    vault = get_vault_client()
    try:
        folder_data = await vault.create_folder(name=req.name, project_id=req.project_id)
        return {"success": True, "data": folder_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/file")
async def create_file(req: FileCreateRequest):
    """Register a file and get presigned upload URL."""
    vault = get_vault_client()
    try:
        file_data = await vault.create_file(
            name=req.name,
            size=req.size,
            extension=req.extension,
            mime_type=req.mime_type,
            project_id=req.project_id,
            parent_folder_id=req.parent_folder_id
        )
        return {"success": True, "data": file_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/file/{file_id}/upload_status")
async def update_upload_status(file_id: str, payload: dict):
    """Confirm file upload status."""
    vault = get_vault_client()
    try:
        response_data = await vault.update_upload_status(file_id, payload)
        return {"success": True, "data": response_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/files/presigned-url")
async def generate_presigned_url(req: PresignedUrlRequest):
    """
    Generate a presigned URL directly. 
    (Fallback if project/folder isn't required by the Vault API design)
    """
    vault = get_vault_client()
    # Assuming we put it in the global notebooks project/folder by default
    # Or you could just create a file without project/parent if Vault allows.
    try:
        project_id, folder_id = await vault.setup_global_notebooks_storage()
        ext = req.file_name.split('.')[-1] if '.' in req.file_name else ''
        file_data = await vault.create_file(
            name=req.file_name,
            size=0, # Unknown size at generation
            extension=ext,
            mime_type=req.content_type or "application/octet-stream",
            project_id=project_id,
            parent_folder_id=folder_id
        )
        # Match the frontend TS response format: data.pre_signed_url, data.file_id
        return {
            "success": True, 
            "data": {
                "pre_signed_url": file_data.get("presigned_url"),
                "file_id": file_data.get("id")
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/file/{file_id}/analyze")
async def analyze_vault_file(file_id: str, response: Response):
    """
    Download a file from Vault, load into Pandas, and start a session.
    Returns dataset metadata and stores session in a secure backend cookie.
    """
    try:
        session = await handle_vault_file(file_id)
        response.set_cookie(
            key="session_id",
            value=session.session_id,
            httponly=True,
            samesite="lax",
            max_age=settings.SESSION_TTL_MINUTES * 60,
        )
        return {
            "success": True,
            "data": {
                "filename": session.filename,
                "row_count": session.row_count,
                "column_count": len(session.columns),
                "columns": session.columns,
                "dtypes": session.dtypes,
                "sample": session.sample_rows,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

