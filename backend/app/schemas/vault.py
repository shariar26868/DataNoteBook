from pydantic import BaseModel
from typing import Optional

class ProjectCreateRequest(BaseModel):
    name: str
    storage_location: str

class FolderCreateRequest(BaseModel):
    name: str
    project_id: str

class FileCreateRequest(BaseModel):
    name: str
    size: int
    extension: str
    mime_type: str
    project_id: str
    parent_folder_id: str

class PresignedUrlRequest(BaseModel):
    file_name: str
    content_type: Optional[str] = "application/octet-stream"
