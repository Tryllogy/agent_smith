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
        self.step_metrics: list = []
        self.solution: str = ""
        self.success: bool = False

    def thought(
        self,
        timeout_max: float
    ):
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
                timeout=timeout_max
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

    def extract(self, text: str):
        self.code: dict = extract_code_from_text(text)
        return self.code["found"] and self.code["error"] == "None"

    def observation(self):
        if not self.code["found"]:
            self.prompt.add_message({"role": "user",
                                     "content": self.code["error"]})
            return False
        # UTILISER LA SANDBOX DE L'AUTRE RANDOM DE PLOMB MAIS JE L'AI PAS
        # POUR LE MOMENT DONC JE PEUX PAS BOSSER
        # If sandbox == bien executed:
        #   If assert == True:
        #       self.solution = self.code["code"]
        #       self.success = True
        #       return True
        #   else:
        #       self.prompt.add_message({"role": "user",
        #                              "content": "Assertion failed"})
        #       return False
        # else:
        #   self.prompt.add_message({"role": "user",
        #                          "content": self.code["error"]})
        # return False

    def run(
        self,
        task_id: str,
    ) -> SolutionOutput:
        self.start_time: float = time.time()
        self.iteration: int = 0
        self.task_id: str = task_id
        while self.iteration < self.iteration_limit:
            try:
                self.thought(min(constants.LLM_TIMEOUT_SECONDS,
                                 (time.time() - self.start_time)))
            except RuntimeError:
                return self.make_solution_output(
                    error="Error from LLM provider"
                )
            except Exception:
                continue
            if time.time() - self.start_time > self.timeout_limit:
                return self.make_solution_output(
                    error="Timeout limit exceeded"
                )
            if self.usage_input > self.max_tokens_input:
                return self.make_solution_output(
                    error="Input token limit exceeded"
                )
            if self.usage_output > self.max_tokens_output:
                return self.make_solution_output(
                    error="Output token limit exceeded"
                )
            self.extract(self.thoughts[-1])
            if self.observation():
                self.iteration += 1
                break
            self.iteration += 1
        return self.make_solution_output(
        )

    def make_solution_output(
        self,
        error: str | None = None
    ) -> SolutionOutput:
        if self.name_bench == "mbpp":
            self.task_id = str(self.task_id)

        n_retries: int = 0
        solution: dict = {
            "task_id": self.task_id,
            "benchmark": self.name_bench,
            "success": self.success,
            "solution": self.solution,
            "iterations": self.iteration,
            "total_requests": self.iteration + n_retries,
            "total_input_tokens": self.usage_input,
            "total_output_tokens": self.usage_output,
            "total_time_seconds": round(time.time() - self.start_time, 2),
            "steps": self.step_metrics,
            "system_prompt": "\n".join([msg["content"]
                                        for msg in self.prompt.prompt
                                        if msg["role"] == "system"]),
            "error": error,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
        }
        return SolutionOutput.model_validate(solution)
