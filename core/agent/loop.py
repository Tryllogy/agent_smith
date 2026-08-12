from core import constants
from core.models import SolutionOutput
from core.agent.prompt import Prompt
from core.agent.extraction import extract_code_from_text
from dotenv import load_dotenv
import time
import os
import json
import httpx


if not load_dotenv():
    raise FileNotFoundError("The .env file was not found."
                            " Please ensure it exists in the project root.")
if not os.getenv("OPENROUTER_API_KEY"):
    raise EnvironmentError("The OPENROUTER_API_KEY environment variable"
                           " is not set."
                           " Please ensure it is defined in the .env file.")


class Loop:
    def __init__(
        self,
        model_name: str,
        provider_url: str,
        prompt: Prompt,
        bench: constants.Bench
    ) -> None:
        self.thoughts: list = []
        self.codes: list = []
        self.observations: list = []
        self.usage_input: int = 0
        self.usage_output: int = 0
        self.endpoint: str = constants.LLM_ENDPOINT
        self.provider_url: str = provider_url
        self.model_name: str = model_name
        self.prompt: Prompt = prompt
        self.name_bench: str = bench.name
        self.max_tokens_input: int = bench.input_max_token
        self.max_tokens_output: int = bench.output_max_token
        self.timeout_limit: int = bench.timeout
        self.iteration_limit: int = bench.iterations

    def thought(self):
        try:
            self.llm_response: httpx.Response = httpx.post(
                url=self.provider_url + self.endpoint,
                headers={"Authorization":
                         f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
                json={
                    "model": self.model_name,
                    "messages": self.prompt.prompt,
                    "stop": constants.LLM_STOP_SEQUENCE
                },
                timeout=constants.LLM_TIMEOUT_SECONDS
            )
            self.llm_response.raise_for_status()
            data: dict = self.llm_response.json()
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
        text: str = data.get("choices")[0].get(
            "message", {}).get("content", "")
        if text is None or text.strip() == "":
            raise ValueError("The LLM response does not contain the expected "
                             "'content' field.")
        usage = data.get("usage", {})
        if not usage:
            raise ValueError("The LLM response does not contain the expected "
                             "'usage' field.")
        self.usage_input += usage.get("prompt_tokens", 0)
        self.usage_output += usage.get("completion_tokens", 0)
        self.thoughts.append(text)
        message = {"role": "assistant", "content": text}
        self.prompt.add_message(message)
        print(text)

    def is_extracted(self, text: str):
        code: dict = extract_code_from_text(text)
        print("EXTRACTED CODE:", code)
        return True

    def observation(self):
        return

    def run(
        self,
    ):
        start_time: float = time.time()
        solution: dict = {}
        iteration: int = 0
        while iteration < self.iteration_limit:
            if start_time + self.timeout_limit < time.time():
                return SolutionOutput().model_validate({})
            if self.usage_input > self.max_tokens_input:
                return SolutionOutput().model_validate({})
            if self.usage_output > self.max_tokens_output:
                return SolutionOutput().model_validate({})
            self.thought()
            if self.is_extracted(self.thoughts[-1]):
                iteration += 1
                break
            self.observation()
            iteration += 1
        SolutionOutput().model_validate(solution)
