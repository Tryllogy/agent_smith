import shlex
import subprocess

from mcp_tools.config import get_config

# run_tests() gets a longer budget than run_command(): an evaluation
# script walks a whole test suite.
EVAL_TIMEOUT = 600

# Exit code of a command `timeout -s KILL` had to kill: 128 + SIGKILL.
TIMEOUT_EXIT = 137

# Extra seconds given to docker itself on top of the command's own limit,
# so that the limit inside the container is the one that fires.
DOCKER_GRACE = 30


def _run(command: str, workdir: str, timeout: int):
    """Run a command line through a shell and return the finished process.

    Private because it returns a CompletedProcess: each public tool turns
    it into the text its caller expects.

    Raises:
        subprocess.TimeoutExpired: If the command outlived `timeout`.
        OSError: If the shell could not be started.
    """
    return subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=workdir,
    )


def _in_container(shell_args, workdir, timeout, stdin=None):
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
        capture_output=True,
        text=True,
        timeout=timeout + DOCKER_GRACE,
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
            cwd = workdir or str(config.repo_root)
            proc = _run(command, cwd, timeout)
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
    if not config.container:
        return run_command(
            f"bash {shlex.quote(str(config.eval_script))}",
            workdir=str(config.repo_root),
            timeout=EVAL_TIMEOUT,
        )
    try:
        proc = _in_container(
            ["-ls"], str(config.repo_alias), EVAL_TIMEOUT,
            stdin=config.eval_script.read_text(),
        )
    except subprocess.TimeoutExpired:
        return f"Tests timed out after {EVAL_TIMEOUT}s"
    except OSError as exc:
        return f"Tests could not be started: {exc}"
    return _report(proc, EVAL_TIMEOUT)


def get_patch() -> str:
    """Retrieve the unified git diff of all changes made to the repository.

    Stages every change first, so that new and deleted files appear in
    the diff, and ignores file mode changes, which are noise.

    Returns:
        The git patch, or a message saying why it could not be built.
    """
    root = str(get_config().repo_root)
    try:
        _run("git add -A", root, 60)
        proc = _run("git -c core.fileMode=false diff --cached", root, 60)
    except subprocess.TimeoutExpired:
        return "Error: git timed out while building the patch"
    except OSError as exc:
        return f"Error: git could not be started in '{root}': {exc}"

    if proc.returncode != 0:
        return f"Error: git diff failed: {proc.stderr.strip()}"
    return proc.stdout
