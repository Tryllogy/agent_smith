import contextlib
import io
import multiprocessing as mp
import os
import queue
import resource
import time
from contextlib import redirect_stderr, redirect_stdout

from core.models import SandboxConfig
from sandbox.manual import render_manual
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

# File descriptors the sandboxed child must close on startup. The agent
# ties a Docker container to its life by holding a pipe (see
# agent_swebench/docker.py); the forked child would otherwise inherit
# that pipe and keep the container alive after the agent is killed.
FDS_TO_CLOSE_IN_CHILD = []

# Largest stdout, stderr or tool result handed back for one entry.
# Past this the output is cut and the model is told, so a flood of text
# cannot blow the token budget or hide the useful lines.
MAX_OUTPUT = 20000


class QueueWriter(io.TextIOBase):
    """A text stream that forwards each write to the parent at once.

    Buffering the output in the child and sending it only at the end
    would lose everything when the child is killed on a timeout. Sending
    each chunk as it is written lets the parent keep the partial output
    and hand it back, as the subject requires for a timeout.
    """

    def __init__(self, outbox, tag):
        self._outbox = outbox
        self._tag = tag

    def write(self, text):
        if text:
            self._outbox.put((self._tag, text))
        return len(text)


class FinalAnswer(Exception):
    def __init__(self, value):
        self.value = value


class ToolError(Exception):
    """A tool call failed. Raised in the sandbox, for the model to read."""


def final_answer(answer):
    # The parameter is named to match the manual, so the model may write
    # final_answer(answer=...) as well as final_answer(...).
    raise FinalAnswer(answer)


def make_dispatch(outbox, answers):
    """Build the messenger the tool wrappers hand their calls to.

    It runs in the child, where the MCP client does not exist: it posts
    the call to the parent and blocks until the parent answers.

    Args:
        outbox: Queue to the parent.
        answers: Queue from the parent.

    Returns:
        A function taking (tool name, arguments) and returning the
        tool's output.
    """

    def dispatch(name, arguments):
        outbox.put(("call", name, arguments))
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


def run_one(code, ns, interactive, outbox):
    """Run one entry, streaming its output, and report the outcome.

    stdout and stderr are streamed to the parent through `outbox` as
    they are written; only the outcome (error, is_final, answer) comes
    back here.
    """
    error, is_final, answer = None, False, None
    out = QueueWriter(outbox, "out")
    err = QueueWriter(outbox, "err")
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
    return (error, is_final, answer)


def worker(jobs, outbox, answers, config: SandboxConfig, specs, manual):
    """The child: lock itself down once, then run entries until told to stop.

    The namespace is built once and kept, so a variable set by one entry
    is still there for the next -- the "persistent variables between
    steps" the subject promises for code-based tool calling.
    """
    # Drop any fd the child must not keep (the Docker lifeline pipe), so
    # that killing the agent really closes it.
    for fd in FDS_TO_CLOSE_IN_CHILD:
        with contextlib.suppress(OSError):
            os.close(fd)
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
    ns = build_namespace(specs, make_dispatch(outbox, answers))
    ns["final_answer"] = final_answer
    # The manual is also reachable from inside the sandbox, so code can
    # look up what it may call without leaving the namespace.
    ns["sandbox_manual"] = manual
    ns["get_manual"] = lambda: manual
    ns["__builtins__"] = builtins_dict

    while True:
        job = jobs.get()
        if job is None:
            return
        code, interactive = job
        outbox.put(("result", run_one(code, ns, interactive, outbox)))


def serve(p, outbox, answers, client, timeout):
    """Answer the child's tool calls until it sends its result.

    The parent cannot just wait with p.join(): the child may need an
    answer from it in the meantime, and both would wait for each other.

    The time spent in a tool call is added back to the deadline. The
    subject applies the timeout to sandboxed code only, and a tool such
    as run_tests() may legitimately run for minutes.

    Args:
        p: The running child.
        outbox: Queue the child posts on.
        answers: Queue to post tool results on.
        client: Connected MCPClient, or None when no server is attached.
        timeout: Seconds of sandboxed execution allowed.

    Returns:
        The child's (stdout, stderr, error, is_final, answer). On a
        timeout or a crash, the output collected so far is still
        returned, so the model sees what ran before it stopped.
    """
    deadline = time.monotonic() + timeout
    output = _Output()

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return output.finish(TIMEOUT.format(timeout), False, None)

        try:
            message = outbox.get(timeout=min(remaining, POLL_SECONDS))
        except queue.Empty:
            if p.is_alive():
                continue
            try:
                message = outbox.get(timeout=DRAIN_SECONDS)
            except queue.Empty:
                return output.finish(DIED, False, None)

        tag = message[0]
        if tag in ("out", "err"):
            output.add(tag, message[1])
            continue
        if tag == "result":
            error, is_final, answer = message[1]
            return output.finish(error, is_final, answer)

        _, name, arguments = message
        started = time.monotonic()
        if client is None:
            answers.put((False, f"no MCP server connected for '{name}'"))
        else:
            try:
                text = client.call_tool(name, arguments)
                answers.put((True, _cap_tool(text)))
            except MCPError as exc:
                answers.put((False, str(exc)))
            except Exception as exc:
                answers.put((False, f"{type(exc).__name__}: {exc}"))
        deadline += time.monotonic() - started


def _cap_tool(text):
    """Cut an over-long tool result and say so, for the model to read."""
    if len(text) <= MAX_OUTPUT:
        return text
    return (text[:MAX_OUTPUT]
            + f"\n... tool output truncated at {MAX_OUTPUT} characters")


class _Output:
    """Collects the child's stdout and stderr, capped at MAX_OUTPUT each.

    Past the cap the stream is cut and a note is appended, so the model
    is told rather than left with a silently shortened observation.
    """

    def __init__(self):
        self._chunks = {"out": [], "err": []}
        self._size = {"out": 0, "err": 0}
        self._cut = {"out": False, "err": False}

    def add(self, tag, text):
        room = MAX_OUTPUT - self._size[tag]
        if room > 0:
            self._chunks[tag].append(text[:room])
        self._size[tag] += len(text)
        if self._size[tag] > MAX_OUTPUT:
            self._cut[tag] = True

    def _text(self, tag, stream):
        body = "".join(self._chunks[tag])
        if self._cut[tag]:
            body += f"\n... {stream} truncated at {MAX_OUTPUT} characters"
        return body

    def finish(self, error, is_final, answer):
        return (self._text("out", "stdout"), self._text("err", "stderr"),
                error, is_final, answer)


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
        # Built once from the connected server, and handed to the child
        # so `sandbox_manual` / `get_manual()` are available in the code.
        self.manual = render_manual(client) if client else ""
        self.p = None

    def start(self):
        # Fresh queues on every start: a dead child may have left a
        # message half-way that must not reach its successor.
        self.jobs, self.outbox, self.answers = (
            mp.Queue(), mp.Queue(), mp.Queue()
        )
        self.p = mp.Process(
            target=worker,
            args=(self.jobs, self.outbox, self.answers,
                  self.config, self.specs, self.manual),
            daemon=True,
        )
        self.p.start()

    def run(self, code, interactive=False, timeout=None):
        """Run one piece of code in the persistent namespace.

        Args:
            code: The Python to run.
            interactive: Print the value of a lone expression, as the
                Python prompt does. Meant for the REPL.
            timeout: Seconds allowed for this entry, or None for the
                configured max_execution_time_seconds. The agent loop
                passes the time its task has left.

        Returns:
            (stdout, stderr, error, is_final, answer).
        """
        if timeout is None:
            timeout = self.config.max_execution_time_seconds
        if self.p is None or not self.p.is_alive():
            self.start()
        self.jobs.put((code, interactive))
        stdout, stderr, error, is_final, answer = serve(
            self.p, self.outbox, self.answers, self.client, timeout
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
