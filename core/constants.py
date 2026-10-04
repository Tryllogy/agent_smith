from dataclasses import dataclass
from enum import Enum

MARGIN_EXECUTION_TIME = 5
LLM_MAX_RETRIES = 4
ESTIMATED_CHARS_PER_TOKEN = 2.5
LLM_STOP_SEQUENCE = [
    "<end_code>",
]
LLM_START_SEQUENCE = [
    "```python",
]
CODE_BLOCK_PATTERN = r"```(?:python)? *\n(.*?)```"

MODELS_CONFIG_FILE = "configs/models.json"
FALLBACK_CONFIG_FILE = "configs/fallback.json"

MBPP_MCP_SERVER = "mcp_tools_mbpp.py"
SWE_MCP_SERVER = "mcp_tools_swebench.py"
SWE_REPO_ROOT = "/testbed"

PATCH_MARKERS = ("diff --git", "--- a/", "+++ b/", "@@")


class BenchName(Enum):
    """Benchmark names, as written in SolutionOutput."""

    SWE = "swebench"
    MBPP = "mbpp"


@dataclass(frozen=True)
class Bench:
    """Hard limits of a benchmark, its default retry delay (s) and the
    longest an LLM call may take (s), always bounded by the time left.
    """

    name: str
    input_max_token: int
    output_max_token: int
    iterations: int
    timeout: int
    retry_after: int
    llm_timeout: int


SWE = Bench(
    name=BenchName.SWE.value,
    input_max_token=300000,
    output_max_token=10000,
    iterations=30,
    timeout=900,
    retry_after=10,
    llm_timeout=60,
)

MBPP = Bench(
    name=BenchName.MBPP.value,
    input_max_token=6000,
    output_max_token=1500,
    iterations=10,
    timeout=120,
    retry_after=5,
    llm_timeout=30,
)

SWE_PROMPT_EXEMPLE = r"""Task: Fix the issue described in the problem statement.
Repo: /testbed (blueprintml/skema @ 7c1a9e0)
Tools: read_file, edit_file, list_files, search_code,
       search_function_or_class_definition_in_code, find_references,
       run_tests, get_patch, run_command

Problem statement: `default_factory` result is shared between loads. A field declared
with `default_factory=list` returns the same object on every `load()`, so mutating one
load's value is visible from every other load — including through `fields.Nested`.

Step 1

Thought: I reproduce both scenarios from the report (flat and nested) to get a local
oracle before touching anything, and I grep for the memoisation the reporter mentions.
Object identity is the real signal here, not just the values, so I print both. Scratch
files go under /tmp/agent so they stay outside the repo and out of the final diff.

```python
print(run_command(command="mkdir -p /tmp/agent && cat > /tmp/agent/repro.py <<'PY'\nfrom skema import Schema, fields\n\nclass Bag(Schema):\n    items = fields.List(fields.Str(), default_factory=list)\n\na, b = Bag.load({}), Bag.load({})\na[\"items\"].append(\"x\")\nprint(\"flat   b =\", b[\"items\"], \"| shared:\", a[\"items\"] is b[\"items\"])\n\nclass Inner(Schema):\n    tags = fields.List(fields.Str(), default_factory=list)\n\nclass Outer(Schema):\n    inner = fields.Nested(Inner)\n\nc, d = Outer.load({\"inner\": {}}), Outer.load({\"inner\": {}})\nc[\"inner\"][\"tags\"].append(\"x\")\nprint(\"nested d =\", d[\"inner\"][\"tags\"], \"| shared:\", c[\"inner\"][\"tags\"] is d[\"inner\"][\"tags\"])\nPY", workdir="/testbed"))
print(run_command(command="python /tmp/agent/repro.py", workdir="/testbed"))
print(search_code(pattern="_default_cache", file_pattern="src/skema/*.py"))
print(search_code(pattern="_defaults", file_pattern="src/skema/*.py"))
print(read_file(filepath="/testbed/src/skema/fields.py", start_line=88, end_line=98))
print(read_file(filepath="/testbed/src/skema/fields.py", start_line=298, end_line=311))
```<end_code>

Observation:
stdout:
flat   b = ['x'] | shared: True
nested d = ['x'] | shared: True
stderr:
exit_code: 0

/testbed/src/skema/fields.py:76        self._default_cache = _UNSET
/testbed/src/skema/fields.py:95            self._default_cache = self.default_factory()
/testbed/src/skema/fields.py:97        return self._default_cache
/testbed/src/skema/fields.py:302        self._defaults = None
/testbed/src/skema/fields.py:307        if self._defaults is None:
/testbed/src/skema/fields.py:308            self._defaults = self.schema._collect_defaults()
/testbed/src/skema/fields.py:309        data = dict(self._defaults)
/testbed/src/skema/schema.py:141     def _collect_defaults(cls):

88:     def has_default(self):
89:         return self.default is not _UNSET or self.default_factory is not None
90:
91:     def get_default(self):
92:         if self.default_factory is None:
93:             return self.default
94:         # cache the factory result so repeated loads stay cheap (#398)
95:         if self._default_cache is _UNSET:
96:             self._default_cache = self.default_factory()
97:         return self._default_cache

298:
299:     def __init__(self, schema, **kwargs):
300:         super().__init__(**kwargs)
301:         self.schema = schema
302:         self._defaults = None
303:
304:     def deserialize(self, value, **kwargs):
305:         if value is _UNSET:
306:             value = {}
307:         if self._defaults is None:
308:             self._defaults = self.schema._collect_defaults()
309:         data = dict(self._defaults)
310:         data.update(self.schema.load(value, **kwargs))
311:         return data

Step 2

Thought: Both cases leak, and the grep shows two independent caches, not one. In `Field`
the factory result is memoised on the field instance, and since fields are class-level
attributes on the schema, that cache lives as long as the class. In `Nested` the whole
defaults mapping is memoised and then copied with `dict(...)`, which is shallow, so the
inner list stays shared no matter what I do to `Field`. Fixing only one would leave half
the bug alive, so I fix both and re-run the reproducer. I deliberately leave the static
`default` branch on line 93 untouched: it is returned by identity on purpose and the
report only concerns `default_factory`.

```python
print(edit_file(filepath="/testbed/src/skema/fields.py",
                old_str="        if self.default_factory is None:\n            return self.default\n        # cache the factory result so repeated loads stay cheap (#398)\n        if self._default_cache is _UNSET:\n            self._default_cache = self.default_factory()\n        return self._default_cache",
                new_str="        if self.default_factory is None:\n            return self.default\n        # the factory must run on every load: caching its result would share a\n        # single (possibly mutable) object across every load of the schema.\n        return self.default_factory()"))
print(edit_file(filepath="/testbed/src/skema/fields.py",
                old_str="        self.schema = schema\n        self._defaults = None",
                new_str="        self.schema = schema"))
print(edit_file(filepath="/testbed/src/skema/fields.py",
                old_str="        if self._defaults is None:\n            self._defaults = self.schema._collect_defaults()\n        data = dict(self._defaults)",
                new_str="        # recomputed on every call: a cached mapping would be copied shallowly\n        # and leak the inner factory-built values between loads.\n        data = self.schema._collect_defaults()"))
print(run_command(command="python /tmp/agent/repro.py", workdir="/testbed"))
```<end_code>

Observation:
/testbed/src/skema/fields.py:92 edited (1 replacement)
/testbed/src/skema/fields.py:300 edited (1 replacement)
/testbed/src/skema/fields.py:305 edited (1 replacement)
stdout:
flat   b = [] | shared: False
nested d = [] | shared: False
stderr:
exit_code: 0

Step 3

Thought: Both scenarios are fixed. Before returning I check the neighbouring behaviours
my patch could have broken — a static `default` must still come back by identity, the
factory must not run when a value is supplied, and `required` must still raise — and I
confirm `_collect_defaults` builds a fresh dict, since my `Nested` change now mutates
its return value directly. Then I run the evaluation script.

```python
print(run_command(command="cat > /tmp/agent/check.py <<'PY'\nfrom skema import Schema, fields\n\ncalls = []\ndef factory():\n    calls.append(1)\n    return []\n\nsentinel = object()\n\nclass S(Schema):\n    a = fields.Raw(default=sentinel)\n    b = fields.List(fields.Str(), default_factory=factory)\n\nprint(\"identity default:\", S.load({})[\"a\"] is sentinel)\nS.load({\"b\": [\"v\"]})\nprint(\"factory skipped :\", len(calls) == 0)\nprint(\"fresh mapping   :\", S._collect_defaults() is not S._collect_defaults())\n\nclass R(Schema):\n    x = fields.Str(required=True)\ntry:\n    R.load({})\n    print(\"required        : NO RAISE (regression)\")\nexcept Exception as e:\n    print(\"required        :\", type(e).__name__)\nPY && python /tmp/agent/check.py", workdir="/testbed"))
print(run_tests())
```<end_code>

Observation:
stdout:
identity default: True
factory skipped : True
fresh mapping   : True
required        : ValidationError
stderr:
exit_code: 0

>>>>> Start Test Output
tests/test_fields.py::test_default_factory_is_called PASSED
tests/test_fields.py::test_default_factory_not_shared_between_loads PASSED
tests/test_fields.py::test_default_factory_not_shared_through_nested PASSED
tests/test_fields.py::test_missing_required_field PASSED
468 passed, 9 skipped in 6.12s
>>>>> End Test Output

Step 4

Thought: All tests pass, both root causes are addressed, and my scratch files live under
/tmp/agent so they are outside the repository and cannot appear in the diff. The edits
are left uncommitted on purpose, since get_patch() diffs the working tree against the
base commit — committing them would produce an empty patch. I assert the patch is
non-empty before returning it, so a silently failed edit surfaces as an error instead of
an empty submission.

```python
patch = get_patch()
assert patch.strip(), "empty patch: no working-tree change was recorded"
final_answer(patch)
```<end_code>
"""

MBPP_PROMPT_EXEMPLE = r'''Task:
task_definition: Return the smallest absolute value in a list of integers.
function_definition: def smallest_abs(a):
test_list: assert smallest_abs([3, -1, 5]) == 1
assert smallest_abs([-5, 2]) == 2
Thought: Smallest absolute value means I take the minimum, then its absolute value. Let me set up the first case.
Code:
```python
print(abs(min([-5, 2])))
```<end_code>
Observation: 5
Thought: Expected 2, got 5. `min` picks -5 because it is the smallest signed value, and abs only runs afterwards. I must map abs over the list first, then take the minimum. test_list never has only negative numbers, but the task covers them, so I add my own assert for that case. I call final_answer right after the asserts: it only runs if they all pass.
Code:
```python
def smallest_abs(a):
    return min(map(abs,a))
assert smallest_abs([3, -1, 5]) == 1, 'smallest_abs([3, -1, 5]) == 1'
assert smallest_abs([-5, 2]) == 2, 'smallest_abs([-5, 2]) == 2'
assert smallest_abs([-4, -9]) == 4, 'smallest_abs([-4, -9]) == 4'
final_answer(r"""def smallest_abs(a):
    return min(map(abs,a))""")
```<end_code>
'''
