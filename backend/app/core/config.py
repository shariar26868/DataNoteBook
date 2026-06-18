from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path

# Resolve .env from the backend folder (where .env currently lives)
# config.py is at backend/app/core/config.py, so parents[2] -> backend
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "null",
    ]

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    MAX_TOKENS: int = 1500

    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = [".csv", ".xlsx", ".xls"]

    SESSION_TTL_MINUTES: int = 60

    # Azure Vault API
    VAULT_API_BASE_URL: str = "https://qual-be.hcloud.q2labs.ai"
    VAULT_EMAIL: str = ""
    VAULT_PASSWORD: str = ""
    VAULT_STORAGE_LOCATION: str = ""

    # Local image storage (for serving chart images to frontend)
    IMAGES_DIR: str = "uploads/images"

    class Config:
        env_file = str(_ENV_FILE)
        env_file_encoding = "utf-8"


settings = Settings()