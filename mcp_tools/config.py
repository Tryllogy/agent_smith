"""Runtime configuration of the MCP tool servers.

The tools run in a process of their own, so what they need to know about
the task -- where the repository is, which script evaluates it, where
the MBPP task is -- reaches them on the server's command line, and is
kept here.

Entry points call `configure_from_argv()` once at startup; the tools
read the result back with `get_config()`.
"""

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path

SCRATCH = Path("/tmp/agent")

CONTAINER_REPO = Path("/testbed")


def _default_repo_root() -> Path:
    """Find the repository root when --repo-root was not given.

    The eval script names the repository by the TESTBED_PATH environment
    variable, so that is honoured first; then /testbed, the path inside a
    task image; then the cwd, for development.
    """
    env = os.environ.get("TESTBED_PATH")
    if env:
        return Path(env)
    testbed = Path("/testbed")
    return testbed if testbed.is_dir() else Path.cwd()


@dataclass
class ToolsConfig:
    """Where the tools find the repository and the task files.

    With a SWE-bench task, the repository lives in a Docker container at
    /testbed, and the tools work on a copy of it mounted from the host:
    `repo_root` is that host copy, `container` names the container, and
    `repo_alias` is the path the model knows the repository by.
    """

    repo_root: Path = field(default_factory=_default_repo_root)
    eval_script: Path = SCRATCH / "eval_script.sh"
    task_file: Path | None = None
    container: str | None = None
    repo_alias: Path | None = None


_config = ToolsConfig()


def get_config() -> ToolsConfig:
    """Return the configuration in force."""
    return _config


class PathError(ValueError):
    """A path the tools must not touch (outside the repository)."""


def to_host(path: str) -> Path:
    """Turn a path as the model writes it into one the tools can open.

    The model only ever sees /testbed, so a path under /testbed is moved
    under the host copy and a relative path is taken from the repository
    root. The result must stay inside the repository: the file tools are
    not the sandbox, so without this check read_file("/etc/passwd") would
    read the host.

    Raises:
        PathError: If the path resolves outside the repository root.
    """
    config = get_config()
    root = config.repo_root
    candidate = Path(path)
    alias = config.repo_alias
    under_alias = alias is not None and (
        candidate == alias or alias in candidate.parents
    )
    if under_alias:
        host = root / candidate.relative_to(alias)
    elif candidate.is_absolute():
        host = candidate
    else:
        host = root / candidate

    try:
        host.resolve().relative_to(root.resolve())
    except ValueError:
        raise PathError(
            f"'{path}' is outside the repository and cannot be accessed"
        ) from None
    return host


def to_alias(path: Path) -> str:
    """Turn a host path back into the one the model knows (/testbed/...).

    Without a container, or for a path outside the repository, the path
    is returned unchanged.
    """
    config = get_config()
    if config.repo_alias is not None:
        try:
            inside = Path(path).relative_to(config.repo_root.resolve())
        except ValueError:
            return str(path)
        return str(config.repo_alias / inside)
    return str(path)


def configure(**overrides) -> ToolsConfig:
    """Override configuration fields, skipping the ones left at None.

    Args:
        **overrides: Field names of `ToolsConfig` and their new values.

    Returns:
        The updated configuration.

    Raises:
        TypeError: If a name is not a field of `ToolsConfig`.
    """
    for name, value in overrides.items():
        if not hasattr(_config, name):
            raise TypeError(f"unknown configuration field '{name}'")
        if value is not None:
            setattr(_config, name, value)
    return _config


def build_parser(benchmark: str) -> argparse.ArgumentParser:
    """Build the command line parser of one of the two tool servers.

    Args:
        benchmark: "mbpp" or "swebench"; selects the options specific
            to that benchmark, on top of the shared ones.

    Returns:
        The parser.
    """
    parser = argparse.ArgumentParser(
        description=f"MCP tool server for the {benchmark} benchmark",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        help="Directory the tools read, search and run commands in "
             "(default: /testbed when it exists, else the cwd).",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="MCP transport to serve on (default: stdio).",
    )
    parser.add_argument("--host", default="127.0.0.1",
                        help="Address to bind for streamable-http.")
    parser.add_argument("--port", type=int, default=8000,
                        help="Port to bind for streamable-http.")
    if benchmark == "swebench":
        parser.add_argument(
            "--container",
            help="Docker container holding the task. Commands and tests "
                 "then run inside it, and --repo-root is taken as the host "
                 "copy of its /testbed.",
        )
        parser.add_argument(
            "--eval-script",
            type=Path,
            help=f"Script run_tests() runs (default: {SCRATCH}/"
                 "eval_script.sh).",
        )
    else:
        parser.add_argument(
            "--task-file",
            type=Path,
            help="JSON file holding the MBPP task whose assertions "
                 "run_tests() checks.",
        )
    return parser


def configure_from_argv(benchmark: str, argv=None) -> argparse.Namespace:
    """Parse the server's command line and apply it.

    Args:
        benchmark: "mbpp" or "swebench".
        argv: Arguments to parse, or None to read sys.argv.

    Returns:
        The parsed arguments, so the entry point can read the transport
        options back.
    """
    args = build_parser(benchmark).parse_args(argv)
    if benchmark == "swebench":
        configure(
            repo_root=args.repo_root,
            eval_script=args.eval_script,
            container=args.container,
            repo_alias=CONTAINER_REPO,
        )
    else:
        configure(repo_root=args.repo_root, task_file=args.task_file)
    return args
