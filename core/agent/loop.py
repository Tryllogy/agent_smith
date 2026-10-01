import ast
import time

from core import constants, errors
from core.agent.extraction import extract_code_from_text
from core.agent.prompt import Prompt
from core.config_models import LLMResponse
from core.llm.client import LLMClient
from core.models import SandboxConfig, SolutionOutput, StepMetrics
from sandbox.executor import execute


class Loop:
    """Thought -> Code -> Observation loop for a single task.

    Calls the LLM, extracts the code block, runs it in the sandbox
    and feeds the observation back, until final_answer() or a
    benchmark limit (iterations, tokens, time). Usage is tracked
    per step for the SolutionOutput.
    """

    def __init__(
        self,
        client: LLMClient,
        prompt: Prompt,
        bench: constants.Bench,
        config_sandbox: SandboxConfig | None = None,
    ) -> None:
        """Bind the client, prompt and benchmark limits.

        config_sandbox defaults to SandboxConfig().
        """
        self.client: LLMClient = client
        self.thoughts: list = []
        self.reasoning: list = []
        self.observations: list = []
        self.usage_input: int = 0
        self.usage_output: int = 0
        self.prompt: Prompt = prompt
        self.bench: constants.Bench = bench
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
        self.llm_output: str = ""
        self.last_usage_input: int = 0
        self.last_usage_output: int = 0
        if config_sandbox is None:
            self.config_sandbox: SandboxConfig = SandboxConfig()
        else:
            self.config_sandbox: SandboxConfig = config_sandbox
        self.requests: int = 0
        self.turn_requests: int = 0

    def thought(self, timeout_max: float, max_tokens: int):
        """Send the conversation to the LLM and append its answer.

        Updates usage, request time and llm_output. LLM errors
        propagate to run().
        """
        self.requests += 1
        self.turn_requests += 1
        llm_response: LLMResponse = self.client.get_llm_reponse(
            timeout_max=timeout_max,
            messages=self.prompt.prompt,
            max_tokens=max_tokens,
        )
        text: str = llm_response.content
        self.request_time_ms = llm_response.request_time_ms
        self.usage_input += llm_response.input_tokens
        self.usage_output += llm_response.output_tokens
        self.last_usage_input = llm_response.input_tokens
        self.last_usage_output = llm_response.output_tokens
        self.finish_reason: str = llm_response.finish_reason
        self.thoughts.append(text)
        reason: str = llm_response.reasoning if llm_response.reasoning else ""
        self.reasoning.append(reason)
        self.llm_output = " ".join(part for part in (reason, text) if part)
        message = {"role": "assistant", "content": text}
        self.prompt.add_message(message)

    def extract(self, text: str) -> bool:
        """Extract the first code block of text into self.code.

        Returns True if a block was found and parses as Python.
        """
        self.code: dict = extract_code_from_text(text)
        return self.code["found"] and self.code["error"] == "None"

    def observation(self, max_execution_time: int) -> bool:
        """Run the extracted code and add the observation for the LLM.

        Returns True only when final_answer() was called with a valid
        answer. Every other outcome is reported as a user message.
        """
        if not self.code["found"]:
            self.sandbox_input = ""
            self.sandbox_output = ""
            self.prompt.add_message(
                {
                    "role": "user",
                    "content": f"Observation: {self.code['error']}."
                    " Must contain a ```python <your code here>``` "
                    " block.",
                }
            )
            return False
        self.sandbox_input: str = self.code["code"]
        config_copy: SandboxConfig = self.config_sandbox.model_copy()
        config_copy.max_execution_time_seconds = max_execution_time
        stdout, stderr, error, is_final, answer = execute(
            self.sandbox_input, config_copy
        )
        self.sandbox_output: str = (
            stdout + stderr + error if error else stdout + stderr
        )
        if error is None and is_final:
            refusal: str | None = self.check_final_answer(answer)
            if refusal is None:
                self.solution = answer
                self.success = True
                return True
            self.prompt.add_message(
                {"role": "user", "content": f"Observation: {refusal}"}
            )
            return False
        elif error is None and not is_final:
            if stdout.strip() == "":
                content: str = (
                    "The code has been executed without any error"
                    " or exception but did not produce any output."
                )
                if self.bench == constants.MBPP:
                    content += (
                        " Make SURE to make AND print the asserts like"
                        " assert cond, '...'."
                    )
            else:
                content: str = (
                    "The code has been"
                    " executed without any error or exception but did not"
                    " produce a final answer. No final_answer() captured."
                    " Provide a final_answer() in the next response."
                )
            output: str = ""
            if self.sandbox_output.strip() != "":
                output = (
                    f"Observation: Output: {self.sandbox_output}. " + content
                )
            self.prompt.add_message(
                {
                    "role": "user",
                    "content": f"{output}"
                    if output
                    else f"Observation: {content}",
                }
            )
            return False
        self.prompt.add_message(
            {"role": "user", "content": f"Observation: {self.sandbox_output}"}
        )
        return False

    def check_final_answer(self, answer) -> str | None:
        """Return why the final answer is refused, or None if it is valid.

        MBPP expects Python source, SWE-bench expects a git patch: a patch
        is never valid Python, so the check depends on the benchmark.
        """
        if not isinstance(answer, str) or answer.strip() == "":
            return "The final answer must be a non-empty string."
        if self.bench == constants.MBPP:
            try:
                ast.parse(answer)
            except (SyntaxError, ValueError):
                return (
                    "The final answer returned by the code is NOT"
                    " a valid Python expression."
                )
            return None
        if not any(marker in answer for marker in constants.PATCH_MARKERS):
            return (
                "The final answer is NOT a git patch."
                " Pass the result of get_patch() to final_answer()."
            )
        return None

    def run(
        self,
        task_id: str,
    ) -> SolutionOutput:
        """Run the loop on task_id and return the SolutionOutput.

        Transient LLM errors are retried; permanent ones and exhausted
        limits end the run with error set instead of raising.
        """
        self.start_time: float = time.time()
        self.iteration: int = 0
        self.task_id: str = task_id
        self.retries: int = 0
        self.turn_requests = 0
        while self.iteration < self.iteration_limit:
            self.sandbox_input = ""
            self.sandbox_output = ""
            self.llm_output = ""
            self.request_time_ms = 0.0
            self.last_usage_input = 0
            self.last_usage_output = 0
            if self.retries > constants.LLM_MAX_RETRIES:
                return self.exit_on_guard(
                    f"LLM max retries exceeded ({self.retries})"
                )
            try:
                if (
                    time.time()
                    - self.start_time
                    + constants.MARGIN_EXECUTION_TIME
                ) > self.timeout_limit:
                    return self.exit_on_guard("Timeout limit exceeded")
                max_tokens: int = self.max_tokens_output - self.usage_output
                if max_tokens <= 0:
                    return self.exit_on_guard("Output token limit exceeded")
                self.thought(
                    min(
                        constants.LLM_TIMEOUT_SECONDS,
                        self.timeout_limit
                        - (time.time() - self.start_time)
                        - constants.MARGIN_EXECUTION_TIME,
                    ),
                    max_tokens=max_tokens,
                )
            except errors.TransientLLMResponseError as e:
                self.retries += 1
                if e.retry_after is None:
                    self.retry_after = self.bench.retry_after
                else:
                    self.retry_after = e.retry_after
                time.sleep(self.retry_after)
                continue
            except errors.PermanentLLMResponseError as e:
                return self.exit_on_guard(f"{str(e)}")
            if (
                self.finish_reason == "length"
                or self.usage_output > self.max_tokens_output
            ):
                return self.exit_on_guard(
                    "LLM response exceeded the maximum token limit"
                )
            if time.time() - self.start_time > self.timeout_limit:
                return self.exit_on_guard("Timeout limit exceeded")
            if self.usage_input > self.max_tokens_input:
                return self.exit_on_guard("Input token limit exceeded")
            self.extract(self.thoughts[-1])
            max_execution_time: int = int(
                self.timeout_limit
                - (time.time() - self.start_time)
                - constants.MARGIN_EXECUTION_TIME
            )
            if max_execution_time <= 0:
                return self.exit_on_guard("Timeout limit exceeded")
            if self.observation(max_execution_time=max_execution_time):
                self.step_metrics.append(self.make_step_metrics())
                self.iteration += 1
                return self.make_solution_output()
            self.step_metrics.append(self.make_step_metrics())
            self.iteration += 1
            self.retries = 0
            self.turn_requests = 0
        return self.make_solution_output(error="Iteration limit exceeded")

    def exit_on_guard(self, error: str) -> SolutionOutput:
        """End the run, recording the turn only if it sent a request."""
        if self.turn_requests > 0:
            self.step_metrics.append(self.make_step_metrics())
        return self.make_solution_output(error=error)

    def make_solution_output(self, error: str | None = None) -> SolutionOutput:
        """Build the SolutionOutput from the current state of the run."""
        self.task_id = str(self.task_id)

        solution: dict = {
            "task_id": self.task_id,
            "benchmark": self.bench.name,
            "success": self.success,
            "solution": self.solution,
            "iterations": self.iteration,
            "total_requests": self.requests,
            "total_input_tokens": self.usage_input,
            "total_output_tokens": self.usage_output,
            "total_time_seconds": round(time.time() - self.start_time, 2),
            "steps": self.step_metrics,
            "system_prompt": "\n".join(
                [
                    msg["content"]
                    for msg in self.prompt.prompt
                    if msg["role"] == "system"
                ]
            ),
            "error": error,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        }
        return SolutionOutput.model_validate(solution)

    def make_step_metrics(
        self,
    ) -> StepMetrics:
        """Build the StepMetrics of the current turn."""
        step_metric: dict = {
            "step": self.iteration + 1,
            "input_tokens": self.last_usage_input,
            "output_tokens": self.last_usage_output,
            "request_time_ms": self.request_time_ms,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            "api_url": self.client.url,
            "model_name": self.client.model_name,
            "llm_output": self.llm_output,
            "sandbox_input": self.sandbox_input,
            "sandbox_output": self.sandbox_output,
            "retries": self.retries,
        }
        return StepMetrics.model_validate(step_metric)
