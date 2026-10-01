import re
from pathlib import Path


def search_code(pattern: str, file_pattern: str) -> str:
    """Search for a text pattern in files matching a glob pattern.

    Recursively searches the current directory for files whose name matches
    `file_pattern` (shell-style, e.g. "*.py"), then returns every line that
    contains `pattern`. Each match is formatted as:

        /absolute/path.py:<line_number> <line_content>

    Args:
        pattern: Literal text to search for on each line.
        file_pattern: Shell-style glob to select which files to search
            (e.g. "*.py", "test_*.py").

    Returns:
        One match per line, or a message if nothing matches.
    """
    result = []
    for path in Path(".").rglob(file_pattern):
        if not path.is_file():
            continue
        try:
            with open(path, "r") as f:
                lines = f.readlines()
        except (UnicodeDecodeError, OSError):
            continue
        for number, content in enumerate(lines, start=1):
            if pattern in content:
                absolute = path.resolve()
                result.append(f"{absolute}:{number} {content.rstrip(chr(10))}")

    if not result:
        return f"No matches for '{pattern}' in files matching '{file_pattern}'"

    return "\n".join(result)


def search_function_or_class_definition_in_code(
        name: str, file_pattern: str) -> str:
    """Find where a function or class is defined.

    Recursively searches files matching `file_pattern` for the definition of
    a function or class called `name`, i.e. a line starting (after optional
    indentation) with `def name` or `class name`. Each match is formatted as:

        /absolute/path.py:<line_number> <line_content>

    Args:
        name: Exact name of the function or class to locate.
        file_pattern: Shell-style glob to select which files to search
            (e.g. "*.py").

    Returns:
        One match per line, or a message if nothing matches.
    """
    prefixes = (f"def {name}", f"class {name}")
    result = []
    for path in Path(".").rglob(file_pattern):
        if not path.is_file():
            continue
        try:
            with open(path, "r") as f:
                lines = f.readlines()
        except (UnicodeDecodeError, OSError):
            continue
        for number, content in enumerate(lines, start=1):
            stripped = content.lstrip()
            if stripped.startswith(prefixes):
                after = stripped[4:] if stripped.startswith(
                    "def ") else stripped[6:]
                rest = after[len(name):]
                if rest[:1] in ("(", ":", " "):
                    absolute = path.resolve()
                    result.append(
                        f"{absolute}:{number} {content.rstrip(chr(10))}")

    if not result:
        return f"No definition of '{name}' in files matching '{file_pattern}'"

    return "\n".join(result)


def find_references(name: str, file_pattern: str) -> str:
    """Find all references (usages) of a symbol.

    Recursively searches files matching `file_pattern` for every line where
    `name` appears as a whole word (so "add" matches `add(x)` but not
    `address` or `add_two`). Each match is formatted as:

        /absolute/path.py:<line_number> <line_content>

    Args:
        name: Exact symbol name to look for.
        file_pattern: Shell-style glob to select which files to search
            (e.g. "*.py").

    Returns:
        One match per line, or a message if nothing matches.
    """
    word = re.compile(r"\b" + re.escape(name) + r"\b")
    result = []
    for path in Path(".").rglob(file_pattern):
        if not path.is_file():
            continue
        try:
            with open(path, "r") as f:
                lines = f.readlines()
        except (UnicodeDecodeError, OSError):
            continue
        for number, content in enumerate(lines, start=1):
            if word.search(content):
                absolute = path.resolve()
                result.append(
                    f"{absolute}:{number} {content.rstrip(chr(10))}")

    if not result:
        return f"No references to '{name}' in files matching '{file_pattern}'"

    return "\n".join(result)
