import json
import os

from dotenv import load_dotenv
from pydantic import ValidationError

from core import constants
from core.agent.loop import Loop
from core.agent.prompt import Prompt
from core.api_key import APIKey
from core.llm.client import LLMClient
from core.llm.provider import Provider
from core.models import MBPPTaskInput, SandboxConfig, SolutionOutput
from core.validators import ModelConfig, ProviderConfig

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

        self.provider_config, self.model_config = (
            get_provider_and_model_config(model_name, provider_url)
        )

        self.llm_client: LLMClient = LLMClient(
            url=provider_url,
            endpoint=self.provider_config.endpoint,
            model_name=model_name,
            api_keys=get_api_keys(self.provider_config),
            stop_sequence=constants.LLM_STOP_SEQUENCE,
            provider=Provider(self.provider_config),
            model_config=self.model_config,
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


def get_provider_and_model_config(
    model_name: str, provider_url: str
) -> tuple[ProviderConfig, ModelConfig]:
    try:
        with open(constants.MODELS_CONFIG_FILE) as f:
            models_config = json.load(f)
            provider_name: str = find_provider_by_url(
                models_config, provider_url
            )
            provider_config = models_config.get(provider_name)
            provider = ProviderConfig.model_validate(
                provider_config.get("provider", {})
            )
            model_config: dict = provider_config.get("models", {}).get(
                model_name, {}
            )
            if model_config == {} or model_config is None:
                model = ModelConfig.model_validate({"reasoning": False})
            else:
                model = ModelConfig.model_validate(model_config)
            return provider, model
    except FileNotFoundError:
        raise FileNotFoundError(
            f"The models configuration file '{constants.MODELS_CONFIG_FILE}'"
            " was not found."
        )
    except json.JSONDecodeError:
        raise ValueError(
            f"The models configuration file '{constants.MODELS_CONFIG_FILE}'"
            " is not a valid JSON file."
        )
    except (ValueError, KeyError) as e:
        raise ValueError(f"Error in models configuration: {e}")
    except Exception as e:
        raise RuntimeError(
            "An unexpected error occurred while"
            f" reading the models configuration: {e}"
        )


def find_provider_by_url(models_config: dict, url: str) -> str:
    for provider_name, config in models_config.items():
        provider = config.get("provider", None)
        if provider is None:
            raise KeyError(
                f"No 'provider' key in config file for {provider_name}."
            )
        if provider.get("url", None) is None:
            raise KeyError(
                f"No 'url' key in provider config for {provider_name}."
            )
        if provider.get("url") == url:
            return provider_name
    raise ValueError(
        f"Provider with URL '{url}' not found in the configuration."
    )


def get_api_keys(provider_config: ProviderConfig) -> list[APIKey]:
    key_name: str = provider_config.api_key_env_var
    api_keys_env = os.getenv(key_name)
    if not api_keys_env:
        raise ValueError(
            f"The {key_name} environment variable is not set."
            " Please ensure it is defined in the .env file."
        )
    keys: list = [
        APIKey(key.strip()) for key in api_keys_env.split(",") if key.strip()
    ]
    if not keys:
        raise ValueError(
            f"The {key_name} environment variable is empty."
            " Please provide at least one valid API key."
        )
    return keys
