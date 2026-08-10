import httpx
from dotenv import load_dotenv
import os
from .. import constants

if not load_dotenv():
    raise FileNotFoundError("The .env file was not found."
                            "Please ensure it exists in the project root.")


class Loop:
    def __init__(
        self,
        model_name: str,
        provider_url: str
    ) -> None:
        self.thoughts: list = []
        self.codes: list = []
        self.observations: list = []
        self.usage_input: int = 0
        self.usage_output: int = 0
        self.endpoint: str = constants.LLM_ENDPOINT
        self.provider_url: str = provider_url
        self.model_name: str = model_name
        self.messages: list = [
            {"role": "system", "content": "You are a helpful assistant that "
             "must generate or debug code."},
        ]

    def thought(self):
        try:
            message: list = self.messages + [{"role": "user", "content":
                                              "Please provide your "
                                              "next thought."}]
            self.llm_response: httpx.Response = httpx.post(
                url=self.provider_url + self.endpoint,
                headers={"Authorization":
                         f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
                json={
                    "model": self.model_name,
                    "messages": message,
                    "stop": ["<end_code>"]
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

    def code(self):
        return

    def observation(self):
        return

    def run(self):
        while True:
            self.thought()
            self.code()
            self.observation()
