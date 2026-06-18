from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

from app.core.config import settings

router = APIRouter()


@router.get("/images/{image_filename}")
async def serve_image(image_filename: str):
    """
    Serve a chart image from local storage.
    Chart images are saved locally because Azure presigned URLs
    are write-only (sp=cw) and cannot be used for reading.
    """
    images_dir = Path(settings.IMAGES_DIR)
    filepath = images_dir / image_filename

    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    # Security: prevent path traversal
    try:
        filepath.resolve().relative_to(images_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    return FileResponse(
        path=str(filepath),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )
