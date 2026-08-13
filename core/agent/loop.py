from core import errors
from core import constants
from core.models import SolutionOutput, StepMetrics
from core.agent.prompt import Prompt
from core.agent.extraction import extract_code_from_text
from sandbox.executor import execute
from core.llm.client import LLMClient
from core.llm.response import LLMResponse
import time


class Loop:
    def __init__(
        self,
        client: LLMClient,
        prompt: Prompt,
        bench: constants.Bench
    ) -> None:
        self.client: LLMClient = client
        self.thoughts: list = []
        self.observations: list = []
        self.usage_input: int = 0
        self.usage_output: int = 0
        self.prompt: Prompt = prompt
        self.name_bench: str = bench.name
        self.max_tokens_input: int = bench.input_max_token
        self.max_tokens_output: int = bench.output_max_token
        self.timeout_limit: int = bench.timeout
        self.iteration_limit: int = bench.iterations
        self.step_metrics: list[StepMetrics] = []
        self.solution: str = ""
        self.success: bool = False
        self.sandbox_input: str = ""
        self.sandbox_output: str = ""
        self.request_time_ms: float = 0.0
        self.last_usage_input: int = 0
        self.last_usage_output: int = 0

    def thought(
        self,
        timeout_max: float,
    ):
        llm_response: LLMResponse = self.client.make_request(
            timeout_max=timeout_max,
            messages=self.prompt.prompt
        )
        text: str = llm_response.content
        self.request_time_ms = llm_response.request_time_ms
        self.usage_input += llm_response.input_tokens
        self.usage_output += llm_response.output_tokens
        self.last_usage_input = llm_response.input_tokens
        self.last_usage_output = llm_response.output_tokens
        self.thoughts.append(text)
        message = {"role": "assistant", "content": text}
        self.prompt.add_message(message)

    def extract(
        self,
        text: str
    ) -> bool:
        self.code: dict = extract_code_from_text(text)
        return self.code["found"] and self.code["error"] == "None"

    def observation(
        self
    ) -> bool:
        if not self.code["found"]:
            self.prompt.add_message({"role": "user",
                                     "content": self.code["error"]})
            return False
        stdout, stderr, error, is_final, answer = execute(self.code["code"])
        self.sandbox_input: str = self.code["code"]
        self.sandbox_output: str = stdout + \
            stderr + error if error else stdout + stderr
        if error is None:
            if is_final:
                self.solution = answer
                self.success = True
                return True
            else:
                self.prompt.add_message({"role": "user",
                                        "content": stdout + stderr})
                return False
        self.prompt.add_message({"role": "user",
                                "content": self.code["error"]})
        return False

    def run(
        self,
        task_id: str,
    ) -> SolutionOutput:
        self.start_time: float = time.time()
        self.iteration: int = 0
        self.task_id: str = task_id
        self.retries: int = 0
        while self.iteration < self.iteration_limit:
            try:
                if time.time() - self.start_time > self.timeout_limit:
                    return self.make_solution_output(
                        error="Timeout limit exceeded"
                    )
                self.thought(
                    min(constants.LLM_TIMEOUT_SECONDS,
                        self.timeout_limit - (time.time() - self.start_time)))
            except errors.TransientLLMResponseError as e:
                self.retries += 1
                self.retry_after = e.retry_after if e.retry_after else 0.0
                time.sleep(self.retry_after)
                continue
            except errors.PermanentLLMResponseError as e:
                return self.make_solution_output(
                    error=f"Permanent LLM error: {str(e)}"
                )
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
                self.step_metrics.append(self.make_step_metrics())
                return self.make_solution_output()
            self.iteration += 1
            self.step_metrics.append(self.make_step_metrics())
            self.retries = 0
        return self.make_solution_output()

    def make_solution_output(
        self,
        error: str | None = None
    ) -> SolutionOutput:
        if self.name_bench == "mbpp":
            self.task_id = str(self.task_id)

        n_retries: int = 0
        for step in self.step_metrics:
            n_retries += step.retries
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

    def make_step_metrics(
        self,
    ) -> StepMetrics:
        step_metric: dict = {
            "step": self.iteration,
            "input_tokens": self.last_usage_input,
            "output_tokens": self.last_usage_output,
            "request_time_ms": self.request_time_ms,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            "api_url": self.client.url,
            "model_name": self.client.model_name,
            "llm_output": self.thoughts[-1] if self.thoughts else "",
            "sandbox_input": self.sandbox_input,
            "sandbox_output": self.sandbox_output,
            "retries": self.retries,
        }
        return StepMetrics.model_validate(step_metric)
