# import time
# import traceback
# import io
# import sys
# import os
# import uuid
# import threading
# import queue
# import asyncio
# import pandas as pd
# import numpy as np
# import matplotlib
# import ast
# from typing import Optional
# from pathlib import Path

# from app.models.session import SessionData
# from app.services.dataset_service import load_dataframe
# from app.services.vault_service import get_vault_client
# from app.core.config import settings


# def _save_image_locally(image_id: str, img_bytes: bytes) -> str:
#     """Save chart image to local uploads/images/ dir and return the serve URL."""
#     images_dir = Path(settings.IMAGES_DIR)
#     images_dir.mkdir(parents=True, exist_ok=True)
#     filepath = images_dir / f"{image_id}.png"
#     filepath.write_bytes(img_bytes)
#     return f"/api/images/{image_id}.png"


# def _upload_image_to_vault_bg(session: Optional[SessionData], image_id: str, img_bytes: bytes):
#     """Upload chart image to Azure via vault in a background thread (fire-and-forget)."""
#     async def _upload():
#         try:
#             vault = get_vault_client()
#             if session and session.vault_project_id and session.vault_folder_id:
#                 await vault.upload_file_complete(
#                     filename=f"{image_id}.png",
#                     file_bytes=img_bytes,
#                     project_id=session.vault_project_id,
#                     folder_id=session.vault_folder_id,
#                     content_type="image/png",
#                 )
#         except Exception as e:
#             import logging
#             logging.getLogger(__name__).warning(f"[Vault] Image upload failed (non-critical): {e}")

#     try:
#         loop = asyncio.get_event_loop()
#         if loop.is_running():
#             asyncio.ensure_future(_upload())
#         else:
#             loop.run_until_complete(_upload())
#     except RuntimeError:
#         asyncio.run(_upload())


# # Blocked keywords for basic sandboxing
# # NOTE: locals() is intentionally NOT blocked — it is safe and the AI uses it for
# # checking variable availability. Only globals() is dangerous for sandbox escape.
# BLOCKED = ["import os", "import sys", "import subprocess", "open(", "__import__",
#            "eval(", "exec(", "compile(", "globals("]


# def _is_safe(code: str) -> tuple[bool, str]:
#     for keyword in BLOCKED:
#         if keyword in code:
#             return False, f"Blocked keyword detected: `{keyword}`"
#     return True, ""


# def infer_df_name(filename: str) -> str:
#     """Convert raw filenames (e.g. people_100.csv) to valid Python identifiers prefixed with df_."""
#     import re
#     # Strip extension
#     base = filename.rsplit('.', 1)[0]
#     # Replace non-alphanumeric characters with underscore
#     sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', base)
#     if sanitized.startswith('df_'):
#         return sanitized
#     return f"df_{sanitized}"


# def _uses_df(code: str, session: Optional[SessionData] = None) -> bool:
#     """Check if code explicitly references 'df' variable or the dynamic df variable name."""
#     import re
#     if bool(re.search(r'\bdf\b', code)):
#         return True
#     if session and session.filename:
#         df_name = infer_df_name(session.filename)
#         if bool(re.search(r'\b' + re.escape(df_name) + r'\b', code)):
#             return True
#     return False


# def _exec_code(code: str, local_ns: dict):
#     """
#     Execute code in the local namespace.
#     If the last statement is an expression, evaluate it and store the result
#     in local_ns["__last_expr_result__"].
#     """
#     try:
#         tree = ast.parse(code)
#     except Exception:
#         exec(code, {"__builtins__": __builtins__}, local_ns)
#         return

#     if not tree.body:
#         return

#     last_node = tree.body[-1]
#     if isinstance(last_node, ast.Expr):
#         tree.body.pop()
#         if tree.body:
#             exec(compile(tree, filename="<string>", mode="exec"), {"__builtins__": __builtins__}, local_ns)
#         expr_val = eval(compile(ast.Expression(body=last_node.value), filename="<string>", mode="eval"), {"__builtins__": __builtins__}, local_ns)
#         local_ns["__last_expr_result__"] = expr_val
#     else:
#         exec(code, {"__builtins__": __builtins__}, local_ns)


# class _LineStreamWriter(io.TextIOBase):
#     """Stdout replacement that puts each written line into a queue."""

#     def __init__(self, q: queue.Queue):
#         self._q = q
#         self._buf = ""

#     def write(self, s: str) -> int:
#         self._buf += s
#         while "\n" in self._buf:
#             line, self._buf = self._buf.split("\n", 1)
#             self._q.put(("stdout", line))
#         return len(s)

#     def flush(self):
#         if self._buf:
#             self._q.put(("stdout", self._buf))
#             self._buf = ""


# def _build_namespace(session: Optional[SessionData], code: str) -> dict:
#     """
#     Build execution namespace.
#     Always provides pd, np imports.
#     If a session exists, reuse its kernel namespace so variables persist across cells.
#     If a session has a cached DataFrame, ALWAYS inject 'df' (and the dynamic df name)
#     into the namespace — regardless of whether the generated code explicitly mentions 'df'.
#     This prevents NameError when the AI generates guards like `if 'df' in locals()` or
#     performs dataset operations without the word 'df' appearing in the prompt.
#     """
#     if session is not None:
#         ns: dict = session.kernel_ns
#         ns.setdefault("pd", pd)
#         ns.setdefault("np", np)
#     else:
#         ns = {"pd": pd, "np": np}

#     if session is not None:
#         try:
#             df = load_dataframe(session)
#             ns["df"] = df
#             if session.filename:
#                 df_name = infer_df_name(session.filename)
#                 ns[df_name] = df
#         except Exception as e:
#             # Log so it's visible in backend logs — code may still run if df isn't needed
#             import logging
#             logging.getLogger(__name__).warning(
#                 f"[Executor] Could not load df for session {getattr(session, 'session_id', '?')}: {e}"
#             )

#     return ns


# def _capture_result(local_ns: dict, initial_ns_keys: set):
#     """
#     Capture the last DataFrame/Series that was EXPLICITLY assigned by user code
#     (i.e., a variable that did NOT exist before exec and is now a DataFrame/Series).
#     This avoids returning the injected `df` itself as a result.
#     """
#     new_vars = {k: v for k, v in local_ns.items() if k not in initial_ns_keys}
#     for var in reversed(list(new_vars.values())):
#         if isinstance(var, (pd.DataFrame, pd.Series)):
#             return var

#     # Also check if user assigned to 'result' or a name ending in _df / _result
#     for name in ['result', 'output', 'out']:
#         if name in local_ns and isinstance(local_ns[name], (pd.DataFrame, pd.Series)):
#             return local_ns[name]

#     return None


# def execute_code(session: Optional[SessionData], code: str) -> dict:
#     safe, reason = _is_safe(code)
#     if not safe:
#         return {"error": reason}

#     try:
#         initial_ns = _build_namespace(session, code)
#     except RuntimeError as e:
#         return {"error": str(e)}

#     initial_keys = set(initial_ns.keys())
#     stdout_capture = io.StringIO()
#     old_stdout = sys.stdout
#     sys.stdout = stdout_capture

#     result_obj = None
#     error = None
#     start = time.time()

#     try:
#         local_ns = dict(initial_ns)
#         _exec_code(code, local_ns)

#         if "__last_expr_result__" in local_ns:
#             expr_val = local_ns["__last_expr_result__"]
#             if isinstance(expr_val, (pd.DataFrame, pd.Series)):
#                 result_obj = expr_val
#             elif expr_val is not None:
#                 print(repr(expr_val))
#         else:
#             result_obj = _capture_result(local_ns, initial_keys)

#         # Persist kernel state and dataset modifications between cells.
#         if session is not None:
#             if session.filename:
#                 df_name = infer_df_name(session.filename)
#                 current_df = local_ns.get("df")
#                 current_df_name = local_ns.get(df_name)
#                 if current_df is not current_df_name:
#                     orig_df = initial_ns.get("df")
#                     if current_df is not orig_df and current_df_name is orig_df:
#                         local_ns[df_name] = current_df
#                     elif current_df_name is not orig_df and current_df is orig_df:
#                         local_ns["df"] = current_df_name
#                     else:
#                         if current_df is not None:
#                             local_ns[df_name] = current_df
#                         elif current_df_name is not None:
#                             local_ns["df"] = current_df_name

#             session.kernel_ns = local_ns
#             if _uses_df(code, session) and "df" in local_ns and isinstance(local_ns["df"], pd.DataFrame):
#                 session.cached_df = local_ns["df"]

#         # Close all active pyplot figures to avoid leaking plots into subsequent executions
#         try:
#             import matplotlib.pyplot as plt
#             plt.close('all')
#         except Exception:
#             pass

#     except Exception:
#         error = traceback.format_exc(limit=5)
#     finally:
#         sys.stdout = old_stdout

#     elapsed = round((time.time() - start) * 1000, 2)
#     printed = stdout_capture.getvalue().strip()

#     if error:
#         return {"error": error, "execution_time_ms": elapsed}

#     if isinstance(result_obj, pd.DataFrame):
#         table = result_obj.head(50).fillna("").to_dict(orient="records")
#         return {"table": table, "output": printed or None, "execution_time_ms": elapsed}

#     if isinstance(result_obj, pd.Series):
#         df_out = result_obj.reset_index()
#         df_out.columns = [str(c) for c in df_out.columns]
#         table = df_out.head(50).fillna("").to_dict(orient="records")
#         return {"table": table, "output": printed or None, "execution_time_ms": elapsed}

#     return {"output": printed or "Executed successfully (no output).", "execution_time_ms": elapsed}


# def execute_code_streaming(session: Optional[SessionData], code: str):
#     """
#     Generator yielding (event_type, data) tuples for SSE streaming.
#     Works with or without a dataset session.
#     """
#     safe, reason = _is_safe(code)
#     if not safe:
#         yield ("error", reason)
#         return

#     try:
#         matplotlib.use("Agg")
#     except Exception:
#         pass

#     try:
#         initial_ns = _build_namespace(session, code)
#     except RuntimeError as e:
#         yield ("error", str(e))
#         return

#     initial_keys = set(initial_ns.keys())
#     output_queue: queue.Queue = queue.Queue()
#     old_stdout = sys.stdout
#     sys.stdout = _LineStreamWriter(output_queue)

#     result_obj = None
#     error = None
#     image_url = None
#     message_id = str(uuid.uuid4())

#     def _run():
#         nonlocal result_obj, error, image_url
#         try:
#             local_ns = dict(initial_ns)
#             _exec_code(code, local_ns)

#             if "__last_expr_result__" in local_ns:
#                 expr_val = local_ns["__last_expr_result__"]
#                 if isinstance(expr_val, (pd.DataFrame, pd.Series)):
#                     result_obj = expr_val
#                 elif expr_val is not None:
#                     print(repr(expr_val))
#             else:
#                 result_obj = _capture_result(local_ns, initial_keys)

#             if session is not None:
#                 if session.filename:
#                     df_name = infer_df_name(session.filename)
#                     current_df = local_ns.get("df")
#                     current_df_name = local_ns.get(df_name)
#                     if current_df is not current_df_name:
#                         orig_df = initial_ns.get("df")
#                         if current_df is not orig_df and current_df_name is orig_df:
#                             local_ns[df_name] = current_df
#                         elif current_df_name is not orig_df and current_df is orig_df:
#                             local_ns["df"] = current_df_name
#                         else:
#                             if current_df is not None:
#                                 local_ns[df_name] = current_df
#                             elif current_df_name is not None:
#                                 local_ns["df"] = current_df_name

#                 session.kernel_ns = local_ns
#                 if _uses_df(code, session) and "df" in local_ns and isinstance(local_ns["df"], pd.DataFrame):
#                     session.cached_df = local_ns["df"]

#             # Capture matplotlib figure → local + Azure
#             fig = None
#             for v in local_ns.values():
#                 try:
#                     if isinstance(v, matplotlib.figure.Figure):
#                         fig = v
#                         break
#                 except Exception:
#                     continue

#             if fig is None and "plt" in local_ns:
#                 try:
#                     fig = local_ns["plt"].gcf()
#                     if not fig.get_axes():
#                         fig = None
#                 except Exception:
#                     fig = None

#             if fig is not None:
#                 img_buf = io.BytesIO()
#                 fig.savefig(img_buf, format="png", bbox_inches="tight")
#                 img_buf.seek(0)
#                 img_bytes = img_buf.read()
#                 # Save locally for frontend display
#                 image_url = _save_image_locally(message_id, img_bytes)
#                 # Upload to Azure in background (fire-and-forget)
#                 _upload_image_to_vault_bg(session, message_id, img_bytes)

#             # Close all active pyplot figures to avoid leaking plots into subsequent executions
#             try:
#                 import matplotlib.pyplot as plt
#                 plt.close('all')
#             except Exception:
#                 pass

#         except Exception:
#             error = traceback.format_exc(limit=5)
#         finally:
#             output_queue.put(("__done__", None))

#     thread = threading.Thread(target=_run, daemon=True)
#     thread.start()

#     while True:
#         try:
#             event, data = output_queue.get(timeout=60)
#         except queue.Empty:
#             yield ("error", "Execution timed out (60s).")
#             break

#         if event == "__done__":
#             break

#         yield (event, data)

#     sys.stdout = old_stdout
#     thread.join(timeout=5)

#     if error:
#         yield ("error", error)
#         return

#     if image_url:
#         yield ("image", image_url)

#     if isinstance(result_obj, pd.DataFrame):
#         table = result_obj.head(50).fillna("").to_dict(orient="records")
#         yield ("table", table)
#     elif isinstance(result_obj, pd.Series):
#         df_out = result_obj.reset_index()
#         df_out.columns = [str(c) for c in df_out.columns]
#         table = df_out.head(50).fillna("").to_dict(orient="records")
#         yield ("table", table)

#     yield ("done", "Execution complete.")


# def execute_code_save_image(session: Optional[SessionData], code: str) -> dict:
#     """Execute code and save generated plot to S3. Returns presigned image URL."""
#     safe, reason = _is_safe(code)
#     if not safe:
#         return {"error": reason}

#     try:
#         matplotlib.use("Agg")
#     except Exception:
#         pass

#     try:
#         initial_ns = _build_namespace(session, code)
#     except RuntimeError as e:
#         return {"error": str(e)}

#     stdout_capture = io.StringIO()
#     old_stdout = sys.stdout
#     sys.stdout = stdout_capture

#     error = None
#     start = time.time()
#     image_url = None
#     message_id = str(uuid.uuid4())

#     try:
#         local_ns = dict(initial_ns)
#         _exec_code(code, local_ns)

#         if "__last_expr_result__" in local_ns:
#             expr_val = local_ns["__last_expr_result__"]
#             if expr_val is not None and not isinstance(expr_val, (pd.DataFrame, pd.Series)):
#                 print(repr(expr_val))

#         fig = None
#         for v in local_ns.values():
#             try:
#                 if isinstance(v, matplotlib.figure.Figure):
#                     fig = v
#                     break
#             except Exception:
#                 continue

#         if fig is None and "plt" in local_ns:
#             try:
#                 fig = local_ns["plt"].gcf()
#                 if not fig.get_axes():
#                     fig = None
#             except Exception:
#                 fig = None

#         if fig is not None:
#             img_buf = io.BytesIO()
#             fig.savefig(img_buf, format="png", bbox_inches="tight")
#             img_buf.seek(0)
#             img_bytes = img_buf.read()
#             # Save locally for frontend display
#             image_url = _save_image_locally(message_id, img_bytes)
#             # Upload to Azure in background
#             _upload_image_to_vault_bg(session, message_id, img_bytes)

#         # Close all active pyplot figures to avoid leaking plots into subsequent executions
#         try:
#             import matplotlib.pyplot as plt
#             plt.close('all')
#         except Exception:
#             pass

#     except Exception:
#         error = traceback.format_exc(limit=5)
#     finally:
#         sys.stdout = old_stdout

#     elapsed = round((time.time() - start) * 1000, 2)
#     printed = stdout_capture.getvalue().strip()

#     if error:
#         return {"error": error}

#     return {
#         "message_id": message_id,
#         "image_url": image_url,
#         "output": printed or None,
#         "execution_time_ms": elapsed,
#     }





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
import logging
from typing import Optional
from pathlib import Path

try:
    matplotlib.use("Agg")
except Exception:
    logging.getLogger(__name__).warning("Could not set matplotlib backend to Agg", exc_info=True)

from app.models.session import SessionData
from app.services.dataset_service import load_dataframe
from app.services.vault_service import get_vault_client
from app.core.config import settings

logger = logging.getLogger(__name__)


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
            logger.warning(f"[Vault] Image upload failed (non-critical): {e}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_upload())
        else:
            loop.run_until_complete(_upload())
    except RuntimeError:
        asyncio.run(_upload())


# Blocked keywords for sandboxing — only truly dangerous operations
# NOTE: open() is intentionally NOT blocked — sklearn, joblib, and other
# legitimate libraries use it internally. Only direct shell/OS escapes are blocked.
BLOCKED = [
    "import subprocess",
    "__import__(",
    "compile(",
    "__builtins__",
    "os.system",
    "os.popen",
    "os.execv",
    "os.execve",
    "os.spawn",
    "subprocess.run",
    "subprocess.call",
    "subprocess.Popen",
]


def _is_safe(code: str) -> tuple[bool, str]:
    for keyword in BLOCKED:
        if keyword in code:
            return False, f"Security restriction: `{keyword}` is not permitted in notebook code."
    return True, ""


def _check_syntax(code: str) -> str | None:
    """
    Optional pre-flight syntax check. Returns a warning string if the code
    has an obvious syntax error, or None if the code looks parseable.

    NOTE: This function NEVER blocks execution. A SyntaxError here means
    Python's exec() will also raise it and return a clean error to the user.
    We keep this only for logging purposes.
    """
    if not code or not code.strip():
        return None
    try:
        ast.parse(code)
        return None  # All good
    except SyntaxError as e:
        # Log it but do NOT block — let exec() handle it naturally
        logger.debug(f"[Executor] Pre-flight syntax check failed: {e}")
        return str(e)
    except Exception:
        return None


def _format_error(tb_str: str) -> str:
    """Format traceback to be clean and readable for the user, hiding internal framework lines."""
    if not tb_str:
        return "Unknown execution error."
    lines = tb_str.splitlines()
    cleaned = []
    for line in lines:
        if "executor_service.py" in line or "execute.py" in line:
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()




def infer_df_name(filename: str) -> str:
    """Convert raw filenames (e.g people_100.csv) to valid Python identifiers prefixed with df_."""
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
    local_ns.setdefault("__builtins__", __builtins__)
    try:
        tree = ast.parse(code)
    except Exception:
        exec(code, local_ns, local_ns)
        return

    if not tree.body:
        return

    last_node = tree.body[-1]
    if isinstance(last_node, ast.Expr):
        tree.body.pop()
        if tree.body:
            exec(compile(tree, filename="<string>", mode="exec"), local_ns, local_ns)
        expr_val = eval(compile(ast.Expression(body=last_node.value), filename="<string>", mode="eval"), local_ns, local_ns)
        local_ns["__last_expr_result__"] = expr_val
    else:
        exec(code, local_ns, local_ns)


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
    Always provides pd, np imports.
    If a session exists, reuse its kernel namespace so variables persist across cells.
    If a session has a cached DataFrame, ALWAYS inject 'df' (and the dynamic df name)
    into the namespace — regardless of whether the generated code explicitly mentions 'df'.
    
    Raises RuntimeError if dataset cannot be loaded.
    """
    if session is not None:
        ns: dict = session.kernel_ns
        ns.setdefault("pd", pd)
        ns.setdefault("np", np)
    else:
        ns = {"pd": pd, "np": np}
        logger.info("[Executor] No session provided, running in clean namespace")

    # ── Inject File Management & Cleaning Helpers ──
    def clean_dataset_wrapper(data_df):
        from app.utils.data_cleaner import clean_dataset as run_clean
        return run_clean(data_df)

    def save_to_vault_wrapper(data, filename):
        import asyncio
        import io
        from app.services.vault_service import get_vault_client
        
        if session is None:
            print("Error: No active session. Cannot save to Vault.")
            return False

        if isinstance(data, pd.DataFrame):
            buf = io.BytesIO()
            if filename.endswith(('.xlsx', '.xls')):
                data.to_excel(buf, index=False)
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            else:
                data.to_csv(buf, index=False)
                content_type = "text/csv"
            file_bytes = buf.getvalue()
        elif isinstance(data, bytes):
            file_bytes = data
            content_type = "application/octet-stream"
        else:
            print("Error: data must be a pandas DataFrame or raw bytes.")
            return False

        async def _upload():
            vault = get_vault_client()
            project_id = session.vault_project_id
            folder_id = session.vault_folder_id
            if not project_id or not folder_id:
                project_id, folder_id = await vault.setup_global_notebooks_storage()
            
            file_data = await vault.upload_file_complete(
                filename=filename,
                file_bytes=file_bytes,
                project_id=project_id,
                folder_id=folder_id,
                content_type=content_type
            )
            file_id = file_data.get("id")
            if file_id:
                await vault.update_upload_status(file_id, {"upload_status": "completed"})
                print(f"File '{filename}' successfully saved/uploaded to Vault (ID: {file_id})")
                
                # Update session details so the active dataset switches to this new file
                if session is not None:
                    session.filename = filename
                    session.vault_file_id = file_id
                    session.blob_name = file_data.get("blob_name", session.blob_name)
                    if isinstance(data, pd.DataFrame):
                        session.columns = [str(c) for c in data.columns.tolist()]
                        # Update dtypes
                        dtypes = {}
                        df_sample = data.head(5)
                        for col in df_sample.columns:
                            if pd.api.types.is_numeric_dtype(df_sample[col]):
                                dtypes[str(col)] = "float"
                            else:
                                dtypes[str(col)] = "str"
                        session.dtypes = dtypes
                        session.row_count = len(data)
                        session.sample_rows = df_sample.fillna("").to_dict(orient="records")
                        session.cached_df = data
                    
                    from app.core.session import save_session
                    save_session(session)
                return True
            else:
                print(f"File '{filename}' registered in Vault but could not confirm completion status.")
                return False

        # Run async synchronously
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _upload())
                    return future.result(timeout=30)
            else:
                return loop.run_until_complete(_upload())
        except Exception as e:
            try:
                return asyncio.run(_upload())
            except Exception as e2:
                print(f"Error saving to Vault: {e2}")
                return False

    def rename_in_vault_wrapper(old_name, new_name):
        import asyncio
        from app.services.vault_service import get_vault_client
        if session is None:
            print("Error: No active session.")
            return False

        async def _rename():
            vault = get_vault_client()
            resources = await vault.list_resources(parent_id=session.vault_folder_id, project_id=session.vault_project_id)
            file_id = None
            for r in resources:
                if r.get("type") == "file" and r.get("name") == old_name:
                    file_id = r.get("id")
                    break
            
            if not file_id:
                print(f"Error: File '{old_name}' not found in current folder.")
                return False
                
            await vault.rename_resource(file_id, new_name)
            print(f"Successfully renamed file '{old_name}' to '{new_name}'")
            return True

        # Run async synchronously
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _rename())
                    return future.result(timeout=30)
            else:
                return loop.run_until_complete(_rename())
        except Exception as e:
            try:
                return asyncio.run(_rename())
            except Exception as e2:
                print(f"Error renaming file: {e2}")
                return False

    def delete_from_vault_wrapper(filename):
        import asyncio
        from app.services.vault_service import get_vault_client
        if session is None:
            print("Error: No active session.")
            return False

        async def _delete():
            vault = get_vault_client()
            resources = await vault.list_resources(parent_id=session.vault_folder_id, project_id=session.vault_project_id)
            file_id = None
            for r in resources:
                if r.get("type") == "file" and r.get("name") == filename:
                    file_id = r.get("id")
                    break
            
            if not file_id:
                print(f"Error: File '{filename}' not found in current folder.")
                return False

            url = f"{vault._base_url}/vault_resources/{file_id}"
            await vault._request("DELETE", url)
            print(f"Successfully deleted file '{filename}' from Vault.")
            return True

        # Run async synchronously
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _delete())
                    return future.result(timeout=30)
            else:
                return loop.run_until_complete(_delete())
        except Exception as e:
            try:
                return asyncio.run(_delete())
            except Exception as e2:
                print(f"Error deleting file: {e2}")
                return False

    def list_vault_files_wrapper():
        import asyncio
        from app.services.vault_service import get_vault_client
        if session is None:
            return []

        async def _list():
            vault = get_vault_client()
            resources = await vault.list_resources(parent_id=session.vault_folder_id, project_id=session.vault_project_id)
            files = [r.get("name") for r in resources if r.get("type") == "file"]
            return files

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _list())
                    return future.result(timeout=30)
            else:
                return loop.run_until_complete(_list())
        except Exception as e:
            try:
                return asyncio.run(_list())
            except Exception as e2:
                print(f"Error listing files: {e2}")
                return []

    ns.setdefault("clean_dataset", clean_dataset_wrapper)
    ns.setdefault("save_to_vault", save_to_vault_wrapper)
    ns.setdefault("rename_in_vault", rename_in_vault_wrapper)
    ns.setdefault("delete_from_vault", delete_from_vault_wrapper)
    ns.setdefault("list_vault_files", list_vault_files_wrapper)

    if session is not None:
        logger.info(f"[Executor] Session {session.session_id}: filename='{session.filename}', "
                   f"cached_df={'available' if session.cached_df is not None else 'None'}")
        if _uses_df(code, session):
            logger.info(f"[Executor] Session {session.session_id}: code references df, loading dataset")
            try:
                df = load_dataframe(session)
                ns["df"] = df
                if session.filename:
                    df_name = infer_df_name(session.filename)
                    ns[df_name] = df
                logger.info(f"[Executor] Successfully loaded dataframe: {len(df)} rows, {len(df.columns)} columns")
            except RuntimeError as e:
                # Re-raise RuntimeError to be caught by routes
                logger.error(f"[Executor] Failed to load dataset: {e}")
                raise RuntimeError(f"Cannot load dataset: {str(e)}")
            except Exception as e:
                # Any other exception also becomes RuntimeError
                logger.error(f"[Executor] Unexpected error loading dataset: {e}", exc_info=True)
                raise RuntimeError(f"Dataset loading failed: {str(e)}")
        else:
            logger.info(f"[Executor] Session {session.session_id}: code does not reference df, skipping dataset load")

    return ns


def _check_and_upload_modified_df(session: Optional[SessionData], initial_df: Optional[pd.DataFrame], code: str):
    """
    Check if the dataframe was modified during execution, and if so, upload the updated version.
    """
    if session is None or not session.filename or initial_df is None:
        return

    current_df = session.cached_df
    if current_df is None or not isinstance(current_df, pd.DataFrame):
        return

    # Check if df was modified
    modified = False
    if current_df is not initial_df:
        modified = True
    elif current_df.shape != initial_df.shape:
        modified = True
    elif not current_df.columns.equals(initial_df.columns):
        modified = True
    else:
        try:
            if not current_df.equals(initial_df):
                modified = True
        except Exception:
            modified = True

    if modified:
        logger.info(f"[Executor] Dataset modification detected for session {session.session_id}. Uploading updated dataset...")
        from app.services.dataset_service import save_and_upload_modified_dataset
        
        async def _upload_task():
            await save_and_upload_modified_dataset(session, current_df)
            
        try:
            try:
                loop = asyncio.get_running_loop()
                running = True
            except RuntimeError:
                running = False

            if running:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _upload_task())
                    future.result(timeout=60)
            else:
                asyncio.run(_upload_task())
        except Exception as e:
            logger.error(f"[Executor] Failed to upload updated dataset: {e}", exc_info=True)


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
    """
    Execute code synchronously. Returns dict with output/table/error.
    
    Raises RuntimeError if dataset cannot be loaded.
    """
    safe, reason = _is_safe(code)
    if not safe:
        return {"error": reason}

    # Pre-flight syntax check (non-blocking — only logs, never refuses)
    syntax_warning = _check_syntax(code)
    if syntax_warning:
        logger.debug(f"[Executor] Syntax pre-check note: {syntax_warning}")

    try:
        matplotlib.use("Agg")
    except Exception:
        logger.debug("[Executor] could not set matplotlib backend to Agg", exc_info=True)

    try:
        initial_ns = _build_namespace(session, code)
    except RuntimeError as e:
        # Propagate dataset loading errors
        raise RuntimeError(str(e))

    initial_keys = set(initial_ns.keys())
    # Capture initial dataframe state copy
    initial_df = initial_ns.get("df")
    initial_df_copy = None
    if isinstance(initial_df, pd.DataFrame):
        try:
            initial_df_copy = initial_df.copy()
        except Exception:
            pass

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
                # Do not auto-upload modified datasets to Vault.
                # Users must explicitly save with save_to_vault(df, filename).
                # _check_and_upload_modified_df(session, initial_df_copy, code)

        # Close all active pyplot figures to avoid leaking plots into subsequent executions
        try:
            import matplotlib.pyplot as plt
            plt.close('all')
        except Exception:
            pass

    except Exception:
        error = _format_error(traceback.format_exc())
    finally:
        sys.stdout = old_stdout

    elapsed = round((time.time() - start) * 1000, 2)
    printed = stdout_capture.getvalue().strip()

    if error:
        return {"error": error, "execution_time_ms": elapsed}

    if isinstance(result_obj, pd.DataFrame):
        table = result_obj.head(200).fillna("").to_dict(orient="records")
        return {"table": table, "output": printed or None, "execution_time_ms": elapsed}

    if isinstance(result_obj, pd.Series):
        df_out = result_obj.reset_index()
        df_out.columns = [str(c) for c in df_out.columns]
        table = df_out.head(200).fillna("").to_dict(orient="records")
        return {"table": table, "output": printed or None, "execution_time_ms": elapsed}

    return {"output": printed or "Executed successfully (no output).", "execution_time_ms": elapsed}


def execute_code_streaming(session: Optional[SessionData], code: str):
    """
    Generator yielding (event_type, data) tuples for SSE streaming.
    Works with or without a dataset session.
    
    Raises RuntimeError if dataset cannot be loaded.
    """
    safe, reason = _is_safe(code)
    if not safe:
        yield ("error", reason)
        return

    # Pre-flight syntax check (non-blocking — only logs, never refuses)
    syntax_warning = _check_syntax(code)
    if syntax_warning:
        logger.debug(f"[Executor] Syntax pre-check note: {syntax_warning}")

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
    # Capture initial dataframe state copy
    initial_df = initial_ns.get("df")
    initial_df_copy = None
    if isinstance(initial_df, pd.DataFrame):
        try:
            initial_df_copy = initial_df.copy()
        except Exception:
            pass

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
                    # Do not automatically upload modified datasets.
                    # Users must explicitly call save_to_vault(df, filename) to persist changes.

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

    # ✅ FIXED: daemon=False so thread won't be killed when main exits
    thread = threading.Thread(target=_run, daemon=False)
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
    """Execute code and save generated plot to local/S3. Returns image URL.
    
    Raises RuntimeError if dataset cannot be loaded.
    """
    safe, reason = _is_safe(code)
    if not safe:
        return {"error": reason}

    # Pre-flight syntax check (non-blocking — only logs, never refuses)
    syntax_warning = _check_syntax(code)
    if syntax_warning:
        logger.debug(f"[Executor] Syntax pre-check note: {syntax_warning}")

    try:
        matplotlib.use("Agg")
    except Exception:
        pass

    try:
        initial_ns = _build_namespace(session, code)
    except RuntimeError as e:
        raise RuntimeError(str(e))

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
        error = _format_error(traceback.format_exc())
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