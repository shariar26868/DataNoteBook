# import json
# from typing import Optional
# from fastapi import APIRouter, Cookie
# from fastapi.responses import StreamingResponse
# from app.schemas.execute import ExecuteRequest, ExecuteResponse
# from app.core.session import get_session
# from app.services.executor_service import execute_code, execute_code_streaming

# router = APIRouter()


# @router.post("/execute", response_model=ExecuteResponse)
# async def execute(request: ExecuteRequest, session_id: Optional[str] = Cookie(None)):
#     """
#     Execute Python code. Session is optional — if present and code uses 'df',
#     the dataset is injected. Without a session, code runs in a clean namespace.
#     """
#     session = get_session(session_id) if session_id else None
#     result = execute_code(session, request.code)

#     return ExecuteResponse(
#         output=result.get("output"),
#         table=result.get("table"),
#         error=result.get("error"),
#         execution_time_ms=result.get("execution_time_ms"),
#     )


# @router.post("/execute/stream")
# async def execute_stream(request: ExecuteRequest, session_id: Optional[str] = Cookie(None)):
#     """
#     Execute Python code with real-time SSE streaming (Colab-style).
#     Session is optional — dataset is only loaded when code references 'df'.

#     Events: data: {"type": "stdout"|"table"|"image"|"error"|"done", "data": ...}
#     """
#     session = get_session(session_id) if session_id else None

#     def event_generator():
#         for event_type, data in execute_code_streaming(session, request.code):
#             payload = json.dumps({"type": event_type, "data": data})
#             yield f"data: {payload}\n\n"

#     return StreamingResponse(
#         event_generator(),
#         media_type="text/event-stream",
#         headers={
#             "Cache-Control": "no-cache",
#             "X-Accel-Buffering": "no",
#         },
#     )














import json
import logging
from typing import Optional
from fastapi import APIRouter, Cookie, HTTPException
from fastapi.responses import StreamingResponse
from app.schemas.execute import ExecuteRequest, ExecuteResponse
from app.core.session import get_session
from app.services.executor_service import execute_code, execute_code_streaming

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/execute", response_model=ExecuteResponse)
async def execute(request: ExecuteRequest, session_id: Optional[str] = Cookie(None)):
    """
    Execute Python code. Session is optional — if present and code uses 'df',
    the dataset is injected. Without a session, code runs in a clean namespace.
    
    Returns:
      - 200 OK with output/table/error
      - 400 Bad Request if code is unsafe
      - 404 Not Found if session doesn't exist
      - 500 Internal Server Error if dataset can't be loaded
    """
    try:
        session = get_session(session_id) if session_id else None
        
        # Execute the code
        result = execute_code(session, request.code)

        return ExecuteResponse(
            output=result.get("output"),
            table=result.get("table"),
            error=result.get("error"),
            execution_time_ms=result.get("execution_time_ms"),
        )
    
    except RuntimeError as e:
        # Dataset loading failed or other critical issue
        logger.error(f"[Execute] RuntimeError: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Dataset error: {str(e)}")
    
    except Exception as e:
        # Catch any unexpected errors
        logger.error(f"[Execute] Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


@router.post("/execute/stream")
async def execute_stream(request: ExecuteRequest, session_id: Optional[str] = Cookie(None)):
    """
    Execute Python code with real-time SSE streaming (Colab-style).
    Session is optional — dataset is only loaded when code references 'df'.

    Events: data: {"type": "stdout"|"table"|"image"|"error"|"done", "data": ...}
    
    Returns:
      - 200 OK with event stream
      - 400 Bad Request if code is unsafe
      - 404 Not Found if session doesn't exist
      - 500 Internal Server Error if dataset can't be loaded
    """
    session = None
    try:
        session = get_session(session_id) if session_id else None
    except Exception as e:
        logger.error(f"[Execute/Stream] Session lookup failed: {str(e)}")
        # Return error event stream
        def error_generator():
            payload = json.dumps({"type": "error", "data": f"Session error: {str(e)}"})
            yield f"data: {payload}\n\n"
        
        return StreamingResponse(
            error_generator(),
            media_type="text/event-stream",
            status_code=500,
        )

    def event_generator():
        try:
            for event_type, data in execute_code_streaming(session, request.code):
                payload = json.dumps({"type": event_type, "data": data})
                yield f"data: {payload}\n\n"
        
        except RuntimeError as e:
            # Dataset loading failed
            logger.error(f"[Execute/Stream] RuntimeError: {str(e)}")
            payload = json.dumps({"type": "error", "data": f"Dataset error: {str(e)}"})
            yield f"data: {payload}\n\n"
        
        except Exception as e:
            # Catch any unexpected errors during streaming
            logger.error(f"[Execute/Stream] Unexpected error: {str(e)}", exc_info=True)
            payload = json.dumps({"type": "error", "data": f"Streaming failed: {str(e)}"})
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )