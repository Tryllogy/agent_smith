import json
import os

from dotenv import load_dotenv
from pydantic import ValidationError

from core import constants
from core.api_key import APIKey
from core.agent.loop import Loop
from core.agent.prompt import Prompt
from core.llm.client import LLMClient
from core.models import MBPPTaskInput, SandboxConfig, SolutionOutput

load_dotenv()


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
            api_keys=get_api_keys(),
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
        return solution

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


def get_api_keys() -> list[APIKey]:
    api_keys_env = os.getenv("OPENROUTER_API_KEY")
    if not api_keys_env:
        raise ValueError(
            "The OPENROUTER_API_KEY environment variable is not set."
            " Please ensure it is defined in the .env file."
        )
    keys: list = [
        APIKey(key.strip()) for key in api_keys_env.split(",") if key.strip()
    ]
    if not keys:
        raise ValueError(
            "The OPENROUTER_API_KEY environment variable is empty."
            " Please provide at least one valid API key."
        )
    return keys
