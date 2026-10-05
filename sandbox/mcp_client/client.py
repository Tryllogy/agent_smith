"""A synchronous handle on an MCP server.

The MCP SDK is asynchronous and hands out a session that only lives for
the duration of an `async with` block (see transports.py). The rest of
the project is neither: the CLI, the manual and the agent loop are plain
synchronous code, and they need the same session to stay alive from the
first iteration to the last.

So the block is entered once, on an event loop running on a thread of
its own, and never left until `close()`. Calls from the main thread are
posted to that loop and waited on, which is what turns `await` into an
ordinary function call.

Connecting also records what the server declares -- tools, resources and
prompts. Nothing here knows the name of any particular tool: an unknown
server is described by whatever it answers.
"""

import asyncio
import shlex
import sys
import threading
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import AsyncExitStack

import mcp.shared.exceptions as _mcp_exc

from sandbox.mcp_client.transports import http_session, stdio_session

# McpError in the mcp SDK 1.x, MCPError in 2.x: whichever this install
# ships is the error call_tool must convert to our own MCPError.
SdkMCPError = getattr(_mcp_exc, "McpError", None) or _mcp_exc.MCPError

# A tool call can legitimately be slow: run_tests() walks a whole test
# suite. Long, but not forever, so a hung server cannot hang the agent.
DEFAULT_CALL_TIMEOUT = 900.0


class MCPError(Exception):
    """Anything that went wrong talking to the server.

    This is the only exception this module raises on purpose, so a
    caller needs nothing beyond `except MCPError`. The SDK has a
    same-named class of its own, `mcp.shared.exceptions.MCPError`,
    which is a different type; `_submit` converts it to this one so it
    never reaches a caller who would have to know the difference.
    """


def _describe(exc: BaseException) -> str:
    """Describe an exception, digging through exception groups.

    anyio runs the transport in a task group, so a server that fails to
    start arrives wrapped as "unhandled errors in a TaskGroup", which
    says nothing about the cause. The real exceptions are the leaves.

    Args:
        exc: The exception caught at the top.

    Returns:
        A description naming the underlying causes.
    """
    nested = getattr(exc, "exceptions", None)
    if not nested:
        return f"{type(exc).__name__}: {exc}"
    return " / ".join(_describe(inner) for inner in nested)


def _text_of(result) -> str:
    """Flatten a tool result into the text the model will read.

    Args:
        result: A result carrying a `content` list of blocks.

    Returns:
        Every text block, newline separated. A block with no text is
        described rather than dropped, so nothing vanishes in silence.
    """
    parts = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text is None:
            parts.append(f"<{type(block).__name__} without text>")
        else:
            parts.append(text)
    return "\n".join(parts)


class MCPClient:
    """Talks to one MCP server, synchronously.

    Either use it as a context manager, or call `connect()` and
    `close()` by hand. After `connect()`, `tools`, `resources` and
    `prompts` describe the server that is actually attached.
    """

    def __init__(self, factory, call_timeout: float = DEFAULT_CALL_TIMEOUT):
        """
        Args:
            factory: Zero-argument callable returning the async context
                manager that yields an initialized session, i.e. one of
                the two functions in transports.py, already given its
                arguments.
            call_timeout: Seconds to wait on any single request.
        """
        self._factory = factory
        self._call_timeout = call_timeout
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stack: AsyncExitStack | None = None
        self._session = None
        self.tools: list = []
        self.resources: list = []
        self.prompts: list = []

    @classmethod
    def from_command(cls, command_line: str, **kwargs) -> "MCPClient":
        """Build a client that launches a server over stdio.

        Args:
            command_line: The whole command as one string, the way the
                CLI receives it (e.g. "python mcp_tools_mbpp.py").
            **kwargs: Passed on to `__init__`.

        Returns:
            A client, not yet connected.

        Raises:
            ValueError: If `command_line` holds no command.
        """
        parts = shlex.split(command_line)
        if not parts:
            raise ValueError("empty MCP server command")
        command, args = parts[0], parts[1:]
        if command in ("python", "python3"):
            command = sys.executable
        return cls(lambda: stdio_session(command, args), **kwargs)

    @classmethod
    def from_url(cls, url: str, **kwargs) -> "MCPClient":
        """Build a client that connects to a server already running.

        Args:
            url: Endpoint of the server, e.g.
                "http://127.0.0.1:8000/mcp".
            **kwargs: Passed on to `__init__`.

        Returns:
            A client, not yet connected.
        """
        return cls(lambda: http_session(url), **kwargs)

    def connect(self) -> "MCPClient":
        """Open the session and record what the server offers.

        Returns:
            This client, so the call can be chained.

        Raises:
            MCPError: If the connection or the handshake failed. The
                thread is stopped before the error is raised, so a
                failed connect leaves nothing running.
        """
        self._start_loop()
        try:
            self._submit(self._open())
        except MCPError as exc:
            self.close()
            raise MCPError(f"could not connect: {exc}") from exc
        except Exception as exc:
            self.close()
            raise MCPError(
                f"could not connect: {_describe(exc)}"
            ) from exc
        return self

    def call_tool(self, name: str, arguments: dict) -> str:
        """Call one tool and return its output as text.

        Args:
            name: Tool name, as the server declares it.
            arguments: Arguments keyed by parameter name.

        Returns:
            The tool's text output.

        Raises:
            MCPError: If the server reported the call as failed. The SDK
                does not raise for that: it answers with is_error set,
                which would otherwise read as an ordinary result.
        """
        result = self._submit(self._session.call_tool(name, arguments))
        text = _text_of(result)
        # isError in the mcp SDK 1.x, is_error in 2.x.
        failed = (getattr(result, "isError", None)
                  or getattr(result, "is_error", None))
        if failed:
            raise MCPError(text or f"tool '{name}' failed")
        return text

    def read_resource(self, uri: str) -> str:
        """Read one resource and return its contents as text.

        Args:
            uri: URI of the resource, as listed in `resources`.

        Returns:
            The resource's text.
        """
        result = self._submit(self._session.read_resource(uri))
        return "\n".join(
            getattr(item, "text", None) or str(item)
            for item in getattr(result, "contents", None) or []
        )

    def get_prompt(self, name: str, arguments: dict | None = None) -> str:
        """Render one prompt and return it as text.

        Args:
            name: Prompt name, as listed in `prompts`.
            arguments: Arguments the prompt takes, if any.

        Returns:
            The rendered messages, one per line.
        """
        result = self._submit(
            self._session.get_prompt(name, arguments or {})
        )
        parts = []
        for message in getattr(result, "messages", None) or []:
            content = getattr(message, "content", None)
            parts.append(getattr(content, "text", None) or str(content))
        return "\n".join(parts)

    def close(self) -> None:
        """Leave the session block, then stop the loop and its thread.

        Safe to call twice, and safe on a client that never managed to
        connect.
        """
        if self._loop is None:
            return
        try:
            if self._stack is not None:
                self._submit(self._stack.aclose())
        except Exception:
            pass
        finally:
            self._stack = None
            self._session = None
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread is not None:
                self._thread.join(timeout=5)
            self._loop = None
            self._thread = None

    def __enter__(self) -> "MCPClient":
        return self.connect()

    def __exit__(self, *_) -> None:
        self.close()

    def _start_loop(self) -> None:
        """Run an event loop on a background thread, and wait for it.

        The event is not decoration: `Thread.start()` returns before the
        thread has run anything, so without the barrier the next line
        could reach `self._loop` while it is still None.
        """
        running = threading.Event()

        def runner() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            running.set()
            self._loop.run_forever()

        self._thread = threading.Thread(
            target=runner, name="mcp-client", daemon=True
        )
        self._thread.start()
        running.wait()

    def _submit(self, coroutine):
        """Run a coroutine on the client's loop and wait for its result.

        This is where async becomes sync: the coroutine is handed to the
        other thread's loop, and `.result()` blocks this one until it is
        done.

        Args:
            coroutine: The coroutine to run.

        Returns:
            Whatever the coroutine returned.
        """
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(self._call_timeout)
        except FutureTimeoutError as exc:
            # Only this call is abandoned; the session stays usable.
            raise MCPError(
                f"no answer from the server after {self._call_timeout}s"
            ) from exc
        except SdkMCPError as exc:
            raise MCPError(str(exc)) from exc

    async def _open(self) -> None:
        """Enter the session block and record what the server declares.

        The stack is what keeps the block open: entering it here and
        closing it only in `close()` is precisely what a plain
        `async with` could not do, since leaving the block would kill
        the server.
        """
        self._stack = AsyncExitStack()
        self._session = await self._stack.enter_async_context(
            self._factory()
        )
        self.tools = (await self._session.list_tools()).tools
        self.resources = await self._list(
            self._session.list_resources, "resources"
        )
        self.prompts = await self._list(
            self._session.list_prompts, "prompts"
        )

    @staticmethod
    async def _list(method, attribute: str) -> list:
        """List one optional primitive, tolerating a server without it.

        Tools are mandatory, resources and prompts are not: an unknown
        server may answer "method not found" for either. That is worth
        noting, not worth refusing the connection over.

        Args:
            method: The session method to await.
            attribute: Field holding the list on the result.

        Returns:
            What the server declared, or an empty list.
        """
        try:
            return getattr(await method(), attribute, [])
        except Exception:
            return []
