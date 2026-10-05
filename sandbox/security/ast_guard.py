import ast

# Attribute names that reach back out of the restricted namespace.
# The sandbox is a security boundary; the builtins are an allowlist, but
# an allowlist of builtins is worth nothing if code can read the real
# builtins off a frame. These attributes walk the call stack, a
# generator or a traceback back to the interpreter's own globals, so
# they are refused before the code ever runs.
FORBIDDEN_ATTRS = frozenset({
    # Frames
    "f_back", "f_globals", "f_locals", "f_builtins", "f_code",
    "f_trace",
    # Generators, coroutines, async generators
    "gi_frame", "gi_code", "cr_frame", "cr_code", "ag_frame", "ag_code",
    # Tracebacks
    "tb_frame", "tb_next",
    # Modules re-exported by otherwise-allowed modules, which hand back
    # the very capabilities the allowlist withholds: `random._os` would
    # not be caught by the underscore rule? it is, but `typing.sys` and
    # the like are not, so the dangerous module names are named here.
    "sys", "os", "subprocess", "builtins", "importlib", "posix", "nt",
    "socket", "ctypes",
})

# namedtuple's public API is spelled with a leading underscore, so the
# underscore rule below would wrongly reject it. These names expose no
# capability (they return fields, dicts or copies), so they are allowed.
SAFE_UNDERSCORE = frozenset({
    "_fields", "_field_defaults", "_asdict", "_replace", "_make",
})


def check_code(code: str) -> None:
    """Reject code that tries to break out before it is executed.

    Refuses three kinds of attribute access that lead from the
    restricted namespace back to the real interpreter:

    - dunder attributes (`__class__`, `__globals__`, ...);
    - single-underscore attributes (`random._os`, ...), the private
      innards an allowed module should not expose;
    - the frame/traceback and dangerous-module names in FORBIDDEN_ATTRS.

    Args:
        code: The source about to be executed.

    Raises:
        ValueError: If the code is malformed, or touches a forbidden
            attribute.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Malformed code: {e}") from None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if node.attr in SAFE_UNDERSCORE:
            continue
        if node.attr.startswith("_") or node.attr in FORBIDDEN_ATTRS:
            raise ValueError(
                f"Forbidden attribute access: {node.attr}"
            ) from None
