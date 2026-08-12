class Prompt:
    def __init__(
        self,
        task: dict,
        tools: list = None,
        allowed_imports: list = None
    ) -> None:
        task_definition: str = task.get("task_definition", "")
        function_definition: str = task.get("function_definition", "")
        test_imports: list = task.get("test_imports", [])
        test_list: list = task.get("test_list", [])
        imports_str: str = "\n".join(test_imports) if test_imports else "None"
        tests_str: str = "\n".join(test_list) if test_list else "None"
        self.user_prompt = f"task_definition: {task_definition}\n" \
            f"function_definition: {function_definition}\n" \
            f'test_imports: {imports_str}\n' \
            f'test_list: {tests_str}'
        tools_str: str = "".join([f"- {tool}\n" for tool
                                  in tools]) if tools else "None"
        allowed_imports_str: str = "".join([f"- {imp}\n" for imp
                                            in allowed_imports]) \
            if allowed_imports else "None"
        self.prompt: list = [
            {"role": "system", "content": "You are an expert assistant who can"
             " solve any task using code."
             " \nTo solve the task, you must plan forward to proceed in a"
             " series of steps, in a cycle of 'thought:', 'code:',"
             " and 'observation:' sequences."
             " You don't have access to the internet."
             " At each step, in the 'thought:', you should"
             " first explain your reasoning towards solving the task"
             " and the tools that you want to use."
             " Then in the 'code:', you should write the"
             " code in simple Python."
             " No docstrings or comments are needed."
             " If nothing is printed, nothing will appear"
             " in the 'observation:'."
             " In the end you have to return a final answer using the"
             " `final_answer` if the task is finished."
             " \nYou will be generating code and must"
             " finish with <end_code> to indicate the end of your code."
             " You have been given access to a list of tools:"
             " these tools are basically Python functions which you"
             " can call with code."
             " final_answer MUST be autosufficent"
             " \nHere are the tools you have access to: \n"
             f" {tools_str}"
             "\nHere are the allowed imports you can use: \n"
             f" {allowed_imports_str}"
             "\nHere is an example:"
             ' \nTask: \ntask_definition: Return the smallest absolute value'
             ' in a list of integers.'
             ' \nfunction_definition: def smallest_abs(a):'
             ' \ntest_list: assert smallest_abs([3, -1, 5]) == 1'
             ' \nassert smallest_abs([-5, 2]) == 2'
             ' \nThought: Smallest absolute value means I take the minimum,'
             ' then its absolute'
             ' value. Let me set up the first case.'
             ' \nCode:'
             ' \n```python'
             ' \nprint(abs(min([-5, 2])))'
             ' \n```<end_code>'
             ' \nObservation: 5'
             ' \nThought: Expected 2, got 5. `min` picks -5 because it is'
             ' the smallest signed'
             ' value, and abs only runs afterwards. I must map abs over'
             ' the list first, then take the minimum.'
             ' \nCode:'
             ' \n```python'
             ' \ndef smallest_abs(a):'
             ' \n    return min(map(abs,a))'
             ' \nassert smallest_abs([3, -1, 5]) == 1'
             ' \nassert smallest_abs([-5, 2]) == 2'
             ' \nfinal_answer("def smallest_abs(a): return min(map(abs,a))")'
             ' \n```<end_code>'
             },
            {"role": "user",
             "content": f"Now, the real task is: {self.user_prompt}"}
        ]
        self.tools: list = tools
        self.allowed_imports: list = allowed_imports

    def add_message(self, message: dict) -> None:
        if not isinstance(message, dict):
            raise TypeError("Message must be a dictionary.")
        if "role" not in message or "content" not in message:
            raise ValueError("Message must contain 'role' and 'content' keys.")
        self.prompt.append(message)
