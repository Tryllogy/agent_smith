import argparse
import sys

from agent_mbpp.cli import AgentMBPP


def check_args(args):
    if not args.model_name or args.model_name.strip() == "":
        raise ValueError("Model name is required.")


def main():
    parser = argparse.ArgumentParser(description="Run the MBPP agent.")
    parser.add_argument(
        "--task-file",
        required=True,
        help="Path to the task file."
    )
    parser.add_argument(
        "--output",
        default="output.json",
        help="Path to the output file."
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

    agent_mbpp = AgentMBPP(
        task_file=args.task_file,
        output_file=args.output,
        model_name=args.model_name,
        provider_url=args.provider_url,
    )
    agent_mbpp.run()


if __name__ == "__main__":
    try:
        main()
        exit(0)
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        exit(1)
