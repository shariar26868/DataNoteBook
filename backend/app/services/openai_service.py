import os
import re
import logging
from openai import AsyncOpenAI, AsyncAzureOpenAI
from app.core.config import settings
from app.utils.prompt_builder import build_system_prompt, build_user_message
from app.models.session import SessionData

logger = logging.getLogger(__name__)

# Initialize client based on available config
if settings.AZURE_OPENAI_API_KEY and settings.AZURE_OPENAI_ENDPOINT:
    endpoint = settings.AZURE_OPENAI_ENDPOINT
    if "/openai/v1" in endpoint:
        endpoint = endpoint.split("/openai/v1")[0]
    if endpoint.endswith("/openai"):
        endpoint = endpoint[: -len("/openai")]
    logger.info(f"[OpenAI] Using Azure endpoint: {endpoint}")
    client = AsyncAzureOpenAI(
        azure_endpoint=endpoint,
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )
else:
    logger.info("[OpenAI] Using standard OpenAI client")
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))


async def generate_code(session: SessionData, user_message: str, image: str = None) -> dict:
    """
    Call the LLM and return a structured result. Never raises.
    """
    try:
        system_prompt = build_system_prompt(
            filename=session.filename,
            columns=session.columns,
            dtypes=session.dtypes,
            row_count=session.row_count,
            sample_rows=session.sample_rows,
        )
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(session.chat_history[-20:])
        
        if image:
            # Map standard OpenAI image block format
            img_url = image if image.startswith("data:image") else f"data:image/png;base64,{image}"
            user_content = [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": img_url
                    }
                },
                {
                    "type": "text",
                    "text": build_user_message(user_message)
                }
            ]
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": build_user_message(user_message)})

        # No token cap - let the model respond fully
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0.2,
            messages=messages,
        )

        finish_reason = response.choices[0].finish_reason
        if finish_reason not in ("stop", "length", None):
            logger.warning(f"[OpenAI] Unexpected finish_reason={finish_reason!r}")

        raw = response.choices[0].message.content or ""
        if not raw.strip():
            logger.warning("[OpenAI] Empty response from model")
            return _error_result("The AI returned an empty response. Please try again.")

        parsed = _parse_response(raw)

        session.chat_history.append({"role": "user", "content": user_message})
        if parsed.get("out_of_scope"):
            session.chat_history.append({
                "role": "assistant",
                "content": f"[Out of scope] {parsed.get('soft_message', '')}",
            })
        else:
            session.chat_history.append({
                "role": "assistant",
                "content": f"EXPLANATION: {parsed['explanation']}\n(Code was generated and sent to the notebook.)",
            })

        from app.core.session import save_session
        save_session(session)
        return parsed

    except Exception as exc:
        logger.error(f"[OpenAI] generate_code failed: {exc}", exc_info=True)
        return _error_result("The AI service is temporarily unavailable. Please try again in a moment.")


def _error_result(message: str) -> dict:
    return {
        "explanation": message,
        "code": "",
        "out_of_scope": False,
        "soft_message": None,
        "truncated": False,
    }


def _parse_response(raw: str) -> dict:
    """
    Robust multi-strategy parser for LLM responses.
    Strategy order:
      1. OUT_OF_SCOPE prefix
      2. EXPLANATION: section + python code fence
      3. Any python code fence without EXPLANATION
      4. Any generic code fence
      5. CODE: section fallback
      6. Entire raw as explanation only
    """
    try:
        text = raw.strip()

        # 1. Out-of-scope
        oos = re.match(r"OUT_OF_SCOPE\s*:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
        if oos:
            soft = oos.group(1).strip().split("\n")[0].strip()
            return {
                "explanation": soft,
                "code": "",
                "out_of_scope": True,
                "soft_message": soft,
                "truncated": False,
            }

        explanation = ""
        code = ""

        # 2. Extract EXPLANATION section
        exp_match = re.search(
            r"EXPLANATION\s*:\s*(.*?)(?=CODE\s*:|```|$)", text, re.DOTALL | re.IGNORECASE
        )
        if exp_match:
            explanation = exp_match.group(1).strip()

        # 3. Python code fence (```python)
        py_match = re.search(r"```python\s*([\s\S]*?)```", text, re.IGNORECASE)
        if py_match:
            code = py_match.group(1).strip()
        else:
            # 4. Any code fence
            any_fence = re.search(r"```(?:\w*\n)?([\s\S]*?)```", text)
            if any_fence:
                code = any_fence.group(1).strip()
            else:
                # 5. CODE: section
                code_match = re.search(r"CODE\s*:\s*([\s\S]+)$", text, re.IGNORECASE)
                if code_match:
                    code = code_match.group(1).strip()

        if not explanation:
            explanation = "Here is the generated code for your request." if code else text

        if code:
            code = _clean_code(code)

        return {
            "explanation": explanation,
            "code": code,
            "out_of_scope": False,
            "soft_message": None,
            "truncated": False,
        }

    except Exception as exc:
        logger.error(f"[OpenAI] _parse_response failed: {exc}", exc_info=True)
        return {
            "explanation": raw[:2000] if raw else "Could not parse the AI response.",
            "code": "",
            "out_of_scope": False,
            "soft_message": None,
            "truncated": False,
        }


def _clean_code(code: str) -> str:
    """Post-process AI code: remove stray fences, fix merged lines, add spacing."""
    try:
        # Remove accidental markdown fences inside the code body
        code = re.sub(r"^```\w*\s*", "", code, flags=re.MULTILINE)
        code = re.sub(r"^```\s*$", "", code, flags=re.MULTILINE)

        # Fix merged statements: closing ) immediately followed by a keyword
        BOUNDARY = re.compile(
            r"(\))"
            r"(?="
            r"import\s|from\s|for\s|if\s|while\s|with\s|def\s|class\s|"
            r"return\s|raise\s|print\s*\(|"
            r"plt\.|sns\.|pd\.|np\.|df[\.\[_]|"
            r"fig[,\s=\(]|ax[,\.\s]|#"
            r")"
        )
        prev, iters = None, 0
        while prev != code and iters < 15:
            prev, code = code, BOUNDARY.sub(r"\1\n", code)
            iters += 1

        # Add blank line before comment lines that directly follow code
        lines = code.split("\n")
        result = []
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith("#") and i > 0:
                prev_line = lines[i - 1].strip()
                if prev_line and not prev_line.startswith("#"):
                    result.append("")
            result.append(line)

        return "\n".join(result).strip()

    except Exception as exc:
        logger.warning(f"[OpenAI] _clean_code failed: {exc}")
        return code
