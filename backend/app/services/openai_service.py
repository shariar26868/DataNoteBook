import re
from openai import AsyncOpenAI
from app.core.config import settings
from app.utils.prompt_builder import build_system_prompt, build_user_message
from app.models.session import SessionData

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def generate_code(session: SessionData, user_message: str) -> dict:
    """
    Call OpenAI with the dataset context and user question.
    Returns {"explanation": str, "code": str}
    """
    system_prompt = build_system_prompt(
        filename=session.filename,
        columns=session.columns,
        dtypes=session.dtypes,
        row_count=session.row_count,
        sample_rows=session.sample_rows,
    )

    # Build messages — include chat history for multi-turn context
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(session.chat_history[-10:])   # last 10 turns max
    messages.append({"role": "user", "content": build_user_message(user_message)})

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        max_tokens=settings.MAX_TOKENS,
        temperature=0.2,
        messages=messages,
    )

    raw = response.choices[0].message.content or ""

    # Append to history
    session.chat_history.append({"role": "user", "content": user_message})
    session.chat_history.append({"role": "assistant", "content": raw})

    return _parse_response(raw)


def _parse_response(raw: str) -> dict:
    explanation = ""
    code = ""

    exp_match = re.search(r"EXPLANATION:\s*(.*?)(?=CODE:|```|$)", raw, re.DOTALL)
    if exp_match:
        explanation = exp_match.group(1).strip()

    code_match = re.search(r"```python\s*([\s\S]*?)```", raw)
    if code_match:
        code = code_match.group(1).strip()
    else:
        # fallback: try bare code block
        code_match2 = re.search(r"CODE:\s*([\s\S]+)$", raw)
        if code_match2:
            code = code_match2.group(1).strip()

    if not explanation:
        explanation = "Here is the generated code for your request."

    return {"explanation": explanation, "code": code}