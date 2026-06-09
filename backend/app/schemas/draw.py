from pydantic import BaseModel
from typing import Optional


class DrawRequest(BaseModel):
    message: str
    save_locally: bool = True  # kept for backward compat, ignored (always S3 now)


class DrawResponse(BaseModel):
    message_id: str
    image_url: Optional[str] = None   # presigned S3 URL
    explanation: Optional[str] = None
    code: Optional[str] = None        # generated Python code shown in UI
