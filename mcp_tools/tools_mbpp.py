"""The run_tests tool of the MBPP server.

The server is a process of its own: it cannot see the function the model
defined inside the sandbox, so the model passes its candidate as `code`.
That code comes from the model: it runs in the sandbox, under the same
restrictions as the model's own code, and in a fresh interpreter, so
nothing it prints can reach the server's stdio channel.
"""

import json
import subprocess
import sys
from pathlib import Path

from core.models import MBPPTaskInput
from mcp_tools.config import get_config

TEST_TIMEOUT = 30
ASSERT_TIMEOUT = 5
PROJECT_ROOT = Path(__file__).resolve().parent.parent

_RUNNER = """
import json
import sys

from core.models import SandboxConfig
from sandbox.executor import execute

job = json.load(sys.stdin)
config = SandboxConfig(max_execution_time_seconds=job["timeout"])
for index, test in enumerate(job["tests"], start=1):
    source = "\\n".join([*job["imports"], job["code"], test])
    _, _, error, is_final, _ = execute(source, config)
    if is_final:
        print(f"{index}. ERROR code calls final_answer(): pass the solution"
              f" only  {test}")
    elif error is None:
        print(f"{index}. PASS  {test}")
    elif error.startswith("AssertionError"):
        print(f"{index}. FAIL  {test}")
    else:
        print(f"{index}. ERROR {error}  {test}")
"""


def run_tests(code: str) -> str:
    """Run the task's test_list against your solution, in the sandbox.

    Args:
        code: The complete source of your solution, imports included,
            as you would pass it to final_answer().

    Returns:
        One line per assertion, PASS, FAIL or ERROR, or a message saying
        why the tests could not run.
    """
    config = get_config()
    if config.task_file is None:
        return ("Error: no MBPP task. Start the tool server with "
                "--task-file pointing at the task JSON.")
    if not code.strip():
        return "Error: code is empty. Pass the source of your solution."
    try:
        task = MBPPTaskInput(**json.loads(config.task_file.read_text()))
    except (OSError, ValueError, TypeError) as exc:
        return f"Error: cannot load the task: {exc}"
    if not task.test_list:
        return "Error: this task carries no assertions."

    job = {
        "imports": task.test_imports,
        "code": code,
        "tests": task.test_list,
        "timeout": ASSERT_TIMEOUT,
    }
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _RUNNER],
            input=json.dumps(job),
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT,
            cwd=PROJECT_ROOT,
        )
    except subprocess.TimeoutExpired:
        return (f"Tests timed out after {TEST_TIMEOUT}s: the solution "
                "most likely loops forever.")
    if proc.returncode != 0:
        return f"The tests could not run:\n{proc.stderr.strip()}"
    return proc.stdout or "No output: the assertions printed nothing."
