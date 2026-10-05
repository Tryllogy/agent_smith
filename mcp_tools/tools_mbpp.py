"""The run_tests tool of the MBPP server.

run_tests checks a candidate function against a list of assertions. Both
can be passed as arguments; whatever is not passed falls back to a file
the server was configured with. The server is a process of its own and
cannot see the function defined inside the sandbox, so the file fallback
reads the candidate from --solution-file (a directory the sandbox
allows) and the assertions from --task-file.
"""

import json
import subprocess
import sys

from core.models import MBPPTaskInput
from mcp_tools.config import get_config

TEST_TIMEOUT = 30

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


def run_tests(code: str = None, test_list: list = None) -> str:
    """Execute a list of assertions against a candidate function.

    Args:
        code: The candidate function's source. If omitted, it is read
            from the configured solution file.
        test_list: The assertions to run (e.g. ["assert f(1) == 2"]).
            If given, these take priority over the task file. If omitted,
            the task file's assertions are used.

    Returns:
        One line per assertion, PASS, FAIL or ERROR, or a message saying
        why the tests could not run.
    """
    test_imports = []
    if test_list is None:
        config = get_config()
        if config.task_file is None:
            return ("Error: no test_list given and no --task-file to fall "
                    "back on.")
        try:
            task = MBPPTaskInput(**json.loads(config.task_file.read_text()))
        except (OSError, ValueError, TypeError) as exc:
            return f"Error: cannot load the task: {exc}"
        test_list = task.test_list
        test_imports = task.test_imports
    if not test_list:
        return "Error: no assertions to run."

    if code is None:
        config = get_config()
        if not config.solution_file.is_file():
            return (f"Error: no candidate given and none at "
                    f"'{config.solution_file}'.")
        try:
            code = config.solution_file.read_text()
        except OSError as exc:
            return f"Error: cannot read the candidate: {exc}"

    script = "\n".join([
        *test_imports,
        code,
        _RUNNER.format(tests=json.dumps(test_list)),
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
