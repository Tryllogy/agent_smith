"""The sandbox manual, written from whatever server is attached.

This is what the model reads to learn what it can call, so nothing in it
is hard-coded: names, descriptions and parameter types all come from the
connected server's schemas. Point the sandbox at another server and the
manual rewrites itself.

`final_answer` is the one exception, and deliberately so: it is a
primitive of the sandbox rather than a tool, and stays whatever is
connected.

The manual lists the tools, which the subject asks to generate from the
tool schemas, and final_answer. It leaves out resources and prompts on
purpose: the sandbox namespace holds exactly those two kinds of
callable, so a resource or a prompt is nothing the model could call from
its code. The client still exposes them (read_resource, get_prompt), and
the CLI shows them at startup.

The first section translates JSON Schema into Python names and
signatures. It is the single source of truth for that translation: the
generated wrappers must define exactly what the manual announces, or the
model is told to call a function that does not exist.

Length matters more than completeness here. MBPP allows 6000 input
tokens for the whole task and the system prompt is resent every
iteration, so each line costs ten times what it looks like.
"""

import keyword
import re

PYTHON_TYPES = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "array": "list",
    "object": "dict",
    "null": "None",
}


def python_name(raw: str) -> str:
    """Turn a server-side tool name into a usable Python identifier.

    MCP names are free-form: they may hold dashes or dots, or start with
    a digit, none of which can be called from Python.

    Args:
        raw: Name as the server declares it.

    Returns:
        A valid, non-keyword identifier.
    """
    cleaned = re.sub(r"\W", "_", raw)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"tool_{cleaned}"
    if keyword.iskeyword(cleaned):
        cleaned = f"{cleaned}_"
    return cleaned


def parameters(schema: dict) -> list:
    """List a tool's parameters, required ones first.

    The order is the one the model will use positionally, so required
    parameters have to come first: a call like read_file(path, 1, 40)
    only works if the signature agrees.

    Args:
        schema: The tool's input schema, as the server declares it.

    Returns:
        Tuples of (name, JSON type, is required).
    """
    properties = (schema or {}).get("properties") or {}
    required = set((schema or {}).get("required") or [])
    ordered = [name for name in properties if name in required]
    ordered += [name for name in properties if name not in required]
    return [
        (name, properties[name].get("type", "any"), name in required)
        for name in ordered
    ]


def _render_type(json_type) -> str:
    """Spell a JSON Schema type the Python way.

    Args:
        json_type: The schema's type, which may be a list when the
            schema allows several.

    Returns:
        A Python type name, or "any" when the schema does not say.
    """
    if isinstance(json_type, list):
        return " | ".join(_render_type(item) for item in json_type)
    return PYTHON_TYPES.get(json_type, "any")


def signature(tool) -> str:
    """Render one tool as the call the model should write.

    Args:
        tool: A tool as listed by the server.

    Returns:
        A line such as "read_file(filepath: str, start_line: int)".
    """
    schema = (getattr(tool, "inputSchema", None)
              or getattr(tool, "input_schema", None))
    rendered = []
    for name, json_type, is_required in parameters(schema):
        shown = f"{name}: {_render_type(json_type)}"
        rendered.append(shown if is_required else f"{shown} = ...")
    return f"{python_name(tool.name)}({', '.join(rendered)})"


HEADER = """\
# Sandbox manual

You write Python that runs in a sandbox. A bare expression's value is
discarded, so print() whatever you need to see.

Two kinds of callables exist: the tools below, and final_answer."""

FINAL_ANSWER = """\
## final_answer(answer)

Ends the task and returns `answer` as the solution. A sandbox
primitive, not a tool: present whatever server is connected."""


def _tool_entry(tool) -> str:
    """Render one tool: its signature, then its own description."""
    description = (getattr(tool, "description", "") or "").strip()
    if not description:
        return signature(tool)
    return f"{signature(tool)}\n{description}"


def _section(title: str, items, render) -> str:
    """Render one section, or nothing at all when it is empty.

    An empty section is dropped rather than announced: on MBPP every
    line is resent on every iteration, and "this server exposes no
    prompts" is not worth paying for ten times.

    Args:
        title: Heading for the section.
        items: What the server declared.
        render: How to render one item.

    Returns:
        The section, or an empty string.
    """
    if not items:
        return ""
    body = "\n\n".join(render(item) for item in items)
    return f"## {title}\n\n{body}"


def render_manual(client) -> str:
    """Write the manual for the server this client is connected to.

    Args:
        client: A connected `MCPClient`.

    Returns:
        The manual, as text to drop into the system prompt.
    """
    sections = [
        HEADER,
        _section("Tools", client.tools, _tool_entry),
        FINAL_ANSWER,
    ]
    return "\n\n".join(section for section in sections if section)
