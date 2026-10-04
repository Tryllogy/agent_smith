import ast
import math
import sys
import time

from core import constants, errors
from core.agent.extraction import extract_code_from_text
from core.agent.prompt import Prompt
from core.config_models import LLMResponse
from core.llm.fallback import FallbackClient
from core.models import SandboxConfig, SolutionOutput, StepMetrics
from sandbox.executor import Sandbox, execute
from sandbox.mcp_client.client import MCPClient


class Loop:
    """Thought -> Code -> Observation loop for a single task.

    Calls the LLM, extracts the code block, runs it in the sandbox
    and feeds the observation back, until final_answer() or a
    benchmark limit (iterations, tokens, time). Usage is tracked
    per step for the SolutionOutput.
    """

    def __init__(
        self,
        client: FallbackClient,
        prompt: Prompt,
        bench: constants.Bench,
        config_sandbox: SandboxConfig | None = None,
        answer_tests: list[str] | None = None,
        mcp_client: MCPClient | None = None,
    ) -> None:
        """Bind the client, prompt and benchmark limits.

        config_sandbox defaults to SandboxConfig(). answer_tests are Python
        lines run after the final answer, alone in the sandbox, before it
        is accepted (MBPP: test_imports then test_list). mcp_client is the
        connected MCP server whose tools the model's code may call; None
        leaves final_answer alone in the sandbox.
        """
        self.client: FallbackClient = client
        self.mcp_client: MCPClient | None = mcp_client
        self.answer_tests: list[str] = answer_tests or []
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
        self.turn_input_tokens: int = 0
        self.turn_output_tokens: int = 0
        self.last_prompt_tokens: int = 0
        self.last_prompt_chars: int = 0
        self.elided_chars: int = 0
        self.observation_indices: list[tuple[int, int]] = []
        self.elided_indices: set[int] = set()
        if config_sandbox is None:
            self.config_sandbox: SandboxConfig = SandboxConfig()
        else:
            self.config_sandbox: SandboxConfig = config_sandbox
        self.requests: int = 0
        self.turn_requests: int = 0
        self.last_llm_error: str = ""

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
        self.turn_input_tokens += llm_response.input_tokens
        self.turn_output_tokens += llm_response.output_tokens
        self.last_prompt_tokens = llm_response.input_tokens
        self.last_prompt_chars = self.prompt_chars()
        self.elided_chars = 0
        self.finish_reason: str = llm_response.finish_reason
        if llm_response.content_from_reasoning:
            sys.stderr.write(
                f"LLM content empty on step {self.iteration + 1}:"
                " answer taken from the reasoning\n"
            )
        self.thoughts.append(text)
        reason: str = llm_response.reasoning if llm_response.reasoning else ""
        self.reasoning.append(reason)
        self.llm_output = " ".join(part for part in (reason, text) if part)
        message = {"role": "assistant", "content": text}
        self.prompt.add_message(message)

    def prompt_chars(self) -> int:
        """Return the number of characters of the conversation."""
        return sum(len(message["content"]) for message in self.prompt.prompt)

    def estimate_next_input(self) -> int:
        """Estimate the input tokens of the next request.

        The provider counted the previous prompt exactly: only the
        messages added since are estimated, at ESTIMATED_CHARS_PER_TOKEN,
        chosen below the ratios measured so the estimate errs high.
        Characters elided since are not deducted, for the same reason.
        """
        added_chars: int = (
            self.prompt_chars() - self.last_prompt_chars + self.elided_chars
        )
        return self.last_prompt_tokens + math.ceil(
            added_chars / constants.ESTIMATED_CHARS_PER_TOKEN
        )

    def extract(self, text: str) -> bool:
        """Extract the first code block of text into self.code.

        Returns True if a block was found and parses as Python.
        """
        self.code: dict = extract_code_from_text(text)
        return self.code["found"] and self.code["error"] == "None"

    def observation(self, max_execution_time: int) -> bool:
        """Run the extracted code and add the observation for the LLM.

        The code may run for the sandbox's configured timeout, cut down to
        max_execution_time, the time the task has left. Returns True only
        when final_answer() was called with a valid answer. Every other
        outcome is reported as a user message.
        """
        if not self.code["found"]:
            self.sandbox_input = ""
            self.sandbox_output = ""
            self.add_observation(
                f"{self.code['error']}."
                " Write your code in one ```python block, then <end_code>."
            )
            return False
        self.sandbox_input: str = self.code["code"]
        stdout, stderr, error, is_final, answer = self.sandbox.run(
            self.sandbox_input,
            timeout=min(
                self.config_sandbox.max_execution_time_seconds,
                max_execution_time,
            ),
        )
        self.sandbox_output: str = (
            stdout + stderr + error if error else stdout + stderr
        )
        shown: str = self.truncate_output(self.sandbox_output)
        if error is None and is_final:
            refusal: str | None = self.check_final_answer(answer)
            if refusal is None and self.bench == constants.MBPP:
                refusal = self.run_answer_tests(answer)
            if refusal is None:
                self.solution = answer
                self.success = True
                return True
            self.add_observation(refusal)
            return False
        elif error is None and not is_final:
            if self.sandbox_output.strip() == "":
                content: str = (
                    "The code ran without error but did not"
                    " produce any output: only what you print() appears"
                    " here."
                )
                if self.bench == constants.MBPP:
                    content += (
                        " Print the report of run_tests() to see which"
                        " tests pass."
                    )
            elif self.bench == constants.MBPP:
                content: str = (
                    f"{shown}\n"
                    "No final_answer() captured. If your checks passed,"
                    " call final_answer() in your next step."
                )
            else:
                content: str = (
                    f"{shown}\n"
                    "No final_answer() captured yet: call"
                    " final_answer(get_patch()) once the fix is verified."
                )
            self.add_observation(content)
            return False
        self.add_observation(shown)
        return False

    def truncate_output(self, output: str) -> str:
        """Return output cut to the bench's observation_max_chars.

        The head and the tail are kept, since errors and test summaries
        come last, and the cut is stated with what to do about it.
        """
        limit: int = self.bench.observation_max_chars
        if len(output) <= limit:
            return output
        head: int = int(limit * constants.TRUNCATED_HEAD_SHARE)
        tail: int = limit - head
        return (
            f"{output[:head]}\n[Output truncated: {len(output)} characters,"
            f" only the first {head} and the last {tail} are shown. Print a"
            " smaller part (for instance a narrower read_file range) to see"
            f" the rest.]\n{output[-tail:]}"
        )

    def add_observation(self, body: str) -> None:
        """Send body to the LLM as the observation of the turn.

        When the code block was malformed but run anyway, the observation
        starts by saying how it was read. Older observations are then
        elided past the bench's full_observations.
        """
        note: str = self.code.get("note", "")
        prefix: str = f"Note: {note}.\n" if note else ""
        self.prompt.add_message(
            {"role": "user", "content": f"Observation: {prefix}{body}"}
        )
        self.observation_indices.append(
            (len(self.prompt.prompt) - 1, self.iteration + 1)
        )
        self.elide_old_observations()

    def elide_old_observations(self) -> None:
        """Replace observations older than full_observations by a stub.

        The whole conversation is resent on every turn: an observation
        kept forever is paid on every later request. The model's own
        messages stay whole, and the stub says how to get the output back.
        An observation shorter than its stub is left as it is.
        """
        keep: int | None = self.bench.full_observations
        if keep is None or len(self.observation_indices) <= keep:
            return
        for index, step in self.observation_indices[:-keep]:
            if index in self.elided_indices:
                continue
            message: dict = self.prompt.prompt[index]
            content: str = message["content"]
            stub: str = (
                f"Observation: [Output of step {step} elided to save"
                f" tokens ({len(content)} characters). Run the code again"
                " if you need it.]"
            )
            self.elided_indices.add(index)
            if len(stub) >= len(content):
                continue
            self.elided_chars += len(content) - len(stub)
            message["content"] = stub

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
            except SyntaxError as e:
                return (
                    "The final answer is NOT valid Python:"
                    f" SyntaxError: {e.msg} (line {e.lineno},"
                    f" column {e.offset}). for, if and while cannot"
                    " follow a ';' on the same line: pass your function"
                    " on several lines, in a triple-quoted string:"
                    ' final_answer(r"""...""").'
                )
            except ValueError as e:
                return f"The final answer is NOT valid Python: {e}."
            return None
        if not any(marker in answer for marker in constants.PATCH_MARKERS):
            return (
                "The final answer is NOT a git patch."
                " Pass the result of get_patch() to final_answer()."
            )
        return None

    def run_answer_tests(self, answer: str) -> str | None:
        """Run the answer alone with answer_tests; return why it fails.

        The moulinette runs the submitted string on its own, so code the
        model executed but left out of final_answer() (an import, a
        helper) is missing there. Skipped when no time is left.
        """
        remaining: int = int(
            self.timeout_limit
            - (time.time() - self.start_time)
            - constants.MARGIN_EXECUTION_TIME
        )
        if not self.answer_tests or remaining <= 0:
            return None
        config: SandboxConfig = self.config_sandbox.model_copy()
        config.max_execution_time_seconds = min(
            config.max_execution_time_seconds, remaining
        )
        code: str = "\n".join(
            [answer, *[self.label_assert(test) for test in self.answer_tests]]
        )
        _, _, error, _, _ = execute(code, config)
        if error is None:
            return None
        return (
            "Your final answer was rejected: run alone, without the rest"
            f" of your code, against test_list it fails with {error}."
            " final_answer() must contain the complete solution, imports"
            " included."
        )

    @staticmethod
    def label_assert(line: str) -> str:
        """Give a bare assert its own source as message, to name it."""
        try:
            tree = ast.parse(line)
        except SyntaxError:
            return line
        if (
            len(tree.body) == 1
            and isinstance(tree.body[0], ast.Assert)
            and tree.body[0].msg is None
        ):
            tree.body[0].msg = ast.Constant(line.strip())
            return ast.unparse(tree)
        return line

    def run(
        self,
        task_id: str,
    ) -> SolutionOutput:
        """Run the loop on task_id and return the SolutionOutput.

        The model's code runs in one sandbox for the whole task, so the
        variables, functions and imports of a step are still there at the
        next; it is closed when the task ends, however it ends.
        Transient LLM errors are retried; permanent ones and exhausted
        limits end the run with error set instead of raising.
        """
        with Sandbox(self.config_sandbox, self.mcp_client) as self.sandbox:
            return self.run_steps(task_id)

    def run_steps(self, task_id: str) -> SolutionOutput:
        """Run the Thought -> Code -> Observation steps of run()."""
        self.start_time: float = time.time()
        self.iteration: int = 0
        self.task_id: str = task_id
        self.retries: int = 0
        self.backend_retries: int = 0
        self.turn_requests = 0
        self.turn_input_tokens = 0
        self.turn_output_tokens = 0
        self.last_llm_error = ""
        while self.iteration < self.iteration_limit:
            self.sandbox_input = ""
            self.sandbox_output = ""
            self.llm_output = ""
            self.request_time_ms = 0.0
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
                next_input: int = self.estimate_next_input()
                if self.usage_input + next_input > self.max_tokens_input:
                    return self.exit_on_guard(
                        "Input token limit exceeded: the next request"
                        f" (~{next_input} tokens) would go over"
                    )
                self.thought(
                    min(
                        self.bench.llm_timeout,
                        self.timeout_limit
                        - (time.time() - self.start_time)
                        - constants.MARGIN_EXECUTION_TIME,
                    ),
                    max_tokens=max_tokens,
                )
            except errors.TransientLLMResponseError as e:
                self.count_rejected_tokens(e)
                self.retries += 1
                self.backend_retries += 1
                self.last_llm_error = self.describe_llm_error(e)
                if self.backend_retries > constants.LLM_MAX_RETRIES:
                    if self.fall_back(self.last_llm_error):
                        continue
                    return self.exit_on_guard(
                        f"LLM max retries exceeded ({self.retries})"
                    )
                if e.retry_after is None:
                    self.retry_after = self.bench.retry_after
                else:
                    self.retry_after = e.retry_after
                if (
                    time.time()
                    - self.start_time
                    + self.retry_after
                    + constants.MARGIN_EXECUTION_TIME
                ) > self.timeout_limit:
                    return self.exit_on_guard("Timeout limit exceeded")
                sys.stderr.write(
                    f"LLM retry {self.retries} on step {self.iteration + 1}:"
                    f" {self.last_llm_error};"
                    f" waiting {self.retry_after:.1f}s\n"
                )
                time.sleep(self.retry_after)
                continue
            except errors.PermanentLLMResponseError as e:
                self.count_rejected_tokens(e)
                if self.fall_back(self.describe_llm_error(e)):
                    self.retries += 1
                    self.last_llm_error = self.describe_llm_error(e)
                    continue
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
            self.backend_retries = 0
            self.turn_requests = 0
            self.turn_input_tokens = 0
            self.turn_output_tokens = 0
            self.last_llm_error = ""
        return self.make_solution_output(error="Iteration limit exceeded")

    def count_rejected_tokens(self, error: errors.LLMResponseError) -> None:
        """Count the tokens of a response the client rejected.

        The provider billed them: they go into the totals and into the
        turn's step, so the totals stay the sum of the steps and the
        token guards see what was really spent.
        """
        self.usage_input += error.input_tokens
        self.usage_output += error.output_tokens
        self.turn_input_tokens += error.input_tokens
        self.turn_output_tokens += error.output_tokens

    @staticmethod
    def describe_llm_error(error: errors.LLMResponseError) -> str:
        """Return the error message, with its HTTP status if known."""
        if error.status_code is None:
            return str(error)
        return f"{error} (HTTP {error.status_code})"

    def fall_back(self, reason: str) -> bool:
        """Switch to the client's next model, which reason made necessary.

        The new model starts with a full retry budget, while the turn
        keeps counting all its retries for the step. Logged on stderr.
        Returns False when no model is left.
        """
        if not self.client.fall_back():
            return False
        self.backend_retries = 0
        sys.stderr.write(
            f"LLM fallback on step {self.iteration + 1}: {reason};"
            f" switching to {self.client.model_name} at {self.client.url}\n"
        )
        return True

    def exit_on_guard(self, error: str) -> SolutionOutput:
        """End the run with error, plus the last LLM error of the turn.

        The turn is recorded as a step only if it sent a request.
        """
        if self.turn_requests > 0:
            self.step_metrics.append(self.make_step_metrics())
        if self.last_llm_error:
            error += f"; last LLM error: {self.last_llm_error}"
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
            "input_tokens": self.turn_input_tokens,
            "output_tokens": self.turn_output_tokens,
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
