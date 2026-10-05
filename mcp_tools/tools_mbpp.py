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
VALUE_CHARS = 200
PROJECT_ROOT = Path(__file__).resolve().parent.parent

_RUNNER = """
import ast
import json
import sys

from core.models import SandboxConfig
from sandbox.executor import execute

job = json.load(sys.stdin)
config = SandboxConfig(max_execution_time_seconds=job["timeout"])


def obtained(test):
    try:
        node = ast.parse(test).body[0]
    except (SyntaxError, IndexError):
        return ""
    if not (isinstance(node, ast.Assert)
            and isinstance(node.test, ast.Compare)
            and len(node.test.ops) == 1
            and isinstance(node.test.ops[0], ast.Eq)):
        return ""
    left = ast.unparse(node.test.left)
    source = "\\n".join(
        [*job["imports"], job["code"], f"print(repr({left}))"])
    out, _, error, is_final, _ = execute(source, config)
    lines = out.strip().splitlines()
    if error is not None or is_final or not lines:
        return ""
    value = lines[-1]
    if len(value) > job["value_chars"]:
        value = value[:job["value_chars"]] + "..."
    return f"  (got {value})"


for index, test in enumerate(job["tests"], start=1):
    source = "\\n".join([*job["imports"], job["code"], test])
    _, _, error, is_final, _ = execute(source, config)
    if is_final:
        print(f"{index}. ERROR code calls final_answer(): pass the solution"
              f" only  {test}")
    elif error is None:
        print(f"{index}. PASS  {test}")
    elif error.startswith("AssertionError"):
        print(f"{index}. FAIL  {test}{obtained(test)}")
    else:
        print(f"{index}. ERROR {error}  {test}")
"""


def run_tests(code: str, test_list: list[str] | None = None) -> str:
    """Run the task's test_list against your solution, in the sandbox.

    Args:
        code: The complete source of your solution, imports included,
            as you would pass it to final_answer().
        test_list: Assertions to run instead of the task's test_list.

    Returns:
        A first line "success: true" or "success: false" with the number
        of tests passed, then one line per assertion, PASS, FAIL or
        ERROR; a failed `assert X == Y` also shows the value X had. Or a
        message saying why the tests could not run.
    """
    if not code.strip():
        return "Error: code is empty. Pass the source of your solution."
    try:
        imports, tests = load_tests(test_list)
    except (OSError, ValueError, TypeError) as exc:
        return f"Error: cannot load the task: {exc}"
    if not tests:
        return (
            "Error: no assertions to run. Pass test_list, or start the"
            " tool server with --task-file pointing at the task JSON."
        )

    job = {
        "imports": imports,
        "code": code,
        "tests": tests,
        "timeout": ASSERT_TIMEOUT,
        "value_chars": VALUE_CHARS,
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
        return (
            f"Tests timed out after {TEST_TIMEOUT}s: the solution "
            "most likely loops forever."
        )
    if proc.returncode != 0:
        return f"The tests could not run:\n{proc.stderr.strip()}"
    return summarize(proc.stdout, len(tests))


def load_tests(test_list: list[str] | None) -> tuple[list[str], list[str]]:
    """Return the test imports and the assertions to run.

    test_list, when given, replaces the task's; the task's test_imports
    still apply when a task file is configured.

    Raises:
        OSError, ValueError, TypeError: If the task file cannot be read.
    """
    config = get_config()
    task = None
    if config.task_file is not None:
        task = MBPPTaskInput(**json.loads(config.task_file.read_text()))
    imports = task.test_imports if task is not None else []
    if test_list is not None:
        return imports, [str(test) for test in test_list]
    return imports, task.test_list if task is not None else []


def summarize(report: str, total: int) -> str:
    """Put the verdict, with the number of tests passed, before report."""
    passed = sum(
        1
        for line in report.splitlines()
        if line.split(" ", 2)[1:2] == ["PASS"]
    )
    verdict = "true" if passed == total else "false"
    return f"success: {verdict} ({passed} of {total} tests passed)\n{report}"
