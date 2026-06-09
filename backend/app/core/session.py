from datetime import datetime, timedelta
from typing import Dict, Optional
from app.models.session import SessionData
from app.core.config import settings


# In-memory store — replace with Redis for production
_store: Dict[str, SessionData] = {}


def create_session(session_id: str, data: SessionData) -> None:
    _store[session_id] = data


def get_session(session_id: str) -> Optional[SessionData]:
    session = _store.get(session_id)
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


def cleanup_expired() -> int:
    """Remove expired sessions. Call periodically if needed."""
    ttl = timedelta(minutes=settings.SESSION_TTL_MINUTES)
    now = datetime.utcnow()
    expired = [sid for sid, s in _store.items() if now - s.created_at > ttl]
    for sid in expired:
        del _store[sid]
    return len(expired)