from core.constants import (
    MBPP_PROMPT_EXEMPLE,
    SWE_PROMPT_EXEMPLE,
    Bench,
    BenchName,
)


class Prompt:
    """Conversation sent to the LLM: system turn, task turn, then the
    assistant and observation turns added by the loop.
    """

    def __init__(
        self,
        bench: Bench,
        task: dict,
        manual: str = None,
        allowed_imports: list = None,
    ) -> None:
        """Build the initial conversation for task on bench.

        manual is the sandbox manual, already rendered from the connected
        MCP server: it goes into the system turn as is, and is left out
        when empty. When it is there, the lines it already covers (print()
        of tool calls, final_answer and get_patch descriptions) are not
        repeated. allowed_imports are listed in the system turn.
        Raises ValueError for an unsupported benchmark.
        """
        self.manual: str = manual
        self.allowed_imports: list = allowed_imports
        self.allowed_imports_str: str = (
            "".join([f"- {imp}\n" for imp in self.allowed_imports])
            if self.allowed_imports
            else "None"
        )
        self.manual_section: str = (
            f"\n{self.manual.strip()}\n\n"
            if self.manual and self.manual.strip()
            else ""
        )
        if bench.name == BenchName.SWE.value:
            self.make_prompt_swe(task)
        elif bench.name == BenchName.MBPP.value:
            self.make_prompt_mbpp(task)
        else:
            raise ValueError(f"Unsupported benchmark: {bench.name}")

    def add_message(self, message: dict) -> None:
        """Append a message, a dict with 'role' and 'content' keys."""
        if not isinstance(message, dict):
            raise TypeError("Message must be a dictionary.")
        if "role" not in message or "content" not in message:
            raise ValueError("Message must contain 'role' and 'content' keys.")
        self.prompt.append(message)

    def make_prompt_swe(self, task: dict) -> list:
        """Build the SWE-bench system and user turns from task."""
        instance_id: str = task.get("instance_id", "")
        problem_statement: str = task.get("problem_statement", "")
        hints_text: str = task.get("hints_text", "")
        repo: str = task.get("repo", "")
        self.user_prompt = (
            f"instance_id: {instance_id}\n"
            f"problem_statement: {problem_statement}\n"
            f"hints_text: {hints_text}\n"
            f"repo: {repo}"
        )
        final_answer_str: str = (
            ""
            if self.manual_section
            else "get_patch() -> str:"
            " get_patch() returns the git patch retrieved.\n"
            "final_answer(patch: str) -> None:"
            " This function is used to return the final answer.\n"
        ) + (
            "Call get_patch() first, check the patch is not empty,"
            " then pass it to final_answer().\n"
        )
        print_rule: str = (
            ""
            if self.manual_section
            else " A tool call alone prints NOTHING: wrap every tool call in"
            " print() or you will get an empty observation."
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
                " If you are unsure how a tool behaves, call it and read"
                " its output instead of guessing.\n"
                "Then in the 'code:', you should write the"
                " code in simple Python. Variables, functions and imports"
                " you define stay available in the next steps."
                " In the end you have to return a final answer using the"
                " `final_answer()` if the task is finished."
                " final_answer() MUST be inside a code block ```python code```"
                " Here is the format of the final answer:\n"
                f"{final_answer_str}\n"
                "You will be generating code and must"
                " finish with <end_code> to indicate the end of your code.\n"
                f"{self.manual_section}"
                "Here are the allowed imports you can use:\n"
                f"{self.allowed_imports_str}\n"
                "It is FORBIDDEN to git commit or make a patch empty."
                " ONLY make 1 and ONLY 1 code block per step."
                f"{print_rule}\n"
                "read_file() prefixes each line with '<line_number>: '."
                " These prefixes are NOT part of the file content: never"
                " include them in the old_str of edit_file(), which matches"
                " the file EXACTLY, indentation included.\n"
                "It is FORBIDDEN to modify test files: the evaluation script"
                " restores them before judging, so editing them changes"
                " nothing and only pollutes the patch.\n"
                "Never edit code you have not read: every old_str must be"
                " copied from a read_file() observation of an EARLIER step,"
                " never written from memory, and never call edit_file() in"
                " the same code block as the read_file() it relies on. Do"
                " not apply a fix you remember for this repository: find"
                " the cause in the code, then fix it.\n"
                "Here is an example:\n"
                f"{SWE_PROMPT_EXEMPLE}",
            },
            {
                "role": "user",
                "content": f"Now, the real task is: {self.user_prompt}",
            },
        ]
        return self.prompt

    def make_prompt_mbpp(self, task: dict) -> list:
        """Build the MBPP system and user turns from task."""
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
            ""
            if self.manual_section
            else " Here is the format of the final answer:\n"
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
                " If you are unsure how a tool behaves, call it and read"
                " its output instead of guessing.\n"
                "Then in the 'code:', you should write the"
                " code in simple Python. Variables, functions and imports"
                " you define stay available in the next steps."
                " NO DOCSTRINGS or COMMENTS."
                " In the end you have to return a final answer using the"
                " `final_answer()` if the task is finished."
                " final_answer() MUST be inside a code block ```python code```"
                "\nYou will be generating code and must"
                " finish with <end_code> to indicate the end of your code."
                " Code inside final_answer MUST BE the EXACT code that"
                " solves the task."
                f"{final_answer_str}\n"
                "Check your function with run_tests(code=...) before"
                " submitting: keep the solution in a variable, print the"
                " report of run_tests(), and call final_answer() with that"
                " same variable, in the same code block, only if every test"
                " passes. test_list is only a sample: your function is also"
                " graded on hidden tests, so cover every requirement stated"
                " in task_definition.\n"
                f"{self.manual_section}"
                "Here are the allowed imports you can use:\n"
                f"{self.allowed_imports_str}\n"
                "Here is an example:\n"
                f"{MBPP_PROMPT_EXEMPLE}",
            },
            {
                "role": "user",
                "content": f"Now, the real task is: {self.user_prompt}",
            },
        ]
        return self.prompt
