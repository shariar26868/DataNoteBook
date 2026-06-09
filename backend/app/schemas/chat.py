from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class DatasetInfo(BaseModel):
    columns: List[str]
    dtypes: Dict[str, str]
    row_count: int
    sample: List[Dict[str, Any]] = []


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    explanation: str
    code: str
    options: List[str] = ["Accept and run", "Accept", "Close"]