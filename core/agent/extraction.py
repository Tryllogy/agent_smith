import re
import ast
import json


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
    tool_call_pattern = r"<tool_call>(.*?)</tool_call>"
    invoke_pattern = r"<invoke>(.*?)</invoke>"
    action_pattern = r"Action:(.*?)(?=<|$)"

    code_blocks = re.findall(code_block_pattern, text, re.DOTALL)
    extracted_code = decode_python(code_blocks[0]) if code_blocks else ""
    tool_calls = re.findall(tool_call_pattern, text, re.DOTALL)
    extracted_code += decode_tool_call(tool_calls[0]) if tool_calls else ""
    invokes = re.findall(invoke_pattern, text, re.DOTALL)
    extracted_code += decode_invoke(invokes[0]) if invokes else ""
    action = re.findall(action_pattern, text, re.DOTALL)
    extracted_code += decode_action(action[0]) if action else ""
    return {
        "code": extracted_code.strip(),
        "found": None,
        "format": None
    }


def decode_python(text: str) -> None:
    try:
        ast.parse(text)
        return text
    except SyntaxError as e:
        raise ValueError(f"The extracted code has a syntax error: {e}")


def decode_tool_call(text: str) -> None:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to decode tool call JSON: {e}")


def decode_invoke(text: str) -> None:
    pass


def decode_action(text: str) -> None:
    pass


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
