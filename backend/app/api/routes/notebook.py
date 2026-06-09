import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from botocore.exceptions import ClientError

from app.core.config import settings
from app.services.s3_service import get_s3_client
from app.schemas.notebook import (
    NotebookSaveRequest, NotebookSaveResponse,
    NotebookLoadResponse, NotebookListResponse,
    NotebookMeta, NotebookCell,
)

router = APIRouter()

PREFIX = settings.S3_NOTEBOOKS_PREFIX
BUCKET = settings.S3_BUCKET_NAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _notebook_key(notebook_id: str) -> str:
    return f"{PREFIX}/{notebook_id}.json"


def _index_key() -> str:
    return f"{PREFIX}/_index.json"


def _load_index() -> list:
    """Load the notebook index from S3. Returns [] if not found."""
    try:
        obj = get_s3_client().get_object(Bucket=BUCKET, Key=_index_key())
        return json.loads(obj["Body"].read().decode("utf-8"))
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return []
        raise


def _save_index(index: list) -> None:
    get_s3_client().put_object(
        Bucket=BUCKET,
        Key=_index_key(),
        Body=json.dumps(index, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )


def _upsert_index(meta: dict) -> None:
    """Insert or update a notebook entry in the index."""
    index = _load_index()
    index = [nb for nb in index if nb.get("notebook_id") != meta["notebook_id"]]
    index.insert(0, meta)  # most recent first
    _save_index(index)


@router.post("/notebooks/save", response_model=NotebookSaveResponse)
async def save_notebook(req: NotebookSaveRequest):
    """Save or update a notebook to S3."""
    now = _now_iso()
    notebook_id = req.notebook_id or str(uuid.uuid4())

    # Build notebook document
    notebook_doc = {
        "notebook_id": notebook_id,
        "title": req.title,
        "dataset_filename": req.dataset_filename,
        "created_at": now,
        "updated_at": now,
        "cells": [cell.model_dump() for cell in req.cells],
    }

    # Preserve original created_at if updating
    if req.notebook_id:
        try:
            existing = get_s3_client().get_object(Bucket=BUCKET, Key=_notebook_key(notebook_id))
            old = json.loads(existing["Body"].read().decode("utf-8"))
            notebook_doc["created_at"] = old.get("created_at", now)
        except ClientError:
            pass  # new notebook

    # Save to S3
    get_s3_client().put_object(
        Bucket=BUCKET,
        Key=_notebook_key(notebook_id),
        Body=json.dumps(notebook_doc, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    # Update index
    _upsert_index({
        "notebook_id": notebook_id,
        "title": req.title,
        "dataset_filename": req.dataset_filename,
        "created_at": notebook_doc["created_at"],
        "updated_at": now,
        "cell_count": len(req.cells),
    })

    return NotebookSaveResponse(notebook_id=notebook_id, message="Saved")


@router.get("/notebooks", response_model=NotebookListResponse)
async def list_notebooks(sort: str = "updated", search: str = ""):
    """List all saved notebooks from the S3 index."""
    index = _load_index()

    if search:
        q = search.lower()
        index = [nb for nb in index if q in nb.get("title", "").lower()]

    if sort == "title":
        index.sort(key=lambda nb: nb.get("title", "").lower())
    else:
        # default: last edited (updated_at desc)
        index.sort(key=lambda nb: nb.get("updated_at", ""), reverse=True)

    notebooks = [NotebookMeta(**nb) for nb in index]
    return NotebookListResponse(notebooks=notebooks)


@router.get("/notebooks/{notebook_id}", response_model=NotebookLoadResponse)
async def load_notebook(notebook_id: str):
    """Load a specific notebook from S3."""
    try:
        obj = get_s3_client().get_object(Bucket=BUCKET, Key=_notebook_key(notebook_id))
        doc = json.loads(obj["Body"].read().decode("utf-8"))
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            raise HTTPException(status_code=404, detail="Notebook not found")
        raise

    cells = [NotebookCell(**c) for c in doc.get("cells", [])]
    return NotebookLoadResponse(
        notebook_id=doc["notebook_id"],
        title=doc.get("title", "Untitled"),
        cells=cells,
        dataset_filename=doc.get("dataset_filename"),
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
    )


@router.delete("/notebooks/{notebook_id}")
async def delete_notebook(notebook_id: str):
    """Delete a notebook from S3 and remove from index."""
    try:
        get_s3_client().delete_object(Bucket=BUCKET, Key=_notebook_key(notebook_id))
    except ClientError:
        pass

    index = _load_index()
    index = [nb for nb in index if nb.get("notebook_id") != notebook_id]
    _save_index(index)

    return {"message": "Deleted"}


@router.patch("/notebooks/{notebook_id}/rename")
async def rename_notebook(notebook_id: str, body: dict):
    """Rename a notebook (updates title in both the doc and index)."""
    new_title = body.get("title", "Untitled")
    now = _now_iso()

    try:
        obj = get_s3_client().get_object(Bucket=BUCKET, Key=_notebook_key(notebook_id))
        doc = json.loads(obj["Body"].read().decode("utf-8"))
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            raise HTTPException(status_code=404, detail="Notebook not found")
        raise

    doc["title"] = new_title
    doc["updated_at"] = now

    get_s3_client().put_object(
        Bucket=BUCKET,
        Key=_notebook_key(notebook_id),
        Body=json.dumps(doc, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    _upsert_index({
        "notebook_id": notebook_id,
        "title": new_title,
        "dataset_filename": doc.get("dataset_filename"),
        "created_at": doc.get("created_at", now),
        "updated_at": now,
        "cell_count": len(doc.get("cells", [])),
    })

    return {"message": "Renamed"}
