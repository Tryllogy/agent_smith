from pathlib import Path


def search_code(pattern: str, file_pattern: str):
    content = Path(".").rglob(file_pattern)

    for
