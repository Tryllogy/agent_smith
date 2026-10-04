"""The run_tests tool of the MBPP server.

The server is a process of its own: it cannot see the function the model
defined inside the sandbox. So the contract is a file. The model writes
its candidate to the solution file (--solution-file, /tmp/agent/solution.py
by default, a directory the sandbox already allows), and run_tests()
checks the task's assertions against it.
"""

import json
import subprocess
import sys

from core.models import MBPPTaskInput
from mcp_tools.config import get_config

# An MBPP task is one short function: past this, it is looping.
TEST_TIMEOUT = 30

# Runs each assertion on its own, so one failure does not hide the
# others, and names the exception instead of printing a traceback.
_RUNNER = """
for _index, _source in enumerate({tests}, start=1):
    try:
        exec(_source)
    except AssertionError:
        print(f"{{_index}}. FAIL  {{_source}}")
    except Exception as _error:
        print(f"{{_index}}. ERROR {{type(_error).__name__}}: {{_error}}"
              f"  {{_source}}")
    else:
        print(f"{{_index}}. PASS  {{_source}}")
"""


def run_tests() -> str:
    """Execute the task's assertions against the candidate solution.

    Returns:
        One line per assertion, PASS, FAIL or ERROR, or a message saying
        why the tests could not run.
    """
    config = get_config()
    if config.task_file is None:
        return ("Error: no MBPP task. Start the tool server with "
                "--task-file pointing at the task JSON.")
    if not config.solution_file.is_file():
        return (f"Error: no candidate solution at '{config.solution_file}'"
                ". Write your function there before calling run_tests().")
    try:
        task = MBPPTaskInput(**json.loads(config.task_file.read_text()))
        solution = config.solution_file.read_text()
    except (OSError, ValueError, TypeError) as exc:
        return f"Error: cannot load the task or the solution: {exc}"
    if not task.test_list:
        return "Error: this task carries no assertions."

    script = "\n".join([
        *task.test_imports,
        solution,
        _RUNNER.format(tests=json.dumps(task.test_list)),
    ])
    try:
        proc = subprocess.run(
            [sys.executable, "-"],
            input=script,
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return (f"Tests timed out after {TEST_TIMEOUT}s: the solution "
                "most likely loops forever.")
    if proc.returncode != 0:
        return f"The solution could not be loaded:\n{proc.stderr.strip()}"
    return proc.stdout or "No output: the assertions printed nothing."
