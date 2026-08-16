from pydantic import BaseModel, ConfigDict


class LLMResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    content: str
    reasoning: str | None = None
    input_tokens: int
    output_tokens: int
    model_name: str
    finish_reason: str
    request_time_ms: float
