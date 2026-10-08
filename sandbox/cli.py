"""Command line of the sandbox: `uv run sandbox`.

    uv run sandbox                                   # defaults
    uv run sandbox sandbox_template.json             # custom configuration
    uv run sandbox --mcp-stdio "python mcp_tools_mbpp.py" sandbox_template.json
    uv run sandbox --mcp-server http://127.0.0.1:8000/mcp

It opens a REPL: each entry runs in the sandbox namespace, under the same
restrictions as the agent's code, with the connected server's tools and
final_answer available. Variables persist from one entry to the next.
`exit` or Ctrl+D leaves.
"""

import argparse
import ast
import codeop
import contextlib
import sys
from pathlib import Path

from pydantic import ValidationError

from core.models import SandboxConfig
from sandbox.executor import Sandbox
from sandbox.mcp_client.client import MCPClient, MCPError

with contextlib.suppress(ImportError):
    import readline  # noqa: F401

PS1 = ">>> "
PS2 = "... "
EXIT_COMMANDS = {"exit", "exit()"}


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="sandbox",
        description="Interactive Agent Smith sandbox.",
    )
    parser.add_argument(
        "config",
        nargs="?",
        type=Path,
        help="JSON file holding a SandboxConfig (default: built-in values).",
    )
    server = parser.add_mutually_exclusive_group()
    server.add_argument(
        "--mcp-stdio",
        metavar="COMMAND",
        help='MCP server to launch over stdio, e.g. '
             '"python mcp_tools_mbpp.py".',
    )
    server.add_argument(
        "--mcp-server",
        metavar="URL",
        help="Running MCP server to reach over streamable HTTP.",
    )
    return parser.parse_args(argv)


def load_config(path):
    """Read a SandboxConfig from JSON, or return the defaults."""
    if path is None:
        return SandboxConfig()
    return SandboxConfig.model_validate_json(path.read_text())


def open_client(args):
    """Connect to the MCP server the command line names, if any."""
    if args.mcp_stdio:
        return MCPClient.from_command(args.mcp_stdio).connect()
    if args.mcp_server:
        return MCPClient.from_url(args.mcp_server).connect()
    return None


def banner(client):
    """Describe the session: what can be called, and how to leave."""
    if client is None:
        tools = "none (no MCP server connected)"
    else:
        tools = ", ".join(tool.name for tool in client.tools) or "none"
    lines = ["Agent Smith sandbox", f"Tools: {tools}, final_answer"]
    if client is not None and client.resources:
        uris = ", ".join(str(r.uri) for r in client.resources)
        lines.append(f"Resources: {uris}")
    if client is not None and client.prompts:
        lines.append(f"Prompts: {', '.join(p.name for p in client.prompts)}")
    lines.append('Type "exit" or press Ctrl+D to leave.')
    return "\n".join(lines)


def read_entry():
    """Read one entry, asking for more lines while the code is unfinished.

    `def f():` alone is not a complete statement, so the prompt switches
    to "... " until a blank line closes the block, as the Python prompt
    does. Code that is simply wrong is returned as is, for the sandbox to
    report.

    Raises:
        EOFError: On Ctrl+D.
        KeyboardInterrupt: On Ctrl+C.
    """
    lines = []
    while True:
        lines.append(input(PS2 if lines else PS1))
        source = "\n".join(lines)
        if not source.strip():
            return ""
        try:
            complete = codeop.compile_command(source, "<sandbox>", "single")
        except (SyntaxError, ValueError, OverflowError):
            return source
        if complete is not None:
            return source


def show(result):
    """Print what one entry produced: output, error, final answer."""
    stdout, stderr, error, is_final, answer = result
    if stdout:
        print(stdout, end="" if stdout.endswith("\n") else "\n")
    if stderr:
        print(stderr, end="" if stderr.endswith("\n") else "\n",
              file=sys.stderr)
    if error:
        print(error, file=sys.stderr)
    if is_final:
        print(f"final_answer: {answer!r}")


def run_script(sandbox):
    """Run piped-in code (`cat prog.py | uv run sandbox`).

    Splitting on blank lines, as the REPL does, would break any block
    that contains one, so the lines are not the unit. But running the
    whole file as one call would stop at the first error or timeout,
    whereas the REPL goes on. So the file is split into top-level
    statements with `ast` and each is run in turn: blocks with blank
    lines stay intact, and later statements still run after a failure.
    """
    source = sys.stdin.read()
    if not source.strip():
        return
    try:
        statements = ast.parse(source).body
    except SyntaxError:
        show(sandbox.run(source, interactive=False))
        return
    for statement in statements:
        segment = ast.get_source_segment(source, statement)
        if segment:
            show(sandbox.run(segment, interactive=False))


def repl(sandbox):
    """Read, run, print, until exit or Ctrl+D."""
    while True:
        try:
            source = read_entry()
        except EOFError:
            print()
            return
        except KeyboardInterrupt:
            print("\nKeyboardInterrupt -- type 'exit' or press Ctrl+D "
                  "to quit")
            continue
        if source.strip() in EXIT_COMMANDS:
            return
        if not source.strip():
            continue
        try:
            show(sandbox.run(source, interactive=True))
        except KeyboardInterrupt:
            sandbox.close()
            print("\nKeyboardInterrupt -- the sandbox was restarted, so "
                  "variables from earlier entries are gone. Type 'exit' "
                  "or press Ctrl+D to quit.", file=sys.stderr)


def main(argv=None):
    args = parse_args(argv)
    try:
        config = load_config(args.config)
    except OSError as exc:
        print(f"sandbox: cannot read {args.config}: {exc}", file=sys.stderr)
        return 1
    except ValidationError as exc:
        print(f"sandbox: invalid configuration in {args.config}:\n{exc}",
              file=sys.stderr)
        return 1

    try:
        client = open_client(args)
    except (MCPError, ValueError) as exc:
        print(f"sandbox: {exc}", file=sys.stderr)
        return 1

    try:
        with Sandbox(config, client) as sandbox:
            if sys.stdin.isatty():
                print(banner(client))
                repl(sandbox)
            else:
                run_script(sandbox)
    finally:
        if client is not None:
            client.close()
    return 0
