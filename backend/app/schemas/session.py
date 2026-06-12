from pydantic import BaseModel
from typing import Dict, Optional


class SessionStatusResponse(BaseModel):
    active: bool
    filename: Optional[str] = None
    columns: Optional[list[str]] = None
    dtypes: Optional[Dict[str, str]] = None
    row_count: Optional[int] = None
