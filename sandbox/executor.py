import multiprocessing as mp
import io
from contextlib import redirect_stdout, redirect_stderr
from sandbox.security.builtins import safe_builtins
from sandbox.security.ast_guard import check_code
from core.models import SandboxConfig
from sandbox.security.imports import make_guarded_import
from sandbox.security.filesystem import make_guarded_directory
import resource


class FinalAnswer(Exception):
    def __init__(self, value):
        self.value = value


def final_answer(value):
    raise FinalAnswer(value)


def run_in_child(code, out_queue, max_memory_mb):
    octets = max_memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (octets, octets))
    config = SandboxConfig()
    builtins_dict = safe_builtins()
    builtins_dict["__import__"] = make_guarded_import(
        config.authorized_imports)
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


def execute(code, timeout=2):
    config = SandboxConfig()
    q = mp.Queue()
    p = mp.Process(target=run_in_child, args=(
        code, q, config.max_memory_mb))
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join(1)
        if p.is_alive():
            p.kill()
            p.join()
        return ("", "", f"Timeout after {timeout}s", False, None)
    return q.get() if not q.empty() else (
        "", "", "No result (process died)", False, None)


if __name__ == "__main__":
    print("A", execute("answer = sum(range(10))"))
    print("B", execute("while True: pass"))
    print("C", execute("answer = 1 / 0"))
    print("D", execute("final_answer('ma reponse')"))
    print("E", execute("print('coucou'); final_answer(42)"))
