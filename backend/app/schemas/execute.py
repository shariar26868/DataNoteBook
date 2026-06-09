from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class ExecuteRequest(BaseModel):
    code: str


class ExecuteResponse(BaseModel):
    output: Optional[str] = None
    table: Optional[List[Dict[str, Any]]] = None   # parsed DataFrame output
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None