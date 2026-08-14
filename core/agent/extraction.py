import ast
import re


def extract_code_from_text(text: str) -> dict:
    """
    Extracts the code from the given text.

    Args:
        text (str): The text containing the code.
    Returns:
        dict: The extracted code.
    """
    extracted_code: str = ""
    code_block_pattern = r"```(?:python)? *\n(.*?)```"

    code_blocks = re.findall(code_block_pattern, text, re.DOTALL)
    if not code_blocks:
        return {
            "code": extracted_code.strip(),
            "found": False,
            "error": "No code block found",
        }
    extracted_code, error_str = decode_python(code_blocks[0])
    return {"code": extracted_code.strip(), "found": True, "error": error_str}


def decode_python(text: str) -> tuple[str, str]:
    try:
        ast.parse(text)
        return text, "None"
    except IndentationError as e:
        return text, f"IndentationError: {e}"
    except SyntaxError as e:
        return text, f"SyntaxError: {e}"
