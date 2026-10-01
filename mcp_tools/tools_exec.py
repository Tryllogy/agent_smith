import subprocess
import shlex


def run_command(
        command: str,
        timeout: int = 60,
        cwd: str = "/testbed",
        raw: bool = False) -> str:
    """Run a shell command and return its output.

    The command is split shell-style (quotes are respected) and run as a
    process list, without a shell, so shell metacharacters have no special
    power. By default, combines the exit code, stdout and stderr into a
    single string for the LLM to read.

    Args:
        command: Shell command line to run (e.g. "pytest -x tests/").
        timeout: Maximum seconds to wait before the command is killed.
        cwd: Directory to run the command in (defaults to the repo root).
        raw: If True, return only the raw stdout (no exit-code/stderr
            decoration). Used when the output must stay machine-usable,
            e.g. a git patch to be applied.

    Returns:
        The decorated output (exit code, stdout, stderr), or just the raw
        stdout if `raw` is True, or a timeout message if the command
        exceeded `timeout`.
    """
    args = shlex.split(command)

    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout, cwd=cwd)
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s"

    if raw:
        return proc.stdout
    return (f"exit code: {proc.returncode}\n"
            f"--- stdout ---\n{proc.stdout}\n"
            f"--- stderr ---\n{proc.stderr}\n"
            )


def run_tests(test_path: str = "", timeout: int = 300) -> str:
    """Run the test suite with pytest and return the result.

    Runs `python -m pytest` in the repo. If `test_path` is given, only that
    file, directory or test is run (e.g. "tests/test_foo.py::test_add");
    if empty, the whole suite runs.

    Args:
        test_path: Optional path or node id to target specific tests. Empty
            runs the entire suite.
        timeout: Maximum seconds to wait before the run is killed.

    Returns:
        The pytest output (exit code, stdout and stderr), or a timeout
        message if the run exceeded `timeout`.
    """
    command = "python -m pytest " + test_path
    return run_command(command, raw=False, timeout=timeout)


def get_patch() -> str:
    """Return all changes made to the repo as a git patch.

    Stages every change (modified, new and deleted files) with `git add -A`,
    then returns the unified diff against the initial commit via
    `git diff --cached`. This diff is the final SWE-bench solution.

    Returns:
        The git patch (unified diff), including newly created files.
    """
    run_command("git add -A")
    return run_command("git diff --cached", raw=True)
