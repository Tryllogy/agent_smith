from dotenv import load_dotenv

from core import constants
from core.agent.loop import Loop
from core.agent.prompt import Prompt
from core.agent_cli_helper import (
    connect_mcp_server,
    get_api_keys,
    get_fallback_clients,
    get_provider_and_model_config,
    get_task_from_file,
    make_llm_client,
)
from core.constants import MBPP
from core.llm.client import LLMClient
from core.llm.fallback import FallbackClient
from core.models import MBPPTaskInput, SandboxConfig, SolutionOutput
from sandbox.manual import render_manual
from sandbox.mcp_client.client import MCPClient

load_dotenv()


class AgentMBPP:
    """MBPP agent: wires a task file to the agent loop."""

    def __init__(
        self,
        task_file: str,
        output_file: str,
        model_name: str,
        provider_url: str,
        start_time: float | None = None,
    ) -> None:
        """Load the task, then build the LLM client, tools, prompt and loop.

        Raises on any configuration error (task file, models.json,
        API keys) or if the MCP tool server cannot start: no request is
        made here. The server is started last, once the configuration is
        known to be valid; the prompt relies on its run_tests().
        start_time is when the agent started, from which the time limit
        runs; None means now.
        """
        self.task: dict = get_task_from_file(task_file, MBPPTaskInput)
        self.output_file: str = output_file

        sandbox: SandboxConfig = SandboxConfig()

        self.provider_config, self.model_config = (
            get_provider_and_model_config(model_name, provider_url)
        )

        self.llm_client: LLMClient = make_llm_client(
            self.provider_config,
            self.model_config,
            model_name,
            get_api_keys(self.provider_config),
        )
        self.client: FallbackClient = FallbackClient(
            [
                self.llm_client,
                *get_fallback_clients(MBPP, model_name, provider_url),
            ]
        )

        self.mcp_client: MCPClient | None = connect_mcp_server(
            constants.MBPP_MCP_SERVER,
            ["--task-file", task_file],
            call_timeout=MBPP.timeout,
        )
        try:
            prompt: Prompt = Prompt(
                bench=MBPP,
                task=self.task,
                manual=render_manual(self.mcp_client),
                allowed_imports=sandbox.authorized_imports,
            )
            self.loop = Loop(
                client=self.client,
                prompt=prompt,
                bench=MBPP,
                config_sandbox=sandbox,
                answer_tests=[
                    *self.task.get("test_imports", []),
                    *self.task.get("test_list", []),
                ],
                mcp_client=self.mcp_client,
                start_time=start_time,
            )
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        """Stop the tool server."""
        if self.mcp_client is not None:
            self.mcp_client.close()
            self.mcp_client = None

    def run(self) -> SolutionOutput:
        """Run the loop and write its SolutionOutput to the output file.

        An unexpected exception inside the loop is reported in the
        output, with the steps already recorded, instead of propagating.
        The tool server is stopped in every case.
        """
        try:
            try:
                solution: SolutionOutput = self.loop.run(self.task["task_id"])
            except Exception as e:
                solution = self.loop.make_solution_output(
                    error=f"Unexpected error: {e}"
                )
            with open(self.output_file, "w") as f:
                f.write(solution.model_dump_json(indent=4))
        finally:
            self.close()
        return solution
