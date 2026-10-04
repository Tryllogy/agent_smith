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
})


def check_code(code: str) -> None:
    """Reject code that tries to break out before it is executed.

    Refuses dunder attribute access (`__class__`, `__globals__`, ...)
    and the frame/generator/traceback attributes in FORBIDDEN_ATTRS,
    both of which lead from the restricted namespace back to the real
    interpreter.

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
        if node.attr.startswith("__") or node.attr in FORBIDDEN_ATTRS:
            raise ValueError(
                f"Forbidden attribute access: {node.attr}"
            ) from None
