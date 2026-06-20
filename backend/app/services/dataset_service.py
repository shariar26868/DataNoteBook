import uuid
import io
import pandas as pd
from pathlib import Path
from fastapi import UploadFile, HTTPException

from app.core.config import settings
from app.core.session import create_session
from app.models.session import SessionData
from app.services.vault_service import get_vault_client


ALLOWED_EXT = {".csv", ".xlsx", ".xls"}

MIME_TYPES = {
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
}


async def handle_upload(file: UploadFile) -> SessionData:
    """
    Upload file to Azure via Vault API, parse a small sample for metadata,
    and create session.

    Flow:
    1. Read file bytes
    2. Parse with pandas for metadata
    3. Create project + folder in vault
    4. Upload file to Azure via vault presigned URL
    5. Create session with vault IDs
    """
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    session_id = str(uuid.uuid4())

    # Read entire file into memory (needed for Azure upload and pandas parsing)
    try:
        raw_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed reading file: {str(e)}")

    # Parse small sample for metadata
    try:
        buf = io.BytesIO(raw_bytes)
        if ext == ".csv":
            df_sample = pd.read_csv(buf, nrows=5)
            # Count rows efficiently
            row_count = max(0, raw_bytes.count(b"\n") - 1)
        else:
            df_sample = pd.read_excel(buf, nrows=5)
            # For Excel, read full index to count rows
            buf2 = io.BytesIO(raw_bytes)
            df_full = pd.read_excel(buf2, usecols=[0])
            row_count = int(df_full.shape[0])
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse file: {str(e)}")

    # Upload to Azure via Vault API
    vault = get_vault_client()
    try:
        # Create project + folder for this session
        project_id, folder_id = await vault.setup_session_storage(
            session_name=f"session-{session_id[:8]}"
        )

        # Upload the dataset file
        content_type = MIME_TYPES.get(ext, "application/octet-stream")
        file_data = await vault.upload_file_complete(
            filename=file.filename,
            file_bytes=raw_bytes,
            project_id=project_id,
            folder_id=folder_id,
            content_type=content_type,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed uploading to Azure: {str(e)}")

    # Build dtype info
    dtypes = {}
    for col in df_sample.columns:
        if pd.api.types.is_numeric_dtype(df_sample[col]):
            dtypes[str(col)] = "float"
        else:
            dtypes[str(col)] = "str"

    # Cache the full DataFrame immediately so we don't need to download later
    try:
        full_buf = io.BytesIO(raw_bytes)
        if ext == ".csv":
            cached_df = pd.read_csv(full_buf)
        else:
            cached_df = pd.read_excel(full_buf)
    except Exception:
        cached_df = None

    session = SessionData(
        session_id=session_id,
        filename=file.filename,
        blob_name=file_data.get("blob_name", ""),
        vault_project_id=project_id,
        vault_folder_id=folder_id,
        vault_file_id=file_data.get("id", ""),
        columns=[str(c) for c in df_sample.columns.tolist()],
        dtypes=dtypes,
        row_count=row_count,
        sample_rows=df_sample.head(5).fillna("").to_dict(orient="records"),
        cached_df=cached_df,
    )
    create_session(session_id, session)
    return session

async def handle_vault_file(file_id: str, vault=None) -> SessionData:
    """
    Download file from Vault, parse it for metadata, and create session.
    Accepts an optional pre-authenticated VaultClient. Falls back to the
    global singleton (which will auto-login with service credentials).
    """
    if vault is None:
        vault = get_vault_client()
    
    # 1. Get file details
    try:
        resource_data = await vault.get_resource(file_id)
        filename = resource_data.get("name", f"file_{file_id}")
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXT:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Failed fetching file details: {str(e)}")

    session_id = str(uuid.uuid4())

    # 2. Download bytes
    try:
        raw_bytes = await vault.download_resource(file_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed downloading file from Azure: {str(e)}")

    # 3. Parse small sample for metadata
    try:
        buf = io.BytesIO(raw_bytes)
        if ext == ".csv":
            df_sample = pd.read_csv(buf, nrows=5)
            row_count = max(0, raw_bytes.count(b"\n") - 1)
        else:
            df_sample = pd.read_excel(buf, nrows=5)
            buf2 = io.BytesIO(raw_bytes)
            df_full = pd.read_excel(buf2, usecols=[0])
            row_count = int(df_full.shape[0])
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse file: {str(e)}")

    # 4. Build dtype info
    dtypes = {}
    for col in df_sample.columns:
        if pd.api.types.is_numeric_dtype(df_sample[col]):
            dtypes[str(col)] = "float"
        else:
            dtypes[str(col)] = "str"

    # 5. Cache the full DataFrame
    try:
        full_buf = io.BytesIO(raw_bytes)
        if ext == ".csv":
            cached_df = pd.read_csv(full_buf)
        else:
            cached_df = pd.read_excel(full_buf)
    except Exception:
        cached_df = None

    # 6. Create session
    # Extract project and folder ID if they exist in the vault resource response
    # The structure of get_resource response includes project as an object
    project_obj = resource_data.get("project") or {}
    project_id = project_obj.get("id", "") if isinstance(project_obj, dict) else project_obj
    folder_id = resource_data.get("parent", "")

    session = SessionData(
        session_id=session_id,
        filename=filename,
        blob_name=resource_data.get("blob_name", ""),
        vault_project_id=project_id,
        vault_folder_id=folder_id,
        vault_file_id=file_id,
        columns=[str(c) for c in df_sample.columns.tolist()],
        dtypes=dtypes,
        row_count=row_count,
        sample_rows=df_sample.head(5).fillna("").to_dict(orient="records"),
        cached_df=cached_df,
    )
    create_session(session_id, session)
    return session



def load_dataframe(session: SessionData) -> pd.DataFrame:
    """
    Return the session's cached DataFrame.
    Since Azure presigned URL is write-only, we rely on the in-memory cache
    that was populated during upload.
    """
    if session.cached_df is not None:
        return session.cached_df

    raise RuntimeError(
        "DataFrame not cached. The dataset may have been lost due to session expiry. "
        "Please re-upload the file."
    )
