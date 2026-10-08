"""Code search tools.

All three share the output format the subject imposes:

    /absolute/path.py:<line_number> <line_content>

Searches start from the repository root the server was configured with,
not from the current directory, so results do not depend on where the
server happened to be launched.
"""

import re

from mcp_tools.config import get_config, to_alias, to_host

PYTHON_FILES = "*.py"

IGNORED_DIRS = {".git", ".venv"}


def _iter_lines(file_pattern: str):
    """Yield (absolute path, line number, line) for every matching file.

    Files under IGNORED_DIRS are left out, and so are files that cannot
    be read as text: a repository holds images and binaries, and no
    search here is looking for them.
    """
    root = get_config().repo_root
    for path in root.rglob(file_pattern):
        if IGNORED_DIRS.intersection(path.relative_to(root).parts):
            continue
        if not path.is_file():
            continue
        try:
            content = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        resolved = path.resolve()
        for number, line in enumerate(content.splitlines(), start=1):
            yield resolved, number, line


def _format(matches: list, empty: str) -> str:
    """Render matches in the common format, or `empty` if there are none."""
    if not matches:
        return empty
    return "\n".join(f"{to_alias(path)}:{number} {line}"
                     for path, number, line in matches)


def search_code(pattern: str, file_pattern: str) -> str:
    """Perform a grep-like search in the codebase.

    Args:
        pattern: Literal text to look for on each line.
        file_pattern: Shell-style glob selecting which files to search
            (e.g. "*.py", "test_*.py").

    Returns:
        One match per line, or a message if nothing matches.
    """
    matches = [(path, number, line)
               for path, number, line in _iter_lines(file_pattern)
               if pattern in line]
    return _format(
        matches,
        f"No matches for '{pattern}' in files matching '{file_pattern}'")


def search_function_or_class_definition_in_code(name: str) -> str:
    """Find the definition of a function or a class.

    Looks through every Python file of the repository for a line that
    starts, after any indentation, with `def name` or `class name`, and
    checks that the name stops there, so that `add` does not match
    `def address`.

    Args:
        name: Exact name of the function or class.

    Returns:
        One match per line, or a message if nothing matches.
    """
    matches = []
    for path, number, line in _iter_lines(PYTHON_FILES):
        stripped = line.lstrip()
        for keyword in ("def ", "class ", "async def "):
            if stripped.startswith(keyword + name):
                rest = stripped[len(keyword) + len(name):]
                if rest[:1] in ("(", ":", " ", ""):
                    matches.append((path, number, line))
                break
    return _format(matches, f"No definition of '{name}' found")


def find_references(name: str, filepath: str, line: int) -> str:
    """Find all usages of a symbol (function or class).

    `filepath` and `line` say which symbol is meant, since the same name
    can be defined in several places. The position is checked first, so
    that a wrong one is reported instead of silently turning into a plain
    name search.

    Args:
        name: Name of the symbol.
        filepath: File where the symbol is defined; a relative path is
            taken from the repository root.
        line: 1-based line of the symbol in that file.

    Returns:
        One usage per line, or a message if the position does not hold
        the symbol or nothing uses it.
    """
    target = to_host(filepath)
    try:
        lines = target.read_text().splitlines()
    except (UnicodeDecodeError, OSError) as exc:
        return f"Error: cannot read '{filepath}': {exc}"

    if not 1 <= line <= len(lines):
        return (f"Error: line {line} is out of range for '{filepath}', "
                f"which has {len(lines)} lines")
    word = re.compile(r"\b" + re.escape(name) + r"\b")
    if not word.search(lines[line - 1]):
        return (f"Error: '{name}' does not appear at {filepath}:{line}. "
                f"That line reads: {lines[line - 1].strip()}")

    matches = [(path, number, text)
               for path, number, text in _iter_lines(PYTHON_FILES)
               if word.search(text)]
    return _format(matches, f"No references to '{name}' found")
