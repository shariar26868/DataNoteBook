import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from app.core.config import settings
from app.models.session import SessionData

logger = logging.getLogger(__name__)

# In-memory store — replace with Redis for production
_store: Dict[str, SessionData] = {}


def get_sessions_dir() -> Path:
    sessions_dir = Path(settings.UPLOAD_DIR) / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    return sessions_dir


def save_session(session: SessionData) -> None:
    """Save session metadata to disk for persistence across worker restarts."""
    try:
        session_file = get_sessions_dir() / f"{session.session_id}.json"
        data = {
            "session_id": session.session_id,
            "filename": session.filename,
            "blob_name": session.blob_name,
            "vault_project_id": session.vault_project_id,
            "vault_folder_id": session.vault_folder_id,
            "vault_file_id": session.vault_file_id,
            "columns": session.columns,
            "dtypes": session.dtypes,
            "row_count": session.row_count,
            "sample_rows": session.sample_rows,
            "chat_history": session.chat_history,
            "created_at": session.created_at.isoformat(),
        }
        session_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"[Session] Saved session {session.session_id} to disk.")
    except Exception as e:
        logger.error(f"[Session] Failed to save session {session.session_id} to disk: {e}", exc_info=True)


def create_session(session_id: str, data: SessionData) -> None:
    _store[session_id] = data
    save_session(data)


def get_session(session_id: str) -> Optional[SessionData]:
    # 1. Try to get from memory
    session = _store.get(session_id)
    
    # 2. Try to restore from disk if missing in memory
    if session is None:
        try:
            session_file = get_sessions_dir() / f"{session_id}.json"
            if session_file.exists():
                logger.info(f"[Session] Session {session_id} not in memory, attempting restore from disk.")
                data = json.loads(session_file.read_text(encoding="utf-8"))
                
                # Parse created_at
                created_at_val = datetime.fromisoformat(data["created_at"])
                
                # Check TTL
                ttl = timedelta(minutes=settings.SESSION_TTL_MINUTES)
                if datetime.utcnow() - created_at_val > ttl:
                    logger.warning(f"[Session] Session {session_id} on disk is expired.")
                    try:
                        session_file.unlink()
                    except Exception:
                        pass
                    return None
                
                session = SessionData(
                    session_id=data["session_id"],
                    filename=data["filename"],
                    blob_name=data.get("blob_name", ""),
                    vault_project_id=data.get("vault_project_id", ""),
                    vault_folder_id=data.get("vault_folder_id", ""),
                    vault_file_id=data.get("vault_file_id", ""),
                    columns=data.get("columns", []),
                    dtypes=data.get("dtypes", {}),
                    row_count=data.get("row_count", 0),
                    sample_rows=data.get("sample_rows", []),
                    chat_history=data.get("chat_history", []),
                    created_at=created_at_val,
                )
                # Store back in memory
                _store[session_id] = session
                logger.info(f"[Session] Successfully restored session {session_id} from disk.")
        except Exception as e:
            logger.error(f"[Session] Failed to restore session {session_id} from disk: {e}", exc_info=True)
            return None

    if session is None:
        return None

    # TTL check
    ttl = timedelta(minutes=settings.SESSION_TTL_MINUTES)
    if datetime.utcnow() - session.created_at > ttl:
        delete_session(session_id)
        return None
    return session


def delete_session(session_id: str) -> None:
    _store.pop(session_id, None)
    try:
        session_file = get_sessions_dir() / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
            logger.info(f"[Session] Deleted session {session_id} from disk.")
    except Exception as e:
        logger.warning(f"[Session] Failed to delete session file: {e}")


def cleanup_expired() -> int:
    """Remove expired sessions from memory and disk. Call periodically if needed."""
    ttl = timedelta(minutes=settings.SESSION_TTL_MINUTES)
    now = datetime.utcnow()
    
    # Clean memory
    expired_in_memory = [sid for sid, s in _store.items() if now - s.created_at > ttl]
    for sid in expired_in_memory:
        del _store[sid]
        
    # Clean disk
    count = 0
    try:
        for p in get_sessions_dir().glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                created_at_val = datetime.fromisoformat(data["created_at"])
                if now - created_at_val > ttl:
                    p.unlink()
                    count += 1
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"[Session] Cleanup disk failed: {e}")
        
    return len(expired_in_memory) + count