from dataclasses import dataclass

MARGIN_EXECUTION_TIME = 5
LLM_TIMEOUT_SECONDS = 30
LLM_ENDPOINT = "/chat/completions"
LLM_STOP_SEQUENCE = [
    "<end_code>",
]
LLM_START_SEQUENCE = [
    "```python",
]


@dataclass(frozen=True)
class Bench:
    name: str
    input_max_token: int
    output_max_token: int
    iterations: int
    timeout: int


SWE = Bench(
    name="swebench",
    input_max_token=300000,
    output_max_token=10000,
    iterations=30,
    timeout=900,
)

MBPP = Bench(
    name="mbpp",
    input_max_token=6000,
    output_max_token=1500,
    iterations=10,
    timeout=120,
)
