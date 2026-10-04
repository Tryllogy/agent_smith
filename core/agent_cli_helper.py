import json
import os
import shlex
import sys
import time

from pydantic import ValidationError

from core import constants
from core.api_key import APIKey
from core.config_models import FallbackConfig, ModelConfig, ProviderConfig
from core.llm.client import LLMClient
from core.llm.provider import Provider
from core.models import MBPPTaskInput, SolutionOutput, SWEBenchTaskInput
from sandbox.mcp_client.client import MCPClient, MCPError


def check_args(args):
    """Raise ValueError if --model-name is missing or blank."""
    if not args.model_name or args.model_name.strip() == "":
        raise ValueError("Model name is required.")


def get_provider_and_model_config(
    model_name: str, provider_url: str
) -> tuple[ProviderConfig, ModelConfig]:
    """Return the provider matching provider_url and the model's entry.

    Only the models declared under the provider are accepted: the file
    lists the free ones, so an absent model, possibly a paid one, is
    refused before any request. Raises FileNotFoundError, ValueError or
    RuntimeError on a bad config.
    """
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
            model_config = ModelConfig.model_validate(
                get_declared_model(provider_config, provider_name, model_name)
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


def get_declared_model(
    provider_entry: dict, provider_name: str, model_name: str
) -> dict:
    """Return the entry of model_name under the provider.

    Raises ValueError if the model is not declared there.
    """
    models = provider_entry.get("models", {})
    if not isinstance(models, dict) or model_name not in models:
        raise ValueError(
            f"Model '{model_name}' is not declared under '{provider_name}'"
            f" in '{constants.MODELS_CONFIG_FILE}': only the models declared"
            " there, all free, are accepted."
        )
    return models[model_name]


def find_provider_by_url(models_config: dict, url: str) -> str:
    """Return the name of the provider whose url is exactly url.

    Raises KeyError on a malformed entry, ValueError if none matches.
    """
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
    """Read the comma-separated API keys from the provider's env var.

    Raises ValueError if the variable is unset or holds no key.
    """
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


def make_llm_client(
    provider_config: ProviderConfig,
    model_config: ModelConfig,
    model_name: str,
    api_keys: list[APIKey],
) -> LLMClient:
    """Build the client of model_name at the provider, with api_keys."""
    return LLMClient(
        url=provider_config.url,
        endpoint=provider_config.endpoint,
        model_name=model_name,
        api_keys=api_keys,
        stop_sequence=constants.LLM_STOP_SEQUENCE,
        provider=Provider(provider_config),
        model_config=model_config,
    )


def read_config_file(path: str) -> dict:
    """Return the JSON object stored at path.

    Raises FileNotFoundError, or ValueError if it is not a JSON object.
    """
    try:
        with open(path) as f:
            config = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"The configuration file '{path}' was not found."
        ) from None
    except json.JSONDecodeError:
        raise ValueError(
            f"The configuration file '{path}' is not a valid JSON file."
        ) from None
    if not isinstance(config, dict):
        raise ValueError(f"The configuration file '{path}' is not an object.")
    return config


def get_fallback_clients(
    bench: constants.Bench, model_name: str, provider_url: str
) -> list[LLMClient]:
    """Build, in order, the fallback clients declared for bench.

    Read from FALLBACK_CONFIG_FILE, an absent file meaning no fallback.
    The requested model is skipped, and so is a fallback whose provider
    has no key in the environment: the .env decides which fallbacks
    exist. A malformed file, an unknown provider or a model not
    declared in models.json raises ValueError.
    """
    if not os.path.exists(constants.FALLBACK_CONFIG_FILE):
        return []
    try:
        fallbacks = FallbackConfig.model_validate(
            read_config_file(constants.FALLBACK_CONFIG_FILE)
        )
    except ValidationError as e:
        raise ValueError(f"Error in fallback configuration: {e}") from e
    models_config: dict = read_config_file(constants.MODELS_CONFIG_FILE)
    clients: list[LLMClient] = []
    for target in getattr(fallbacks, bench.name):
        entry = models_config.get(target.provider)
        if not isinstance(entry, dict):
            raise ValueError(
                f"Fallback provider '{target.provider}' is not declared in"
                f" '{constants.MODELS_CONFIG_FILE}'."
            )
        provider_config = ProviderConfig.model_validate(
            entry.get("provider", {})
        )
        model_config = ModelConfig.model_validate(
            get_declared_model(entry, target.provider, target.model)
        )
        if provider_config.url == provider_url and target.model == model_name:
            continue
        try:
            api_keys: list[APIKey] = get_api_keys(provider_config)
        except ValueError:
            continue
        clients.append(
            make_llm_client(
                provider_config, model_config, target.model, api_keys
            )
        )
    return clients


def get_task_from_file(
    file_path: str, bench_input: MBPPTaskInput | SWEBenchTaskInput
) -> dict:
    """Load the task file, validate it against bench_input, return it.

    The task is returned as the raw dict, not as the model.
    """
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


def connect_mcp_server(
    script: str, args: list[str], call_timeout: float
) -> MCPClient:
    """Start the MCP server script with args, return the connected client.

    The server runs on the agent's own interpreter, over stdio, and
    call_timeout bounds each request to it. Raises RuntimeError if the
    server does not start or fails the handshake.
    """
    command: str = shlex.join(["python", script, *args])
    try:
        return MCPClient.from_command(
            command, call_timeout=call_timeout
        ).connect()
    except (MCPError, ValueError) as e:
        raise RuntimeError(f"MCP server '{script}' unavailable: {e}") from e


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
