"""The Docker side of a SWE-bench task.

Each task ships an image whose /testbed holds the repository to fix, at
the right commit, with its own Python environment. The sandbox and the
MCP tools stay on the host (option (b) of the subject); this module gives
them a container to work with:

1. the image's /testbed is copied to a temporary directory on the host;
2. a container is started with that copy mounted back on /testbed, so
   the host and the container see the very same files;
3. the MCP server is told where the copy is (--repo-root) and which
   container to run commands and tests in (--container).

File tools then read and edit the host copy directly, git builds the
patch from it, and only commands and the evaluation script go through
`docker exec`, where the repository's own interpreter lives.

Cleaning up is our job, per the subject: leaving the `with` block, by any
route, removes the container and the copy. Containers are named
`sweb-...`, which `make clean-docker` also sweeps up.

    with TaskContainer(task) as box:
        with MCPClient.from_command(box.server_command()) as client:
            ...
"""

import atexit
import contextlib
import shlex
import shutil
import signal
import subprocess
import tempfile
import uuid
import weakref
from pathlib import Path

# Where every SWE-bench image keeps the repository.
TESTBED = "/testbed"

# The tool server, at the root of the repository, as the subject requires.
SERVER = Path(__file__).resolve().parents[1] / "mcp_tools_swebench.py"

# Pulling a SWE-bench image means several gigabytes.
PULL_TIMEOUT = 1800

# Every container currently started, so the safety net below can remove
# them even when the normal `with` exit is skipped.
_LIVE = weakref.WeakSet()
_NET_INSTALLED = False


def _install_safety_net():
    """Arrange to remove live containers even on an abrupt exit.

    The `with` block cleans up on any normal return or exception, but not
    when the process is killed outright -- the moulinette's own timeout
    sends SIGTERM. atexit covers a plain interpreter exit; the SIGTERM
    handler covers the kill, then chains to whatever was there before so
    the process still ends. Installed once.
    """
    global _NET_INSTALLED
    if _NET_INSTALLED:
        return
    _NET_INSTALLED = True

    atexit.register(_cleanup_all)

    previous = signal.getsignal(signal.SIGTERM)

    def handle(signum, frame):
        _cleanup_all()
        if callable(previous):
            previous(signum, frame)
        else:
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            signal.raise_signal(signal.SIGTERM)

    # Only the main thread may install a signal handler; a worker thread
    # still gets the atexit net.
    with contextlib.suppress(ValueError):
        signal.signal(signal.SIGTERM, handle)


def _cleanup_all():
    """Remove every container still live. Never raises."""
    for box in list(_LIVE):
        with contextlib.suppress(Exception):
            box.stop()


class DockerError(Exception):
    """A docker command failed."""


def docker(*args, timeout=120):
    """Run one docker command and return its stdout.

    Raises:
        DockerError: If docker failed or did not answer in time.
    """
    try:
        proc = subprocess.run(
            ["docker", *args], capture_output=True, text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DockerError(f"docker {args[0]}: {exc}") from exc
    if proc.returncode != 0:
        raise DockerError(f"docker {args[0]}: {proc.stderr.strip()}")
    return proc.stdout.strip()


class TaskContainer:
    """The container of one SWE-bench task, and the host copy of its repo.

    Attributes, once started:
        name: Name of the running container.
        workdir: Temporary host directory holding everything below.
        repo: Host copy of the container's /testbed.
        eval_script: The task's evaluation script, written on the host.
    """

    def __init__(self, task):
        """
        Args:
            task: A SWEBenchTaskInput.
        """
        self.task = task
        self.name = f"sweb-{task.instance_id}-{uuid.uuid4().hex[:8]}"
        self.workdir = None
        self.repo = None
        self.eval_script = None
        self.started = False

    def start(self):
        """Pull the image if needed, copy /testbed out, start the container.

        Raises:
            DockerError: If any step failed. Whatever was already set up
                is removed before the error propagates.
        """
        _install_safety_net()
        _LIVE.add(self)
        try:
            self.pull()
            self.workdir = Path(tempfile.mkdtemp(prefix="agent_smith_"))
            self.repo = self.workdir / "testbed"
            self.copy_testbed()
            docker("run", "-d", "--name", self.name,
                   "-v", f"{self.repo}:{TESTBED}",
                   self.task.docker_image, "sleep", "infinity")
            self.started = True
            self.eval_script = self.workdir / "eval_script.sh"
            self.eval_script.write_text(self.task.eval_script)
        except Exception:
            self.stop()
            raise
        return self

    def pull(self):
        """Fetch the task's image, unless it is already there."""
        try:
            docker("image", "inspect", self.task.docker_image)
        except DockerError:
            docker("pull", "-q", self.task.docker_image,
                   timeout=PULL_TIMEOUT)

    def copy_testbed(self):
        """Copy the image's /testbed into the host working directory.

        A container is created but never started, just to have something
        to copy from, then removed.
        """
        source = docker("create", self.task.docker_image)
        try:
            docker("cp", f"{source}:{TESTBED}", str(self.repo), timeout=600)
        finally:
            docker("rm", "-f", source)

    def server_command(self):
        """The command line that starts the MCP server for this task.

        Meant for MCPClient.from_command().
        """
        return " ".join(shlex.quote(part) for part in [
            "python", str(SERVER),
            "--repo-root", str(self.repo),
            "--container", self.name,
            "--eval-script", str(self.eval_script),
        ])

    def stop(self):
        """Remove the container and the host copy. Safe to call twice."""
        if self.started:
            # Already gone means nothing left to clean.
            with contextlib.suppress(DockerError):
                docker("rm", "-f", self.name)
            self.started = False
        if self.workdir is not None:
            shutil.rmtree(self.workdir, ignore_errors=True)
            self.workdir = None
        _LIVE.discard(self)

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.stop()
