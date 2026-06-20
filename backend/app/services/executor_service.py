import time
import traceback
import io
import sys
import os
import uuid
import threading
import queue
import asyncio
import pandas as pd
import numpy as np
import matplotlib
import ast
from typing import Optional
from pathlib import Path

from app.models.session import SessionData
from app.services.dataset_service import load_dataframe
from app.services.vault_service import get_vault_client
from app.core.config import settings


def _save_image_locally(image_id: str, img_bytes: bytes) -> str:
    """Save chart image to local uploads/images/ dir and return the serve URL."""
    images_dir = Path(settings.IMAGES_DIR)
    images_dir.mkdir(parents=True, exist_ok=True)
    filepath = images_dir / f"{image_id}.png"
    filepath.write_bytes(img_bytes)
    return f"/api/images/{image_id}.png"


def _upload_image_to_vault_bg(session: Optional[SessionData], image_id: str, img_bytes: bytes):
    """Upload chart image to Azure via vault in a background thread (fire-and-forget)."""
    async def _upload():
        try:
            vault = get_vault_client()
            if session and session.vault_project_id and session.vault_folder_id:
                await vault.upload_file_complete(
                    filename=f"{image_id}.png",
                    file_bytes=img_bytes,
                    project_id=session.vault_project_id,
                    folder_id=session.vault_folder_id,
                    content_type="image/png",
                )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[Vault] Image upload failed (non-critical): {e}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_upload())
        else:
            loop.run_until_complete(_upload())
    except RuntimeError:
        asyncio.run(_upload())


# Blocked keywords for basic sandboxing
BLOCKED = ["import os", "import sys", "import subprocess", "open(", "__import__",
           "eval(", "exec(", "compile(", "globals(", "locals("]


def _is_safe(code: str) -> tuple[bool, str]:
    for keyword in BLOCKED:
        if keyword in code:
            return False, f"Blocked keyword detected: `{keyword}`"
    return True, ""


def infer_df_name(filename: str) -> str:
    """Convert raw filenames (e.g. people_100.csv) to valid Python identifiers prefixed with df_."""
    import re
    # Strip extension
    base = filename.rsplit('.', 1)[0]
    # Replace non-alphanumeric characters with underscore
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', base)
    if sanitized.startswith('df_'):
        return sanitized
    return f"df_{sanitized}"


def _uses_df(code: str, session: Optional[SessionData] = None) -> bool:
    """Check if code explicitly references 'df' variable or the dynamic df variable name."""
    import re
    if bool(re.search(r'\bdf\b', code)):
        return True
    if session and session.filename:
        df_name = infer_df_name(session.filename)
        if bool(re.search(r'\b' + re.escape(df_name) + r'\b', code)):
            return True
    return False


def _exec_code(code: str, local_ns: dict):
    """
    Execute code in the local namespace.
    If the last statement is an expression, evaluate it and store the result
    in local_ns["__last_expr_result__"].
    """
    try:
        tree = ast.parse(code)
    except Exception:
        exec(code, {"__builtins__": __builtins__}, local_ns)
        return

    if not tree.body:
        return

    last_node = tree.body[-1]
    if isinstance(last_node, ast.Expr):
        tree.body.pop()
        if tree.body:
            exec(compile(tree, filename="<string>", mode="exec"), {"__builtins__": __builtins__}, local_ns)
        expr_val = eval(compile(ast.Expression(body=last_node.value), filename="<string>", mode="eval"), {"__builtins__": __builtins__}, local_ns)
        local_ns["__last_expr_result__"] = expr_val
    else:
        exec(code, {"__builtins__": __builtins__}, local_ns)


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
      2. The code actually references 'df' or dynamic df name
    Always provides pd, np, matplotlib imports.
    If a session exists, reuse its kernel namespace so variables persist across cells.
    """
    if session is not None:
        ns: dict = session.kernel_ns
        ns.setdefault("pd", pd)
        ns.setdefault("np", np)
    else:
        ns = {"pd": pd, "np": np}

    if session is not None and _uses_df(code, session):
        try:
            df = load_dataframe(session)
            ns["df"] = df
            if session.filename:
                df_name = infer_df_name(session.filename)
                ns[df_name] = df
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
        _exec_code(code, local_ns)

        if "__last_expr_result__" in local_ns:
            expr_val = local_ns["__last_expr_result__"]
            if isinstance(expr_val, (pd.DataFrame, pd.Series)):
                result_obj = expr_val
            elif expr_val is not None:
                print(repr(expr_val))
        else:
            result_obj = _capture_result(local_ns, initial_keys)

        # Persist kernel state and dataset modifications between cells.
        if session is not None:
            if session.filename:
                df_name = infer_df_name(session.filename)
                current_df = local_ns.get("df")
                current_df_name = local_ns.get(df_name)
                if current_df is not current_df_name:
                    orig_df = initial_ns.get("df")
                    if current_df is not orig_df and current_df_name is orig_df:
                        local_ns[df_name] = current_df
                    elif current_df_name is not orig_df and current_df is orig_df:
                        local_ns["df"] = current_df_name
                    else:
                        if current_df is not None:
                            local_ns[df_name] = current_df
                        elif current_df_name is not None:
                            local_ns["df"] = current_df_name

            session.kernel_ns = local_ns
            if _uses_df(code, session) and "df" in local_ns and isinstance(local_ns["df"], pd.DataFrame):
                session.cached_df = local_ns["df"]

        # Close all active pyplot figures to avoid leaking plots into subsequent executions
        try:
            import matplotlib.pyplot as plt
            plt.close('all')
        except Exception:
            pass

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
            _exec_code(code, local_ns)

            if "__last_expr_result__" in local_ns:
                expr_val = local_ns["__last_expr_result__"]
                if isinstance(expr_val, (pd.DataFrame, pd.Series)):
                    result_obj = expr_val
                elif expr_val is not None:
                    print(repr(expr_val))
            else:
                result_obj = _capture_result(local_ns, initial_keys)

            if session is not None:
                if session.filename:
                    df_name = infer_df_name(session.filename)
                    current_df = local_ns.get("df")
                    current_df_name = local_ns.get(df_name)
                    if current_df is not current_df_name:
                        orig_df = initial_ns.get("df")
                        if current_df is not orig_df and current_df_name is orig_df:
                            local_ns[df_name] = current_df
                        elif current_df_name is not orig_df and current_df is orig_df:
                            local_ns["df"] = current_df_name
                        else:
                            if current_df is not None:
                                local_ns[df_name] = current_df
                            elif current_df_name is not None:
                                local_ns["df"] = current_df_name

                session.kernel_ns = local_ns
                if _uses_df(code, session) and "df" in local_ns and isinstance(local_ns["df"], pd.DataFrame):
                    session.cached_df = local_ns["df"]

            # Capture matplotlib figure → local + Azure
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
                # Save locally for frontend display
                image_url = _save_image_locally(message_id, img_bytes)
                # Upload to Azure in background (fire-and-forget)
                _upload_image_to_vault_bg(session, message_id, img_bytes)

            # Close all active pyplot figures to avoid leaking plots into subsequent executions
            try:
                import matplotlib.pyplot as plt
                plt.close('all')
            except Exception:
                pass

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
    message_id = str(uuid.uuid4())

    try:
        local_ns = dict(initial_ns)
        _exec_code(code, local_ns)

        if "__last_expr_result__" in local_ns:
            expr_val = local_ns["__last_expr_result__"]
            if expr_val is not None and not isinstance(expr_val, (pd.DataFrame, pd.Series)):
                print(repr(expr_val))

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
            # Save locally for frontend display
            image_url = _save_image_locally(message_id, img_bytes)
            # Upload to Azure in background
            _upload_image_to_vault_bg(session, message_id, img_bytes)

        # Close all active pyplot figures to avoid leaking plots into subsequent executions
        try:
            import matplotlib.pyplot as plt
            plt.close('all')
        except Exception:
            pass

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
        "output": printed or None,
        "execution_time_ms": elapsed,
    }
