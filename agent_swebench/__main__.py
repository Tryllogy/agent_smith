import argparse
import sys

from agent_swebench.cli import AgentSWEBENCH
from core.agent_cli_helper import check_args


def main():
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

    check_args(args)

    agent_swebench = AgentSWEBENCH(
        task_file=args.task_file,
        output_file=args.output,
        model_name=args.model_name,
        provider_url=args.provider_url,
    )
    agent_swebench.run()


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)
