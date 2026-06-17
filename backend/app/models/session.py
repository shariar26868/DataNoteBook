from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

import pandas as pd


@dataclass
class SessionData:
    session_id: str
    filename: str
    blob_name: str = ""                     # Azure blob name of the uploaded file
    vault_project_id: str = ""              # Vault project ID for this session
    vault_folder_id: str = ""               # Vault folder ID for this session
    vault_file_id: str = ""                 # Vault file ID for the dataset
    columns: List[str] = field(default_factory=list)
    dtypes: Dict[str, str] = field(default_factory=dict)
    row_count: int = 0
    sample_rows: List[Dict[str, Any]] = field(default_factory=list)
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    cached_df: Optional[pd.DataFrame] = None
    kernel_ns: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

