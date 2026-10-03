import ast
import re

from core import constants


def extract_code_from_text(text: str) -> dict:
    """
    Extracts the code from the given text.

    Args:
        text (str): The text containing the code.
    Returns:
        dict: The extracted code.
    """
    extracted_code: str = ""

    code_blocks = re.findall(constants.CODE_BLOCK_PATTERN, text, re.DOTALL)
    if not code_blocks:
        return {
            "code": extracted_code.strip(),
            "found": False,
            "error": "No code block found",
        }
    extracted_code, error_str = decode_python(code_blocks[0])
    return {"code": extracted_code.strip(), "found": True, "error": error_str}


def decode_python(text: str) -> tuple[str, str]:
    """Return the code with "None" if it parses, else with the error."""
    try:
        ast.parse(text)
        return text, "None"
    except IndentationError as e:
        return text, f"IndentationError: {e}"
    except SyntaxError as e:
        return text, f"SyntaxError: {e}"
