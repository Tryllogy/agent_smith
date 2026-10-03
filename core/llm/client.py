import json
import math
import re
import threading
import time

import httpx
from pydantic import ValidationError

from core import constants, errors
from core.api_key import APIKey
from core.config_models import (
    LLMResponse,
    ModelConfig,
)
from core.llm.provider import Provider


class LLMClient:
    """Chat completion client with API key rotation.

    The only module that makes HTTP calls. Every failure is raised
    as a TransientLLMResponseError or a PermanentLLMResponseError.
    """

    def __init__(
        self,
        url: str,
        endpoint: str,
        model_name: str,
        provider: Provider,
        model_config: ModelConfig | dict,
        api_keys: list[APIKey],
        stop_sequence: list[str] | None = None,
    ) -> None:
        """Target model_name at url + endpoint, with the given keys.

        model_config may be a ModelConfig or its dict form. Raises
        ValueError unless api_keys is a list of APIKey.
        """
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
        self.model_config: ModelConfig = ModelConfig.model_validate(
            model_config
        )
        self.last_api_key_index: int = 0

    def get_reponses(
        self,
        thread_result: dict,
        timeout_max: float,
        messages: list,
        max_tokens: int,
    ) -> None:
        """Thread target: POST the request into thread_result.

        Stores the response under 'request' or the exception under
        'error'.
        """
        try:
            header = self.replace_header_api_key(self.provider.config.header)
            request: httpx.Response = httpx.post(
                url=self.url,
                headers={**header},
                json={
                    **self.model_config.extra_body,
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
        """Run the request in a daemon thread bounded by timeout_max.

        httpx timeouts apply per I/O phase, the join bounds the total.
        Returns the response and its duration in milliseconds.
        """
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
        """Send messages to the LLM and return the parsed LLMResponse.

        Raises TransientLLMResponseError or PermanentLLMResponseError.
        """
        if not self.api_keys:
            raise errors.PermanentLLMResponseError(
                "No API key provided for LLM client.",
                status_code=None,
            )
        self.check_token_rate(messages=messages, max_tokens=max_tokens)
        try:
            request, request_time_ms = self.make_request(
                timeout_max=timeout_max,
                messages=messages,
                max_tokens=max_tokens,
            )
            self.record_token_rate(request.headers)
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
        consumed: dict = self.consumed_tokens(data)
        message: dict = self.provider.get_message(data)
        if message is None:
            raise errors.PermanentLLMResponseError(
                "The LLM response does not contain the expected"
                + " 'message' field.",
                status_code=request.status_code,
                **consumed,
            )
        content: str = self.provider.get_content(data)
        reasoning = self.provider.get_reasoning(data)
        content_from_reasoning: bool = False
        if content is None or content.strip() == "":
            if not self.reasoning_holds_code(reasoning):
                raise errors.TransientLLMResponseError(
                    "The LLM response does not contain the expected"
                    + " 'content' field, nor a code block in its"
                    + " reasoning.",
                    status_code=request.status_code,
                    **consumed,
                )
            content, reasoning = reasoning, None
            content_from_reasoning = True
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
                reasoning=reasoning,
                input_tokens=self.provider.get_input_tokens(data),
                output_tokens=self.provider.get_output_tokens(data),
                model_name=model if model != "" else self.model_name,
                finish_reason=self.provider.get_finish_reason(data),
                request_time_ms=request_time_ms,
                content_from_reasoning=content_from_reasoning,
            )
        except ValidationError as e:
            raise errors.PermanentLLMResponseError(
                "The LLM response does not match the expected"
                + f" schema: {e}",
                status_code=request.status_code,
                **consumed,
            ) from e

    def consumed_tokens(self, data: dict) -> dict:
        """Return the tokens the provider billed for this response.

        Kept on the error when the response is rejected: the tokens were
        spent all the same. A count that is not an integer counts as 0.
        """
        input_tokens = self.provider.get_input_tokens(data)
        output_tokens = self.provider.get_output_tokens(data)
        return {
            "input_tokens": input_tokens
            if isinstance(input_tokens, int)
            else 0,
            "output_tokens": output_tokens
            if isinstance(output_tokens, int)
            else 0,
        }

    @staticmethod
    def reasoning_holds_code(reasoning) -> bool:
        """Return True if reasoning is text holding a complete code block.

        A reasoning model sometimes writes its whole answer in the
        reasoning and leaves content empty: the answer is then usable.
        Without a closed code block, the reasoning is only thinking.
        """
        return isinstance(reasoning, str) and bool(
            re.search(constants.CODE_BLOCK_PATTERN, reasoning, re.DOTALL)
        )

    @staticmethod
    def estimate_cost(messages: list, max_tokens: int) -> int:
        """Estimate a request's tokens from above: prompt plus max_tokens.

        The prompt is counted at ESTIMATED_CHARS_PER_TOKEN, below the
        ratios measured, and the answer at its maximum.
        """
        chars: int = sum(len(str(m.get("content", ""))) for m in messages)
        return (
            math.ceil(chars / constants.ESTIMATED_CHARS_PER_TOKEN) + max_tokens
        )

    def check_token_rate(self, messages: list, max_tokens: int) -> None:
        """Hold back a request the provider's token rate would refuse.

        Uses the limit and the tokens left that each key's last answer
        reported, while its window runs. The key in use is kept if it
        has enough, else the next usable key that has enough is taken.
        Raises PermanentLLMResponseError if the request exceeds the
        limit itself, TransientLLMResponseError with the shortest wait
        if no key has enough left.
        """
        config = self.provider.config.token_rate_limit
        if config is None:
            return
        cost: int = self.estimate_cost(messages, max_tokens)
        waits: list[float] = []
        for offset in range(len(self.api_keys)):
            index: int = (self.index_api_key + offset) % len(self.api_keys)
            key: APIKey = self.api_keys[index]
            if not key.get_usable():
                continue
            budget = key.get_token_budget()
            if budget is None:
                self.index_api_key = index
                return
            limit, remaining, observed_at = budget
            if cost > limit:
                raise errors.PermanentLLMResponseError(
                    f"This request (~{cost} tokens) exceeds the provider's"
                    f" limit of {limit} tokens per"
                    f" {config.window_seconds:g}s window.",
                    status_code=None,
                )
            elapsed: float = time.time() - observed_at
            if elapsed >= config.window_seconds or cost <= remaining:
                self.index_api_key = index
                return
            waits.append(config.window_seconds - elapsed)
        if not waits:
            return
        raise errors.TransientLLMResponseError(
            f"Token rate limit: this request needs ~{cost} tokens, more"
            " than any key has left in its"
            f" {config.window_seconds:g}s window.",
            status_code=None,
            retry_after=min(waits),
        )

    def record_token_rate(self, headers: httpx.Headers) -> None:
        """Store on the key in use the token budget its answer reported."""
        token_rate = self.provider.get_token_rate(headers)
        if token_rate is not None:
            self.api_keys[self.index_api_key].set_token_budget(*token_rate)

    def check_error(
        self,
        error: Exception,
        timeout_max: float,
    ) -> Exception | None:
        """Raise the typed LLM error matching a request exception.

        Returns the exception unchanged if it is not a request error.
        """
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
        """Raise the typed LLM error matching an HTTP status code.

        429 rotates to the next key and 402 retires the current one.
        Permanent when no usable key is left or the wait exceeds
        timeout_max.
        """
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
        """Move to the next usable key and return it, or None if none.

        Records retry_after on the current key and retires it on 402.
        A key whose wait exceeds timeout_max is retired and skipped.
        """
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
        """Return a copy of headers with {api_key} set to the current key."""
        header = headers.copy()
        for key, value in header.items():
            if "{api_key}" in value:
                header[key] = value.replace(
                    "{api_key}", self.api_keys[self.index_api_key].get_key()
                )
        return header
