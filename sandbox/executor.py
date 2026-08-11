import multiprocessing as mp
import io
from contextlib import redirect_stdout, redirect_stderr
from sandbox.security.builtins import safe_builtins


class FinalAnswer(Exception):
    def __init__(self, value):
        self.value = value


def final_answer(value):
    raise FinalAnswer(value)


def run_in_child(code, out_queue):
    ns = {"__builtins__": safe_builtins(), "final_answer": final_answer}
    error, is_final, answer = None, False, None

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
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
    q = mp.Queue()
    p = mp.Process(target=run_in_child, args=(code, q))
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
