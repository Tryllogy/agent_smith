from core import errors
from core.llm.response import LLMResponse
import httpx
import json
import time


class LLMClient:
    def __init__(
        self,
        url: str,
        endpoint: str,
        model_name: str,
        api_key: str,
        stop_sequence: list[str] | None = None,
    ) -> None:
        self.url = url + endpoint
        self.model_name = model_name
        self.api_key = api_key
        self.stop_sequence = stop_sequence

    def make_request(
        self,
        timeout_max: float,
        messages: list
    ) -> LLMResponse:
        start_time = time.time()
        try:
            request: httpx.Response = httpx.post(
                url=self.url,
                headers={"Authorization":
                         f"Bearer {self.api_key}"},
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "stop": self.stop_sequence,
                },
                timeout=timeout_max
            )
            request_time_ms: float = round(
                (time.time() - start_time) * 1000, 2)
            request.raise_for_status()
            data: dict = request.json()
            if data.get("error"):
                self.check_status_error(
                    status_code=data.get("error").get("code", "Unknown error")
                )
            if not data.get("choices"):
                raise errors.PermanentLLMResponseError(
                    "The LLM response does not contain the expected" +
                    " 'choices' field.",
                    status_code=request.status_code
                )
        except json.JSONDecodeError:
            raise errors.TransientLLMResponseError(
                "The LLM response is not a valid JSON.",
                status_code=request.status_code
            )
        except httpx.TimeoutException:
            raise errors.TransientLLMResponseError(
                "The request to the LLM provider timed out.",
            )
        except httpx.RequestError as e:
            raise errors.TransientLLMResponseError(
                "An error occurred while making the request to"
                f" the LLM provider: {e}",
                status_code=None
            )
        except httpx.HTTPStatusError as e:
            self.check_status_error(
                status_code=e.response.status_code,
                retry_after=e.response.headers.get("Retry-After"),
                error=e,
            )
        except KeyboardInterrupt:
            raise KeyboardInterrupt("The operation was interrupted by "
                                    "the user.")
        message: dict = data.get("choices")[0].get("message")
        if message is None:
            raise errors.PermanentLLMResponseError(
                "The LLM response does not contain the expected" +
                " 'message' field.",
                status_code=request.status_code
            )
        if message.get("content") is None or message.get("content").strip() == "":
            raise errors.TransientLLMResponseError(
                "The LLM response does not contain the expected" +
                " 'content' field.",
                status_code=request.status_code
            )
        if not data.get("usage"):
            raise errors.PermanentLLMResponseError(
                "The LLM response does not contain the expected" +
                " 'usage' field.",
                status_code=request.status_code
            )
        return LLMResponse(
            content=message.get("content", ""),
            input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
            output_tokens=data.get("usage", {}).get("completion_tokens", 0),
            model_name=data.get("model", self.model_name),
            finish_reason=data.get("choices")[0].get("finish_reason", ""),
            request_time_ms=request_time_ms
        )

    @staticmethod
    def check_status_error(
        status_code: int,
        retry_after: float | None = None,
        error: Exception | None = None
    ) -> None:
        if status_code in errors.ERRORS_TRANSIENT:
            if isinstance(retry_after, str) and retry_after.isdigit():
                retry_after = float(retry_after)
            else:
                retry_after = None
            raise errors.TransientLLMResponseError(
                f"Transient error from LLM provider: {error}",
                status_code=status_code,
                retry_after=retry_after
            )
        elif status_code in errors.ERRORS_PERMANENT:
            raise errors.PermanentLLMResponseError(
                f"Permanent error from LLM provider: {error}",
                status_code=status_code
            )
        else:
            raise errors.PermanentLLMResponseError(
                f"Unexpected error from LLM provider: {error}",
                status_code=status_code
            )
