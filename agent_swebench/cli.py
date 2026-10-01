from dotenv import load_dotenv

from core.agent import Loop
from core.agent.prompt import Prompt
from core.agent_cli_helper import (
    get_api_keys,
    get_provider_and_model_config,
    get_task_from_file,
)
from core.constants import LLM_STOP_SEQUENCE, SWE
from core.llm.client import LLMClient
from core.llm.provider import Provider
from core.models import SandboxConfig, SolutionOutput, SWEBenchTaskInput

load_dotenv()


class AgentSWEBENCH:
    """SWE-bench agent: wires a task file to the agent loop."""

    def __init__(
        self,
        task_file: str,
        output_file: str,
        model_name: str,
        provider_url: str,
    ):
        """Load the task, then build the prompt, LLM client and loop.

        Raises on any configuration error (task file, models.json,
        API keys): no request is made here.
        """
        self.task: dict = get_task_from_file(task_file, SWEBenchTaskInput)
        self.output_file: str = output_file

        sandbox: SandboxConfig = SandboxConfig()
        tools = None

        prompt: Prompt = Prompt(
            bench=SWE,
            task=self.task,
            tools=tools,
            allowed_imports=sandbox.authorized_imports,
        )

        self.provider_config, self.model_config = (
            get_provider_and_model_config(model_name, provider_url)
        )

        self.llm_client: LLMClient = LLMClient(
            url=provider_url,
            endpoint=self.provider_config.endpoint,
            model_name=model_name,
            api_keys=get_api_keys(self.provider_config),
            stop_sequence=LLM_STOP_SEQUENCE,
            provider=Provider(self.provider_config),
            model_config=self.model_config,
        )

        self.loop = Loop(
            client=self.llm_client,
            prompt=prompt,
            bench=SWE,
            config_sandbox=sandbox,
        )

    def run(self) -> SolutionOutput:
        """Run the loop and write its SolutionOutput to the output file.

        An unexpected exception inside the loop is reported in the
        output, with the steps already recorded, instead of propagating.
        """
        try:
            solution = self.loop.run(self.task["instance_id"])
        except Exception as e:
            solution = self.loop.make_solution_output(
                error=f"Unexpected error: {e}"
            )
        with open(self.output_file, "w") as f:
            f.write(solution.model_dump_json(indent=4))
        return solution
