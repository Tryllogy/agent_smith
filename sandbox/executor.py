import io
import multiprocessing as mp
import queue
import resource
import time
from contextlib import redirect_stderr, redirect_stdout

from core.models import SandboxConfig
from sandbox.mcp_client.client import MCPError
from sandbox.mcp_client.wrappers import build_namespace, tool_spec
from sandbox.security.ast_guard import check_code
from sandbox.security.builtins import safe_builtins
from sandbox.security.filesystem import make_guarded_directory
from sandbox.security.imports import make_guarded_import
from sandbox.security.network import block_network

# How often the parent looks up from the queue, to notice a child that
# died without sending anything.
POLL_SECONDS = 0.05

# Once the child is gone, how long to keep reading the queue: a result
# still in flight must not be mistaken for a crash.
DRAIN_SECONDS = 0.5


class FinalAnswer(Exception):
    def __init__(self, value):
        self.value = value


class ToolError(Exception):
    """A tool call failed. Raised in the sandbox, for the model to read."""


def final_answer(value):
    raise FinalAnswer(value)


def make_dispatch(requests, answers):
    """Build the messenger the tool wrappers hand their calls to.

    It runs in the child, where the MCP client does not exist: it posts
    the call to the parent and blocks until the parent answers.

    Args:
        requests: Queue to the parent.
        answers: Queue from the parent.

    Returns:
        A function taking (tool name, arguments) and returning the
        tool's output.
    """

    def dispatch(name, arguments):
        requests.put(("call", name, arguments))
        succeeded, payload = answers.get()
        if not succeeded:
            raise ToolError(payload)
        return payload

    return dispatch


def run_in_child(code, requests, answers, config: SandboxConfig, specs):
    octets = config.max_memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (octets, octets))
    block_network()
    builtins_dict = safe_builtins()
    builtins_dict["__import__"] = make_guarded_import(
        config.authorized_imports
    )
    builtins_dict["open"] = make_guarded_directory(config.allowed_directories)
    # Exactly two kinds of callables: the wrappers of the connected
    # server's tools, and final_answer.
    ns = build_namespace(specs, make_dispatch(requests, answers))
    ns["final_answer"] = final_answer
    ns["__builtins__"] = builtins_dict
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
    requests.put(("result", (stdout, stderr, error, is_final, answer)))


def serve(p, requests, answers, client, timeout):
    """Answer the child's tool calls until it sends its result.

    The parent cannot just wait with p.join(): the child may need an
    answer from it in the meantime, and both would wait for each other.

    The time spent in a tool call is added back to the deadline. The
    subject applies the timeout to sandboxed code only, and a tool such
    as run_tests() may legitimately run for minutes.

    Args:
        p: The running child.
        requests: Queue the child posts on.
        answers: Queue to post tool results on.
        client: Connected MCPClient, or None when no server is attached.
        timeout: Seconds of sandboxed execution allowed.

    Returns:
        The child's (stdout, stderr, error, is_final, answer), or the
        tuple describing a timeout or a crash.
    """
    deadline = time.monotonic() + timeout

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return ("", "", f"Timeout after {timeout}s", False, None)

        try:
            message = requests.get(timeout=min(remaining, POLL_SECONDS))
        except queue.Empty:
            if p.is_alive():
                continue
            try:
                message = requests.get(timeout=DRAIN_SECONDS)
            except queue.Empty:
                return ("", "", "No result (process died)", False, None)

        if message[0] == "result":
            return message[1]

        _, name, arguments = message
        started = time.monotonic()
        if client is None:
            answers.put((False, f"no MCP server connected for '{name}'"))
        else:
            try:
                answers.put((True, client.call_tool(name, arguments)))
            except MCPError as exc:
                answers.put((False, str(exc)))
            except Exception as exc:
                answers.put((False, f"{type(exc).__name__}: {exc}"))
        deadline += time.monotonic() - started


def stop(p):
    if not p.is_alive():
        return
    p.terminate()
    p.join(1)
    if p.is_alive():
        p.kill()
        p.join()


def execute(code, config=None, client=None):
    """Run `code` in the sandbox.

    Args:
        code: The Python the model produced.
        config: Limits and allowlists, or None for the defaults.
        client: Connected MCPClient whose tools the code may call, or
            None to run with final_answer alone (as before).

    Returns:
        (stdout, stderr, error, is_final, answer).
    """
    if config is None:
        config = SandboxConfig()
    timeout = config.max_execution_time_seconds
    specs = [tool_spec(t) for t in client.tools] if client else []
    requests, answers = mp.Queue(), mp.Queue()
    p = mp.Process(
        target=run_in_child, args=(code, requests, answers, config, specs)
    )
    p.start()
    try:
        return serve(p, requests, answers, client, timeout)
    finally:
        stop(p)
