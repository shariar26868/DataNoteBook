# import uuid
# import io
# import pandas as pd
# from pathlib import Path
# from fastapi import UploadFile, HTTPException

# from app.core.config import settings
# from app.core.session import create_session
# from app.models.session import SessionData
# from app.services.vault_service import get_vault_client


# ALLOWED_EXT = {".csv", ".xlsx", ".xls"}

# MIME_TYPES = {
#     ".csv": "text/csv",
#     ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#     ".xls": "application/vnd.ms-excel",
# }


# async def handle_upload(file: UploadFile) -> SessionData:
#     """
#     Upload file to Azure via Vault API, parse a small sample for metadata,
#     and create session.

#     Flow:
#     1. Read file bytes
#     2. Parse with pandas for metadata
#     3. Create project + folder in vault
#     4. Upload file to Azure via vault presigned URL
#     5. Create session with vault IDs
#     """
#     ext = Path(file.filename).suffix.lower()
#     if ext not in ALLOWED_EXT:
#         raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

#     session_id = str(uuid.uuid4())

#     # Read entire file into memory (needed for Azure upload and pandas parsing)
#     try:
#         raw_bytes = await file.read()
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed reading file: {str(e)}")

#     # Parse small sample for metadata
#     try:
#         buf = io.BytesIO(raw_bytes)
#         if ext == ".csv":
#             df_sample = pd.read_csv(buf, nrows=5)
#             # Count rows efficiently
#             row_count = max(0, raw_bytes.count(b"\n") - 1)
#         else:
#             df_sample = pd.read_excel(buf, nrows=5)
#             # For Excel, read full index to count rows
#             buf2 = io.BytesIO(raw_bytes)
#             df_full = pd.read_excel(buf2, usecols=[0])
#             row_count = int(df_full.shape[0])
#     except Exception as e:
#         raise HTTPException(status_code=422, detail=f"Could not parse file: {str(e)}")

#     # Upload to Azure via Vault API
#     vault = get_vault_client()
#     try:
#         # Create project + folder for this session
#         project_id, folder_id = await vault.setup_session_storage(
#             session_name=f"session-{session_id[:8]}"
#         )

#         # Upload the dataset file
#         content_type = MIME_TYPES.get(ext, "application/octet-stream")
#         file_data = await vault.upload_file_complete(
#             filename=file.filename,
#             file_bytes=raw_bytes,
#             project_id=project_id,
#             folder_id=folder_id,
#             content_type=content_type,
#         )
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed uploading to Azure: {str(e)}")

#     # Build dtype info
#     dtypes = {}
#     for col in df_sample.columns:
#         if pd.api.types.is_numeric_dtype(df_sample[col]):
#             dtypes[str(col)] = "float"
#         else:
#             dtypes[str(col)] = "str"

#     # Cache the full DataFrame immediately so we don't need to download later
#     try:
#         full_buf = io.BytesIO(raw_bytes)
#         if ext == ".csv":
#             cached_df = pd.read_csv(full_buf)
#         else:
#             cached_df = pd.read_excel(full_buf)
#     except Exception:
#         cached_df = None

#     session = SessionData(
#         session_id=session_id,
#         filename=file.filename,
#         blob_name=file_data.get("blob_name", ""),
#         vault_project_id=project_id,
#         vault_folder_id=folder_id,
#         vault_file_id=file_data.get("id", ""),
#         columns=[str(c) for c in df_sample.columns.tolist()],
#         dtypes=dtypes,
#         row_count=row_count,
#         sample_rows=df_sample.head(5).fillna("").to_dict(orient="records"),
#         cached_df=cached_df,
#     )
#     create_session(session_id, session)
#     return session

# async def handle_vault_file(file_id: str, vault=None) -> SessionData:
#     """
#     Download file from Vault, parse it for metadata, and create session.
#     Accepts an optional pre-authenticated VaultClient. Falls back to the
#     global singleton (which will auto-login with service credentials).
#     """
#     if vault is None:
#         vault = get_vault_client()
    
#     # 1. Get file details
#     try:
#         resource_data = await vault.get_resource(file_id)
#         filename = resource_data.get("name", f"file_{file_id}")
#         ext = Path(filename).suffix.lower()
#         if ext not in ALLOWED_EXT:
#             raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
#     except Exception as e:
#         raise HTTPException(status_code=404, detail=f"Failed fetching file details: {str(e)}")

#     session_id = str(uuid.uuid4())

#     # 2. Download bytes
#     try:
#         raw_bytes = await vault.download_resource(file_id)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed downloading file from Azure: {str(e)}")

#     # 3. Parse small sample for metadata
#     try:
#         buf = io.BytesIO(raw_bytes)
#         if ext == ".csv":
#             df_sample = pd.read_csv(buf, nrows=5)
#             row_count = max(0, raw_bytes.count(b"\n") - 1)
#         else:
#             df_sample = pd.read_excel(buf, nrows=5)
#             buf2 = io.BytesIO(raw_bytes)
#             df_full = pd.read_excel(buf2, usecols=[0])
#             row_count = int(df_full.shape[0])
#     except Exception as e:
#         raise HTTPException(status_code=422, detail=f"Could not parse file: {str(e)}")

#     # 4. Build dtype info
#     dtypes = {}
#     for col in df_sample.columns:
#         if pd.api.types.is_numeric_dtype(df_sample[col]):
#             dtypes[str(col)] = "float"
#         else:
#             dtypes[str(col)] = "str"

#     # 5. Cache the full DataFrame
#     try:
#         full_buf = io.BytesIO(raw_bytes)
#         if ext == ".csv":
#             cached_df = pd.read_csv(full_buf)
#         else:
#             cached_df = pd.read_excel(full_buf)
#     except Exception:
#         cached_df = None

#     # 6. Create session
#     # Extract project and folder ID if they exist in the vault resource response
#     # The structure of get_resource response includes project as an object
#     project_obj = resource_data.get("project") or {}
#     project_id = project_obj.get("id", "") if isinstance(project_obj, dict) else project_obj
#     folder_id = resource_data.get("parent", "")

#     session = SessionData(
#         session_id=session_id,
#         filename=filename,
#         blob_name=resource_data.get("blob_name", ""),
#         vault_project_id=project_id,
#         vault_folder_id=folder_id,
#         vault_file_id=file_id,
#         columns=[str(c) for c in df_sample.columns.tolist()],
#         dtypes=dtypes,
#         row_count=row_count,
#         sample_rows=df_sample.head(5).fillna("").to_dict(orient="records"),
#         cached_df=cached_df,
#     )
#     create_session(session_id, session)
#     return session



# def load_dataframe(session: SessionData) -> pd.DataFrame:
#     """
#     Return the session's cached DataFrame.
#     If the in-memory cache is missing (e.g. after a worker restart or memory pressure),
#     attempt a synchronous re-download from Azure Vault using the session's vault_file_id.
#     """
#     if session.cached_df is not None:
#         return session.cached_df

#     # ── Fallback: re-download from Vault ──────────────────────────────────────
#     if session.vault_file_id:
#         import asyncio
#         import logging
#         log = logging.getLogger(__name__)
#         log.warning(
#             f"[Session {session.session_id}] cached_df is None for '{session.filename}'. "
#             f"Attempting re-download from Vault (file_id={session.vault_file_id})..."
#         )
#         try:
#             from app.services.vault_service import get_vault_client
#             vault = get_vault_client()

#             # Run the async download synchronously
#             try:
#                 loop = asyncio.get_event_loop()
#                 if loop.is_running():
#                     import concurrent.futures
#                     with concurrent.futures.ThreadPoolExecutor() as pool:
#                         future = pool.submit(asyncio.run, vault.download_resource(session.vault_file_id))
#                         raw_bytes = future.result(timeout=30)
#                 else:
#                     raw_bytes = loop.run_until_complete(vault.download_resource(session.vault_file_id))
#             except RuntimeError:
#                 raw_bytes = asyncio.run(vault.download_resource(session.vault_file_id))

#             ext = Path(session.filename).suffix.lower()
#             buf = io.BytesIO(raw_bytes)
#             if ext == ".csv":
#                 df = pd.read_csv(buf)
#             else:
#                 df = pd.read_excel(buf)

#             session.cached_df = df  # repopulate cache
#             log.info(f"[Session {session.session_id}] Re-download successful — {len(df)} rows loaded.")
#             return df

#         except Exception as e:
#             log.error(f"[Session {session.session_id}] Vault re-download failed: {e}")

#     raise RuntimeError(
#         f"DataFrame for '{session.filename}' is not cached and could not be re-downloaded. "
#         "Please re-upload or re-select the file."
#     )






import uuid
import io
import pandas as pd
import logging
from pathlib import Path
from fastapi import UploadFile, HTTPException

from app.core.config import settings
from app.core.session import create_session
from app.models.session import SessionData
from app.services.vault_service import get_vault_client

logger = logging.getLogger(__name__)


def _get_session_cache_dir(session_id: str) -> Path:
    cache_dir = Path(settings.UPLOAD_DIR) / "sessions" / session_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _get_cached_dataset_path(session_id: str, filename: str) -> Path:
    return _get_session_cache_dir(session_id) / Path(filename).name


def _save_dataset_cache(session_id: str, filename: str, raw_bytes: bytes) -> None:
    cache_path = _get_cached_dataset_path(session_id, filename)
    cache_path.write_bytes(raw_bytes)


def _load_dataframe_from_local_cache(session: SessionData) -> "Optional[pd.DataFrame]":
    if not session.session_id or not session.filename:
        return None

    cache_path = _get_cached_dataset_path(session.session_id, session.filename)
    if not cache_path.exists():
        return None

    try:
        raw_bytes = cache_path.read_bytes()
        buf = io.BytesIO(raw_bytes)
        if cache_path.suffix.lower() == ".csv":
            return pd.read_csv(buf)
        return pd.read_excel(buf)
    except Exception as e:
        logger.warning(f"[Dataset Cache] Failed to load local cached dataset for session {session.session_id}: {e}")
        return None



logger = logging.getLogger(__name__)

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
    
    Raises:
      - HTTPException 400 if file type not supported
      - HTTPException 422 if file can't be parsed
      - HTTPException 500 if Azure upload fails
    """
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    session_id = str(uuid.uuid4())

    # Read entire file into memory (needed for Azure upload and pandas parsing)
    try:
        raw_bytes = await file.read()
    except Exception as e:
        logger.error(f"[Upload] Failed reading file: {str(e)}")
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
        logger.error(f"[Upload] Could not parse file '{file.filename}': {str(e)}")
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
        file_id = file_data.get("id")
        if file_id:
            try:
                await vault.update_upload_status(file_id, {"upload_status": "completed"})
                logger.info(f"[Upload] Confirmed upload completion for file {file_id}")
            except Exception as se:
                logger.warning(f"[Upload] Failed to confirm upload completion for file {file_id}: {se}")
    except Exception as e:
        logger.error(f"[Upload] Failed uploading to Azure: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed uploading to Azure: {str(e)}")

    # Save a local copy of the uploaded dataset so the session can be restored later
    try:
        _save_dataset_cache(session_id, file.filename, raw_bytes)
        logger.info(f"[Dataset Cache] Saved local cache for session {session_id}")
    except Exception as e:
        logger.warning(f"[Dataset Cache] Could not save local dataset cache for session {session_id}: {e}")

    # Build dtype info
    dtypes = {}
    for col in df_sample.columns:
        if pd.api.types.is_numeric_dtype(df_sample[col]):
            dtypes[str(col)] = "float"
        else:
            dtypes[str(col)] = "str"

    # Cache the full DataFrame immediately so we don't need to download later
    cached_df = None
    try:
        full_buf = io.BytesIO(raw_bytes)
        if ext == ".csv":
            cached_df = pd.read_csv(full_buf)
        else:
            cached_df = pd.read_excel(full_buf)
        logger.info(f"[Upload] Cached {len(cached_df)} rows for '{file.filename}'")
    except Exception as e:
        logger.warning(f"[Upload] Could not cache full dataframe: {str(e)}")
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
    logger.info(f"[Upload] Created session {session_id} for '{file.filename}'")
    return session


async def handle_vault_file(file_id: str, vault=None) -> SessionData:
    """
    Download file from Vault, parse it for metadata, and create session.
    Accepts an optional pre-authenticated VaultClient. Falls back to the
    global singleton (which will auto-login with service credentials).
    
    Raises:
      - HTTPException 400 if file type not supported
      - HTTPException 404 if file not found in vault
      - HTTPException 422 if file can't be parsed
      - HTTPException 500 if Azure download fails
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Vault Select] Failed fetching file details: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Failed fetching file details: {str(e)}")

    session_id = str(uuid.uuid4())

    # 2. Download bytes
    try:
        raw_bytes = await vault.download_resource(file_id)
        logger.info(f"[Vault Select] Downloaded {len(raw_bytes)} bytes for '{filename}'")
    except Exception as e:
        logger.error(f"[Vault Select] Failed downloading file from Azure: {str(e)}")
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
        logger.error(f"[Vault Select] Could not parse file '{filename}': {str(e)}")
        raise HTTPException(status_code=422, detail=f"Could not parse file: {str(e)}")

    # 4. Build dtype info
    dtypes = {}
    for col in df_sample.columns:
        if pd.api.types.is_numeric_dtype(df_sample[col]):
            dtypes[str(col)] = "float"
        else:
            dtypes[str(col)] = "str"

    # 5. Cache the full DataFrame
    cached_df = None
    try:
        full_buf = io.BytesIO(raw_bytes)
        if ext == ".csv":
            cached_df = pd.read_csv(full_buf)
        else:
            cached_df = pd.read_excel(full_buf)
        logger.info(f"[Vault Select] Cached {len(cached_df)} rows for '{filename}'")
    except Exception as e:
        logger.warning(f"[Vault Select] Could not cache full dataframe: {str(e)}")
        cached_df = None

    # 6. Create session
    # Extract project and folder ID if they exist in the vault resource response
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
    logger.info(f"[Vault Select] Created session {session_id} for '{filename}'")
    return session


def load_dataframe(session: SessionData) -> pd.DataFrame:
    """
    Return the session's cached DataFrame.
    If the in-memory cache is missing (e.g. after a worker restart or memory pressure),
    attempt a synchronous re-download from Azure Vault using the session's vault_file_id.
    
    Raises RuntimeError if:
      - Session has no cached_df AND
      - vault_file_id is missing OR
      - Re-download from Vault fails
    """
    if session.cached_df is not None:
        return session.cached_df

    # ── Fallback: re-download from Vault ──────────────────────────────────────
    if not session.vault_file_id:
        logger.error(f"[Load DF] Session {session.session_id}: cached_df is None and vault_file_id is missing")
        raise RuntimeError(
            f"Dataset for '{session.filename}' is not cached and cannot be retrieved. "
            "Please re-upload or re-select the file."
        )

    logger.warning(
        f"[Load DF] Session {session.session_id}: cached_df is None. "
        f"Attempting local cache restore or Vault re-download (file_id={session.vault_file_id})..."
    )

    # First try a local cached copy saved at upload time
    cached_df = _load_dataframe_from_local_cache(session)
    if cached_df is not None:
        session.cached_df = cached_df
        logger.info(f"[Load DF] Session {session.session_id}: restored dataset from local cache.")
        return cached_df

    try:
        import asyncio
        from app.services.vault_service import get_vault_client
        
        vault = get_vault_client()

        # ✅ FIXED: Proper async/sync handling
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, use a thread pool
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, vault.download_resource(session.vault_file_id))
                    raw_bytes = future.result(timeout=60)
            else:
                # We're in a sync context, run_until_complete is safe
                raw_bytes = loop.run_until_complete(vault.download_resource(session.vault_file_id))
        except RuntimeError:
            # No event loop exists, create a new one
            raw_bytes = asyncio.run(vault.download_resource(session.vault_file_id))

        # Parse the downloaded file
        ext = Path(session.filename).suffix.lower()
        buf = io.BytesIO(raw_bytes)
        
        if ext == ".csv":
            df = pd.read_csv(buf)
        else:
            df = pd.read_excel(buf)

        session.cached_df = df  # repopulate cache
        logger.info(f"[Load DF] Session {session.session_id}: Re-download successful — {len(df)} rows loaded.")
        return df

    except Exception as e:
        logger.error(f"[Load DF] Session {session.session_id}: Vault re-download failed: {str(e)}", exc_info=True)
        raise RuntimeError(
            f"Dataset for '{session.filename}' is not cached and re-download from Azure failed: {str(e)}"
        )


async def save_and_upload_modified_dataset(session: SessionData, df: pd.DataFrame) -> None:
    """
    Convert the modified DataFrame to bytes, upload to Azure Vault,
    update the session metadata (columns, dtypes, row_count, sample_rows, vault_file_id, blob_name),
    and save the updated session to disk.
    
    Preserves all historical versions untouched by generating sequential unique names.
    """
    logger.info(f"[Dataset Update] Uploading modified dataset for session {session.session_id}")
    
    # 1. Get format and content type based on the active filename
    filename = session.filename or "dataset.csv"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        ext = ".csv"  # default fallback
        
    content_type = MIME_TYPES.get(ext, "application/octet-stream")
    
    # 2. Query Vault to find existing files in project folder and resolve sequential version
    vault = get_vault_client()
    existing_names = set()
    if session.vault_project_id and session.vault_folder_id:
        try:
            resources = await vault.list_resources(parent_id=session.vault_folder_id, project_id=session.vault_project_id)
            existing_names = {r.get("name") for r in resources if r.get("type") == "file"}
        except Exception as le:
            logger.warning(f"[Dataset Update] Could not list project resources: {le}")

    # Strip versioning & cleaned_ prefix from active filename to find original base name
    import re
    base = Path(filename).stem
    if base.startswith("cleaned_"):
        base = base[8:]
    base = re.sub(r'_(cleaned|v|version)?_?\d+$', '', base)
    base = re.sub(r'_cleaned$', '', base)
    
    # Find next unique version filename
    version = 1
    while True:
        candidate = f"cleaned_{base}_v{version}{ext}"
        if candidate not in existing_names:
            target_filename = candidate
            break
        version += 1
        
    logger.info(f"[Dataset Update] Target unique filename resolved: '{target_filename}'")
    
    # 3. Convert DataFrame to bytes
    buf = io.BytesIO()
    if ext in (".xlsx", ".xls"):
        df.to_excel(buf, index=False)
    else:
        df.to_csv(buf, index=False)
    file_bytes = buf.getvalue()
    
    # Upload the updated file bytes
    try:
        file_data = await vault.upload_file_complete(
            filename=target_filename,
            file_bytes=file_bytes,
            project_id=session.vault_project_id,
            folder_id=session.vault_folder_id,
            content_type=content_type,
        )
        
        # Confirm upload status
        file_id = file_data.get("id")
        if file_id:
            try:
                await vault.update_upload_status(file_id, {"upload_status": "completed"})
                logger.info(f"[Dataset Update] Confirmed upload completion for updated file {file_id}")
            except Exception as se:
                logger.warning(f"[Dataset Update] Failed to confirm upload completion for file {file_id}: {se}")
        else:
            logger.warning("[Dataset Update] Upload completed but no ID returned from Vault.")
            
    except Exception as e:
        logger.error(f"[Dataset Update] Failed uploading modified dataset to Vault: {str(e)}")
        raise RuntimeError(f"Failed uploading modified dataset to Vault: {str(e)}")
        
    # 4. Update session metadata
    session.filename = target_filename
    session.vault_file_id = file_data.get("id", session.vault_file_id)
    session.blob_name = file_data.get("blob_name", session.blob_name)
    session.columns = [str(c) for c in df.columns.tolist()]
    
    # Update dtypes
    dtypes = {}
    df_sample = df.head(5)
    for col in df_sample.columns:
        if pd.api.types.is_numeric_dtype(df_sample[col]):
            dtypes[str(col)] = "float"
        else:
            dtypes[str(col)] = "str"
    session.dtypes = dtypes
    
    session.row_count = len(df)
    session.sample_rows = df_sample.fillna("").to_dict(orient="records")
    session.cached_df = df
    
    # 5. Persist updated session
    from app.core.session import save_session
    save_session(session)
    logger.info(f"[Dataset Update] Successfully updated session {session.session_id} with modified dataset.")
