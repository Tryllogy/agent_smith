from dotenv import load_dotenv

from core.agent.loop import Loop
from core.agent.prompt import Prompt
from core.agent_cli_helper import (
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

load_dotenv()


class AgentMBPP:
    """MBPP agent: wires a task file to the agent loop."""

    def __init__(
        self,
        task_file: str,
        output_file: str,
        model_name: str,
        provider_url: str,
    ) -> None:
        """Load the task, then build the prompt, LLM client and loop.

        Raises on any configuration error (task file, models.json,
        API keys): no request is made here.
        """
        self.task: dict = get_task_from_file(task_file, MBPPTaskInput)
        self.output_file: str = output_file

        sandbox: SandboxConfig = SandboxConfig()
        manual = None

        prompt: Prompt = Prompt(
            bench=MBPP,
            task=self.task,
            manual=manual,
            allowed_imports=sandbox.authorized_imports,
        )

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

        self.loop = Loop(
            client=self.client,
            prompt=prompt,
            bench=MBPP,
            config_sandbox=sandbox,
            answer_tests=[
                *self.task.get("test_imports", []),
                *self.task.get("test_list", []),
            ],
        )

    def run(self) -> SolutionOutput:
        """Run the loop and write its SolutionOutput to the output file.

        An unexpected exception inside the loop is reported in the
        output, with the steps already recorded, instead of propagating.
        """
        try:
            solution: SolutionOutput = self.loop.run(self.task["task_id"])
        except Exception as e:
            solution = self.loop.make_solution_output(
                error=f"Unexpected error: {e}"
            )
        with open(self.output_file, "w") as f:
            f.write(solution.model_dump_json(indent=4))
        return solution
