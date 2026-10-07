import argparse
import sys
import time

from core.agent_cli_helper import (
    check_args,
    find_provider_url_by_model,
    interrupt_on_signals,
    read_task_id,
    write_failure_output,
)
from core.constants import SWE, SWE_DEFAULT_MODEL

from .cli import AgentSWEBENCH


def main() -> int:
    """Parse the arguments, run the SWE-bench agent, return the exit code.

    Any error, or a SIGINT, SIGTERM or SIGHUP, still leaves a
    solution.json (success=false) at --output, after the container is
    removed, and the exit code is then 1. The time limit runs from here,
    so pulling the image counts.
    """
    start_time: float = time.time()
    parser = argparse.ArgumentParser(description="Run the SWEbench agent.")
    parser.add_argument(
        "--task-file", required=True, help="Path to the task file."
    )
    parser.add_argument(
        "--output", default="output.json", help="Path to the output file."
    )
    parser.add_argument(
        "--model-name",
        default=SWE_DEFAULT_MODEL,
        help="Name of the language model to use (default: %(default)s).",
    )
    parser.add_argument(
        "--provider-url",
        default=None,
        help="URL of the LLM provider (default: the provider that"
        " declares the model in configs/models.json).",
    )

    args = parser.parse_args()
    interrupt_on_signals()

    try:
        check_args(args)
        agent = AgentSWEBENCH(
            task_file=args.task_file,
            output_file=args.output,
            model_name=args.model_name,
            provider_url=args.provider_url
            or find_provider_url_by_model(args.model_name),
            start_time=start_time,
        )
        agent.run()
    except Exception as e:
        error: str = str(e)
    except KeyboardInterrupt as e:
        error = f"Interrupted by {e or 'SIGINT'}"
    else:
        return 0
    sys.stderr.write(f"Error: {error}\n")
    write_failure_output(
        output_file=args.output,
        bench=SWE,
        task_id=read_task_id(args.task_file, "instance_id"),
        error=error,
        start_time=start_time,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
