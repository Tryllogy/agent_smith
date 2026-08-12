import re
import ast


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
            "format": None
        }
    extracted_code, format_str = decode_python(code_blocks[0])
    return {
        "code": extracted_code.strip(),
        "found": True,
        "format": format_str
    }


def decode_python(text: str) -> tuple[str, str]:
    try:
        ast.parse(text)
        return text, "python"
    except SyntaxError:
        return text, ""
