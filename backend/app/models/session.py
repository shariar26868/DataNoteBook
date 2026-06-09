from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any


@dataclass
class SessionData:
    session_id: str
    filename: str
    s3_key: str                             # S3 key of the uploaded file
    columns: List[str] = field(default_factory=list)
    dtypes: Dict[str, str] = field(default_factory=dict)
    row_count: int = 0
    sample_rows: List[Dict[str, Any]] = field(default_factory=list)
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
