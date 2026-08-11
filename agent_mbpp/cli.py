from core.agent.loop import Loop
from core.models import MBPPTaskInput
from pydantic import ValidationError
from core.agent.prompt import Prompt
import json
from core.models import SandboxConfig


class AgentMBPP:
    def __init__(
        self,
        task_file: str,
        output_file: str,
        model_name: str,
        provider_url: str
    ) -> None:
        self.task: dict = self.get_task_from_file(task_file)
        self.output_file: str = output_file
        prompt: Prompt = Prompt(task=self.task,
                                tools=None,
                                allowed_imports=SandboxConfig.allowed_imports)

        self.loop = Loop(
            model_name=model_name,
            provider_url=provider_url,
            prompt=prompt,
        )

    def run(self):
        self.loop.thought()

    def get_task_from_file(
        self,
        file_path: str
    ) -> dict:
        try:
            with open(file_path, 'r') as file:
                task: dict = json.load(file)
                MBPPTaskInput.model_validate(task)
                return task
        except json.JSONDecodeError:
            raise ValueError(f"The task file '{file_path}' is not a valid "
                             f"JSON file. Please check the file content.")
        except FileNotFoundError:
            raise FileNotFoundError(f"The task file '{file_path}' was not "
                                    f"found. Please ensure the path is "
                                    f"correct.")
        except ValidationError as e:
            raise ValueError(f"Invalid task format in file '{file_path}': {e}")
        except Exception as e:
            raise RuntimeError(f"An error occurred while reading the task "
                               f"file: {e}")
