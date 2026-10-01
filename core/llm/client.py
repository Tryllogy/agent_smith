import json
import threading
import time

import httpx
from pydantic import ValidationError

from core import errors
from core.api_key import APIKey
from core.config_models import (
    LLMResponse,
)
from core.llm.provider import Provider


class LLMClient:
    def __init__(
        self,
        url: str,
        endpoint: str,
        model_name: str,
        provider: Provider,
        model_config: dict,
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
        self.provider = provider
        self.model_config: dict = model_config
        self.last_api_key_index: int = 0

    def get_reponses(
        self,
        thread_result: dict,
        timeout_max: float,
        messages: list,
        max_tokens: int,
    ) -> None:
        try:
            header = self.replace_header_api_key(self.provider.config.header)
            request: httpx.Response = httpx.post(
                url=self.url,
                headers={**header},
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "stop": self.stop_sequence,
                    "max_tokens": max_tokens,
                },
                timeout=timeout_max,
            )
            request.raise_for_status()
        except Exception as e:
            thread_result["error"] = e
            return
        thread_result["request"] = request

    def make_request(
        self,
        timeout_max: float,
        messages: list,
        max_tokens: int,
    ) -> tuple[dict, float]:
        start_time = time.time()
        thread_result: dict = {
            "error": None,
            "request": None,
        }
        thread = threading.Thread(
            target=self.get_reponses,
            args=(thread_result, timeout_max, messages, max_tokens),
            daemon=True,
        )
        thread.start()
        thread.join(timeout=timeout_max)
        if thread_result.get("error"):
            raise thread_result.get("error")
        if thread_result.get("request") is None:
            raise errors.TransientLLMResponseError(
                "The request to the LLM provider timed out.",
            )
        request_time_ms: float = round((time.time() - start_time) * 1000, 2)
        request = thread_result.get("request")
        return request, request_time_ms

    def get_llm_reponse(
        self,
        timeout_max: float,
        messages: list,
        max_tokens: int,
    ) -> LLMResponse:
        if not self.api_keys:
            raise errors.PermanentLLMResponseError(
                "No API key provided for LLM client.",
                status_code=None,
            )
        try:
            request, request_time_ms = self.make_request(
                timeout_max=timeout_max,
                messages=messages,
                max_tokens=max_tokens,
            )
            data: dict = request.json()
            if not isinstance(data, dict):
                raise errors.TransientLLMResponseError(
                    "The LLM response is not a valid JSON.",
                    status_code=request.status_code,
                )
            error_provider: dict = self.provider.get_error(data)
            if error_provider:
                self.check_status_error(
                    status_code=error_provider.get(
                        "code", request.status_code
                    ),
                    timeout_max=timeout_max,
                    retry_after=self.provider.get_retry_after(request.headers),
                    error=Exception(f"{error_provider.get('message')}"),
                )
        except Exception as e:
            error: Exception | None = self.check_error(
                error=e, timeout_max=timeout_max
            )
            if error:
                raise error from e
        message: dict = self.provider.get_message(data)
        if message is None:
            raise errors.PermanentLLMResponseError(
                "The LLM response does not contain the expected"
                + " 'message' field.",
                status_code=request.status_code,
            )
        content: str = self.provider.get_content(data)
        if content is None or content.strip() == "":
            raise errors.TransientLLMResponseError(
                "The LLM response does not contain the expected"
                + " 'content' field.",
                status_code=request.status_code,
            )
        if self.provider.get_usage(data) is None:
            raise errors.PermanentLLMResponseError(
                "The LLM response does not contain the expected"
                + " 'usage' field.",
                status_code=request.status_code,
            )
        try:
            model: str | None = self.provider.get_model(data)
            return LLMResponse(
                content=content,
                reasoning=self.provider.get_reasoning(data),
                input_tokens=self.provider.get_input_tokens(data),
                output_tokens=self.provider.get_output_tokens(data),
                model_name=model if model != "" else self.model_name,
                finish_reason=self.provider.get_finish_reason(data),
                request_time_ms=request_time_ms,
            )
        except ValidationError as e:
            raise errors.PermanentLLMResponseError(
                "The LLM response does not match the expected"
                + f" schema: {e}",
                status_code=request.status_code,
            ) from e

    def check_error(
        self,
        error: Exception,
        timeout_max: float,
    ) -> Exception | None:
        match error:
            case json.JSONDecodeError():
                raise errors.TransientLLMResponseError(
                    "The LLM response is not a valid JSON.",
                    status_code=None,
                )
            case httpx.TimeoutException():
                raise errors.TransientLLMResponseError(
                    "The request to the LLM provider timed out.",
                )
            case httpx.RequestError():
                raise errors.TransientLLMResponseError(
                    "An error occurred while making the request to"
                    f" the LLM provider: {error}",
                    status_code=None,
                )
            case httpx.HTTPStatusError():
                retry_after: float | None = self.provider.get_retry_after(
                    error.response.headers
                )
                try:
                    reponse_error: dict = error.response.json()
                    if not isinstance(reponse_error, dict):
                        reponse_error = {}
                    provider_error: dict = self.provider.get_error(
                        reponse_error
                    )
                except json.JSONDecodeError:
                    provider_error = {}
                self.check_status_error(
                    status_code=error.response.status_code,
                    retry_after=retry_after,
                    error=provider_error.get("message", error),
                    timeout_max=timeout_max,
                )
            case _:
                return error

    def check_status_error(
        self,
        status_code: int,
        retry_after: float | None = None,
        error: Exception | str | None = None,
        timeout_max: float = 0.0,
    ) -> None:
        if retry_after is not None and retry_after < 0:
            retry_after = 0.0
        if status_code in errors.ERRORS_TRANSIENT:
            if status_code == 429:
                self.last_api_key_index = self.index_api_key
                api_key: str | None = self.get_next_api_key(
                    timeout_max=timeout_max,
                    status_code=status_code,
                    retry_after=retry_after,
                )
                if self.last_api_key_index != self.index_api_key:
                    retry_after = None
                elif api_key is None:
                    raise errors.PermanentLLMResponseError(
                        "The LLM provider has rate limited the requests"
                        " and there are no more usable API keys.",
                        status_code=status_code,
                    )
            if retry_after is not None and retry_after > timeout_max:
                raise errors.PermanentLLMResponseError(
                    "The LLM provider has rate limited the requests"
                    " and the retry time exceeds the bench timeout.",
                    status_code=status_code,
                )
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
            if (
                self.get_next_api_key(
                    timeout_max=timeout_max, status_code=status_code
                )
                is None
            ):
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
        timeout_max: float,
        status_code: int | None = None,
        retry_after: float = 0.0,
    ) -> str | None:
        if (
            all(not key.get_usable() for key in self.api_keys)
            or not self.api_keys
        ):
            return None
        self.api_keys[self.index_api_key].set_retry_time(retry_after)
        if status_code == 402:
            self.api_keys[self.index_api_key].set_usable(False)
        self.index_api_key = (self.index_api_key + 1) % len(self.api_keys)
        while not self.api_keys[self.index_api_key].get_usable():
            self.index_api_key = (self.index_api_key + 1) % len(self.api_keys)
            if self.index_api_key == 0 and all(
                not key.get_usable() for key in self.api_keys
            ):
                return None
        next_retry_time = self.api_keys[self.index_api_key].get_retry_time()
        if next_retry_time > timeout_max:
            self.api_keys[self.index_api_key].set_usable(False)
            return self.get_next_api_key(
                timeout_max=timeout_max,
                status_code=status_code,
                retry_after=retry_after,
            )
        return self.api_keys[self.index_api_key]

    def replace_header_api_key(self, headers: dict) -> dict:
        header = headers.copy()
        for key, value in header.items():
            if "{api_key}" in value:
                header[key] = value.replace(
                    "{api_key}", self.api_keys[self.index_api_key].get_key()
                )
        return header
