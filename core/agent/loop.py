import httpx
from dotenv import load_dotenv
import os
from core.agent.prompt import Prompt
from core import constants
from core.models import SolutionOutput


if not load_dotenv():
    raise FileNotFoundError("The .env file was not found."
                            "Please ensure it exists in the project root.")


class Loop:
    def __init__(
        self,
        model_name: str,
        provider_url: str,
        prompt: Prompt = None
    ) -> None:
        self.thoughts: list = []
        self.codes: list = []
        self.observations: list = []
        self.usage_input: int = 0
        self.usage_output: int = 0
        self.endpoint: str = constants.LLM_ENDPOINT
        self.provider_url: str = provider_url
        self.model_name: str = model_name
        self.prompt: Prompt = prompt if prompt is not None else Prompt("")

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
        data: dict = self.llm_response.json()
        text: str = data.get("choices", [{}])[0].get(
            "message", {}).get("content", "")
        usage = data.get("usage", 0)
        self.usage_input += usage.get("prompt_tokens", 0)
        self.usage_output += usage.get("completion_tokens", 0)
        self.thoughts.append(text)
        message = {"role": "assistant", "content": text}
        self.prompt.add_message(message)

    def extract(self):
        return

    def observation(self):
        return

    def run(
        self,
        limit_iter: int,
        max_tokens: int,
    ):
        # while True:
        #     self.thought()
        #     self.extract()
        #     self.observation()
        pass
        solution: dict = {}
        SolutionOutput()
