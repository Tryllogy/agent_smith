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

# The two ways an entry can end without the child answering.
TIMEOUT = "Timeout after {}s"
DIED = "No result (process died)"


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


def compile_entry(code, interactive):
    """Compile one entry, the way an interactive prompt would if asked.

    In interactive mode a lone expression has its value printed, as in
    the Python prompt (`>>> 1 + 1` shows 2). That only works for a
    single statement, so anything longer falls back to plain execution,
    where a bare expression's value is discarded.
    """
    if interactive:
        try:
            return compile(code, "<sandbox>", "single")
        except SyntaxError:
            pass
    return compile(code, "<sandbox>", "exec")


def run_one(code, ns, interactive):
    """Run one entry in the persistent namespace and describe the outcome."""
    error, is_final, answer = None, False, None
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            check_code(code)
            exec(compile_entry(code, interactive), ns)
        except FinalAnswer as fa:
            is_final, answer = True, fa.value
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
    return (out.getvalue(), err.getvalue(), error, is_final, answer)


def worker(jobs, requests, answers, config: SandboxConfig, specs):
    """The child: lock itself down once, then run entries until told to stop.

    The namespace is built once and kept, so a variable set by one entry
    is still there for the next -- the "persistent variables between
    steps" the subject promises for code-based tool calling.
    """
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

    while True:
        job = jobs.get()
        if job is None:
            return
        code, interactive = job
        requests.put(("result", run_one(code, ns, interactive)))


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
            return ("", "", TIMEOUT.format(timeout), False, None)

        try:
            message = requests.get(timeout=min(remaining, POLL_SECONDS))
        except queue.Empty:
            if p.is_alive():
                continue
            try:
                message = requests.get(timeout=DRAIN_SECONDS)
            except queue.Empty:
                return ("", "", DIED, False, None)

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


class Sandbox:
    """A sandbox whose namespace lasts from one entry to the next.

    One child process is started and kept: every call to `run()` sends
    it a new piece of code, executed in the same namespace. The only
    thing that wipes that namespace is a child that has to be killed --
    a timeout, or a crash -- and the error then says so, so that the
    model does not go looking for a variable that no longer exists.

    Use it as a context manager, or call `close()` when done.
    """

    def __init__(self, config=None, client=None):
        """
        Args:
            config: Limits and allowlists, or None for the defaults.
            client: Connected MCPClient whose tools the code may call,
                or None to run with final_answer alone.
        """
        self.config = config if config is not None else SandboxConfig()
        self.client = client
        self.specs = [tool_spec(t) for t in client.tools] if client else []
        self.p = None

    def start(self):
        # Fresh queues on every start: a dead child may have left a
        # message half-way that must not reach its successor.
        self.jobs, self.requests, self.answers = (
            mp.Queue(), mp.Queue(), mp.Queue()
        )
        self.p = mp.Process(
            target=worker,
            args=(self.jobs, self.requests, self.answers,
                  self.config, self.specs),
            daemon=True,
        )
        self.p.start()

    def run(self, code, interactive=False):
        """Run one piece of code in the persistent namespace.

        Args:
            code: The Python to run.
            interactive: Print the value of a lone expression, as the
                Python prompt does. Meant for the REPL.

        Returns:
            (stdout, stderr, error, is_final, answer).
        """
        timeout = self.config.max_execution_time_seconds
        if self.p is None or not self.p.is_alive():
            self.start()
        self.jobs.put((code, interactive))
        stdout, stderr, error, is_final, answer = serve(
            self.p, self.requests, self.answers, self.client, timeout
        )
        if error in (TIMEOUT.format(timeout), DIED) or not self.p.is_alive():
            stop(self.p)
            self.p = None
            error = (f"{error or 'The sandbox stopped'}; the sandbox was "
                     "restarted, so variables from earlier entries are gone")
        return stdout, stderr, error, is_final, answer

    def close(self):
        """Stop the child, politely if it is idle."""
        if self.p is None:
            return
        if self.p.is_alive():
            self.jobs.put(None)
            self.p.join(1)
        stop(self.p)
        self.p = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def execute(code, config=None, client=None):
    """Run `code` once, in a sandbox of its own.

    Kept for callers that want a single run with nothing carried over.
    For variables that persist between runs, use a `Sandbox`.

    Args:
        code: The Python the model produced.
        config: Limits and allowlists, or None for the defaults.
        client: Connected MCPClient whose tools the code may call, or
            None to run with final_answer alone.

    Returns:
        (stdout, stderr, error, is_final, answer).
    """
    with Sandbox(config, client) as sandbox:
        return sandbox.run(code)
