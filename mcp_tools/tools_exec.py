import shlex
import subprocess

from mcp_tools.config import PathError, get_config, to_host

EVAL_TIMEOUT = 600

TIMEOUT_EXIT = 137

DOCKER_GRACE = 30

MAX_TEST_OUTPUT = 18000

START_MARKER = ">>>>> Start Test Output"
END_MARKER = ">>>>> End Test Output"


def _run(command: str, workdir: str, timeout: int, merge: bool = False):
    """Run a command line through a shell and return the finished process.

    Private because it returns a CompletedProcess: each public tool turns
    it into the text its caller expects.

    Args:
        merge: Send stderr into stdout, so a traced script's markers and
            its test output stay in the order they were written.

    Raises:
        subprocess.TimeoutExpired: If the command outlived `timeout`.
        OSError: If the shell could not be started.
    """
    return subprocess.run(
        command,
        shell=True,
        text=True,
        timeout=timeout,
        cwd=workdir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if merge else subprocess.PIPE,
    )


def _in_container(shell_args, workdir, timeout, stdin=None, merge=False):
    """Run a command inside the task's container and return the process.

    `bash -l` loads the image's profile, which activates the conda
    environment the repository was installed in; without it, `python`
    would be the wrong interpreter.

    The time limit is enforced inside the container with `timeout`:
    killing the `docker exec` client on the host would leave the command
    running in the container.

    Args:
        shell_args: What bash runs: ["-lc", command], or ["-ls"] to read
            a script from stdin.
        workdir: Directory inside the container.
        timeout: Seconds before the command is killed.
        stdin: Text to feed the command, if any.

    Returns:
        The CompletedProcess. A command killed for its time has exit code
        TIMEOUT_EXIT.

    Raises:
        subprocess.TimeoutExpired: If docker itself stopped answering.
        OSError: If docker could not be started.
    """
    args = ["docker", "exec", "-i", "-w", workdir, get_config().container,
            "timeout", "-s", "KILL", str(timeout), "bash", *shell_args]
    return subprocess.run(
        args,
        input=stdin,
        text=True,
        timeout=timeout + DOCKER_GRACE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if merge else subprocess.PIPE,
    )


def _report(proc, timeout):
    """Render a finished command the way the model reads it."""
    if get_config().container and proc.returncode == TIMEOUT_EXIT:
        return (f"Command timed out after {timeout}s (or was killed for "
                "its memory)")
    return (f"exit code: {proc.returncode}\n"
            f"--- stdout ---\n{proc.stdout}\n"
            f"--- stderr ---\n{proc.stderr}\n"
            )


def run_command(command: str, workdir: str = "", timeout: int = 60) -> str:
    """Execute a shell command in the specified working directory.

    The command goes through a shell, so pipes, redirections, `&&` and
    heredocs behave as they would in a terminal. For a SWE-bench task it
    runs inside the task's container, with the repository's own Python.

    Args:
        command: Shell command line to run (e.g. "pytest -x tests/").
        workdir: Directory to run it in. Empty means the repository root.
        timeout: Maximum seconds to wait before the command is killed.

    Returns:
        The exit code, stdout and stderr, or a message saying the command
        timed out or could not be started.
    """
    config = get_config()
    try:
        if config.container:
            cwd = workdir or str(config.repo_alias)
            proc = _in_container(["-lc", command], cwd, timeout)
        else:
            cwd = str(to_host(workdir)) if workdir else str(config.repo_root)
            proc = _run(command, cwd, timeout)
    except PathError as exc:
        return f"Error: {exc}"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s"
    except OSError as exc:
        return f"Command could not be started in '{cwd}': {exc}"
    return _report(proc, timeout)


def run_tests() -> str:
    """Execute the evaluation script of the task.

    The script is the one the server was started with (--eval-script).
    For a SWE-bench task it is fed to bash inside the task's container,
    where it expects to run.

    Returns:
        The script's exit code, stdout and stderr, or a message saying
        why it could not be run.
    """
    config = get_config()
    if not config.eval_script.is_file():
        return (f"Error: no evaluation script at '{config.eval_script}'. "
                "Start the tool server with --eval-script pointing at "
                "the task's eval_script.")
    try:
        if config.container:
            proc = _in_container(
                ["-ls"], str(config.repo_alias), EVAL_TIMEOUT,
                stdin=config.eval_script.read_text(), merge=True,
            )
        else:
            proc = _run(
                f"bash {shlex.quote(str(config.eval_script))}",
                str(config.repo_root), EVAL_TIMEOUT, merge=True,
            )
    except subprocess.TimeoutExpired:
        return f"Tests timed out after {EVAL_TIMEOUT}s"
    except OSError as exc:
        return f"Tests could not be started: {exc}"
    return _test_report(proc)


def _test_report(proc) -> str:
    """Render run_tests output: the real test run, not the script's code.

    The eval script ends with a git checkout, so its exit code says
    nothing about the tests. The run between the markers is what matters,
    and its own pass/fail summary is inside it.
    """
    if get_config().container and proc.returncode == TIMEOUT_EXIT:
        return f"Tests timed out after {EVAL_TIMEOUT}s (or killed for memory)"
    section = _between_markers(proc.stdout)
    if section is not None:
        return f"--- test output ---\n{_keep_tail(section)}"
    return (f"No test-output markers in the script's output; the full "
            f"output follows (the exit code {proc.returncode} is the "
            f"script's, not the tests'):\n{_keep_tail(proc.stdout)}")


def _keep_tail(text: str) -> str:
    """Trim long test output from the start, not the end.

    The pass/fail summary a test runner prints is its last lines, so
    when the output must be cut it is the beginning that goes. (The
    generic tool cap keeps the start; test output is the exception.)
    """
    if len(text) <= MAX_TEST_OUTPUT:
        return text
    return (f"... {len(text) - MAX_TEST_OUTPUT} characters cut from the "
            f"start; the end, with the summary, follows\n"
            + text[-MAX_TEST_OUTPUT:])


def _between_markers(text: str):
    """Return what the eval script printed between its two markers.

    Args:
        text: The script's combined output.

    Returns:
        The text between the markers, or None if they are not both there.
    """
    start = text.find(START_MARKER)
    if start == -1:
        return None
    start = text.find("\n", start)
    end = text.find(END_MARKER, start + 1) if start != -1 else -1
    if start == -1 or end == -1:
        return None
    return text[start + 1:text.rfind("\n", start, end)].strip()


def get_patch() -> str:
    """Retrieve the unified git diff of all changes made to the repository.

    Stages every change first, so that new and deleted files appear in
    the diff, and ignores file mode changes, which are noise.

    Returns:
        The git patch, or a message saying why it could not be built.
    """
    root = str(get_config().repo_root)
    try:
        _run("git -c core.fileMode=false add -A", root, 60)
        proc = _run("git -c core.fileMode=false diff --cached", root, 60)
    except subprocess.TimeoutExpired:
        return "Error: git timed out while building the patch"
    except OSError as exc:
        return f"Error: git could not be started in '{root}': {exc}"

    if proc.returncode != 0:
        return f"Error: git diff failed: {proc.stderr.strip()}"
    return proc.stdout
