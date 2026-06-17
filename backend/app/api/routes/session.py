

from typing import Optional

from fastapi import APIRouter, Cookie

from app.core.session import get_session
from app.schemas.session import SessionStatusResponse

router = APIRouter()


@router.get('/session', response_model=SessionStatusResponse)
async def get_session_status(session_id: Optional[str] = Cookie(None)):
    session = get_session(session_id) if session_id else None
    if not session:
        return SessionStatusResponse(active=False)

    return SessionStatusResponse(
        active=True,
        filename=session.filename,
        columns=session.columns,
        dtypes=session.dtypes,
        row_count=session.row_count,
    )
