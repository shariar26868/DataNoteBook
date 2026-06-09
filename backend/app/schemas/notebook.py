from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class NotebookCell(BaseModel):
    id: str
    type: str          # "code" | "text"
    source: str        # cell content
    output: Optional[str] = None   # last stdout output (plain text)
    output_type: Optional[str] = None  # "text" | "table" | "image" | None


class NotebookSaveRequest(BaseModel):
    notebook_id: Optional[str] = None   # None = create new
    title: str = "Untitled"
    cells: List[NotebookCell] = []
    dataset_filename: Optional[str] = None


class NotebookMeta(BaseModel):
    notebook_id: str
    title: str
    dataset_filename: Optional[str] = None
    created_at: str
    updated_at: str
    cell_count: int


class NotebookSaveResponse(BaseModel):
    notebook_id: str
    message: str


class NotebookLoadResponse(BaseModel):
    notebook_id: str
    title: str
    cells: List[NotebookCell]
    dataset_filename: Optional[str] = None
    created_at: str
    updated_at: str


class NotebookListResponse(BaseModel):
    notebooks: List[NotebookMeta]
