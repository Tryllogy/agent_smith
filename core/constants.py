from dataclasses import dataclass
from enum import Enum

MARGIN_EXECUTION_TIME = 5
LLM_MAX_RETRIES = 4
ESTIMATED_CHARS_PER_TOKEN = 2.5
LLM_STOP_SEQUENCE = [
    "<end_code>",
    "Observation:",
]
LLM_START_SEQUENCE = [
    "```python",
]
CODE_BLOCK_PATTERN = r"```(?:python)? *\n(.*?)```"
FENCED_BLOCK_PATTERN = r"```(\w*) *\n(.*?)```"
PYTHON_BLOCK_TAGS = ("", "python")
TRUNCATED_HEAD_SHARE = 0.7
OPEN_BLOCK_PATTERN = r"```(\w*) *\n"

MODELS_CONFIG_FILE = "configs/models.json"
FALLBACK_CONFIG_FILE = "configs/fallback.json"

MBPP_MCP_SERVER = "mcp_tools_mbpp.py"
SWE_MCP_SERVER = "mcp_tools_swebench.py"

MBPP_DEFAULT_MODEL = "codestral-2508"
SWE_DEFAULT_MODEL = "codestral-2508"

PATCH_MARKERS = ("diff --git", "--- a/", "+++ b/", "@@")


class BenchName(Enum):
    """Benchmark names, as written in SolutionOutput."""

    SWE = "swebench"
    MBPP = "mbpp"


@dataclass(frozen=True)
class Bench:
    """Hard limits of a benchmark, its default retry delay (s) and the
    longest an LLM call may take (s), always bounded by the time left.

    observation_max_chars caps what one observation shows the LLM: the
    whole conversation is resent on every turn, against a cumulative
    input limit. full_observations is how many of the latest observations
    stay whole in the conversation, older ones being elided; None keeps
    them all.
    """

    name: str
    input_max_token: int
    output_max_token: int
    iterations: int
    timeout: int
    retry_after: int
    llm_timeout: int
    observation_max_chars: int = 10000
    full_observations: int | None = None


SWE = Bench(
    name=BenchName.SWE.value,
    input_max_token=300000,
    output_max_token=10000,
    iterations=30,
    timeout=900,
    retry_after=10,
    llm_timeout=60,
    observation_max_chars=10000,
    full_observations=3,
)

MBPP = Bench(
    name=BenchName.MBPP.value,
    input_max_token=6000,
    output_max_token=1500,
    iterations=10,
    timeout=120,
    retry_after=5,
    llm_timeout=30,
    observation_max_chars=2000,
    full_observations=None,
)

SWE_EXAMPLE = r"""Task: Fix the issue described in the problem statement.
Repo: /testbed (acme/shopcart)

Problem statement: Items added to one `Cart` also appear in every other `Cart` created without arguments.

Step 1

Thought: Before touching anything I reproduce the report, to get a local oracle, then I find where `Cart` is defined and read its constructor. I will only edit code I have read.

```python
print(run_command(command="python -c \"from shopcart import Cart; a, b = Cart(), Cart(); a.add('x'); print(b.items)\"", workdir="/testbed"))
print(search_code(pattern="class Cart", file_pattern="*.py"))
print(read_file(filepath="/testbed/shopcart/cart.py", start_line=1, end_line=6))
```<end_code>

Observation: exit code: 0
--- stdout ---
['x']

--- stderr ---


/testbed/shopcart/cart.py:1 class Cart:
1: class Cart:
2:     def __init__(self, items=[]):
3:         self.items = items
4: 
5:     def add(self, item):
6:         self.items.append(item)

Step 2

Thought: `b` holds the item added to `a`. The default `items=[]` is built once, when the function is defined, so every `Cart()` shares that list. I default to `None` and give each cart its own list, copying a list passed in so the caller's list is not mutated either. Then I re-run the reproduction and the evaluation script.

```python
print(edit_file(filepath="/testbed/shopcart/cart.py", old_str="    def __init__(self, items=[]):\n        self.items = items", new_str="    def __init__(self, items=None):\n        self.items = list(items) if items is not None else []"))
print(run_command(command="python -c \"from shopcart import Cart; a, b = Cart(), Cart(); a.add('x'); print(b.items)\"", workdir="/testbed"))
print(run_tests())
```<end_code>

Observation: Edited /testbed/shopcart/cart.py: 1 replacement
exit code: 0
--- stdout ---
[]

--- stderr ---


exit code: 0
--- stdout ---
>>>>> Start Test Output
tests/test_cart.py::test_add PASSED
tests/test_cart.py::test_carts_do_not_share_items PASSED
12 passed in 0.08s
>>>>> End Test Output

--- stderr ---
+ git checkout 3f2a9c1 tests/test_cart.py



Step 3

Thought: The reproduction now prints `[]`, and the test output between the markers ends with `12 passed` and no failure or error: the exit code alone would not have told me that. I take the patch, check that it is not empty, and submit it.

```python
patch = get_patch()
assert patch.strip(), "empty patch: no working-tree change was recorded"
final_answer(patch)
```<end_code>
"""

MBPP_EXAMPLE = r'''Task:
task_definition: Return the smallest absolute value in a list of integers.
function_definition: def smallest_abs(a):
test_list: assert smallest_abs([3, -1, 5]) == 1
assert smallest_abs([-5, 2]) == 2
Thought: Smallest absolute value means I take the minimum, then its absolute value. I keep the solution in a variable, check it with run_tests, and submit that same variable only if every test passes.
Code:
```python
solution = r"""def smallest_abs(a):
    return abs(min(a))"""
report = run_tests(code=solution)
print(report)
if report.startswith("success: true"):
    final_answer(solution)
```<end_code>
Observation: success: false (1 of 2 tests passed)
1. PASS  assert smallest_abs([3, -1, 5]) == 1
2. FAIL  assert smallest_abs([-5, 2]) == 2  (got 5)
Thought: Test 2 fails: my function returned 5 instead of 2. `min` picks -5 because it is the smallest signed value, and abs only runs afterwards. I must map abs over the list first, then take the minimum.
Code:
```python
solution = r"""def smallest_abs(a):
    return min(map(abs, a))"""
report = run_tests(code=solution)
print(report)
if report.startswith("success: true"):
    final_answer(solution)
```<end_code>
'''
