from contextlib import asynccontextmanager

import mcp
from mcp.client.streamable_http import streamable_http_client


@asynccontextmanager
async def stdio_session(command: str, args: list):
    """Open an MCP session over stdio and yield it ready to use.

    Spawns the server as a subprocess (`command` + `args`), wires the two
    stdio streams into a ClientSession, performs the mandatory handshake,
    then yields the initialized session. The subprocess and streams are
    closed automatically when the `async with` block exits.

    Args:
        command: Executable to launch the server (e.g. "python").
        args: Arguments passed to it (e.g. ["mcp_tools_swebench.py"]).

    Yields:
        An initialized mcp.ClientSession, ready for list_tools/call_tool.
    """
    params = mcp.StdioServerParameters(command=command, args=args)
    async with mcp.stdio_client(params) as (read, write):
        async with mcp.ClientSession(read, write) as session:
            await session.initialize()
            yield session


@asynccontextmanager
async def http_session(url: str):
    """Open an MCP session over streamable HTTP and yield it ready to use.

    Connects to an already-running server at `url`, wires its streams into
    a ClientSession, performs the mandatory handshake, then yields the
    initialized session. The connection is closed automatically when the
    `async with` block exits.

    Args:
        url: Base URL of the running MCP server.

    Yields:
        An initialized mcp.ClientSession, ready for list_tools/call_tool.
    """
    async with streamable_http_client(url) as (read, write, *_):
        async with mcp.ClientSession(read, write) as session:
            await session.initialize()
            yield session
