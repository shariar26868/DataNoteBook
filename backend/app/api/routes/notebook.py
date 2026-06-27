import json
import uuid
import os
import logging
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.schemas.notebook import (
    NotebookSaveRequest, NotebookSaveResponse,
    NotebookLoadResponse, NotebookListResponse,
    NotebookMeta, NotebookCell, NotebookMessage,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Local filesystem storage for notebooks
NOTEBOOKS_DIR = Path(settings.UPLOAD_DIR) / "notebooks"
NOTEBOOKS_DIR.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _notebook_path(notebook_id: str) -> Path:
    return NOTEBOOKS_DIR / f"{notebook_id}.json"


def _index_path() -> Path:
    return NOTEBOOKS_DIR / "_index.json"


def _load_index() -> list:
    """Load the notebook index from local filesystem. Returns [] if not found."""
    idx_path = _index_path()
    if not idx_path.exists():
        return []
    try:
        return json.loads(idx_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return []


def _save_index(index: list) -> None:
    _index_path().write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _upsert_index(meta: dict) -> None:
    """Insert or update a notebook entry in the index."""
    index = _load_index()
    index = [nb for nb in index if nb.get("notebook_id") != meta["notebook_id"]]
    index.insert(0, meta)  # most recent first
    _save_index(index)


def _find_by_vault_file_id(vault_file_id: str) -> Optional[dict]:
    """Find an existing index entry that belongs to the given vault file ID."""
    for entry in _load_index():
        if entry.get("vault_file_id") == vault_file_id:
            return entry
    return None


@router.post("/notebooks/save", response_model=NotebookSaveResponse)
async def save_notebook(req: NotebookSaveRequest):
    """
    Save or update a notebook to Vault API storage.

    If vault_file_id is provided and a notebook for that file already exists,
    the existing notebook is updated (true file-level persistence).
    """
    from app.services.vault_service import get_vault_client

    vault = get_vault_client()
    try:
        project_id, folder_id = await vault.setup_global_notebooks_storage()
    except Exception as e:
        logger.warning(f"Could not setup global notebooks storage: {e}")
        raise HTTPException(status_code=500, detail="Vault storage setup failed")

    now = _now_iso()

    # --- Resolve which notebook_id to update ---
    # Priority: explicit notebook_id > vault_file_id lookup > create new
    old_notebook_id = req.notebook_id

    if not old_notebook_id and req.vault_file_id:
        # Look up if a notebook was previously saved for this vault file
        existing = _find_by_vault_file_id(req.vault_file_id)
        if existing:
            old_notebook_id = existing["notebook_id"]
            logger.info(f"[Notebook] Found existing notebook {old_notebook_id} for vault_file_id={req.vault_file_id}")

    # Build notebook document
    notebook_doc = {
        "title": req.title,
        "vault_file_id": req.vault_file_id,
        "dataset_filename": req.dataset_filename,
        "created_at": now,
        "updated_at": now,
        "cells": [cell.model_dump() for cell in req.cells],
        "messages": [msg.model_dump() for msg in req.messages],
    }

    if old_notebook_id:
        # Preserve original created_at
        index = _load_index()
        old_meta = next((nb for nb in index if nb.get("notebook_id") == old_notebook_id), None)
        if old_meta:
            notebook_doc["created_at"] = old_meta.get("created_at", now)

        # Delete old file in Vault to replace it
        try:
            await vault.delete_resource(old_notebook_id)
        except Exception:
            pass  # Ignore if not found in Vault

    # Upload new/updated file to Vault
    file_bytes = json.dumps(notebook_doc, ensure_ascii=False, indent=2).encode("utf-8")
    filename = f"{req.title}.json"

    try:
        file_data = await vault.upload_file_complete(
            filename=filename,
            file_bytes=file_bytes,
            project_id=project_id,
            folder_id=folder_id,
            content_type="application/json"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload notebook to Vault: {e}")

    new_notebook_id = file_data.get("id")
    if not new_notebook_id:
        raise HTTPException(status_code=500, detail="Vault upload succeeded but no ID returned")

    notebook_doc["notebook_id"] = new_notebook_id

    # If updating, clean up old index entry
    if old_notebook_id and old_notebook_id != new_notebook_id:
        index = _load_index()
        index = [nb for nb in index if nb.get("notebook_id") != old_notebook_id]
        _save_index(index)

    # Update local index
    _upsert_index({
        "notebook_id": new_notebook_id,
        "vault_file_id": req.vault_file_id,
        "title": req.title,
        "dataset_filename": req.dataset_filename,
        "created_at": notebook_doc["created_at"],
        "updated_at": now,
        "cell_count": len(req.cells),
    })

    logger.info(f"[Notebook] Saved notebook {new_notebook_id} for vault_file_id={req.vault_file_id}")
    return NotebookSaveResponse(notebook_id=new_notebook_id, message="Saved to Vault")


@router.get("/notebooks/by-file/{vault_file_id}", response_model=NotebookLoadResponse)
async def load_notebook_by_file(vault_file_id: str):
    """
    Load the notebook associated with a specific vault dataset file ID.
    This is the primary endpoint for restoring work when a user re-opens a file.
    Returns 404 if no notebook has been saved for this file yet.
    """
    existing = _find_by_vault_file_id(vault_file_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"No notebook found for vault_file_id={vault_file_id}")

    notebook_id = existing["notebook_id"]
    return await _load_notebook_doc(notebook_id)


@router.get("/notebooks", response_model=NotebookListResponse)
async def list_notebooks(sort: str = "updated", search: str = ""):
    """List all saved notebooks from the local index."""
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
    """Load a specific notebook from Vault storage by notebook ID."""
    return await _load_notebook_doc(notebook_id)


async def _load_notebook_doc(notebook_id: str) -> NotebookLoadResponse:
    """Shared helper: download and parse a notebook doc from Vault (or local fallback)."""
    from app.services.vault_service import get_vault_client
    vault = get_vault_client()

    try:
        file_bytes = await vault.download_resource(notebook_id)
        doc = json.loads(file_bytes.decode("utf-8"))
    except Exception as e:
        # Fallback to local storage
        nb_path = _notebook_path(notebook_id)
        if nb_path.exists():
            try:
                doc = json.loads(nb_path.read_text(encoding="utf-8"))
            except Exception as e2:
                raise HTTPException(status_code=500, detail=f"Failed to read local notebook: {e2}")
        else:
            raise HTTPException(status_code=404, detail=f"Notebook not found in Vault or local: {e}")

    cells = [NotebookCell(**c) for c in doc.get("cells", [])]

    # Load messages (chat history) — gracefully handle old notebooks that don't have this field
    raw_msgs = doc.get("messages", [])
    messages = []
    for m in raw_msgs:
        try:
            messages.append(NotebookMessage(**m))
        except Exception:
            pass  # Skip malformed messages

    return NotebookLoadResponse(
        notebook_id=notebook_id,
        vault_file_id=doc.get("vault_file_id"),
        title=doc.get("title", "Untitled"),
        cells=cells,
        messages=messages,
        dataset_filename=doc.get("dataset_filename"),
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
    )


@router.delete("/notebooks/{notebook_id}")
async def delete_notebook(notebook_id: str):
    """Delete a notebook from Vault storage and remove from index."""
    from app.services.vault_service import get_vault_client
    vault = get_vault_client()

    try:
        await vault.delete_resource(notebook_id)
    except Exception:
        pass  # Ignore vault deletion error

    # Delete local file if it exists (for backward compatibility)
    nb_path = _notebook_path(notebook_id)
    if nb_path.exists():
        nb_path.unlink()

    index = _load_index()
    index = [nb for nb in index if nb.get("notebook_id") != notebook_id]
    _save_index(index)

    return {"message": "Deleted from Vault"}


@router.patch("/notebooks/{notebook_id}/rename")
async def rename_notebook(notebook_id: str, body: dict):
    """Rename a notebook in Vault (updates title in index and doc)."""
    from app.services.vault_service import get_vault_client
    new_title = body.get("title", "Untitled")
    now = _now_iso()
    vault = get_vault_client()

    # 1. Update Vault resource name
    try:
        await vault.rename_resource(notebook_id, f"{new_title}.json")
    except Exception:
        pass  # Ignore if move endpoint fails

    # 2. Update local index
    index = _load_index()
    for nb in index:
        if nb.get("notebook_id") == notebook_id:
            nb["title"] = new_title
            nb["updated_at"] = now
    _save_index(index)

    return {"message": "Renamed"}


