import json
import time

import httpx
from pydantic import ValidationError

from core import errors
from core.api_key import APIKey
from core.llm.response import LLMResponse


class LLMClient:
    def __init__(
        self,
        url: str,
        endpoint: str,
        model_name: str,
        api_keys: list[APIKey],
        stop_sequence: list[str] | None = None,
    ) -> None:
        if not isinstance(api_keys, list) or not all(
            isinstance(key, APIKey) for key in api_keys
        ):
            raise ValueError(
                "api_keys must be a list of APIKey."
                "Please provide a list of API keys."
            )
        self.url = url + endpoint
        self.model_name = model_name
        self.api_keys: list[APIKey] = api_keys
        self.stop_sequence = stop_sequence
        self.index_api_key: int = 0

    def make_request(
        self,
        timeout_max: float,
        messages: list,
        max_tokens: int,
    ) -> LLMResponse:
        start_time = time.time()
        if not self.api_keys:
            raise errors.PermanentLLMResponseError(
                "No API key provided for LLM client.",
                status_code=None,
            )
        try:
            request: httpx.Response = httpx.post(
                url=self.url,
                headers={
                    "Authorization":
                    f"Bearer {self.api_keys[self.index_api_key].get_key()}"
                },
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "stop": self.stop_sequence,
                    "max_tokens": max_tokens,
                },
                timeout=timeout_max,
            )
            request_time_ms: float = round(
                (time.time() - start_time) * 1000, 2
            )
            request.raise_for_status()
            data: dict = request.json()
            if data.get("error"):
                self.check_status_error(
                    status_code=data.get("error").get("code", "Unknown error")
                )
            if not data.get("choices"):
                raise errors.PermanentLLMResponseError(
                    "The LLM response does not contain the expected"
                    + " 'choices' field.",
                    status_code=request.status_code,
                )
        except json.JSONDecodeError:
            raise errors.TransientLLMResponseError(
                "The LLM response is not a valid JSON.",
                status_code=request.status_code,
            )
        except httpx.TimeoutException:
            raise errors.TransientLLMResponseError(
                "The request to the LLM provider timed out.",
            )
        except httpx.RequestError as e:
            raise errors.TransientLLMResponseError(
                "An error occurred while making the request to"
                f" the LLM provider: {e}",
                status_code=None,
            )
        except httpx.HTTPStatusError as e:
            self.check_status_error(
                status_code=e.response.status_code,
                retry_after=e.response.headers.get("Retry-After"),
                error=e,
            )
        except KeyboardInterrupt:
            raise KeyboardInterrupt(
                "The operation was interrupted by the user."
            )
        message: dict = data.get("choices")[0].get("message")
        if message is None:
            raise errors.PermanentLLMResponseError(
                "The LLM response does not contain the expected"
                + " 'message' field.",
                status_code=request.status_code,
            )
        if (
            message.get("content") is None
            or message.get("content").strip() == ""
        ):
            raise errors.TransientLLMResponseError(
                "The LLM response does not contain the expected"
                + " 'content' field.",
                status_code=request.status_code,
            )
        if not data.get("usage"):
            raise errors.PermanentLLMResponseError(
                "The LLM response does not contain the expected"
                + " 'usage' field.",
                status_code=request.status_code,
            )
        try:
            return LLMResponse(
                content=message.get("content", ""),
                reasoning=message.get("reasoning"),
                input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                output_tokens=data.get("usage", {}).get(
                    "completion_tokens", 0
                ),
                model_name=data.get("model", self.model_name),
                finish_reason=data.get("choices")[0].get("finish_reason", ""),
                request_time_ms=request_time_ms,
            )
        except ValidationError as e:
            raise errors.PermanentLLMResponseError(
                "The LLM response does not match the expected"
                + f" schema: {e}",
                status_code=request.status_code,
            )

    def check_status_error(
        self,
        status_code: int,
        retry_after: float | None = None,
        error: Exception | None = None,
    ) -> None:
        if status_code in errors.ERRORS_TRANSIENT:
            if status_code == 429:
                last_api_key = self.api_keys[self.index_api_key]
                self.get_next_api_key(status_code=status_code)
                if last_api_key != self.api_keys[self.index_api_key]:
                    retry_after = 0
            if isinstance(retry_after, str) and retry_after.isdigit():
                retry_after = float(retry_after)
            else:
                retry_after = None
            raise errors.TransientLLMResponseError(
                f"Transient error from LLM provider: {error}",
                status_code=status_code,
                retry_after=retry_after,
            )
        elif status_code in errors.ERRORS_PERMANENT:
            raise errors.PermanentLLMResponseError(
                f"Permanent error from LLM provider: {error}",
                status_code=status_code,
            )
        elif status_code == 402:
            if self.get_next_api_key(status_code=status_code) is None:
                raise errors.PermanentLLMResponseError(
                    "Payment required error from LLM provider. "
                    "No more API keys available.",
                    status_code=status_code,
                )
            raise errors.TransientLLMResponseError(
                "Payment required error from LLM provider. "
                "Please check your API key and account status.",
                status_code=status_code,
            )
        else:
            raise errors.PermanentLLMResponseError(
                f"Unexpected error from LLM provider: {error}",
                status_code=status_code,
            )

    def get_next_api_key(
        self,
        status_code: int | None = None,
    ) -> str | None:
        if not self.api_keys:
            return None
        if all(not key.get_usable() for key in self.api_keys):
            return None
        if status_code == 402:
            self.api_keys[self.index_api_key].set_usable(False)
        self.index_api_key = (self.index_api_key + 1) % len(self.api_keys)
        while not self.api_keys[self.index_api_key].get_usable():
            self.index_api_key = (self.index_api_key + 1) % len(self.api_keys)
            if self.index_api_key == 0:
                if all(not key.get_usable() for key in self.api_keys):
                    return None
        return self.api_keys[self.index_api_key]
