import ast
import re

from core import constants


def extract_code_from_text(text: str) -> dict:
    """
    Extracts the code from the given text.

    A well-formed ```python block (or an untagged one) is taken as is. A
    malformed one is still run when it can be read, and "note" tells the
    model how it was read: a block tagged with another language, a block
    with no closing fence, or several blocks of which only the first runs.
    "note" is empty for a well-formed answer.

    Args:
        text (str): The text containing the code.
    Returns:
        dict: The extracted code, under "code", "found", "error", "note".
    """
    notes: list[str] = []
    blocks = re.findall(constants.FENCED_BLOCK_PATTERN, text, re.DOTALL)
    code_blocks = [
        code for tag, code in blocks if tag in constants.PYTHON_BLOCK_TAGS
    ]
    if code_blocks:
        code: str = code_blocks[0]
        if len(code_blocks) > 1:
            notes.append(
                f"Your answer had {len(code_blocks)} code blocks: only the"
                " first one was run"
            )
    else:
        code = read_malformed_block(text, blocks, notes)
        if code is None:
            return {
                "code": "",
                "found": False,
                "error": "No code block found",
                "note": "",
            }
    extracted_code, error_str = decode_python(code)
    return {
        "code": extracted_code.strip(),
        "found": True,
        "error": error_str,
        "note": "; ".join(notes),
    }


def read_malformed_block(
    text: str, blocks: list[tuple[str, str]], notes: list[str]
) -> str | None:
    """Return the code of a malformed block, or None if there is none.

    blocks are the closed fenced blocks of text, as (tag, code), none of
    them tagged python. The first one is run as Python; without any, an
    opening fence with no closing one is run up to the end of the text,
    or up to <end_code>. Appends to notes how the block was read.
    """
    if blocks:
        tag, code = blocks[0]
        notes.append(
            f"Your code block was tagged '{tag}' instead of python: it was"
            " run as Python"
        )
        return code
    opening = re.search(constants.OPEN_BLOCK_PATTERN, text)
    if opening is None:
        return None
    code: str = text[opening.end() :]
    for stop in constants.LLM_STOP_SEQUENCE:
        code = code.split(stop, 1)[0]
    if code.strip() == "":
        return None
    notes.append(
        "Your code block had no closing ```: everything after its opening"
        " line was run as Python"
    )
    return code


def decode_python(text: str) -> tuple[str, str]:
    """Return the code with "None" if it parses, else with the error."""
    try:
        ast.parse(text)
        return text, "None"
    except IndentationError as e:
        return text, f"IndentationError: {e}"
    except SyntaxError as e:
        return text, f"SyntaxError: {e}"
