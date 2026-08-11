import multiprocessing as mp


class FinalAnswer(Exception):
    def __init__(self, value):
        self.value = value


def final_answer(value):
    raise FinalAnswer(value)


def run_in_child(code, out_queue):
    ns = {"__builtins__": __builtins__, "final_answer": final_answer}
    error, is_final, answer = None, False, None
    try:
        exec(code, ns)
    except FinalAnswer as fa:
        is_final, answer = True, fa.value
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        error = f"{type(e).__name__}: {e}"

    out_queue.put((error, is_final, answer))


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
        return ("timeout", None)
    return q.get() if not q.empty() else ("no_result", None)


if __name__ == "__main__":
    pass
