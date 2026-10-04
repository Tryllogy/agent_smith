from pathlib import Path

from mcp_tools.config import to_alias, to_host


def _resolve(filepath: str) -> Path:
    """Find the file the model means.

    The model writes both "/testbed/src/mail.py" and "src/mail.py"; both
    must reach the same file, wherever the server was started from, and
    even when /testbed is in fact a copy on the host (see to_host).
    """
    return to_host(filepath)


def read_file(filepath: str, start_line: int, end_line: int) -> str:
    """Read the content of a file with line numbers.

    Reads `filepath` and returns the lines from `start_line` to `end_line`
    inclusive (1-based line numbering). Each line is formatted like `cat -n`:

        <line_number>: <line_content>

    Args:
        filepath: Path to the file to read.
        start_line: First line to include (1 = first line of the file).
        end_line: Last line to include (inclusive).

    Returns:
        The selected lines as a single string, one per line.
    """
    with open(_resolve(filepath)) as f:
        lines = f.readlines()

    selected = lines[start_line - 1:end_line]

    result = []
    for offset, content in enumerate(selected):
        number = start_line + offset
        result.append(f"{number}: {content.rstrip(chr(10))}")

    return "\n".join(result)


def edit_file(filepath: str, old_str: str, new_str: str) -> str:
    """Replace an exact string in a file with a new string.

    Reads the whole file, replaces the unique occurrence of `old_str`
    with `new_str`, and writes the file back.

    Args:
        filepath: Path to the file to edit.
        old_str: Exact text to search for (must appear exactly once).
        new_str: Text to replace it with.

    Returns:
        A confirmation message, or an error if `old_str` is missing or
        not unique.
    """
    path = _resolve(filepath)
    with open(path) as f:
        content = f.read()

    count = content.count(old_str)
    if count == 0:
        return f"Error: old_str not found in {filepath}"
    if count > 1:
        return (
            f"Error: old_str is not unique in {filepath} "
            f"({count} occurrences)"
        )

    new_content = content.replace(old_str, new_str)
    with open(path, "w") as f:
        f.write(new_content)

    return f"Edited {filepath}: 1 replacement"


def list_files(directory: str, pattern: str) -> str:
    """List files in a directory matching a given pattern.

    Searches `directory` recursively and returns every file whose name
    matches `pattern` (shell-style, e.g. "*.py"), one absolute path per line.

    Args:
        directory: Directory to search in.
        pattern: Shell-style glob pattern (e.g. "*.py", "test_*.py").

    Returns:
        One absolute path per line, or a message if nothing matches.
    """
    result = []
    for found in _resolve(directory).rglob(pattern):
        result.append(to_alias(found.resolve()))

    if not result:
        return f"No files matching '{pattern}' in {directory}"

    return "\n".join(result)
