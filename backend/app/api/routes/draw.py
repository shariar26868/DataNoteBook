# from typing import Optional
# from fastapi import APIRouter, Cookie, HTTPException
# from app.schemas.draw import DrawRequest, DrawResponse
# from app.core.session import get_session
# from app.services.openai_service import generate_code
# from app.services.executor_service import execute_code_save_image

# router = APIRouter()


# @router.post("/draw", response_model=DrawResponse)
# async def draw(request: DrawRequest, session_id: Optional[str] = Cookie(None)):
#     """
#     Generate a plot based on the dataset and user message.
#     The resulting image is stored in S3 and a presigned URL is returned.
#     """
#     if not session_id:
#         raise HTTPException(status_code=401, detail="Session cookie missing. Please upload your dataset first.")

#     session = get_session(session_id)
#     if session is None:
#         raise HTTPException(status_code=404, detail="Session not found or expired. Please re-upload your file.")

#     result = await generate_code(session, request.message)
#     exec_result = execute_code_save_image(session, result["code"])

#     if exec_result.get("error"):
#         raise HTTPException(status_code=400, detail=exec_result.get("error"))

#     return DrawResponse(
#         message_id=exec_result.get("message_id"),
#         image_url=exec_result.get("image_url"),
#         explanation=result.get("explanation"),
#         code=result.get("code"),
#     )





from typing import Optional
from fastapi import APIRouter, Cookie, HTTPException
from app.schemas.draw import DrawRequest, DrawResponse
from app.core.session import get_session
from app.services.openai_service import generate_code
from app.services.executor_service import execute_code_save_image

router = APIRouter()


@router.post("/draw", response_model=DrawResponse)
async def draw(request: DrawRequest, session_id: Optional[str] = Cookie(None)):
    """
    Generate a plot based on the dataset and user message.
    The resulting image is stored locally/Azure and a URL is returned.
    """
    if not session_id:
        raise HTTPException(status_code=401, detail="Session cookie missing. Please upload your dataset first.")

    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired. Please re-upload your file.")

    result = await generate_code(session, request.message)

    if result.get("out_of_scope") or not result.get("code"):
        raise HTTPException(
            status_code=400,
            detail=result.get("soft_message") or "This request couldn't be converted into a chart."
        )

    try:
        exec_result = execute_code_save_image(session, result["code"])
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"Dataset error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Draw failed: {str(e)}")

    if exec_result.get("error"):
        raise HTTPException(status_code=400, detail=exec_result.get("error"))

    return DrawResponse(
        message_id=exec_result.get("message_id"),
        image_url=exec_result.get("image_url"),
        explanation=result.get("explanation"),
        code=result.get("code"),
    )