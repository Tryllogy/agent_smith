"""Stand-ins, in the sandbox, for the tools that live on the MCP server.

The model writes ordinary Python -- `read_file("src/calc.py", 1, 40)` --
so the sandbox namespace needs a function called `read_file` that
accepts those arguments. The real one runs in the server's process,
out of reach, so each tool gets a wrapper instead: a function with the
same name and the same parameters, which does no work of its own. It
turns the call into the shape MCP expects, a tool name and a dict of
named arguments, and hands it to `dispatch`, whose job is to get it to
the server and bring the answer back.

The wrappers know nothing about how `dispatch` does that. That keeps
them testable on their own, with a dispatch that just prints.

Names and parameter order come from `sandbox.manual`, so that every
wrapper defines exactly the call the manual tells the model to write.
"""

import inspect
import keyword

from sandbox.manual import parameters, python_name


def tool_spec(tool) -> dict:
    """Reduce a tool to what can cross into the sandbox's process.

    The sandboxed code runs in a child process, and only picklable
    values can be handed to it. Plain dicts are; the SDK's objects are
    not worth betting on.

    Args:
        tool: A tool as the server lists it.

    Returns:
        Its name, description and input schema.
    """
    return {
        "name": tool.name,
        "description": (getattr(tool, "description", "") or "").strip(),
        "schema": (getattr(tool, "inputSchema", None)
                   or getattr(tool, "input_schema", None) or {}),
    }


def _usable(name: str) -> bool:
    """Say whether a parameter name can be a Python parameter."""
    return name.isidentifier() and not keyword.iskeyword(name)


def _signature(params: list) -> inspect.Signature | None:
    """Build the Python signature a tool's parameters describe.

    Optional parameters default to None. Only the arguments the model
    actually passes are sent, so the server still applies its own
    defaults rather than receiving a None it never asked for.

    Args:
        params: Tuples of (name, JSON type, is required), required
            first, as `parameters` returns them.

    Returns:
        The signature, or None when a parameter name cannot be a Python
        identifier (a dash, say), in which case the tool can only be
        reached by keyword.
    """
    if not all(_usable(name) for name, _, _ in params):
        return None
    return inspect.Signature([
        inspect.Parameter(
            name,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=inspect.Parameter.empty if is_required else None,
        )
        for name, _, is_required in params
    ])


def make_wrapper(spec: dict, alias: str, dispatch):
    """Build the stand-in for one tool.

    Args:
        spec: The tool, as `tool_spec` describes it.
        alias: Python name the wrapper will be called by.
        dispatch: Callable taking (tool name, arguments dict) and
            returning the tool's output.

    Returns:
        A function the model can call positionally or by keyword.
    """
    tool_name = spec["name"]
    signature = _signature(parameters(spec["schema"]))

    def wrapper(*args, **kwargs):
        if signature is None:
            if args:
                raise TypeError(f"{alias}() takes keyword arguments only")
            return dispatch(tool_name, kwargs)
        try:
            bound = signature.bind(*args, **kwargs)
        except TypeError as exc:
            raise TypeError(f"{alias}(): {exc}") from None
        return dispatch(tool_name, dict(bound.arguments))

    wrapper.__name__ = alias
    wrapper.__qualname__ = alias
    wrapper.__doc__ = spec["description"]
    if signature is not None:
        wrapper.__signature__ = signature
    return wrapper


def build_namespace(specs: list, dispatch) -> dict:
    """Build the wrappers the sandboxed code will find in its namespace.

    Args:
        specs: Tools, as `tool_spec` describes them.
        dispatch: Callable taking (tool name, arguments dict) and
            returning the tool's output.

    Returns:
        A mapping of Python name to wrapper.
    """
    namespace = {}
    for spec in specs:
        alias = python_name(spec["name"])
        while alias in namespace or alias == "final_answer":
            alias = f"{alias}_"
        namespace[alias] = make_wrapper(spec, alias, dispatch)
    return namespace
