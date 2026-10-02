# Benchmark Report

> **Status — 2026-10-02.** The MBPP part is complete and backed by the runs
> listed in [Backing data](#backing-data). The SWE-bench part is **pending**:
> the MCP tools are not callable from the sandbox yet, so no SWE-bench task can
> be solved. The SWE-bench sections keep the structure required by the subject
> and will be filled once the tools are wired.

## 1. Setup

### 1.1 Agent under test

A Thought → Code → Observation loop (`core/agent/loop.py`). Each turn, the
first ```` ```python ```` block of the model's answer runs in the sandbox, and
its output is sent back as the next observation. The task ends when the code
calls `final_answer()`, or when a benchmark limit is reached:

| Benchmark | Iterations | Input tokens (cumulative) | Output tokens (cumulative) | Time |
|---|---|---|---|---|
| MBPP | 10 | 6,000 | 1,500 | 120 s |
| SWE-bench | 30 | 300,000 | 10,000 | 900 s |

Every LLM call has its own 30 s deadline, and transient errors are retried up
to 4 times. Two checks on the final answer are part of what is measured below:

- **since 2026-10-01**, an MBPP `final_answer` is run **alone** against
  `test_imports` + `test_list` before being accepted, exactly as the checker
  will run it; a failing answer is refused and the error shown to the model;
- **since 2026-10-02**, the loop refuses to send a request that would push the
  cumulative input over the limit, and a refused answer that is not valid
  Python comes with its `SyntaxError` and how to fix it (ablation D).

### 1.2 How results are judged

Every MBPP verdict in this report comes from the official checker:

```
moulinette_eval validate mbpp <task.json> <solution.json>
```

run in Docker (`python:3.11-slim`). It reports **Correctness** (the submitted
code against all the tests of the task, including one test hidden from the
agent) and **Metrics** (the `solution.json` totals against the limits above).
A task counts as passed when Correctness is `PASSED`. Runs 5 to 8 were first
checked by running `test_list` locally; they were all re-validated with the
checker on 2026-10-02, which turns `run7` from 9/10 into **8/10** (MBPP 400
fails the hidden test).

### 1.3 Tasks

| Set | Dump | MBPP task ids |
|---|---|---|
| **A** | `moulinette_eval dump mbpp --seed 1` … `10` | 127, 80, 252, 251, 264, 94, 305, 247, 457, 65 |
| **B** | seeds 11 … 20 | 451, 462, 266, 108, 234, 400, 431, 168, 71, 138 |
| C | seeds 21 … 31 (`run8` only) | 160, 130, 283, 413, 410, 230, 465, 113, 91, 19 |

Why these tasks: seeded dumps are reproducible, the three sets do not overlap,
and **the same task files are copied into every run directory**, so every
comparison below is made on identical inputs. The dump gives the agent
`test_list` without its first test, which the checker keeps hidden: this is
what makes MBPP 400 fail for almost every model (section 2.1). Sets A and B
are used for every model comparison; set C was used once.

### 1.4 Models and providers

| Provider | Model | Free access | MBPP runs |
|---|---|---|---|
| Groq | `openai/gpt-oss-120b` | free tier, 8,000 tokens/min | run6, 7, 9, 10, 12, 13, 14 |
| OpenRouter | `nvidia/nemotron-3-super-120b-a12b:free` | `:free` models, 50 requests/day per account | run5 |
| OpenRouter | `minimax/minimax-m3:free` | idem (no longer free since 2026-10-01) | run8 |
| OpenRouter | `qwen/qwen3.8-27b:free` | idem | run11 |
| NVIDIA Build | `nvidia/nemotron-3-super-120b-a12b` | free API, 40 requests/min | run15, 16 |
| NVIDIA Build | `nvidia/nemotron-3-ultra-550b-a55b` | idem | run17, 18 |
| Mistral | `codestral-2508` | monthly free credits | run19, 20, 25, 26 |
| Mistral | `ministral-14b-2512` | idem | run21, 22 |
| Mistral | `ministral-8b-2512` | idem | run23, 24 |

The two NVIDIA models run with reasoning disabled
(`chat_template_kwargs` in `configs/models.json`): with reasoning on,
`nemotron-3-super` needed 17 s and hit the 1,500-token output cap on a single
SWE prompt, against 5 s without.

**Providers considered and excluded** (checked 2026-10-01/02): Cerebras and
Together AI require a payment method or a credit purchase, which the subject
forbids; Gemini's free tier allows about 20 requests/day; 17 of the 19 NVIDIA
models probed were too slow (over 120 s), incompatible with a text protocol
(tool calls inside the reasoning, empty `content`), degenerate, or not served
(HTTP 404). Groq is kept for MBPP but cannot be used for SWE-bench: its free
tier rejects any request above 8,000 tokens (HTTP 413).

## 2. Results

### 2.1 MBPP — model comparison

Same 20 tasks (sets A + B), same agent: commit `4c8d206` for Groq, `94539e7`
for the others (the commits in between only touch the SWE-bench prompt and
the per-model request settings, empty for Groq). "Codestral, fixed loop" is the same model rerun with
the two loop fixes of ablation D. Times are the agent's wall-clock time per
task.

| Model | Pass | Valid metrics | Iterations (mean) | Input tokens (mean) | Output tokens (mean) | Time per task (mean / max) | Total time |
|---|---|---|---|---|---|---|---|
| Groq `gpt-oss-120b` | **16/20** | 20/20 | 1.05 | 1,068 | 534 | **5.7 s** / 27.7 s | 114 s |
| NVIDIA `nemotron-3-super` | 15/20 | 20/20 | 1.10 | 1,311 | 789 | 16.8 s / 79.9 s | 336 s |
| NVIDIA `nemotron-3-ultra` | 14/20 | 19/20 | 1.35 | 1,659 | 414 | 34.9 s / 94.2 s | 697 s |
| Mistral `codestral-2508` | 11/20 | 17/20 | 1.90 | 3,126 | 888 | 8.8 s / 17.3 s | 177 s |
| Mistral `codestral-2508`, fixed loop | **17/20** | 20/20 | 1.90 | 2,099 | 635 | 6.1 s / 17.5 s | 121 s |
| Mistral `ministral-14b-2512` | 15/20 | 20/20 | 1.05 | 1,317 | 780 | 8.1 s / 21.5 s | 162 s |
| Mistral `ministral-8b-2512` | 15/20 | 19/20 | 1.10 | 1,464 | 689 | 8.2 s / 26.7 s | 163 s |

Per task — **P** pass / F fail, followed by the iterations used; ⚠ metrics
invalid (cumulative input above 6,000); † the agent reported success but the
checker failed the solution:

| MBPP task | Groq `gpt-oss-120b` | `nemotron-3-super` | `nemotron-3-ultra` | `codestral` | `codestral`, fixed loop | `ministral-14b` | `ministral-8b` |
|---|---|---|---|---|---|---|---|
| 127 | **P** 1 | **P** 1 | **P** 1 | **P** 2 | **P** 2 | **P** 1 | **P** 1 |
| 80 | F 0 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 252 | F 2 | **P** 1 | F 0 | **P** 2 | **P** 1 | **P** 2 | **P** 1 |
| 251 | **P** 1 | F 2 | **P** 2 | **P** 2 | **P** 2 | **P** 1 | **P** 2 |
| 264 | **P** 2 | **P** 1 | F 3 † | F 4 ⚠ | F 5 | **P** 1 | **P** 1 |
| 94 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 2 | **P** 1 |
| 305 | **P** 1 | **P** 1 | **P** 1 | F 3 | **P** 2 | **P** 1 | F 1 |
| 247 | **P** 1 | F 1 | **P** 2 | F 3 ⚠ | **P** 2 | F 0 | **P** 1 |
| 457 | **P** 1 | **P** 1 | **P** 2 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 65 | **P** 1 | **P** 3 | **P** 1 | F 3 | **P** 3 | **P** 1 | **P** 1 |
| 451 | **P** 2 | **P** 2 | **P** 1 | **P** 2 | **P** 2 | **P** 1 | **P** 1 |
| 462 | F 0 | F 0 | F 2 ⚠ | F 2 | F 1 | F 1 | F 2 ⚠ |
| 266 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 108 | **P** 1 | F 0 | F 2 | F 1 | **P** 1 | F 1 | F 1 |
| 234 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 400 | F 1 † | F 1 † | F 1 † | F 2 | **P** 2 | F 1 † | F 1 † |
| 431 | **P** 1 | **P** 1 | **P** 3 | **P** 1 | **P** 2 | **P** 1 | **P** 1 |
| 168 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 2 | **P** 1 | **P** 1 |
| 71 | **P** 1 | **P** 1 | **P** 1 | F 2 | **P** 2 | **P** 2 | **P** 2 |
| 138 | **P** 1 | **P** 1 | F 0 | F 3 ⚠ | F 4 | F 0 | F 0 |
| **Total** | **16/20** | **15/20** | **14/20** | **11/20** | **17/20** | **15/20** | **15/20** |

Two tasks fail for nearly every model, for reasons that do not depend on the
model's reasoning:

- **MBPP 462** fails for all: its `test_list` alone is about 1,000 tokens, and
  the answers hit the 1,500-token cumulative output cap;
- **MBPP 400** fails the hidden test ("order irrespective") for all but one
  run, and in 5 of them the agent reported a success the checker rejected.

### 2.2 MBPP — earlier campaigns

These runs measured the agent while it was being built: the agent version
changes from one line to the next, so they are not a model comparison. Times
are the sum of the per-task agent times.

| Run | Date / commit | Model | Set | Pass | Valid metrics | Iterations | Input (mean) | Output (mean) | Total time |
|---|---|---|---|---|---|---|---|---|---|
| run5 | 2026-09-02 | OpenRouter `nemotron-3-super:free` | A | 4/10 | 9/10 | 1.20 | 1,357 | 1,009 | 496 s |
| run6 | 2026-09-02 | Groq `gpt-oss-120b` | A | **10/10** | 10/10 | 1.10 | 890 | 496 | 48 s |
| run7 | 2026-09-02 | Groq `gpt-oss-120b` | B | 8/10 | 10/10 | 1.20 | 1,071 | 508 | 53 s |
| run8 | 2026-09-03 | OpenRouter `minimax-m3:free` | C | 9/10 | 10/10 | 2.70 | 3,415 | 722 | 274 s |
| run9 | `9c4754a` | Groq `gpt-oss-120b` | A | **10/10** | 10/10 | 1.50 | 1,274 | 602 | 42 s |
| run10 | `9c4754a` | Groq `gpt-oss-120b` | B | 7/10 | 10/10 | 1.50 | 1,477 | 564 | 137 s |
| run11 | `9c4754a` | OpenRouter `qwen3.8-27b:free` | A | 7/10 | 9/10 | 1.20 | 1,035 | 443 | 520 s |
| run12 | `2f7b56b` + prompt change | Groq `gpt-oss-120b` | B | 6/10 | 10/10 | 0.80 | 850 | 503 | 123 s |
| run13 | `4c8d206` | Groq `gpt-oss-120b` | B | 8/10 | 10/10 | 1.00 | 1,032 | 558 | 56 s |
| run14 | `4c8d206` | Groq `gpt-oss-120b` | A | 8/10 | 10/10 | 1.10 | 1,105 | 511 | 59 s |

`run5` and `run6` used the **same tasks and the same agent**: 4/10 on
OpenRouter's free `nemotron-3-super` against 10/10 on Groq's `gpt-oss-120b`.
Four of the six `run5` failures hit the 1,500-token output cap.

### 2.3 SWE-bench — *to be completed*

Planned tasks: `sympy__sympy-14711`, `sympy__sympy-13480`,
`pydata__xarray-4629`. Planned models: the five of section 2.1 except Groq
(HTTP 413 above 8,000 tokens per request).

| Model | Task | Pass/Fail | Iterations | Input tokens | Output tokens | Wall-clock |
|---|---|---|---|---|---|---|
| | | | | | | |

## 3. Provider reliability

### 3.1 MBPP runs

An *attempt* is one HTTP request, retries included. *Availability* is the
share of attempts that got a usable answer. *Response time* is measured on
answered requests only (a failed attempt can last up to the 30 s deadline).
A task is *lost* when 5 attempts in a row fail.

| Provider / model | Runs | Tasks | Attempts | Retries | Availability | Response time (mean / median / max) | Tasks lost |
|---|---|---|---|---|---|---|---|
| Groq `gpt-oss-120b` | 6, 7, 9, 10, 12–14 | 70 | 146 | 60 | 59 % | **1.5 / 1.2 / 5.1 s** | 4 |
| OpenRouter `nemotron-3-super:free` | 5 | 10 | 29 | 13 | 55 % | 15.9 / 16.2 / 29.1 s | 0 |
| OpenRouter `minimax-m3:free` | 8 | 10 | 29 | 1 | 97 % | 8.5 / 5.9 / 25.5 s | 0 |
| OpenRouter `qwen3.8-27b:free` | 11 | 10 | 34 | 22 | 35 % | 11.3 / 9.5 / 27.0 s | 3 |
| NVIDIA `nemotron-3-super` | 15, 16 | 20 | 30 | 4 | 87 % | 7.5 / 6.1 / 20.1 s | 0 |
| NVIDIA `nemotron-3-ultra` | 17, 18 | 20 | 55 | 26 | 53 % | 11.4 / 10.5 / 22.8 s | 2 |
| Mistral `codestral-2508` | 19, 20, 25, 26 | 40 | 86 | 0 | **100 %** | 3.4 / 3.4 / 10.2 s | 0 |
| Mistral `ministral-14b-2512` | 21, 22 | 20 | 25 | 0 | **100 %** | 6.5 / 4.6 / 21.5 s | 0 |
| Mistral `ministral-8b-2512` | 23, 24 | 20 | 26 | 0 | **100 %** | 6.3 / 4.7 / 23.7 s | 0 |

Causes, where the agent logged them (from run12 on, one line per retry on
stderr):

- **Groq**: all 27 logged retries of run12–14 are an HTTP 200 answer with an
  empty `content` field, the model having put its whole answer in `reasoning`.
  Fast when it answers, but four answers in ten are unusable;
- **NVIDIA `nemotron-3-ultra`**: 18 × HTTP 503 "Service temporarily
  overloaded" and 6 × the 30 s deadline;
  **`nemotron-3-super`**: 4 × the 30 s deadline;
- **OpenRouter**: causes were not logged at the time. Bursts of 429
  "temporarily rate-limited upstream" were frequent in our OpenRouter tests,
  on top of the 50 requests/day account quota;
- **Mistral**: no failure at all in 137 attempts.

### 3.2 SWE-bench — *to be completed*

Preliminary latency on a single 56,000-token request (synthetic history,
2026-10-02): `nemotron-3-super` 44.4 / 13.2 / 8.8 s over three tries,
`nemotron-3-ultra` 15.6 / 9.9 / 8.0 s, `codestral-2508` 2.2 s,
`ministral-14b-2512` 4.1 s, `ministral-8b-2512` 6.0 s. One NVIDIA answer in
six exceeds the 30 s per-call deadline, which has to be raised for SWE-bench.

## 4. Intermediary metrics

### 4.1 MBPP

The subject's metrics are defined for SWE-bench. The one that carries over to
MBPP is **submission discipline**: the number of iterations between the first
step where the agent's own asserts run without error and the accepted
`final_answer` (0 is ideal). Two related counts complete it:

- a **blind submission** is a `final_answer` accepted although no assert has
  ever run (measured on the AST of the executed code: asserts written *inside*
  the answer string do not count);
- a **loop refusal** is a `final_answer` refused by the loop's own checks
  (invalid Python, or failing `test_list` when run alone).

| Model (runs) | Submitted | Blind | Discipline = 0 | Discipline (mean) | Loop refusals | False successes |
|---|---|---|---|---|---|---|
| Groq, prompt of 2026-09-02 (run6, 7) | 19 | **6** | 11/13 | 0.23 | 1 | 1 |
| Groq, prompt `9c4754a` (run9, 10) | 18 | **5** | 5/13 | 0.62 | 0 | 1 |
| Groq, asserts + `final_answer` in one block (run12) | 8 | **0** | 8/8 | 0.00 | 0 | 2 |
| Groq, + loop verification (run13, 14) | 17 | **0** | 16/17 | 0.06 | 2 | 1 |
| NVIDIA `nemotron-3-super` (run15, 16) | 16 | 0 | 15/16 | 0.06 | 3 | 1 |
| NVIDIA `nemotron-3-ultra` (run17, 18) | 16 | 0 | 15/16 | 0.12 | 1 | 2 |
| Mistral `codestral-2508` (run19, 20) | 11 | 0 | 10/11 | 0.09 | **9** | 0 |
| Mistral `codestral-2508`, fixed loop (run25, 26) | 17 | 0 | 10/17 | 0.41 | **9** | 0 |
| Mistral `ministral-14b-2512` (run21, 22) | 16 | 0 | 16/16 | 0.00 | 0 | 1 |
| Mistral `ministral-8b-2512` (run23, 24) | 16 | 0 | 16/16 | 0.00 | 0 | 1 |

Blind submissions disappeared when the prompt started asking for the asserts
and `final_answer()` in the same code block: since then `final_answer` only
runs if every assert before it passed. In 2026-09-02's `run6`, MBPP 127 had
been "solved" with the asserts written inside the answer string: they never
ran. `codestral`'s higher discipline after the fix is a side effect of the
fix: a refused answer is corrected one iteration later.

### 4.2 SWE-bench — *to be completed*

To be measured on the SWE-bench runs: the step at which the agent first reads
or edits the file of the final patch (exploration efficiency), and the
iterations between the first passing test run and `final_answer`
(submission discipline).

## 5. Ablation studies

All on MBPP, same task files, same model, one change at a time.

| | Change | Model, tasks | Before | After |
|---|---|---|---|---|
| A | Prompt and feedback messages rewritten (`9c4754a`) | Groq `gpt-oss-120b`, A + B | run6 + 7: **18/20**, input 981 tokens/task, 6 blind | run9 + 10: **17/20**, input 1,375 tokens/task, 5 blind |
| B | Asserts and `final_answer()` in the same code block (prompt) | Groq `gpt-oss-120b`, B | run10: **7/10**, 2 blind, input 1,477 | run12: **6/10**, 0 blind, input 850 |
| C | The loop runs the answer alone against `test_list` before accepting it | Groq `gpt-oss-120b`, B | run12: **6/10**, 2 false successes | run13: **8/10**, 1 false success |
| D | Input limit checked before sending + `SyntaxError` explained on refusal | Mistral `codestral-2508`, A + B | run19 + 20: **11/20**, 17/20 valid | run25 + 26: **17/20**, 20/20 valid |

- **A** cost 40 % more input for no gain in pass rate. Its value was to make
  the model run its tests: the one-iteration successes of the old prompt were
  partly blind submissions.
- **B** removed blind submissions but created a new failure: MBPP 451 was
  tested with `import re` in the block, then submitted without it.
- **C** fixed exactly that case: the refused answer was resubmitted with its
  import and passed (run13). The remaining false success is MBPP 400, whose
  failing test is the hidden one.
- **D**: `codestral` copied the one-line `final_answer("def f(a): ...")` of the
  prompt's example onto multi-statement functions joined with `;`, which is
  not valid Python. The old refusal did not say why, so the model repeated the
  mistake until the output cap (5 of its 9 failures). With the explicit
  message it fixes the answer on the next iteration (6 submissions switched
  to a triple-quoted string). The five invalid metrics of the campaign were
  all cumulative inputs of 6,163 to 7,513 tokens, caused by a request already
  sent when the loop noticed: none left after the fix.

Caveat: each task was run **once** per configuration. On 10 to 20 tasks, a
difference of one or two tasks is within noise; only B's blind submissions
(2 → 0), C's MBPP 451 and D's invalid metrics (3 → 0) are clear-cut.

SWE-bench ablation — *to be completed*.

## 6. Conclusions

### 6.1 MBPP (provisional)

- **Groq `gpt-oss-120b`** has the best score (16/20) and by far the shortest
  answer time (1.2 s median), but 41 % of its attempts are retries (empty
  `content`), and it cannot be used for SWE-bench (HTTP 413 above 8,000
  tokens).
- **Mistral `ministral-14b-2512`** is the selected candidate for MBPP: 15/20,
  every metric valid, no retry in 25 attempts, 8.1 s per task.
  **NVIDIA `nemotron-3-super`** is the fallback: same score, twice as slow, 4
  timeouts in 30 attempts.
- **Mistral `codestral-2508`** went from 11/20 to 17/20 with the loop fixes,
  the best score of this report, on a single run that remains to be confirmed.
- **Disregarded**: NVIDIA `nemotron-3-ultra` (26 retries in 55 attempts, 2
  tasks lost, 35 s per task); OpenRouter's `:free` models (50 requests/day per
  account, 3 tasks lost to upstream 429 in run11, 4/10 for `nemotron-3-super`
  in run5); `minimax-m3`, no longer free.
- On these 20 tasks the ceiling is about 18/20: MBPP 462 (output cap) and
  MBPP 400 (hidden test) defeat nearly every model.

### 6.2 SWE-bench — *to be completed*

## Backing data

All runs are versioned under [`benchmarks/mbpp/`](benchmarks/mbpp/), one
directory per run (`benchmarks/mbpp/runN/`). Each holds `META.txt` (model,
provider, task set, commit, start and end times), `RESUME.json` (one line per
task), `task_XX.json`, `solution_XX.json` and `logs/` (agent stdout/stderr,
checker output). [`benchmarks/README.md`](benchmarks/README.md) describes the
files and which checker output is authoritative for each run.

| Runs | Model |
|---|---|
| run5 | OpenRouter `nemotron-3-super:free` |
| run6, run7, run9, run10, run12, run13, run14 | Groq `gpt-oss-120b` |
| run8 | OpenRouter `minimax-m3:free` |
| run11 | OpenRouter `qwen3.8-27b:free` |
| run15, run16 | NVIDIA `nemotron-3-super` |
| run17, run18 | NVIDIA `nemotron-3-ultra` |
| run19, run20, run25, run26 | Mistral `codestral-2508` |
| run21, run22 | Mistral `ministral-14b-2512` |
| run23, run24 | Mistral `ministral-8b-2512` |

To rerun one task and check it:

```
uv run python -m agent_mbpp --task-file benchmarks/mbpp/run15/task_01.json \
    --output solution.json --model-name nvidia/nemotron-3-super-120b-a12b \
    --provider-url https://integrate.api.nvidia.com/v1
cd moulinette && uv run moulinette_eval validate mbpp \
    ../benchmarks/mbpp/run15/task_01.json ../solution.json
```
