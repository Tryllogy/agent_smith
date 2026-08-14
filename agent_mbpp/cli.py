import json
import os

from dotenv import load_dotenv
from pydantic import ValidationError

from core import constants
from core.agent.loop import Loop
from core.agent.prompt import Prompt
from core.llm.client import LLMClient
from core.models import MBPPTaskInput, SandboxConfig, SolutionOutput

if not load_dotenv():
    raise FileNotFoundError(
        "The .env file was not found."
        " Please ensure it exists in the project root."
    )
if not os.getenv("OPENROUTER_API_KEY"):
    raise OSError(
        "The OPENROUTER_API_KEY environment variable"
        " is not set."
        " Please ensure it is defined in the .env file."
    )


class AgentMBPP:
    def __init__(
        self,
        task_file: str,
        output_file: str,
        model_name: str,
        provider_url: str,
    ) -> None:
        self.task: dict = self.get_task_from_file(task_file)
        self.output_file: str = output_file
        prompt: Prompt = Prompt(
            task=self.task,
            tools=None,
            allowed_imports=SandboxConfig().authorized_imports,
        )

        self.llm_client: LLMClient = LLMClient(
            url=provider_url,
            endpoint=constants.LLM_ENDPOINT,
            model_name=model_name,
            api_key=os.getenv("OPENROUTER_API_KEY"),
            stop_sequence=constants.LLM_STOP_SEQUENCE,
        )

        self.loop = Loop(
            client=self.llm_client,
            prompt=prompt,
            bench=constants.MBPP,
            config_sandbox=SandboxConfig(),
        )

    def run(self) -> SolutionOutput:
        solution: SolutionOutput = self.loop.run(self.task["task_id"])
        with open(self.output_file, "w") as f:
            f.write(solution.model_dump_json(indent=4))
        if solution.success and solution.error is None:
            return solution
        raise RuntimeError(
            f"Agent failed to solve the task. Error: {solution.error}"
        )

    def get_task_from_file(self, file_path: str) -> dict:
        try:
            with open(file_path) as file:
                task: dict = json.load(file)
                MBPPTaskInput.model_validate(task)
                return task
        except json.JSONDecodeError:
            raise ValueError(
                f"The task file '{file_path}' is not a valid "
                f"JSON file. Please check the file content."
            )
        except FileNotFoundError:
            raise FileNotFoundError(
                f"The task file '{file_path}' was not "
                f"found. Please ensure the path is "
                f"correct."
            )
        except ValidationError as e:
            raise ValueError(f"Invalid task format in file '{file_path}': {e}")
        except Exception as e:
            raise RuntimeError(
                f"An error occurred while reading the task file: {e}"
            )
