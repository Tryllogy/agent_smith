import argparse
from agent_mbpp.cli import AgentMBPP


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Run the MBPP agent.")
    parser.add_argument("--task-file",
                        default="task.json",
                        help="Path to the task file.")
    parser.add_argument("--output",
                        default="output.json",
                        help="Path to the output file.")
    parser.add_argument("--model-name",
                        default="nvidia/nemotron-3-ultra-550b-a55b:free",
                        help="Name of the language model to use.")
    parser.add_argument("--provider-url",
                        default="https://openrouter.ai/api/v1",
                        help="URL of the LLM provider.")

    args = parser.parse_args()

    agent_mbpp = AgentMBPP(
        task_file=args.task_file,
        output_file=args.output,
        model_name=args.model_name,
        provider_url=args.provider_url
    )
    agent_mbpp.run()
