from fastapi import APIRouter, HTTPException, Response, Header
from app.schemas.vault import (
    ProjectCreateRequest,
    FolderCreateRequest,
    FileCreateRequest,
    PresignedUrlRequest
)
from app.services.vault_service import get_vault_client, VaultClient
from app.services.dataset_service import handle_vault_file
from app.core.config import settings

router = APIRouter()

def _get_authed_vault(authorization: str | None) -> VaultClient:
    """Get the singleton VaultClient and inject user token if provided."""
    vault = get_vault_client()
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "", 1).strip()
        vault._token = token
    return vault

@router.post("/project")
async def create_project(req: ProjectCreateRequest, authorization: str | None = Header(None)):
    """Create a new project via Vault API."""
    vault = _get_authed_vault(authorization)
    try:
        project_data = await vault.create_project(
            name=req.name,
            storage_location=req.storage_location
        )
        return {"success": True, "data": project_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/project")
async def list_projects(authorization: str | None = Header(None)):
    """List all projects in the vault."""
    vault = _get_authed_vault(authorization)
    try:
        projects_data = await vault.list_projects()
        return {"success": True, "data": projects_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def _get_all_resources_recursive(vault, project_id: str, parent_id: str | None = None) -> list:
    """Fetch all resources recursively, excluding hidden files."""
    level_resources = await vault.list_resources(parent_id=parent_id, project_id=project_id)
    all_resources = []
    for r in level_resources:
        if r.get("hidden"):
            continue
        all_resources.append(r)
        if r.get("type") == "folder":
            folder_id = r.get("id")
            if folder_id:
                nested = await _get_all_resources_recursive(vault, project_id, parent_id=folder_id)
                all_resources.extend(nested)
    return all_resources

@router.get("/project/{project_id}/resources")
async def list_project_resources(project_id: str, parent_id: str | None = None, authorization: str | None = Header(None)):
    """List resources (folders/files) under a project."""
    vault = _get_authed_vault(authorization)
    try:
        if parent_id is None:
            # Recursively load the entire project resource tree
            resources = await _get_all_resources_recursive(vault, project_id)
        else:
            # Load specific folder
            resources = await vault.list_resources(parent_id=parent_id, project_id=project_id)
            # Filter out hidden files
            resources = [r for r in resources if not r.get("hidden")]
        return {"success": True, "data": resources}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/folder")
async def create_folder(req: FolderCreateRequest, authorization: str | None = Header(None)):
    """Create a new folder via Vault API."""
    vault = _get_authed_vault(authorization)
    try:
        folder_data = await vault.create_folder(name=req.name, project_id=req.project_id)
        return {"success": True, "data": folder_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/file")
async def create_file(req: FileCreateRequest, authorization: str | None = Header(None)):
    """Register a file and get presigned upload URL."""
    vault = _get_authed_vault(authorization)
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
async def update_upload_status(file_id: str, payload: dict, authorization: str | None = Header(None)):
    """Confirm file upload status."""
    vault = _get_authed_vault(authorization)
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
async def analyze_vault_file(file_id: str, response: Response, authorization: str | None = Header(None)):
    """
    Download a file from Vault, load into Pandas, and start a session.
    Returns dataset metadata and stores session in a secure backend cookie.
    """
    vault = _get_authed_vault(authorization)
    try:
        session = await handle_vault_file(file_id, vault)
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

