from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    content_from_reasoning: bool = False


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


class TokenRateLimitConfig(BaseModel):
    """Response headers giving a key's token budget per window.

    limit is the most tokens a window allows, remaining what is left
    after the request; both are read on every answer.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    limit: str
    remaining: str
    window_seconds: float = Field(default=60.0, gt=0)


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
    token_rate_limit: TokenRateLimitConfig | None = None


# ===== ModelConfig ======

LOOP_OWNED_BODY_KEYS = frozenset({"model", "messages", "stop", "max_tokens"})


class ModelConfig(BaseModel):
    """Per-model settings declared under "models" in configs/models.json.

    extra="forbid" turns a typo into a startup error instead of a
    silently ignored key. send_stop=False keeps the stop sequence out of
    the request, for a model whose provider also applies it to the
    reasoning: the client then cuts the content at the stop itself.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    extra_body: dict = Field(default_factory=dict)
    send_stop: bool = True

    @field_validator("extra_body")
    @classmethod
    def keep_loop_owned_keys(cls, value: dict) -> dict:
        """Refuse keys the loop computes itself, like max_tokens."""
        clash = sorted(LOOP_OWNED_BODY_KEYS & value.keys())
        if clash:
            raise ValueError(
                f"extra_body cannot set {clash}: the loop sets them"
            )
        return value


class FallbackTarget(BaseModel):
    """One fallback: a provider named as in configs/models.json, a model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str
    model: str


class FallbackConfig(BaseModel):
    """Ordered fallbacks per benchmark, from configs/fallback.json.

    Keys are the BenchName values. extra="forbid" turns a misspelled
    benchmark into a startup error.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mbpp: list[FallbackTarget] = Field(default_factory=list)
    swebench: list[FallbackTarget] = Field(default_factory=list)
