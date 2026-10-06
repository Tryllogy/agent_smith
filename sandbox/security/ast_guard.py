import ast

# Attribute names that reach back out of the restricted namespace.
# The sandbox is a security boundary; the builtins are an allowlist, but
# an allowlist is worth nothing if code can read the real builtins or a
# dangerous module off something it is allowed to touch.
FORBIDDEN_ATTRS = frozenset({
    # Frames
    "f_back", "f_globals", "f_locals", "f_builtins", "f_code",
    "f_trace",
    # Generators, coroutines, async generators
    "gi_frame", "gi_code", "cr_frame", "cr_code", "ag_frame", "ag_code",
    # Tracebacks
    "tb_frame", "tb_next",
    # Modules re-exported by otherwise-allowed modules, which hand back
    # the very capabilities the allowlist withholds (e.g. `typing.sys`).
    "sys", "os", "subprocess", "builtins", "importlib", "posix", "nt",
    "socket", "ctypes",
})

# Helpers that fetch an attribute, or a module, by a *string* name, and
# so slip past a guard that only reads attributes written literally:
# `operator.attrgetter('_os')(random)` returns the real os module. They
# are blocked both as attributes and as imported names, so neither
# `operator.attrgetter` nor `from operator import attrgetter` reaches
# them.
INDIRECTION = frozenset({
    "attrgetter", "methodcaller", "Formatter",
    "get_field", "get_value", "vformat",
})

# namedtuple's public API is spelled with a leading underscore, so the
# underscore rule would wrongly reject it. These names expose no
# capability (they return fields, dicts or copies).
SAFE_UNDERSCORE = frozenset({
    "_fields", "_field_defaults", "_asdict", "_replace", "_make",
})

BLOCKED = FORBIDDEN_ATTRS | INDIRECTION


def _forbidden(name: str) -> bool:
    """Say whether a name must not be accessed or imported.

    Args:
        name: An attribute name, or a name imported with `from ...`.

    Returns:
        True for dunder names, private (single-underscore) names other
        than namedtuple's API, and the frame/module/indirection names.
    """
    if name in SAFE_UNDERSCORE:
        return False
    return name.startswith("_") or name in BLOCKED


def check_code(code: str) -> None:
    """Reject code that tries to break out before it is executed.

    Three doors lead from the restricted namespace back to the real
    interpreter, and all three are shut here:

    - attribute access to a dunder, a private name, a frame/traceback
      field or a dangerous module (`x.__globals__`, `random._os`,
      `typing.sys`);
    - the string-indirection helpers that would reach those by a name
      given as text (`operator.attrgetter('_os')`, `string.Formatter`);
    - importing any of the above by name (`from operator import
      attrgetter`, `from random import _os`).

    Args:
        code: The source about to be executed.

    Raises:
        ValueError: If the code is malformed or touches a forbidden name.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Malformed code: {e}") from None
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if _forbidden(node.attr):
                raise ValueError(
                    f"Forbidden attribute access: {node.attr}"
                ) from None
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if _forbidden(alias.name):
                    raise ValueError(
                        f"Forbidden import: {alias.name}"
                    ) from None
