from core.constants import Bench, BenchName


class Prompt:
    def __init__(
        self,
        bench: Bench,
        task: dict,
        tools: list = None,
        allowed_imports: list = None,
    ) -> None:
        self.tools: list = tools
        self.allowed_imports: list = allowed_imports
        self.allowed_imports_str: str = (
            "".join([f"- {imp}\n" for imp in self.allowed_imports])
            if self.allowed_imports
            else "None"
        )
        self.tools_str: str = (
            "".join([f"- {tool}\n" for tool in self.tools])
            if self.tools
            else "None"
        )
        if bench.name == BenchName.SWE.value:
            self.make_prompt_swe(task)
        elif bench.name == BenchName.MBPP.value:
            self.make_prompt_mbpp(task)
        else:
            raise ValueError(f"Unsupported benchmark: {bench.name}")

    def add_message(self, message: dict) -> None:
        if not isinstance(message, dict):
            raise TypeError("Message must be a dictionary.")
        if "role" not in message or "content" not in message:
            raise ValueError("Message must contain 'role' and 'content' keys.")
        self.prompt.append(message)

    def make_prompt_swe(self, task: dict) -> list:
        instance_id: str = task.get("instance_id", "")
        problem_statement: str = task.get("problem_statement", "")
        docker_image: str = task.get("docker_image", "")
        eval_script: str = task.get("eval_script", "")
        hints_text: str = task.get("hints_text", "")
        repo: str = task.get("repo", "")
        self.user_prompt = (
            f"instance_id: {instance_id}\n"
            f"problem_statement: {problem_statement}\n"
            f"docker_image: {docker_image}\n"
            f"eval_script: {eval_script}\n"
            f"hints_text: {hints_text}\n"
            f"repo: {repo}"
        )
        final_answer_str: str = (
            "final_answer(get_patch()) -> None:"
            " This function is used"
            " to return the final answer.\n"
            "get_patch() -> str:"
            " get_path() return the git patch retrieved.\n"
        )
        self.prompt: list = [
            {
                "role": "system",
                "content": "You are an expert assistant who can"
                " solve any task using code.\n"
                "To solve the task, you must plan forward to proceed in a"
                " series of steps, in a cycle of 'thought:', 'code:',"
                " and 'observation:' sequences."
            }
        ]
        return self.prompt

    def make_prompt_mbpp(self, task: dict) -> list:
        task_definition: str = task.get("task_definition", "")
        function_definition: str = task.get("function_definition", "")
        test_imports: list = task.get("test_imports", [])
        test_list: list = task.get("test_list", [])
        imports_str: str = "\n".join(test_imports) if test_imports else "None"
        tests_str: str = "\n".join(test_list) if test_list else "None"
        self.user_prompt = (
            f"task_definition: {task_definition}\n"
            f"function_definition: {function_definition}\n"
            f"test_imports: {imports_str}\n"
            f"test_list: {tests_str}"
        )
        final_answer_str: str = (
            "final_answer(code: str) -> None:"
            " This function is used"
            " to return the final answer."
        )
        self.prompt: list = [
            {
                "role": "system",
                "content": "You are an expert assistant who can"
                " solve any task using code.\n"
                "To solve the task, you must plan forward to proceed in a"
                " series of steps, in a cycle of 'thought:', 'code:',"
                " and 'observation:' sequences."
                " You don't have access to the internet."
                " At each step, in the 'thought:', you should"
                " first explain your reasoning towards solving the task"
                " and the tools that you want to use."
                " If you have doubts about how work a tool, execute it"
                " instead of making assumptions\n."
                " Then in the 'code:', you should write the"
                " code in simple Python."
                " NO DOCSTRINGS or COMMENTS."
                " In the end you have to return a final answer using the"
                " `final_answer()` if the task is finished."
                " final_answer() MUST be inside a code block ```python code```"
                " \nYou will be generating code and must"
                " finish with <end_code> to indicate the end of your code."
                " You have been given access to a list of tools:"
                " these tools are basically Python functions which you"
                " can call with code."
                " Code inside final_answer MUST BE the EXACT code that"
                " solves the task."
                " Here is the format of the final answer:\n"
                f"{final_answer_str}\n"
                "Make SURE to use the assert to VALIDATE your code"
                " and make sure it works like assert cond, '...'.\n"
                "Here are the tools you have access to:\n"
                f"{self.tools_str} \n"
                "Here are the allowed imports you can use:\n"
                f"{self.allowed_imports_str}\n"
                "Here is an example:\n"
                "Task:\ntask_definition: Return the smallest"
                " absolute value"
                " in a list of integers.\n"
                "function_definition: def smallest_abs(a):\n"
                "test_list: assert smallest_abs([3, -1, 5]) == 1\n"
                "assert smallest_abs([-5, 2]) == 2\n"
                "Thought: Smallest absolute value means I take the minimum,"
                " then its absolute"
                " value. Let me set up the first case.\n"
                "Code:\n"
                "```python\n"
                "print(abs(min([-5, 2])))\n"
                "```<end_code>\n"
                "Observation: 5\n"
                "Thought: Expected 2, got 5. `min` picks -5 because it is"
                " the smallest signed"
                " value, and abs only runs afterwards. I must map abs over"
                " the list first, then take the minimum.\n"
                "Code:\n"
                "```python\n"
                "def smallest_abs(a):\n"
                "    return min(map(abs,a))\n"
                "assert smallest_abs([3, -1, 5]) == 1,"
                " 'smallest_abs([3, -1, 5]) == 1'\n"
                "assert smallest_abs([-5, 2]) == 2\n,"
                " 'smallest_abs([-5, 2]) == 2'"
                "```<end_code>\n"
                'Obvservation: True'
                'Thought: I have solved the task, now I will'
                ' return the final answer.\n'
                "Code:\n"
                "```python\n"
                'final_answer("def smallest_abs(a):\n'
                'return min(map(abs,a))")\n'
                "```<end_code>\n"
            },
            {
                "role": "user",
                "content": f"Now, the real task is: {self.user_prompt}",
            },
        ]
        return self.prompt
