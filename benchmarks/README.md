# Benchmark backing data

The raw data behind [BENCHMARK_REPORT.md](../BENCHMARK_REPORT.md): one
directory per campaign, named as in the report.

```
benchmarks/
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

- **run9 to run54**: the `reel` and `metrics` fields of `RESUME.json` are the
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
