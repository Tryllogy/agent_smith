import shlex
import subprocess

from mcp_tools.config import get_config

# run_tests() gets a longer budget than run_command(): an evaluation
# script walks a whole test suite.
EVAL_TIMEOUT = 600


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


def run_command(command: str, workdir: str = "", timeout: int = 60) -> str:
    """Execute a shell command in the specified working directory.

    The command goes through a shell, so pipes, redirections, `&&` and
    heredocs behave as they would in a terminal.

    Args:
        command: Shell command line to run (e.g. "pytest -x tests/").
        workdir: Directory to run it in. Empty means the repository root.
        timeout: Maximum seconds to wait before the command is killed.

    Returns:
        The exit code, stdout and stderr, or a message saying the command
        timed out or could not be started.
    """
    cwd = workdir or str(get_config().repo_root)
    try:
        proc = _run(command, cwd, timeout)
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s"
    except OSError as exc:
        return f"Command could not be started in '{cwd}': {exc}"

    return (f"exit code: {proc.returncode}\n"
            f"--- stdout ---\n{proc.stdout}\n"
            f"--- stderr ---\n{proc.stderr}\n"
            )


def run_tests() -> str:
    """Execute the evaluation script of the task.

    The script is the one the server was started with (--eval-script),
    run from the repository root.

    Returns:
        The script's exit code, stdout and stderr, or a message saying
        why it could not be run.
    """
    config = get_config()
    if not config.eval_script.is_file():
        return (f"Error: no evaluation script at '{config.eval_script}'. "
                "Start the tool server with --eval-script pointing at "
                "the task's eval_script.")
    return run_command(
        f"bash {shlex.quote(str(config.eval_script))}",
        workdir=str(config.repo_root),
        timeout=EVAL_TIMEOUT,
    )


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
