import uuid
import io
import pandas as pd
from pathlib import Path
from fastapi import UploadFile, HTTPException

from app.core.config import settings
from app.core.session import create_session
from app.models.session import SessionData
from app.services.s3_service import upload_fileobj_to_s3, download_fileobj_from_s3


ALLOWED_EXT = {".csv", ".xlsx", ".xls"}


async def handle_upload(file: UploadFile) -> SessionData:
    """Stream-upload file to S3, parse a small sample for metadata, and create session."""
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    session_id = str(uuid.uuid4())
    s3_key = f"{settings.S3_UPLOADS_PREFIX}/{session_id}{ext}"

    # Read entire file into memory (needed for both S3 upload and pandas parsing)
    try:
        raw_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed reading file: {str(e)}")

    # Upload to S3
    try:
        content_type = "text/csv" if ext == ".csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        upload_fileobj_to_s3(io.BytesIO(raw_bytes), s3_key, content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed uploading to S3: {str(e)}")

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

    dtypes = {}
    for col in df_sample.columns:
        if pd.api.types.is_numeric_dtype(df_sample[col]):
            dtypes[str(col)] = "float"
        else:
            dtypes[str(col)] = "str"

    session = SessionData(
        session_id=session_id,
        filename=file.filename,
        s3_key=s3_key,
        columns=[str(c) for c in df_sample.columns.tolist()],
        dtypes=dtypes,
        row_count=row_count,
        sample_rows=df_sample.head(5).fillna("").to_dict(orient="records"),
    )
    create_session(session_id, session)
    return session


def load_dataframe(session: SessionData) -> pd.DataFrame:
    """Download file from S3 and return as DataFrame."""
    ext = Path(session.s3_key).suffix.lower()
    buf = download_fileobj_from_s3(session.s3_key)
    if ext == ".csv":
        return pd.read_csv(buf)
    return pd.read_excel(buf)
