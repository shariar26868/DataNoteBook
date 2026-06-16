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

    # Build messages — include chat history for multi-turn context.
    # We store only explanation summaries (NOT raw code) in history so the AI
    # does not copy-paste previous code blocks into new responses.
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(session.chat_history[-10:])
    messages.append({"role": "user", "content": build_user_message(user_message)})

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        max_tokens=settings.MAX_TOKENS,
        temperature=0.2,
        messages=messages,
    )

    raw = response.choices[0].message.content or ""
    parsed = _parse_response(raw)

    # Store concise history — explanation only, no code block
    session.chat_history.append({"role": "user", "content": user_message})
    session.chat_history.append({
        "role": "assistant",
        "content": f"EXPLANATION: {parsed['explanation']}\n(Code was generated and executed separately.)"
    })

    return parsed


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
        code_match2 = re.search(r"CODE:\s*([\s\S]+)$", raw)
        if code_match2:
            code = code_match2.group(1).strip()

    if not explanation:
        explanation = "Here is the generated code for your request."

    if code:
        code = _fix_merged_lines(code)

    return {"explanation": explanation, "code": code}


def _fix_merged_lines(code: str) -> str:
    """
    Fix cases where the LLM outputs multiple statements merged onto one line.
    E.g.: print("msg")import foo  →  print("msg")\\nimport foo

    Strategy: use regex to find closing ) followed immediately by a known
    statement-starting keyword, then insert a newline between them.
    Also adds blank lines before comment blocks.
    """
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
    while prev != code:
        prev = code
        code = BOUNDARY.sub(r'\1\n', code)

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
