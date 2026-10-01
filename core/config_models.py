from enum import Enum

from pydantic import BaseModel, ConfigDict

# ===== LLMResponse ======


class LLMResponse(BaseModel):
    """LLM answer normalized from any provider's response format."""

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
    """How a rate-limit header encodes its delay."""

    EPOCH = "epoch"
    DATE = "date"
    DURATION = "duration"


class NamesRetryAfterConfig(BaseModel):
    """Formats of one rate-limit header, and the divisor to seconds."""

    model_config = ConfigDict(frozen=True)

    scale: int
    format: list[NameRetryAfterEnum]


class RetryAfterConfig(BaseModel):
    """Rate-limit headers to read, by header name."""

    model_config = ConfigDict(frozen=True)

    names: dict[str, NamesRetryAfterConfig]


class ProviderConfig(BaseModel):
    """How to talk to a provider, as declared in configs/models.json.

    url, endpoint, header and api_key_env_var shape the request; the
    other string fields name the keys to read in the response.
    """

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
