from dataclasses import dataclass
from enum import Enum

MARGIN_EXECUTION_TIME = 5
LLM_TIMEOUT_SECONDS = 30
LLM_STOP_SEQUENCE = [
    "<end_code>",
]
LLM_START_SEQUENCE = [
    "```python",
]

MODELS_CONFIG_FILE = "configs/models.json"


class BenchName(Enum):
    SWE = "swebench"
    MBPP = "mbpp"


@dataclass(frozen=True)
class Bench:
    name: str
    input_max_token: int
    output_max_token: int
    iterations: int
    timeout: int


SWE = Bench(
    name=BenchName.SWE.value,
    input_max_token=300000,
    output_max_token=10000,
    iterations=30,
    timeout=900,
)

MBPP = Bench(
    name=BenchName.MBPP.value,
    input_max_token=6000,
    output_max_token=1500,
    iterations=10,
    timeout=120,
)
