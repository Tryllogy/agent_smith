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


def generate(name: str, args: list) -> str:
    # """
    # Generates a code snippet based on the given name and arguments.

    # Args:
    #     name (str): The name of the function or tool.
    #     args (list): The list of arguments for the function or tool.
    # Returns:
    #     str: The generated code snippet.
    # """
    # args_str = ", ".join(map(str, args))
    # return f"{name}({args_str})"
    pass
