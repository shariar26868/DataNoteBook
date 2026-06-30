from pydantic import BaseModel
from typing import Dict, Optional


class SessionStatusResponse(BaseModel):
    active: bool
    filename: Optional[str] = None
    columns: Optional[list[str]] = None
    dtypes: Optional[Dict[str, str]] = None
    row_count: Optional[int] = None
    vault_file_id: Optional[str] = None
    vault_project_id: Optional[str] = None
    vault_folder_id: Optional[str] = None

