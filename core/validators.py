from enum import Enum

from pydantic import BaseModel, ConfigDict, RootModel

# ===== LLMResponse ======


class LLMResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    content: str
    reasoning: str | None = None
    input_tokens: int
    output_tokens: int
    model_name: str
    finish_reason: str
    request_time_ms: float


# ===== ProviderConfig ======


class NameRetryAfterEnum(str, Enum):
    EPOCH = "epoch"
    DATE = "date"
    DURATION = "duration"


class NamesRetryAfterConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    scale: int
    format: list[NameRetryAfterEnum]


class RetryAfterConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    names: dict[str, NamesRetryAfterConfig]


class ProviderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    endpoint: str
    header: dict
    api_key_env_var: str
    reasoning: str
    choice: str
    usage: str
    model: str
    error: str
    content: str
    input_tokens: str
    output_tokens: str
    finish_reason: str
    message: str
    retry_after: RetryAfterConfig


# ===== ModelConfig ======


class ModelConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    reasoning: bool


class RootModelConfig(RootModel[dict[str, ModelConfig]]):
    model_config = ConfigDict(frozen=True)

    def __getitem__(self, key: str) -> ModelConfig:
        return self.root[key]
