# Benchmark backing data

The raw data behind [BENCHMARK_REPORT.md](../BENCHMARK_REPORT.md): one
directory per campaign, named as in the report.

```
benchmarks/
├── swebench/runN/    same layout, SWE-bench tasks (see the end of this file)
└── mbpp/
    └── runN/
        ├── META.txt          model, provider, task set, commit, start/end time
        ├── RESUME.json       one line per task: claimed and checked result, tokens, time
        ├── task_XX.json      the task given to the agent (moulinette dump)
        ├── solution_XX.json  the agent's output, as read by the checker
        └── logs/             agent stdout/stderr and checker output
```

`runN/task_XX.json` and `runN/solution_XX.json` go together: `XX` is the
position of the task in the run, not its MBPP id (the id is in both files).

## Checking a solution

```
cd moulinette
uv run moulinette_eval validate mbpp ../benchmarks/mbpp/run15/task_01.json \
    ../benchmarks/mbpp/run15/solution_01.json
```

Docker must be running, with the `python:3.11-slim` image available. With
rootless Docker, the checker needs `DOCKER_HOST` set to the rootless socket
(e.g. `unix:///run/user/$UID/docker.sock`); a missing image makes every
solution FAIL without any error in the checker's output.

## Which verdict is authoritative

- **run9 to run64**: the `reel` and `metrics` fields of `RESUME.json` are the
  checker's verdicts; its full output is in `logs/validate_XX.txt`.
- **run5 to run8**: these runs were first checked by running `test_list`
  locally, and `RESUME.json` keeps that verdict. They were re-validated with
  the checker on 2026-10-02, output in `logs/checker_2026-10-02_XX.txt`; the
  report uses those results. The only difference is `run7/task_06` (MBPP
  400): passed locally, **failed** by the checker on the hidden test.

The log files of run5 to run8 come from an earlier campaign script:
`run_XX.out` / `run_XX.err` (agent stdout/stderr), `metrics_XX.txt`,
`timings.txt`, `quota.txt`, and for run5 and run8 a first checker output in
`validate_XX.txt`. From run9 on, the agent's stdout and stderr are
in `logs/agent_XX.log`; since run12, every LLM retry is logged there with its
cause (`LLM retry N on step S: <cause>; waiting X.Xs`).

From run27 on, `RESUME.json` also has a `fallback` field: how many times the
task switched to a fallback model, each switch being logged as `LLM fallback
on step S: <cause>; switching to <model> at <url>`. `META.txt` has an
`exemple_mbpp` field: `une-ligne` (one-line `final_answer` in the prompt's
MBPP example) or `multiligne` (multi-line, ablation E of the report).

`run39` and `run40` asked for NVIDIA `nemotron-3-super`, retired that
morning: every task got HTTP 410 and was done by the fallback model, Groq
`gpt-oss-120b`. `META.txt` names the requested model; the `model_name` of
each step names the model that answered.

From run41 on, `RESUME.json` has a `from_reasoning` field: how many answers
the client took from the reasoning because `content` was empty (logged as
`LLM content empty on step S: answer taken from the reasoning`). The token
totals of run41 on include the rejected responses; earlier ones do not.

From run45 on, the agent is connected to the MBPP MCP server
(`mcp_tools_mbpp.py`): the sandbox manual is in the system prompt and
`run_tests()` can be called. `META.txt` has an `mcp` field, and
`exemple_mbpp=multiligne-r` means the prompt's MBPP example submits with
`final_answer(r"""...""")`. `RESUME.json` has a `run_tests` field: the
number of steps whose code called `run_tests(`. run45 to run54 were all
re-validated once the campaign was over: the checker's image was missing
for the first tasks.

From run55 on (`exemple_mbpp=run_tests`), the MBPP prompt no longer
asks for asserts: the model keeps its solution in a variable, checks it
with `run_tests(code=solution)` (run in the sandbox by the MCP server)
and calls `final_answer(solution)` in the same block only if every test
passes. The agent refuses to start without its MCP server.

## SWE-bench runs

`swebench/run1` to `run5` (2026-10-04) hold one model each on the same
three tasks (`task_01` `sympy__sympy-14711`, `task_02`
`sympy__sympy-13480`, `task_03` `pydata__xarray-4629`), dumped once with
`moulinette_eval dump swebench --task_id …`. Every verdict comes from
`moulinette_eval validate swebench`, output in `logs/validate_XX.txt`; it
needs a regular Docker daemon (with rootless Docker the checker fails to
copy the patch into the container, on `lchown`). The checker writes
`/tmp/patch.diff` and `/tmp/eval.sh`, so two SWE-bench validations must
not run at the same time.

`RESUME.json` has the MBPP fields, plus `resolution` (the checker's
status, `RESOLVED_FULL` for a pass), `wall` (seconds from the agent's start
to its exit, container set-up included; `sec` is the agent's own
`total_time_seconds`), `edit_file` and `get_patch` (calls in the steps'
code) and `models` (the models that answered). The last line of each
`logs/agent_XX.log` gives the agent's exit code and `wall`.

`run5` (Qwen) has only `task_02` and `task_03` so far: `task_01` waits for
the OpenRouter free quota. Its `task_02` was run twice, the second run
overwriting the first; `META.txt` records the first run's figures.
