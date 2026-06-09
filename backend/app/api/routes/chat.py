from typing import Optional
from fastapi import APIRouter, Cookie, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse
from app.core.session import get_session
from app.services.openai_service import generate_code

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, session_id: Optional[str] = Cookie(None)):
    """
    Send a message about the dataset.
    OpenAI generates Python code + explanation.
    """
    if not session_id:
        raise HTTPException(status_code=401, detail="Session cookie missing. Please upload your dataset first.")

    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired. Please re-upload your file.")

    result = await generate_code(session, request.message)

    return ChatResponse(
        explanation=result["explanation"],
        code=result["code"],
    )