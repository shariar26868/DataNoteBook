import json
from typing import Optional
from fastapi import APIRouter, Cookie
from fastapi.responses import StreamingResponse
from app.schemas.execute import ExecuteRequest, ExecuteResponse
from app.core.session import get_session
from app.services.executor_service import execute_code, execute_code_streaming

router = APIRouter()


@router.post("/execute", response_model=ExecuteResponse)
async def execute(request: ExecuteRequest, session_id: Optional[str] = Cookie(None)):
    """
    Execute Python code. Session is optional — if present and code uses 'df',
    the dataset is injected. Without a session, code runs in a clean namespace.
    """
    session = get_session(session_id) if session_id else None
    result = execute_code(session, request.code)

    return ExecuteResponse(
        output=result.get("output"),
        table=result.get("table"),
        error=result.get("error"),
        execution_time_ms=result.get("execution_time_ms"),
    )


@router.post("/execute/stream")
async def execute_stream(request: ExecuteRequest, session_id: Optional[str] = Cookie(None)):
    """
    Execute Python code with real-time SSE streaming (Colab-style).
    Session is optional — dataset is only loaded when code references 'df'.

    Events: data: {"type": "stdout"|"table"|"image"|"error"|"done", "data": ...}
    """
    session = get_session(session_id) if session_id else None

    def event_generator():
        for event_type, data in execute_code_streaming(session, request.code):
            payload = json.dumps({"type": event_type, "data": data})
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
