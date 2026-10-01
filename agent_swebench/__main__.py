import argparse
import sys
import time

from agent_swebench.cli import AgentSWEBENCH
from core.agent_cli_helper import (
    check_args,
    read_task_id,
    write_failure_output,
)
from core.constants import SWE


def main() -> int:
    """Parse the arguments, run the SWE-bench agent, return the exit code.

    Any error still leaves a solution.json (success=false) at
    --output, and the exit code is then 1.
    """
    parser = argparse.ArgumentParser(description="Run the SWEbench agent.")
    parser.add_argument(
        "--task-file", required=True, help="Path to the task file."
    )
    parser.add_argument(
        "--output", default="output.json", help="Path to the output file."
    )
    parser.add_argument(
        "--model-name",
        required=True,
        help="Name of the language model to use.",
    )
    parser.add_argument(
        "--provider-url",
        required=True,
        help="URL of the LLM provider.",
    )

    args = parser.parse_args()
    start_time: float = time.time()

    try:
        check_args(args)
        agent_swebench = AgentSWEBENCH(
            task_file=args.task_file,
            output_file=args.output,
            model_name=args.model_name,
            provider_url=args.provider_url,
        )
        agent_swebench.run()
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        write_failure_output(
            output_file=args.output,
            bench=SWE,
            task_id=read_task_id(args.task_file, "instance_id"),
            error=str(e),
            start_time=start_time,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
