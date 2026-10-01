import json
import os
import sys
import time

from pydantic import ValidationError

from core import constants
from core.api_key import APIKey
from core.config_models import ProviderConfig
from core.models import MBPPTaskInput, SolutionOutput, SWEBenchTaskInput


def check_args(args):
    if not args.model_name or args.model_name.strip() == "":
        raise ValueError("Model name is required.")


def get_provider_and_model_config(
    model_name: str, provider_url: str
) -> tuple[ProviderConfig, dict]:
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
            return provider, model_config
    except FileNotFoundError:
        raise FileNotFoundError(
            f"The models configuration file '{constants.MODELS_CONFIG_FILE}'"
            " was not found."
        ) from None
    except json.JSONDecodeError:
        raise ValueError(
            f"The models configuration file '{constants.MODELS_CONFIG_FILE}'"
            " is not a valid JSON file."
        ) from None
    except (ValueError, KeyError) as e:
        raise ValueError(f"Error in models configuration: {e}") from e
    except Exception as e:
        raise RuntimeError(
            "An unexpected error occurred while"
            f" reading the models configuration: {e}"
        ) from e


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


def get_task_from_file(
    file_path: str, bench_input: MBPPTaskInput | SWEBenchTaskInput
) -> dict:
    try:
        with open(file_path) as file:
            task: dict = json.load(file)
            bench_input.model_validate(task)
            return task
    except json.JSONDecodeError:
        raise ValueError(
            f"The task file '{file_path}' is not a valid "
            f"JSON file. Please check the file content."
        ) from None
    except FileNotFoundError:
        raise FileNotFoundError(
            f"The task file '{file_path}' was not "
            f"found. Please ensure the path is "
            f"correct."
        ) from None
    except ValidationError as e:
        raise ValueError(
            f"Invalid task format in file '{file_path}': {e}"
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"An error occurred while reading the task file: {e}"
        ) from e


def read_task_id(file_path: str, key: str) -> str:
    """Best-effort task id for a failure report, "" if unreadable."""
    try:
        with open(file_path) as file:
            task = json.load(file)
    except (OSError, ValueError):
        return ""
    return str(task.get(key, "")) if isinstance(task, dict) else ""


def write_failure_output(
    output_file: str,
    bench: constants.Bench,
    task_id: str,
    error: str,
    start_time: float,
) -> None:
    """Write a valid solution.json for a run that failed before its loop."""
    solution = SolutionOutput(
        task_id=task_id,
        benchmark=bench.name,
        success=False,
        solution="",
        iterations=0,
        total_requests=0,
        total_input_tokens=0,
        total_output_tokens=0,
        total_time_seconds=round(time.time() - start_time, 2),
        error=error,
    )
    try:
        with open(output_file, "w") as f:
            f.write(solution.model_dump_json(indent=4))
    except OSError as e:
        sys.stderr.write(f"Error: could not write '{output_file}': {e}\n")
