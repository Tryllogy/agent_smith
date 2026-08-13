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
                raise RuntimeError(f"Error from LLM provider: {data['error']}")
            if not data.get("choices"):
                raise ValueError("The LLM response does not contain"
                                 " the expected 'choices' field")
        except json.JSONDecodeError:
            raise ValueError("Failed to decode JSON response from the LLM "
                             "provider. Please check the provider's response.")
        except httpx.TimeoutException:
            raise TimeoutError("The request to the LLM provider timed out. "
                               "Please try again later.")
        except httpx.RequestError as e:
            raise ConnectionError(f"An error occurred while requesting the LLM"
                                  f" provider: {e}")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Received an error response from the LLM "
                               f"provider: {e.response.status_code} - "
                               f"{e.response.text}")
        except KeyboardInterrupt:
            raise KeyboardInterrupt("The operation was interrupted by "
                                    "the user.")
        return LLMResponse(
            content=data.get("choices")[0].get(
                "message", {}).get("content", ""),
            input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
            output_tokens=data.get("usage", {}).get("completion_tokens", 0),
            model_name=data.get("model", self.model_name),
            finish_reason=data.get("choices")[0].get("finish_reason", ""),
            request_time_ms=request_time_ms
        )
