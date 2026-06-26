# import re
# from openai import AsyncOpenAI
# from app.core.config import settings
# from app.utils.prompt_builder import build_system_prompt, build_user_message
# from app.models.session import SessionData

# client = AsyncOpenAI(
#     base_url=settings.AZURE_OPENAI_ENDPOINT,
#     api_key=settings.AZURE_OPENAI_API_KEY,
# )


# async def generate_code(session: SessionData, user_message: str) -> dict:
#     """
#     Call OpenAI with the dataset context and user question.
#     Returns one of:
#       {"explanation": str, "code": str}                            — normal response
#       {"explanation": "", "code": "", "out_of_scope": True,
#        "soft_message": str}                                        — off-topic question
#     """
#     system_prompt = build_system_prompt(
#         filename=session.filename,
#         columns=session.columns,
#         dtypes=session.dtypes,
#         row_count=session.row_count,
#         sample_rows=session.sample_rows,
#     )

#     # Build messages — include chat history for multi-turn context.
#     # We store only explanation summaries (NOT raw code) in history so the AI
#     # does not copy-paste previous code blocks into new responses.
#     messages = [{"role": "system", "content": system_prompt}]
#     messages.extend(session.chat_history[-10:])
#     messages.append({"role": "user", "content": build_user_message(user_message)})

#     response = await client.chat.completions.create(
#         model=settings.OPENAI_MODEL,
#         temperature=0.2,
#         messages=messages,
#         extra_body={"max_completion_tokens": settings.MAX_TOKENS},
#     )

#     raw = response.choices[0].message.content or ""
#     parsed = _parse_response(raw)

#     # Store concise history — skip history entry for out-of-scope so it doesn't
#     # pollute context with irrelevant exchanges.
#     session.chat_history.append({"role": "user", "content": user_message})
#     if parsed.get("out_of_scope"):
#         session.chat_history.append({
#             "role": "assistant",
#             "content": f"[Out of scope] {parsed['soft_message']}"
#         })
#     else:
#         session.chat_history.append({
#             "role": "assistant",
#             "content": f"EXPLANATION: {parsed['explanation']}\n(Code was generated and executed separately.)"
#         })

#     return parsed


# def _parse_response(raw: str) -> dict:
#     # ── Check for out-of-scope response first ──
#     oos_match = re.match(r"OUT_OF_SCOPE:\s*(.+)", raw.strip(), re.IGNORECASE | re.DOTALL)
#     if oos_match:
#         soft_message = oos_match.group(1).strip().split("\n")[0]  # first line only
#         return {
#             "explanation": "",
#             "code": "",
#             "out_of_scope": True,
#             "soft_message": soft_message,
#         }

#     explanation = ""
#     code = ""

#     exp_match = re.search(r"EXPLANATION:\s*(.*?)(?=CODE:|```|$)", raw, re.DOTALL)
#     if exp_match:
#         explanation = exp_match.group(1).strip()

#     code_match = re.search(r"```python\s*([\s\S]*?)```", raw)
#     if code_match:
#         code = code_match.group(1).strip()
#     else:
#         code_match2 = re.search(r"CODE:\s*([\s\S]+)$", raw)
#         if code_match2:
#             code = code_match2.group(1).strip()

#     if not explanation:
#         explanation = "Here is the generated code for your request."

#     if code:
#         code = _fix_merged_lines(code)

#     return {"explanation": explanation, "code": code, "out_of_scope": False, "soft_message": None}


# def _fix_merged_lines(code: str) -> str:
#     """
#     Fix cases where the LLM outputs multiple statements merged onto one line.
#     E.g.: print("msg")import foo  →  print("msg")\\nimport foo

#     Strategy: use regex to find closing ) followed immediately by a known
#     statement-starting keyword, then insert a newline between them.
#     Also adds blank lines before comment blocks.
#     """
#     BOUNDARY = re.compile(
#         r'(\))'
#         r'(?='                            # lookahead — don't consume
#         r'import\s|from\s|for\s|if\s|while\s|with\s|def\s|class\s|'
#         r'return\s|raise\s|print\s*\(|'
#         r'plt\.|sns\.|pd\.|np\.|df[\.\[_]|'
#         r'fig[,\s=\(]|ax[,\.\s]|#'
#         r')'
#     )

#     # Apply repeatedly until stable (handles chains like )import)plt.)
#     prev = None
#     while prev != code:
#         prev = code
#         code = BOUNDARY.sub(r'\1\n', code)

#     # Add blank line before # comment lines that directly follow code
#     lines = code.split('\n')
#     final = []
#     for i, line in enumerate(lines):
#         stripped = line.lstrip()
#         if stripped.startswith('#') and i > 0:
#             prev_line = lines[i - 1].strip()
#             if prev_line and not prev_line.startswith('#'):
#                 final.append('')
#         final.append(line)

#     return '\n'.join(final)









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
    # ── Azure OpenAI Configuration ──
    # Clean the endpoint if it contains '/openai/v1' suffix
    endpoint = settings.AZURE_OPENAI_ENDPOINT
    if "/openai/v1" in endpoint:
        endpoint = endpoint.split("/openai/v1")[0]
        
    logger.info(f"[OpenAI] Initializing AsyncAzureOpenAI client with endpoint: {endpoint}")
    client = AsyncAzureOpenAI(
        azure_endpoint=endpoint,
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )
else:
    # ── Standard OpenAI Configuration ──
    # Fallback to standard OpenAI API (usually gets API key from environment variable OPENAI_API_KEY)
    logger.info("[OpenAI] Initializing standard AsyncOpenAI client")
    client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY", ""),
    )


async def generate_code(session: SessionData, user_message: str) -> dict:
    """
    Call OpenAI with the dataset context and user question.
    Returns one of:
      {"explanation": str, "code": str}                            — normal response
      {"explanation": "", "code": "", "out_of_scope": True,
       "soft_message": str}                                        — off-topic question
      {"explanation": str, "code": "", "truncated": True}         — response cut off at max_tokens
    
    Never raises exceptions — returns parsed response or empty code for errors.
    """
    try:
        system_prompt = build_system_prompt(
            filename=session.filename,
            columns=session.columns,
            dtypes=session.dtypes,
            row_count=session.row_count,
            sample_rows=session.sample_rows,
        )

        # Build messages — include chat history for multi-turn context.
        # We store only explanation summaries (NOT raw code) in history so the AI
        # does not copy-paste previous code blocks into new responses.
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(session.chat_history[-10:])
        messages.append({"role": "user", "content": build_user_message(user_message)})

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0.2,
            messages=messages,
            extra_body={"max_completion_tokens": settings.MAX_TOKENS},
        )

        # ── Max-tokens guard ──────────────────────────────────────────────────
        # If the model stopped because it hit the token limit the generated code
        # may be syntactically incomplete. Executing a truncated script can crash
        # the executor. We catch this here and refuse to run it.
        finish_reason = response.choices[0].finish_reason
        if finish_reason == "max_tokens":
            logger.warning(
                "[OpenAI] Response truncated (finish_reason=max_tokens). "
                "Skipping code execution to prevent partial-script crash."
            )
            truncated_msg = (
                "⚠️ The generated response was cut off because it was too long. "
                "Please try asking a more specific or narrower question so the answer fits within the token limit."
            )
            session.chat_history.append({"role": "user", "content": user_message})
            session.chat_history.append({
                "role": "assistant",
                "content": f"[Truncated — not executed] {truncated_msg}"
            })
            from app.core.session import save_session
            save_session(session)
            return {
                "explanation": truncated_msg,
                "code": "",
                "out_of_scope": False,
                "soft_message": None,
                "truncated": True,
            }
        # ─────────────────────────────────────────────────────────────────────

        raw = response.choices[0].message.content or ""
        parsed = _parse_response(raw)

        # Store concise history — skip history entry for out-of-scope so it doesn't
        # pollute context with irrelevant exchanges.
        session.chat_history.append({"role": "user", "content": user_message})
        if parsed.get("out_of_scope"):
            session.chat_history.append({
                "role": "assistant",
                "content": f"[Out of scope] {parsed['soft_message']}"
            })
        else:
            session.chat_history.append({
                "role": "assistant",
                "content": f"EXPLANATION: {parsed['explanation']}\n(Code was generated and executed separately.)"
            })

        from app.core.session import save_session
        save_session(session)

        return parsed

    except Exception as e:
        logger.error(f"[OpenAI] Code generation failed: {str(e)}", exc_info=True)
        # Return safe default (empty code, no error to user)
        return {
            "explanation": "Code generation encountered an issue. Please try again.",
            "code": "",
            "out_of_scope": False,
            "soft_message": None,
        }



def _parse_response(raw: str) -> dict:
    """
    Parse OpenAI response into structured format.
    Handles:
      - OUT_OF_SCOPE responses (off-topic questions)
      - EXPLANATION + CODE sections
      - Various code block formats (```python, CODE:, etc)
    """
    try:
        # ── Check for out-of-scope response first ──
        oos_match = re.match(r"OUT_OF_SCOPE:\s*(.+)", raw.strip(), re.IGNORECASE | re.DOTALL)
        if oos_match:
            soft_message = oos_match.group(1).strip().split("\n")[0]  # first line only
            return {
                "explanation": "",
                "code": "",
                "out_of_scope": True,
                "soft_message": soft_message,
            }

        explanation = ""
        code = ""

        # Extract explanation
        exp_match = re.search(r"EXPLANATION:\s*(.*?)(?=CODE:|```|$)", raw, re.DOTALL)
        if exp_match:
            explanation = exp_match.group(1).strip()

        # Extract code from ```python``` block
        code_match = re.search(r"```python\s*([\s\S]*?)```", raw)
        if code_match:
            code = code_match.group(1).strip()
        else:
            # Fallback: try CODE: format
            code_match2 = re.search(r"CODE:\s*([\s\S]+)$", raw)
            if code_match2:
                code = code_match2.group(1).strip()

        if not explanation:
            explanation = "Here is the generated code for your request."

        if code:
            code = _fix_merged_lines(code)

        return {
            "explanation": explanation,
            "code": code,
            "out_of_scope": False,
            "soft_message": None,
        }

    except Exception as e:
        logger.error(f"[Parse Response] Failed to parse OpenAI response: {str(e)}")
        # Return safe default
        return {
            "explanation": "Could not parse response properly.",
            "code": "",
            "out_of_scope": False,
            "soft_message": None,
        }


def _fix_merged_lines(code: str) -> str:
    """
    Fix cases where the LLM outputs multiple statements merged onto one line.
    E.g.: print("msg")import foo  →  print("msg")\\nimport foo

    Strategy: use regex to find closing ) followed immediately by a known
    statement-starting keyword, then insert a newline between them.
    Also adds blank lines before comment blocks.
    """
    try:
        BOUNDARY = re.compile(
            r'(\))'
            r'(?='                            # lookahead — don't consume
            r'import\s|from\s|for\s|if\s|while\s|with\s|def\s|class\s|'
            r'return\s|raise\s|print\s*\(|'
            r'plt\.|sns\.|pd\.|np\.|df[\.\[_]|'
            r'fig[,\s=\(]|ax[,\.\s]|#'
            r')'
        )

        # Apply repeatedly until stable (handles chains like )import)plt.)
        prev = None
        iterations = 0
        while prev != code and iterations < 10:  # Prevent infinite loops
            prev = code
            code = BOUNDARY.sub(r'\1\n', code)
            iterations += 1

        # Add blank line before # comment lines that directly follow code
        lines = code.split('\n')
        final = []
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith('#') and i > 0:
                prev_line = lines[i - 1].strip()
                if prev_line and not prev_line.startswith('#'):
                    final.append('')
            final.append(line)

        return '\n'.join(final)

    except Exception as e:
        logger.warning(f"[Fix Merged Lines] Could not fix merged lines: {str(e)}")
        # Return original code if fixing fails
        return code