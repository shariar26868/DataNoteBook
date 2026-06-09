import time
import traceback
import io
import sys
import uuid
import threading
import queue
import pandas as pd
import numpy as np
import matplotlib
from typing import Optional

from app.models.session import SessionData
from app.services.dataset_service import load_dataframe
from app.services.s3_service import upload_bytes_to_s3, generate_presigned_url
from app.core.config import settings


# Blocked keywords for basic sandboxing
BLOCKED = ["import os", "import sys", "import subprocess", "open(", "__import__",
           "eval(", "exec(", "compile(", "globals(", "locals("]


def _is_safe(code: str) -> tuple[bool, str]:
    for keyword in BLOCKED:
        if keyword in code:
            return False, f"Blocked keyword detected: `{keyword}`"
    return True, ""


def _uses_df(code: str) -> bool:
    """Check if code explicitly references 'df' variable."""
    import re
    return bool(re.search(r'\bdf\b', code))


class _LineStreamWriter(io.TextIOBase):
    """Stdout replacement that puts each written line into a queue."""

    def __init__(self, q: queue.Queue):
        self._q = q
        self._buf = ""

    def write(self, s: str) -> int:
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._q.put(("stdout", line))
        return len(s)

    def flush(self):
        if self._buf:
            self._q.put(("stdout", self._buf))
            self._buf = ""


def _build_namespace(session: Optional[SessionData], code: str) -> dict:
    """
    Build execution namespace.
    Only loads the dataset if:
      1. A session exists, AND
      2. The code actually references 'df'
    Always provides pd, np, matplotlib imports.
    """
    ns: dict = {"pd": pd, "np": np}

    if session is not None and _uses_df(code):
        try:
            ns["df"] = load_dataframe(session)
        except Exception as e:
            raise RuntimeError(f"Could not load dataset: {str(e)}")

    return ns


def _capture_result(local_ns: dict, initial_ns_keys: set):
    """
    Capture the last DataFrame/Series that was EXPLICITLY assigned by user code
    (i.e., a variable that did NOT exist before exec and is now a DataFrame/Series).
    This avoids returning the injected `df` itself as a result.
    """
    new_vars = {k: v for k, v in local_ns.items() if k not in initial_ns_keys}
    for var in reversed(list(new_vars.values())):
        if isinstance(var, (pd.DataFrame, pd.Series)):
            return var

    # Also check if user assigned to 'result' or a name ending in _df / _result
    for name in ['result', 'output', 'out']:
        if name in local_ns and isinstance(local_ns[name], (pd.DataFrame, pd.Series)):
            return local_ns[name]

    return None


def execute_code(session: Optional[SessionData], code: str) -> dict:
    safe, reason = _is_safe(code)
    if not safe:
        return {"error": reason}

    try:
        initial_ns = _build_namespace(session, code)
    except RuntimeError as e:
        return {"error": str(e)}

    initial_keys = set(initial_ns.keys())
    stdout_capture = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = stdout_capture

    result_obj = None
    error = None
    start = time.time()

    try:
        local_ns = dict(initial_ns)
        exec(code, {"__builtins__": __builtins__}, local_ns)
        result_obj = _capture_result(local_ns, initial_keys)

    except Exception:
        error = traceback.format_exc(limit=5)
    finally:
        sys.stdout = old_stdout

    elapsed = round((time.time() - start) * 1000, 2)
    printed = stdout_capture.getvalue().strip()

    if error:
        return {"error": error, "execution_time_ms": elapsed}

    if isinstance(result_obj, pd.DataFrame):
        table = result_obj.head(50).fillna("").to_dict(orient="records")
        return {"table": table, "output": printed or None, "execution_time_ms": elapsed}

    if isinstance(result_obj, pd.Series):
        df_out = result_obj.reset_index()
        df_out.columns = [str(c) for c in df_out.columns]
        table = df_out.head(50).fillna("").to_dict(orient="records")
        return {"table": table, "output": printed or None, "execution_time_ms": elapsed}

    return {"output": printed or "Executed successfully (no output).", "execution_time_ms": elapsed}


def execute_code_streaming(session: Optional[SessionData], code: str):
    """
    Generator yielding (event_type, data) tuples for SSE streaming.
    Works with or without a dataset session.
    """
    safe, reason = _is_safe(code)
    if not safe:
        yield ("error", reason)
        return

    try:
        matplotlib.use("Agg")
    except Exception:
        pass

    try:
        initial_ns = _build_namespace(session, code)
    except RuntimeError as e:
        yield ("error", str(e))
        return

    initial_keys = set(initial_ns.keys())
    output_queue: queue.Queue = queue.Queue()
    old_stdout = sys.stdout
    sys.stdout = _LineStreamWriter(output_queue)

    result_obj = None
    error = None
    image_url = None
    message_id = str(uuid.uuid4())

    def _run():
        nonlocal result_obj, error, image_url
        try:
            local_ns = dict(initial_ns)
            exec(code, {"__builtins__": __builtins__}, local_ns)

            # Capture explicitly assigned DataFrame/Series (not the injected df)
            result_obj = _capture_result(local_ns, initial_keys)

            # Capture matplotlib figure → S3
            fig = None
            for v in local_ns.values():
                try:
                    if isinstance(v, matplotlib.figure.Figure):
                        fig = v
                        break
                except Exception:
                    continue

            if fig is None and "plt" in local_ns:
                try:
                    fig = local_ns["plt"].gcf()
                    if not fig.get_axes():
                        fig = None
                except Exception:
                    fig = None

            if fig is not None:
                img_buf = io.BytesIO()
                fig.savefig(img_buf, format="png", bbox_inches="tight")
                img_buf.seek(0)
                s3_key = f"{settings.S3_IMAGES_PREFIX}/{message_id}.png"
                upload_bytes_to_s3(img_buf.read(), s3_key, "image/png")
                image_url = generate_presigned_url(s3_key, settings.S3_PRESIGNED_URL_EXPIRY)

        except Exception:
            error = traceback.format_exc(limit=5)
        finally:
            output_queue.put(("__done__", None))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    while True:
        try:
            event, data = output_queue.get(timeout=60)
        except queue.Empty:
            yield ("error", "Execution timed out (60s).")
            break

        if event == "__done__":
            break

        yield (event, data)

    sys.stdout = old_stdout
    thread.join(timeout=5)

    if error:
        yield ("error", error)
        return

    if image_url:
        yield ("image", image_url)

    if isinstance(result_obj, pd.DataFrame):
        table = result_obj.head(50).fillna("").to_dict(orient="records")
        yield ("table", table)
    elif isinstance(result_obj, pd.Series):
        df_out = result_obj.reset_index()
        df_out.columns = [str(c) for c in df_out.columns]
        table = df_out.head(50).fillna("").to_dict(orient="records")
        yield ("table", table)

    yield ("done", "Execution complete.")


def execute_code_save_image(session: Optional[SessionData], code: str) -> dict:
    """Execute code and save generated plot to S3. Returns presigned image URL."""
    safe, reason = _is_safe(code)
    if not safe:
        return {"error": reason}

    try:
        matplotlib.use("Agg")
    except Exception:
        pass

    try:
        initial_ns = _build_namespace(session, code)
    except RuntimeError as e:
        return {"error": str(e)}

    stdout_capture = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = stdout_capture

    error = None
    start = time.time()
    image_url = None
    s3_image_key = None
    message_id = str(uuid.uuid4())

    try:
        local_ns = dict(initial_ns)
        exec(code, {"__builtins__": __builtins__}, local_ns)

        fig = None
        for v in local_ns.values():
            try:
                if isinstance(v, matplotlib.figure.Figure):
                    fig = v
                    break
            except Exception:
                continue

        if fig is None and "plt" in local_ns:
            try:
                fig = local_ns["plt"].gcf()
                if not fig.get_axes():
                    fig = None
            except Exception:
                fig = None

        if fig is not None:
            img_buf = io.BytesIO()
            fig.savefig(img_buf, format="png", bbox_inches="tight")
            img_buf.seek(0)
            img_bytes = img_buf.read()
            s3_image_key = f"{settings.S3_IMAGES_PREFIX}/{message_id}.png"
            upload_bytes_to_s3(img_bytes, s3_image_key, "image/png")
            image_url = generate_presigned_url(s3_image_key, settings.S3_PRESIGNED_URL_EXPIRY)

    except Exception:
        error = traceback.format_exc(limit=5)
    finally:
        sys.stdout = old_stdout

    elapsed = round((time.time() - start) * 1000, 2)
    printed = stdout_capture.getvalue().strip()

    if error:
        return {"error": error}

    return {
        "message_id": message_id,
        "image_url": image_url,
        "s3_key": s3_image_key,
        "output": printed or None,
        "execution_time_ms": elapsed,
    }
