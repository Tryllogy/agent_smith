import io
import multiprocessing as mp
import resource
from contextlib import redirect_stderr, redirect_stdout

from core.models import SandboxConfig
from sandbox.security.ast_guard import check_code
from sandbox.security.builtins import safe_builtins
from sandbox.security.filesystem import make_guarded_directory
from sandbox.security.imports import make_guarded_import
from sandbox.security.network import block_network


class FinalAnswer(Exception):
    def __init__(self, value):
        self.value = value


def final_answer(value):
    raise FinalAnswer(value)


def run_in_child(code, out_queue, config: SandboxConfig):
    octets = config.max_memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (octets, octets))
    block_network()
    builtins_dict = safe_builtins()
    builtins_dict["__import__"] = make_guarded_import(
        config.authorized_imports
    )
    builtins_dict["open"] = make_guarded_directory(config.allowed_directories)
    ns = {"__builtins__": builtins_dict, "final_answer": final_answer}
    error, is_final, answer = None, False, None

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            check_code(code)
            exec(code, ns)
        except FinalAnswer as fa:
            is_final, answer = True, fa.value
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            error = f"{type(e).__name__}: {e}"

    stdout = out.getvalue()
    stderr = err.getvalue()
    out_queue.put((stdout, stderr, error, is_final, answer))


def execute(code, config=None):
    if config is None:
        config = SandboxConfig()
    timeout = config.max_execution_time_seconds
    q = mp.Queue()
    p = mp.Process(target=run_in_child, args=(code, q, config))
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join(1)
        if p.is_alive():
            p.kill()
            p.join()
        return ("", "", f"Timeout after {timeout}s", False, None)
    return (
        q.get()
        if not q.empty()
        else ("", "", "No result (process died)", False, None)
    )
