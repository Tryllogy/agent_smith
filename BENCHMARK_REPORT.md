# Benchmark Report

> **Status — 2026-10-06.** Complete. The MBPP part is backed by the runs
> listed in [Backing data](#backing-data). The SWE-bench part rests on two
> campaigns: on 2026-10-04, **five models × the three recommended tasks**
> with the official checker (section 2.3); on 2026-10-06, **five models ×
> the six tasks the exam can draw, run twice** (sections 2.4 and 5,
> ablation H), graded by the checker's own grading code because the
> machine's rootless Docker cannot run `validate swebench` (section 1.2).
> Four mock exams (section 2.5) show the agent as the evaluators will run
> it. Each model runs each task once per campaign arm: section 5 shows
> that this is too few to rank the models, and says what it measures
> instead.

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

Every LLM call has its own deadline (30 s for MBPP; 60 s for SWE-bench since
2026-10-02), and transient errors are retried up to 4 times. **Since
2026-10-02**, a task whose model fails permanently, or 5 times in a row, is
not lost any more: it continues on the next model of `configs/fallback.json`
(for MBPP: Groq `gpt-oss-120b`, then Mistral `ministral-14b-2512`, then
NVIDIA `nemotron-3-super` until NVIDIA retired it on 2026-10-03,
`nemotron-3-ultra` since; the requested model is skipped). Tasks finished
by a fallback model are marked ↪ below. Two checks on the final answer are
part of what is measured below:

- **since 2026-10-01**, an MBPP `final_answer` is run **alone** against
  `test_imports` + `test_list` before being accepted, exactly as the checker
  will run it; a failing answer is refused and the error shown to the model;
- **since 2026-10-02**, the loop refuses to send a request that would push the
  cumulative input over the limit, and a refused answer that is not valid
  Python comes with its `SyntaxError` and how to fix it (ablation D).

**Since 2026-10-03**, the MBPP example of the prompt submits its function on
several lines, in a triple-quoted string, instead of a one-line
`final_answer("def f(a): ...")` (ablation E).

**Since 2026-10-04** (run45 to run54), the agent starts the MBPP MCP server
(`mcp_tools_mbpp.py`) for each task: the sandbox manual, generated from the
server's tool schemas, is in the system prompt, and the server's
`run_tests()` can be called from the sandbox. The manual adds about 100
input tokens to every turn (first-turn input 888 → 983 tokens for Groq,
859 → 959 for the Mistral models). The same day, the MBPP example switched
to a raw string, `final_answer(r"""...""")`: in a plain triple-quoted
string, a regex backreference `\1` copied from the tested code became the
character `\x01` (MBPP 396, `codestral-2508`: the visible tests passed, the
hidden one failed).

**Later the same day** (run55 to run64, ablation G), the MBPP prompt
stopped asking for asserts. The server's tool became `run_tests(code)`: it
takes the candidate as an argument and runs each assertion of `test_list`
in the sandbox, under the same restrictions as the model's code (before,
it read a file whose path the model was never told, and ran it with an
unrestricted `python`). The prompt and its example now keep the solution
in a variable, print the report of `run_tests(code=solution)`, and call
`final_answer(solution)` in the same block only if every test passes: the
string tested is the string submitted. Since the prompt relies on that
tool, the MBPP agent now refuses to start without its MCP server.

**Three client changes of 2026-10-03**, measured by run41 to run44 only
(ablation F):

- an empty `content` is no longer always retried: when the reasoning holds a
  complete code block, it is used as the answer (section 3.1 explains why
  this rescues only a minority of Groq's empty answers);
- the tokens of a response the client rejects (empty `content`, missing
  `message`) are now counted, in the totals and in the step. **Before, they
  were not**, so the token figures of run5 to run40 omit them. Groq is the
  provider concerned: nearly all its failures are such answers (section
  3.1). Mistral had no failure, NVIDIA's were HTTP 503 and timeouts, which
  carry no token count, and OpenRouter's causes were not logged. **Groq's
  input and output tokens are therefore understated up to run40**;
- Groq `gpt-oss-120b` no longer receives the stop sequence
  (`"send_stop": false` in `configs/models.json`): the provider applied it to
  the reasoning too and cut the answer before it was written (section 3.1).
  The client cuts the answer at `<end_code>` itself.

**Since 2026-10-05** (commit `89b76b0`, after the mock exam of section 2.5;
no MBPP run of this report used it; the second SWE-bench campaign, section
2.4, runs with it and with everything below):

- the SWE-bench prompt says that the exit code `run_tests()` prints is the
  evaluation script's, whose last command restores the test files, so it
  is 0 even when tests fail: the model must judge the tests by what is
  printed between `>>>>> Start Test Output` and `>>>>> End Test Output`,
  and never call a fix verified while a test fails there. The last step of
  the example now reads the test summary. The SWE-bench system prompt grows
  by 486 characters, about 150 tokens per turn;
- the MBPP `run_tests` tool takes an optional `test_list`, which replaces
  the task's (the evaluators' sandbox test calls it that way), and its
  report starts with a verdict line, `success: true (2 of 2 tests passed)`.
  The example submits when the report starts with `success: true`, instead
  of searching it for `FAIL` and `ERROR`, words a test could contain. About
  50 more input tokens per MBPP turn;
- the time limit runs from the agent's start instead of the loop's:
  pulling the task's image and copying `/testbed` now count against
  SWE-bench's 900 s, as they do for the exam script, which times the whole
  process.
- a step whose code **and** output are identical to an earlier step's now
  ends its observation with a note saying so, and that running it again
  will not change the result. In the versioned runs, that happens 32 times
  in SWE-bench, on 5 tasks including all 4 failures of section 2.3 (11
  identical `edit_file` calls for `codestral` on `sympy-13480`), and 9
  times in MBPP; the same code with another output (tests rerun after an
  edit, 8 cases) is not flagged. The model is told, nothing is stopped.
- `Observation:` is now a stop sequence, next to `<end_code>`. When a model
  closes its block without `<end_code>` and goes on with `Observation:`, it
  invents the outputs and the next steps: in the versioned runs, such
  answers are 5 % of `codestral`'s SWE-bench steps but 42 % of its output
  tokens, and in the 2026-10-05 exam one of them used up the whole 10,000
  output tokens of `scikit-learn-13439`. Rerun once with the stop
  sequence, that task passed (`RESOLVED_FULL` by the checker's grading
  code, 1,459 output tokens);
- `iterations` now counts the turn that ends on a guard after a request,
  so that it always equals the number of steps, as the schema says ("one
  entry per agent iteration"). Before, such a run reported one step more
  than iterations.

Since the evening of 2026-10-05 (commit `5c0fbf3`, after the mock exams
of that day; measured by the second SWE-bench campaign only, and the
second bullet by ablation H):

- on a failed `assert X == Y`, the MBPP `run_tests` report also shows the
  value the function returned, computed in the same sandbox and cut at 200
  characters: `2. FAIL  assert sum_div(12)==16  (got 28)`. All 80 visible
  tests of the versioned MBPP tasks have that form. Only the visible tests
  are concerned, so nothing new about the hidden ones is revealed. The
  prompt's example shows it;
- an `edit_file` call whose `old_str` holds a line that no earlier
  observation (or the task itself) showed is not run: the model is told
  to read those lines first and copy `old_str` from that output. This
  enforces the prompt's rule against reciting code from memory. Replayed
  on the 60 SWE-bench edits of the versioned runs and mock exams, it
  refuses 19: 16 that failed with "old_str not found" and 3 that
  succeeded from memory (`sympy-14711`);
- the repeated-step note now says what to do instead of "change your
  approach": compare the returned value with the expected one (MBPP), or
  read the lines again before editing (SWE-bench). From the third
  identical step, it says the step was repeated again.

Since the evening of 2026-10-06 (after the second campaign; **not
measured by the campaigns**), three changes from section 4.2:

- `"```\n\n"`, a closing fence followed by a blank line, is a third stop
  sequence, so that an answer ends after its first code block; the loop
  gives back the closing fence the provider drops with it. Replayed on
  the 2,139 versioned answers, it cuts 491 of the 565 multi-block answers
  before their second block and 18 % of all output characters, and cuts
  one answer before the end of its first block (a `bash` block placed
  first). A fence followed by a single line break is not caught;
- a SWE-bench `final_answer()` is refused unless it is what `get_patch()`
  returns at that moment (surrounding whitespace aside): a diff typed by
  the model is refused, with a separate message when the repository holds
  no change;
- the refusal of unread edits counts as seen the `new_str` of every
  `edit_file` call whose output reports it done, so that a model can edit
  again a line it wrote itself.

The second SWE-bench campaign (2026-10-06, commit `f27644a`) also runs with
the tool and sandbox changes merged on 2026-10-05 and 2026-10-06: the
SWE-bench `run_tests()` returns only what the evaluation script prints
between its start and end markers, cut from the start when it is long so
that the test summary survives (`8db5195`, `2331b77`); the file tools are
confined to the repository; the task's container is tied to the agent's
process, so that even a `kill -9` removes it (`5f27c08`).

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
fails the hidden test). On 2026-10-04 the rootless Docker daemon used for
the checker had no `python:3.11-slim` image, and every solution came out
FAILED with no error in the checker's output: the image was pulled, and
run45 to run54 were all re-validated once the campaign was over.

Every SWE-bench verdict comes from the same checker:

```
moulinette_eval validate swebench <task.json> <solution.json>
```

It starts a fresh container from the task's image, applies the submitted
patch (`git apply --verbose`, with two fallbacks), runs the task's
evaluation script, and grades the log with SWE-bench's own logic: a task
passes only when the status is `RESOLVED_FULL`, every FAIL_TO_PASS and
PASS_TO_PASS test passing. The rootless Docker of our first machines could
not run it (the patch copy failed on `lchown`); the campaign of 2026-10-04
ran on a machine with a regular Docker daemon, where all 10 submitted
patches were applied by the first method (the 4 failed tasks submitted
none). The checker writes `/tmp/patch.diff` and
`/tmp/eval.sh` at fixed paths, so the campaign script ran the validations
one at a time.

**The second campaign (2026-10-06) ran on rootless Docker**, where
`validate swebench` fails on `lchown` before running any test. Its
verdicts come from **the checker's own grading code, called outside
`moulinette_eval`**: a fresh container from the task's image, the patch
copied in as base64 text instead of a tar archive (the step that fails),
the checker's three apply methods in the same order, the task's
evaluation script, then the checker's functions `get_logs_eval`,
`get_eval_tests_report` and `get_resolution_status` on the log. Only the
copy differs. Run on the 14 solutions of the first campaign, it gives the
official verdict all 14 times (10 `RESOLVED_FULL`, 4 without a patch).
Its output is in `logs/grade_XX.txt`. The metrics are checked against the
checker's SWE-bench limits (`MetricsLimits.swebench_defaults`).

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

SWE-bench tasks, dumped once with `moulinette_eval dump swebench --task_id
…` and copied into every run directory:

| Task | Repository | What is broken |
|---|---|---|
| `sympy__sympy-14711` | sympy | `sum([N.x, 0 * N.x])` raises `TypeError`: `Vector.__add__` refuses the scalar `0` |
| `sympy__sympy-13480` | sympy | `coth(log(tan(x))).subs(x, 2)` raises `NameError`: `cotm` instead of `cothm` |
| `pydata__xarray-4629` | xarray | `merge(..., combine_attrs="override")` returns the first object's `attrs` instead of a copy |

These are the three tasks the subject recommends. All three are in the
checker's exam pool and rated "<15 min fix" in SWE-bench Verified. They come
from two repositories. All three statements point at the code to change:
the `13480` traceback names the file and line, the `4629` title names the
function and the missing copy, and the `14711` traceback goes through
`Vector.__add__`, showing the commented-out line `#if other == 0: return
self` just above the failing call. The `14711` fix is less local, though:
the scalar `0` must be accepted by `__add__` (or `_check_vector`) without
breaking the other operators that rely on the same check.

The second campaign (2026-10-06, section 2.4) adds the three other tasks
of the checker's exam pool (`EXAM_POOL` in `moulinette/swebench/
interact.py`), so that it covers **every task the exam can draw**. They
were taken from the dumps of the mock exams of 2026-10-05, which drew them:

| Task | Repository | What is broken |
|---|---|---|
| `sympy__sympy-18189` | sympy | `diophantine(..., syms=(n, m), permute=True)` returns 1 solution instead of 8: the recursive call drops `permute` |
| `django__django-11066` | django | `RenameContentType._rename()` saves the content type without `using=db`, on the default database |
| `scikit-learn__scikit-learn-13439` | scikit-learn | `len(pipe)` raises `TypeError`: `Pipeline` has no `__len__` |

They differ from the first three in how much the task gives away. The
`hints_text` of `18189` holds the fix itself, as a diff of lines 182–185
(`diophantine(eq, param, permute=permute)`), and the `11066` statement
quotes the faulty line and suggests `using=db`. `13439` is the only task
of the six whose fix is new code (a method to add) rather than a changed
line, and its statement names the class but no line.

### 1.4 Models and providers

| Provider | Model | Free access | MBPP runs |
|---|---|---|---|
| Groq | `openai/gpt-oss-120b` | free tier, 8,000 tokens/min | run6, 7, 9, 10, 12, 13, 14, 27, 28, 31, 32, 41–46, 55, 56; run39, 40 as the fallback |
| OpenRouter | `nvidia/nemotron-3-super-120b-a12b:free` | `:free` models, 50 requests/day per account | run5 |
| OpenRouter | `minimax/minimax-m3:free` | idem (no longer free since 2026-10-01) | run8 |
| OpenRouter | `qwen/qwen3.8-27b:free` | idem | run11 |
| NVIDIA Build | `nvidia/nemotron-3-super-120b-a12b` | free API, 40 requests/min; **retired on 2026-10-03** (HTTP 410) | run15, 16 (run39, 40 attempted) |
| NVIDIA Build | `nvidia/nemotron-3-ultra-550b-a55b` | idem | run17, 18, 53, 54, 63, 64 |
| Mistral | `codestral-2508` | monthly free credits | run19, 20, 25, 26, 29, 30, 33, 34, 47, 48, 57, 58 |
| Mistral | `ministral-14b-2512` | idem | run21, 22, 35, 36, 49, 50, 59, 60 |
| Mistral | `ministral-8b-2512` | idem | run23, 24, 37, 38, 51, 52, 61, 62 |

SWE-bench runs (`benchmarks/swebench/`). First campaign (2026-10-04):
`codestral-2508` run1, `ministral-14b-2512` run2, `ministral-8b-2512` run3,
`nemotron-3-ultra` run4, OpenRouter `qwen/qwen3.8-27b:free` run5. Second
campaign (2026-10-06): the same first four models in run6 to run9, Mistral
`ministral-3b-2512` in run10; ablation H in run11 to run15, same order.

The two NVIDIA models run with reasoning disabled
(`chat_template_kwargs` in `configs/models.json`): with reasoning on,
`nemotron-3-super` needed 17 s and hit the 1,500-token output cap on a single
SWE prompt, against 5 s without. Qwen runs with reasoning disabled too
(`"reasoning": {"enabled": false}`): with it on, a 15,000-token SWE-bench
context produced 2,000 tokens of reasoning and an empty answer, against an
answer in 1.5 s without.

**Providers considered and excluded** (checked 2026-10-01/02): Cerebras and
Together AI require a payment method or a credit purchase, which the subject
forbids; Gemini's free tier allows about 20 requests/day; 17 of the 19 NVIDIA
models probed were too slow (over 120 s), incompatible with a text protocol
(tool calls inside the reasoning, empty `content`), degenerate, or not served
(HTTP 404). Groq is kept for MBPP but cannot be used for SWE-bench: its free
tier rejects any request above 8,000 tokens (HTTP 413).

**The fifth SWE-bench model** (probed on 2026-10-04, after NVIDIA retired
`nemotron-3-super`), on the real SWE-bench prompt and on a 15,000-token
context:

- **Mistral**: Devstral (`mistral-vibe-cli-*`), Magistral, Mistral Medium
  and Small are closed on our free account (`x-ratelimit-limit-req-minute:
  0`). `codestral-latest` is open, but it is another version of Codestral,
  which is already in the comparison.
- **NVIDIA**: `kimi-k3`, `glm-5.3` and `deepseek-v4.1-flash` were still
  saturated (over 90 s per answer). `nemotron-3-nano-omni` answered its
  first turn with `print(get_patch())`, before reading anything.
- **OpenRouter**: `nemotron-3-super:free` is still served, by NVIDIA, but
  that endpoint does not support `stop`. OpenRouter silently drops the
  parameter, and in our agent the model wrote past `<end_code>`, invented
  an observation, and spent the task's whole 10,000-token output budget in
  its first answer. Among the free models whose endpoint supports `stop`,
  `inkling` is restricted to listed applications and `north-mini-code`
  returned empty or looping answers. **`qwen/qwen3.8-27b:free`** answered
  in the expected format and was kept. It is from a third family
  (Alibaba), and the free tier allows 50 requests a day, about one
  three-task campaign.

**The fifth model of the second campaign** (probed on 2026-10-06). Qwen is
gone: OpenRouter now answers "This model is unavailable for free. The paid
version is available now", and a paid model is out of the subject's rules.
So its `sympy-14711` run of the first campaign will not be made.

- **NVIDIA**: `gemma-4-31b-it`, `deepseek-v4.1-flash`, `kimi-k3`,
  `glm-5.3` and `glm-5.3-flash` gave no answer within 90 s to a one-word
  prompt; `kimi-k2.6` and `mistral-large-2-instruct` returned HTTP 404.
  `openai/gpt-oss-20b` answered in 0.5 s, but on the real SWE-bench prompt
  it writes a native tool call inside its reasoning (`{"cmd":["bash","-lc",
  "ls -R"]}`) and leaves `content` empty, with or without the stop
  sequence and with `reasoning_effort: low`: in our agent, its first turn
  was retried 5 times and the task went to the fallback model.
- **OpenRouter**: 16 `:free` models remain. 10 are served without `stop`
  (Gemma 4 among them). Of the 6 with `stop`, two were rejected on
  2026-10-04 (`inkling`, `north-mini-code`) and four were not probed. In
  any case, 50 requests a day cannot cover six tasks (up to 180).
- **Mistral**: on our free account, Small, Medium, Magistral and Vibe are
  still closed (`x-ratelimit-limit-req-minute: 0`), but **`ministral-3b-
  2512`** is open (750 requests and 1,300,000 tokens a minute). It was
  kept. It is a fourth Mistral model, but it completes a size series of
  one family on identical tasks (14B, 8B, 3B), which section 2.4 uses.

## 2. Results

### 2.1 MBPP — model comparison

Same 20 tasks (sets A + B), same agent: commit `4c8d206` for Groq, `94539e7`
for the others (the commits in between only touch the SWE-bench prompt and
the per-model request settings, empty for Groq). "Codestral, fixed loop" is the same model rerun with
the two loop fixes of ablation D. The "current agent" rows are the reruns
of 2026-10-03 (commit `e13feb3` or its content, with the loop fixes, the
provider fallback and the multi-line MBPP example of ablation E).
`nemotron-3-super` could not be rerun: NVIDIA retired it that morning
(HTTP 410), and its 20 tasks went to the fallback model, Groq (the second
Groq "current agent" row). The last Groq row is run43 + 44, with the client
changes of ablation F: unlike the earlier rows, its token counts are complete.
The "MCP agent" rows are the reruns of 2026-10-04 (run45 to run54, commit
`ca8f0ad` plus the MCP wiring and the raw-string example of section 1.1):
every model of the comparison still available, same 20 tasks, run the same
afternoon, token counts complete. The "run_tests agent" rows are the same
models and tasks a few hours later (run55 to run64), with the prompt of
ablation G: validation through `run_tests(code)` instead of asserts.
Times are the agent's wall-clock time per task.

| Model | Pass | Valid metrics | Iterations (mean) | Input tokens (mean) | Output tokens (mean) | Time per task (mean / max) | Total time |
|---|---|---|---|---|---|---|---|
| Groq `gpt-oss-120b` | **16/20** | 20/20 | 1.05 | 1,068 | 534 | **5.7 s** / 27.7 s | 114 s |
| Groq `gpt-oss-120b`, current agent | **18/20** | 20/20 | 1.05 | 1,004 | 517 | 6.7 s / 23.0 s | 134 s |
| Groq `gpt-oss-120b`, current agent, as the fallback | 16/20 | 20/20 | 0.95 | 942 | 548 | 5.4 s / 19.7 s | 108 s |
| Groq `gpt-oss-120b`, current agent, no stop sequence | **18/20** | 20/20 | 1.00 | 941 | 537 | **1.6 s** / 3.8 s | **32 s** |
| Groq `gpt-oss-120b`, MCP agent | **18/20** | 20/20 | 1.00 | 1,043 | 551 | 2.9 s / 8.3 s | 58 s |
| Groq `gpt-oss-120b`, run_tests agent | **19/20** | 20/20 | 1.10 | 1,110 | 447 | 3.0 s / 10.2 s | 60 s |
| NVIDIA `nemotron-3-super` | 15/20 | 20/20 | 1.10 | 1,311 | 789 | 16.8 s / 79.9 s | 336 s |
| NVIDIA `nemotron-3-ultra` | 14/20 | 19/20 | 1.35 | 1,659 | 414 | 34.9 s / 94.2 s | 697 s |
| NVIDIA `nemotron-3-ultra`, MCP agent | 16/20 | 20/20 | 1.30 | 1,677 | 540 | 27.1 s / 114.5 s | 542 s |
| NVIDIA `nemotron-3-ultra`, run_tests agent | **18/20** | 20/20 | 1.40 | 1,573 | 198 | 16.5 s / 67.0 s | 330 s |
| Mistral `codestral-2508` | 11/20 | 17/20 | 1.90 | 3,126 | 888 | 8.8 s / 17.3 s | 177 s |
| Mistral `codestral-2508`, fixed loop | **17/20** | 20/20 | 1.90 | 2,099 | 635 | 6.1 s / 17.5 s | 121 s |
| Mistral `codestral-2508`, current agent | **17/20** | 20/20 | 1.25 | 1,317 | 524 | **5.4 s** / 20.6 s | 108 s |
| Mistral `codestral-2508`, MCP agent | 15/20 | 20/20 | 1.50 | 1,954 | 612 | 5.9 s / 17.3 s | 118 s |
| Mistral `codestral-2508`, run_tests agent | **18/20** | 20/20 | 1.30 | 1,466 | 289 | **4.4 s** / 17.3 s | 88 s |
| Mistral `ministral-14b-2512` | 15/20 | 20/20 | 1.05 | 1,317 | 780 | 8.1 s / 21.5 s | 162 s |
| Mistral `ministral-14b-2512`, current agent | 13/20 | 20/20 | 1.05 | 1,522 | 811 | 9.7 s / 19.0 s | 194 s |
| Mistral `ministral-14b-2512`, MCP agent | 14/20 | 20/20 | 1.05 | 1,525 | 781 | 8.0 s / 15.8 s | 159 s |
| Mistral `ministral-14b-2512`, run_tests agent | 12/20 | 20/20 | 0.90 | 1,331 | 674 | 8.9 s / 38.4 s | 178 s |
| Mistral `ministral-8b-2512` | 15/20 | 19/20 | 1.10 | 1,464 | 689 | 8.2 s / 26.7 s | 163 s |
| Mistral `ministral-8b-2512`, current agent | 13/20 | 20/20 | 0.90 | 1,179 | 664 | **5.5 s** / 14.7 s | 111 s |
| Mistral `ministral-8b-2512`, MCP agent | 12/20 | 20/20 | 1.25 | 1,781 | 837 | 10.2 s / 48.6 s | 205 s |
| Mistral `ministral-8b-2512`, run_tests agent | 14/20 | 20/20 | 1.15 | 1,544 | 526 | 7.7 s / 27.5 s | 154 s |

Per task, for the agent of 2026-10-02 (the "current agent" runs follow in
the next table) — **P** pass / F fail, followed by the iterations used;
⚠ metrics invalid (cumulative input above 6,000); † the agent reported
success but the checker failed the solution:

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
  `codestral` is the exception, and it passed it again in both reruns of
  2026-10-03.

Per task, current agent (2026-10-03) — same marks; ↪ finished by the
fallback model:

| MBPP task | Groq `gpt-oss-120b` | Groq, as the fallback | `codestral` | `ministral-14b` | `ministral-8b` |
|---|---|---|---|---|---|
| 127 | **P** 1 | **P** 1 ↪ | **P** 1 | **P** 1 | **P** 1 |
| 80 | **P** 1 | **P** 1 ↪ | **P** 1 | **P** 1 | **P** 1 |
| 252 | **P** 3 | **P** 1 ↪ | **P** 1 | **P** 1 | **P** 1 |
| 251 | **P** 1 | **P** 1 ↪ | **P** 1 | **P** 1 | **P** 2 |
| 264 | **P** 1 | **P** 1 ↪ | **P** 1 | F 0 | F 0 |
| 94 | **P** 1 | **P** 1 ↪ | **P** 1 | **P** 1 | **P** 1 |
| 305 | **P** 1 | F 1 ↪ | **P** 2 | F 2 | F 0 |
| 247 | **P** 1 | **P** 1 ↪ | **P** 1 | F 1 | **P** 1 |
| 457 | **P** 1 | **P** 1 ↪ | **P** 1 | **P** 1 | **P** 1 |
| 65 | **P** 1 | **P** 1 ↪ | **P** 1 | **P** 1 | **P** 1 |
| 451 | **P** 1 | **P** 1 ↪ | **P** 2 | **P** 1 | **P** 1 |
| 462 | F 0 | F 0 ↪ | F 2 | F 1 | F 1 |
| 266 | **P** 1 | **P** 1 ↪ | **P** 3 | **P** 1 | **P** 1 |
| 108 | **P** 1 | **P** 1 ↪ | F 0 | F 2 | F 1 |
| 234 | **P** 1 | **P** 1 ↪ | **P** 1 | **P** 1 | **P** 1 |
| 400 | F 1 † | F 1 † ↪ | **P** 1 | F 1 † | F 1 † |
| 431 | **P** 1 | **P** 1 ↪ | **P** 1 | **P** 2 | **P** 1 |
| 168 | **P** 1 | **P** 1 ↪ | **P** 1 | **P** 1 | **P** 1 |
| 71 | **P** 1 | F 1 † ↪ | **P** 1 | **P** 1 | F 1 † |
| 138 | **P** 1 | **P** 1 ↪ | F 2 | F 0 | F 0 |
| **Total** | **18/20** | **16/20** | **17/20** | **13/20** | **13/20** |

The two `ministral` models lose two tasks each against their runs of
2026-10-02. Three of the four lost tasks (MBPP 264 for both, 305 for
`ministral-14b`) end the same way: the model keeps reasoning in its Thought,
for 264 trying formula after formula for dog years, until the 1,500-token
output cap, before writing any code. The fourth (MBPP 71, `ministral-8b`)
fails the hidden test. None involves the final answer, so the multi-line
example is not the cause. Groq, on the same agent, scored 18/20 then 16/20:
a spread of two tasks is within the noise of a single run.

Per task, MCP agent (2026-10-04) — same marks:

| MBPP task | Groq `gpt-oss-120b` | `codestral` | `ministral-14b` | `ministral-8b` | `nemotron-3-ultra` |
|---|---|---|---|---|---|
| 127 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 80 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 252 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 2 |
| 251 | **P** 1 | **P** 1 | F 2 | F 3 | **P** 1 |
| 264 | **P** 1 | F 4 | **P** 1 | F 0 | F 3 |
| 94 | **P** 1 ↪ | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 305 | **P** 2 | F 2 | **P** 1 | F 4 | **P** 2 |
| 247 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 2 |
| 457 | **P** 1 | **P** 2 | **P** 1 | **P** 1 | **P** 1 |
| 65 | **P** 1 | **P** 1 | F 2 | **P** 1 | **P** 1 |
| 451 | **P** 1 | **P** 2 | **P** 1 | **P** 1 | **P** 1 |
| 462 | F 0 | F 1 | F 0 | F 2 | F 1 |
| 266 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 108 | **P** 1 | F 1 | F 1 | F 1 | **P** 1 |
| 234 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 400 | F 1 † | **P** 1 | F 1 † | F 1 † | F 1 † |
| 431 | **P** 1 | **P** 2 | **P** 1 | **P** 1 | **P** 2 |
| 168 | **P** 1 | **P** 2 | **P** 1 | **P** 1 | **P** 1 |
| 71 | **P** 1 | **P** 1 | **P** 2 | F 2 | **P** 1 |
| 138 | **P** 1 | F 3 | F 0 | F 0 | F 1 |
| **Total** | **18/20** | **15/20** | **14/20** | **12/20** | **16/20** |

**No model called `run_tests()`** in any of the 100 tasks: all of them kept
validating with their own asserts, as the prompt's example does. The tool's
description, generated from the server, says what it checks but not where
the candidate must be written for it, so on MBPP the manual is, for now, a
cost of about 100 tokens per turn without a use. It must stay all the same
(the subject requires the manual, V.2.6): section 6.1 says how to make it
useful. **The raw string was
adopted at once**: 103 of the 104 `final_answer` calls of the campaign use
`r"""..."""` (the other one is `nemotron-3-ultra`'s), against none of
the 101 calls of the previous run of each model. The scores move by one or
two tasks against those runs (Groq 18 → 18, `codestral` 17 → 15,
`ministral-14b` 13 → 14, `ministral-8b` 13 → 12, `nemotron-3-ultra` 14 → 16
on an agent two days older), within the noise of section 5. `codestral`
loses MBPP 264, printing intermediate values for four iterations without
submitting until the input budget runs out, and MBPP 305, whose third answer
hits the output cap after two failing asserts. As on 2026-10-03, most
`ministral` failures are answers that reach the output cap (9 of 14) or the
input budget (3 of 14).

Per task, run_tests agent (2026-10-04, ablation G) — same marks:

| MBPP task | Groq `gpt-oss-120b` | `codestral` | `ministral-14b` | `ministral-8b` | `nemotron-3-ultra` |
|---|---|---|---|---|---|
| 127 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 80 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 252 | **P** 1 | **P** 1 | F 0 | **P** 1 | **P** 2 |
| 251 | **P** 1 | **P** 1 | F 1 | **P** 3 | **P** 1 |
| 264 | **P** 1 | **P** 2 | **P** 1 | F 0 | **P** 1 |
| 94 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 305 | **P** 1 | **P** 2 | **P** 2 | **P** 3 | **P** 1 |
| 247 | **P** 1 ↪ | **P** 1 | F 0 | **P** 1 | **P** 2 |
| 457 | **P** 2 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 65 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 451 | **P** 1 | **P** 1 | **P** 2 | **P** 1 | **P** 2 |
| 462 | **P** 1 | F 2 | F 0 | F 2 | **P** 2 |
| 266 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 108 | **P** 1 | **P** 2 | F 1 | F 1 | **P** 2 |
| 234 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 400 | F 1 † | **P** 1 | F 1 † | F 1 † | F 1 † |
| 431 | **P** 1 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 168 | **P** 2 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 71 | **P** 1 | **P** 1 | F 1 † | F 1 † | **P** 1 |
| 138 | **P** 1 | F 3 | F 0 | F 0 | F 4 |
| **Total** | **19/20** | **18/20** | **12/20** | **14/20** | **18/20** |

**`run_tests()` is now used**: 112 of the 126 steps of the campaign call
it, and 112 of the 113 `final_answer` calls submit the variable that was
just tested. 81 tasks pass out of 100, against 75 for the MCP agent. MBPP
462, which almost every earlier run lost on the output cap, passes for
Groq and `nemotron-3-ultra`: without asserts to write, the answers are
shorter. `ministral-14b` is the only model to lose ground (14 → 12), on
two tasks where it reasons into the output cap before writing any code
(252, 247) and one hidden test (71).

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

### 2.3 SWE-bench — first campaign (2026-10-04)

Same three tasks (section 1.3), same agent (commit `84d22b1`: Docker, MCP
tools, persistent sandbox), one run per model, 2026-10-04. The task images
were pulled beforehand: *agent time* is the `total_time_seconds` the
checker limits to 900 s; *wall-clock* adds the copy of `/testbed` and the
container start, about 2 s. (Since 2026-10-05, `total_time_seconds` itself
counts from the agent's start, section 1.1.)

| Model | Task | Pass/Fail | Iterations | Input tokens | Output tokens | Agent time | Wall-clock |
|---|---|---|---|---|---|---|---|
| `codestral-2508` | `sympy-14711` | **PASS** | 22 | 122,628 | 2,281 | 56.5 s | 58.6 s |
| `codestral-2508` | `sympy-13480` | FAIL | 30 | 261,127 | 3,458 | 131.8 s | 133.8 s |
| `codestral-2508` | `xarray-4629` | **PASS** | 3 | 11,940 | 713 | 12.5 s | 14.3 s |
| `ministral-14b-2512` | `sympy-14711` | FAIL | 30 | 266,950 | 9,739 | 127.9 s | 129.9 s |
| `ministral-14b-2512` | `sympy-13480` | **PASS** | 3 | 9,772 | 455 | 13.4 s | 15.5 s |
| `ministral-14b-2512` | `xarray-4629` | **PASS** | 7 | 33,719 | 1,370 | 25.3 s | 27.1 s |
| `ministral-8b-2512` | `sympy-14711` | FAIL | 30 | 164,287 | 7,562 | 98.9 s | 100.9 s |
| `ministral-8b-2512` | `sympy-13480` | **PASS** | 6 | 27,827 | 973 | 20.2 s | 22.4 s |
| `ministral-8b-2512` | `xarray-4629` | **PASS** | 6 | 27,507 | 1,904 | 21.0 s | 22.8 s |
| `nemotron-3-ultra` | `sympy-14711` | FAIL | 30 | 168,424 | 1,802 | 108.2 s | 110.3 s |
| `nemotron-3-ultra` | `sympy-13480` | **PASS** | 5 | 14,750 | 300 | 23.3 s | 25.4 s |
| `nemotron-3-ultra` | `xarray-4629` | **PASS** | 15 | 98,746 | 2,028 | 57.8 s | 59.6 s |
| `qwen3.8-27b` | `sympy-14711` | *not run* | | | | | |
| `qwen3.8-27b` | `sympy-13480` | **PASS** | 10 | 47,678 | 772 | 48.0 s | 50.1 s |
| `qwen3.8-27b` | `xarray-4629` | **PASS** | 8 | 34,064 | 521 | 28.8 s | 30.7 s |

| Model | `sympy-14711` | `sympy-13480` | `xarray-4629` | Pass | Input (mean) | Output (mean) |
|---|---|---|---|---|---|---|
| `codestral-2508` | **P** 22 | F 30 | **P** 3 | **2/3** | 131,898 | 2,151 |
| `ministral-14b-2512` | F 30 | **P** 3 | **P** 7 | **2/3** | 103,480 | 3,855 |
| `ministral-8b-2512` | F 30 | **P** 6 | **P** 6 | **2/3** | 73,207 | 3,480 |
| `nemotron-3-ultra` | F 30 | **P** 5 | **P** 15 | **2/3** | 93,973 | 1,377 |
| `qwen3.8-27b` | *not run* | **P** 10 | **P** 8 | **2/2** | 40,871 (2 tasks) | 647 (2 tasks) |
| **Tasks passed** | 1/4 | 4/5 | 5/5 | **10/14** | | |

**Every model resolves at least two tasks out of three**, the exam's pass
mark; Qwen has passed both of the tasks it has run so far. Every metric is
within its limits (14/14 valid), and every claimed success is a real one:
the 10 tasks the agent reported as solved are the 10 `RESOLVED_FULL`, and
the 4 others submitted nothing. **All 4 failures are the 30-iteration cap
with no patch submitted**: the agent never handed in a wrong fix. All five
models fixed `xarray-4629` with the same one-line patch (`return
dict(variable_attrs[0])`), and the four that fixed `sympy-13480` made the
same `cotm` → `cothm` change. `codestral` is the only model to solve
`sympy-14711` so far. It does so by having `_check_vector` turn a sympy
scalar into a `Vector`. Section 4.2 explains each failure.

**Qwen's `sympy-13480` was run twice.** The campaign script, started for
`xarray-4629`, replayed the task already done. The first run passed in 5
iterations (16,209 input and 401 output tokens, 30.4 s, two HTTP 429
retried). Its files were overwritten by the second run, which is the one
above and on disk. Both are `RESOLVED_FULL`; `run5/META.txt` records the
first.

The groups are too small to rank the models: each ran each task once, and
`codestral` had solved `sympy-13480` in 4 iterations earlier the same day,
on the agent just before commit `84d22b1`. Groq's free tier stays out of
reach for SWE-bench: it rejects any request above 8,000 tokens (HTTP 413),
and these runs sent requests of up to 19,071 tokens. NVIDIA retired
`nemotron-3-super` on 2026-10-03, and Qwen replaced it as the fifth model
(section 1.4). **Qwen's `sympy-14711` was never run**: the probes and
these two tasks used most of the account's 50 free requests for
2026-10-04, and when the quota came back OpenRouter no longer served the
model for free (section 1.4). The second campaign (section 2.4) replaces
Qwen with `ministral-3b-2512`.

### 2.4 SWE-bench — second campaign (2026-10-06, six tasks)

The six tasks of the exam pool (section 1.3), five models, the agent of
commit `f27644a` (every change of section 1.1), one run per model per task,
2026-10-06 from 14:29 to 15:04. The task images were pulled beforehand,
three or four runs went in parallel on a 4-core machine, and the verdicts
come from the checker's grading code (section 1.2). ↪ *n*: the task
switched to the fallback model, `ministral-14b-2512`, at step *n*
(section 3.2); ✗: claimed success, rejected by the checker.

| Model | Task | Pass/Fail | Iterations | Input tokens | Output tokens | Agent time | Wall-clock |
|---|---|---|---|---|---|---|---|
| `codestral-2508` | `sympy-14711` | FAIL | 30 | 178,800 | 4,697 | 81.5 s | 83.5 s |
| `codestral-2508` | `sympy-13480` | **PASS** | 3 | 10,933 | 360 | 24.3 s | 26.1 s |
| `codestral-2508` | `xarray-4629` | **PASS** | 3 | 13,132 | 644 | 33.6 s | 35.4 s |
| `codestral-2508` | `sympy-18189` | **PASS** | 4 | 15,759 | 379 | 48.1 s | 49.9 s |
| `codestral-2508` | `django-11066` | **PASS** | 3 | 12,105 | 328 | 24.8 s | 26.9 s |
| `codestral-2508` | `sklearn-13439` | FAIL | 18 | 80,924 | 10,000 | 101.2 s | 102.9 s |
| `ministral-14b-2512` | `sympy-14711` | FAIL, **false success** | 18 | 126,331 | 5,994 | 115.6 s | 117.5 s |
| `ministral-14b-2512` | `sympy-13480` | **PASS** | 13 | 62,615 | 1,983 | 70.2 s | 76.7 s |
| `ministral-14b-2512` | `xarray-4629` | **PASS** | 5 | 30,155 | 1,398 | 36.2 s | 38.7 s |
| `ministral-14b-2512` | `sympy-18189` | FAIL | 30 | 261,425 | 10,000 | 160.1 s | 161.8 s |
| `ministral-14b-2512` | `django-11066` | FAIL | 30 | 231,561 | 7,224 | 116.2 s | 118.4 s |
| `ministral-14b-2512` | `sklearn-13439` | **PASS** | 13 | 65,333 | 2,709 | 62.4 s | 64.4 s |
| `ministral-8b-2512` | `sympy-14711` | FAIL | 21 | 157,361 | 10,000 | 108.6 s | 111.4 s |
| `ministral-8b-2512` | `sympy-13480` | **PASS** | 19 | 113,438 | 5,049 | 90.7 s | 92.9 s |
| `ministral-8b-2512` | `xarray-4629` | **PASS** | 9 | 56,640 | 2,169 | 54.4 s | 56.1 s |
| `ministral-8b-2512` | `sympy-18189` | FAIL | 30 | 216,598 | 9,077 | 133.2 s | 135.3 s |
| `ministral-8b-2512` | `django-11066` | FAIL | 30 | 251,632 | 8,522 | 138.7 s | 140.5 s |
| `ministral-8b-2512` | `sklearn-13439` | **PASS** | 9 | 47,412 | 2,129 | 42.0 s | 44.4 s |
| `nemotron-3-ultra` | `sympy-14711` | **PASS** ↪ 23 | 24 | 117,858 | 2,794 | 481.1 s | 483.1 s |
| `nemotron-3-ultra` | `sympy-13480` | **PASS** ↪ 14 | 17 | 66,613 | 1,453 | 285.4 s | 287.5 s |
| `nemotron-3-ultra` | `xarray-4629` | **PASS** ↪ 4 | 8 | 33,823 | 866 | 91.5 s | 95.2 s |
| `nemotron-3-ultra` | `sympy-18189` | FAIL | 30 | 186,521 | 3,203 | 607.8 s | 611.2 s |
| `nemotron-3-ultra` | `django-11066` | **PASS** ↪ 13 | 30 | 152,746 | 2,250 | 297.8 s | 299.9 s |
| `nemotron-3-ultra` | `sklearn-13439` | **PASS** ↪ 15 | 16 | 73,255 | 1,490 | 302.4 s | 304.5 s |
| `ministral-3b-2512` | `sympy-14711` | FAIL | 15 | 103,951 | 10,000 | 60.3 s | 62.0 s |
| `ministral-3b-2512` | `sympy-13480` | FAIL, **false success** | 16 | 70,177 | 4,304 | 36.3 s | 37.9 s |
| `ministral-3b-2512` | `xarray-4629` | **PASS** | 6 | 25,726 | 1,550 | 19.1 s | 20.7 s |
| `ministral-3b-2512` | `sympy-18189` | **PASS** | 10 | 43,387 | 1,637 | 19.9 s | 21.5 s |
| `ministral-3b-2512` | `django-11066` | **PASS** | 22 | 127,621 | 5,096 | 39.5 s | 41.3 s |
| `ministral-3b-2512` | `sklearn-13439` | FAIL | 20 | 97,071 | 10,000 | 63.4 s | 66.3 s |

| Model | `sympy-14711` | `sympy-13480` | `xarray-4629` | `sympy-18189` | `django-11066` | `sklearn-13439` | Pass | Input (mean) | Output (mean) |
|---|---|---|---|---|---|---|---|---|---|
| `codestral-2508` | F 30 | **P** 3 | **P** 3 | **P** 4 | **P** 3 | F 18 | **4/6** | 51,942 | 2,735 |
| `ministral-14b-2512` | F 18 ✗ | **P** 13 | **P** 5 | F 30 | F 30 | **P** 13 | **3/6** | 129,570 | 4,885 |
| `ministral-8b-2512` | F 21 | **P** 19 | **P** 9 | F 30 | F 30 | **P** 9 | **3/6** | 140,514 | 6,158 |
| `nemotron-3-ultra` | **P** 24 ↪ | **P** 17 ↪ | **P** 8 ↪ | F 30 | **P** 30 ↪ | **P** 16 ↪ | **5/6** | 105,136 | 2,009 |
| `ministral-3b-2512` | F 15 | F 16 ✗ | **P** 6 | **P** 10 | **P** 22 | F 20 | **3/6** | 77,989 | 5,431 |
| **Tasks passed** | 1/5 | 4/5 | 5/5 | 2/5 | 3/5 | 3/5 | **18/30** | | |

**18 of the 30 runs pass, and every model passes at least half of the
six tasks.** `codestral-2508` passes 4 with the fewest input tokens
(51,942 per task) and the shortest successes (3 or 4 iterations each). `nemotron-3-ultra` shows 5 passes, but NVIDIA was overloaded that
afternoon: 5 of its 6 tasks went to the fallback model before the end.
`nemotron` itself wrote the fix of `sympy-14711`, `sympy-13480` and
`sklearn-13439` (the fallback only ran the tests and submitted), while
`ministral-14b` wrote the fix of `xarray-4629` and `django-11066`; its
only task without a switch, `sympy-18189`, failed. Its own record is
therefore 3 fixes, 1 failure and 2 tasks it did not finish.

**Difficulty is not where the first campaign put it.** `xarray-4629`
passes 5/5 again and `sympy-13480` 4/5, but `sympy-18189`, whose hint
holds the fix as a diff, passes only 2/5: `ministral-14b` and
`ministral-8b` read the right lines at step 1 and 7, then never manage
the one-word edit, and spend the 30 iterations in repeated steps (18 and 9)
and multi-block answers (section 4.2). `sympy-14711` stays the hardest
(1/5, and that one through the fallback switch).

**Two false successes**, the second kind of failure besides the cap:
`ministral-14b` submitted a real but wrong fix of `sympy-14711` in the
same block as its reproduction and its `run_tests()`, so without reading
either: the reproduction still raised the `TypeError` and the tests printed
"3 passed, 1 exceptions". `ministral-3b`
submitted a diff **it wrote by hand** for `sympy-13480`. Its `sed` command
had changed nothing, so `get_patch()` was empty and the agent's assertion
stopped the submission; the model then typed a diff in a string and passed
it to `final_answer()`. That diff has no `diff --git` header and the wrong
indentation, and none of the checker's three methods can apply it.

**The size series of one family** (`ministral` 14B, 8B and 3B on the same
tasks, the same agent, the same day) shows no order on six tasks: 3, 3 and
3 passes here, 5, 3 and 4 in the second run of section 5. The 3B model
answers as fast as `codestral` (1.8 s per answer, section 3.2), but it
wrote all four hand-made diffs of the 60 runs of this campaign and its
ablation.

**Six runs out of 60 ended on the 10,000-token output cap**, and none of
them on the input or time limit. They come from answers that go on after
their code block (section 4.2).

### 2.5 Mock exams (2026-10-04 to 2026-10-06)

The four scripts the evaluators use (`exams/`) were first run on the
night of 2026-10-04, on commit `4d0a580`, whose agent is the one of
section 2.3 (`84d22b1`), on the machine with a regular Docker daemon, with
`codestral-2508` given explicitly. The scripts draw their own tasks: five
random MBPP tasks, and three SWE-bench tasks out of the pool of six. The
raw output of that first exam stayed on that machine and is not
versioned; the three later ones are (`benchmarks/exams/`).

| Exam | Task | Result | Iterations | Input / output tokens | Agent time |
|---|---|---|---|---|---|
| MBPP | 92 | **PASS** | 1 | 935 / 253 | 2.7 s |
| MBPP | 290 | **PASS** | 1 | 984 / 241 | 2.4 s |
| MBPP | 116 | **PASS** | 1 | 939 / 147 | 2.1 s |
| MBPP | 235 | FAIL | 4 | 5,242 / 746 | 9.4 s |
| MBPP | 441 | **PASS** | 1 | 929 / 131 | 1.9 s |
| SWE-bench | `sympy__sympy-13480` | **PASS** | 3 | 13,271 / 358 | 13.5 s |
| SWE-bench | `sympy__sympy-14711` | FAIL, **false success** | 11 | 55,869 / 1,333 | 23.7 s |
| SWE-bench | `scikit-learn__scikit-learn-13439` | FAIL | 30 | 172,882 / 4,733 | 48.3 s (135 s with the image pull) |

**MBPP passes, 4/5**, the bar: MBPP 235 found no solution in 4 iterations,
and the loop stopped before a request that would have crossed the input
limit, with valid metrics. **SWE-bench fails, 1/3** against a bar of 2/3;
every container was removed after its task.

**`sympy-14711` is the agent's first false success.** It claimed success
and submitted a patch that makes `_check_vector` turn a scalar into
`Vector([(other, None)])`, which the checker rejects (`RESOLVED_NO`). Just
before, `run_tests()` printed `exit code: 0` at the top and "3 passed, 1
exceptions" further down, and the model wrote "The fix now works
correctly". That exit code is the evaluation script's last command, a `git
checkout` (section 4.2). `scikit-learn-13439`, never tried before, went to
the 30-iteration cap: two `edit_file` calls with an `old_str` it had not
read (steps 5 and 11), then 19 steps of `read_file` through `pipeline.py`
in 20-line windows, without another edit.

The exam also showed that the evaluators' commands may leave out
`--model-name` and `--provider-url`, which both agents required: since
2026-10-05 the model defaults to `codestral-2508`, and the provider is the
one that declares the model in `configs/models.json`.

**Three more full exams** followed on rootless Docker, each on the commit
of the day, without `--model-name` (so with `codestral-2508`). The
checker's SWE-bench validation fails there on `lchown` (section 1.2), so
the official SWE-bench result is 0/3 each time; the *real* column grades
the same patches with the checker's grading code, as in section 2.4.

| Exam | Commit | Sandbox | MBPP | SWE-bench tasks drawn | SWE-bench, real |
|---|---|---|---|---|---|
| 2026-10-04, 22:10 | `4d0a580` | 8/14 | **4/5** | `sympy-13480` P, `sympy-14711` F ✗, `sklearn-13439` F | 1/3 (official) |
| 2026-10-05, 15:37 | `90ef54a` | **14/14** + bonus | **5/5** (17, 232, 295, 390, 96) | `sympy-18189` P, `sympy-14711` F, `sklearn-13439` F | 1/3 |
| 2026-10-05, 16:18 | `1453d0c` | **14/14** + bonus | 3/5 (245 F, 430 F) | `sympy-18189` P, `django-11066` P, `sklearn-13439` F | **2/3** |
| 2026-10-06, 13:49 | `f27644a` | **14/14** + bonus | **4/5** (138 F) | `xarray-4629` P, `sympy-13480` P, `sympy-14711` F | **2/3** |

- **MBPP** passes three exams out of four, **16/20 tasks**. Every task
  passed is passed in 1 or 2 iterations. The three failures since
  2026-10-05 (MBPP 245, 430, 138) are the model resubmitting the same
  wrong code, despite the repeated-step note, until the loop stops it
  before the input limit.
- **SWE-bench** reaches the exam bar of 2/3 in the last two exams. Since
  the prompt rule of 2026-10-05 on the exit code of `run_tests()`, every
  success claimed in an exam is real, and every failure is the
  30-iteration or the 10,000-token cap without a patch. `sklearn-13439`
  and `sympy-14711` failed each of the three times they were drawn.
- **`CLEANUP: FAILED`** appears on every task whose patch the checker tried
  to validate on rootless Docker, and on no other. A `docker ps` taken every
  2 s during the 2026-10-06 exam shows the agent's container gone at
  13:57:17 and a container running `tail -f /dev/null` from 13:57:21: the
  checker's own validation container, left behind when its copy fails on
  `lchown`. On the regular Docker daemon of 2026-10-04, the three tasks
  were `CLEANUP: OK`.
- **The first MBPP exam of 2026-10-06 gave 0/5**: the machine's Docker
  storage had been wiped, so the checker's `python:3.11-slim` image was
  missing and every solution failed validation in 3 to 7 s. Re-validated
  once the image was pulled, the same five solutions give 4/5
  (`benchmarks/exams/2026-10-06_13-49/mbpp_first_pass/`).

## 3. Provider reliability

### 3.1 MBPP runs

An *attempt* is one HTTP request, retries included. *Availability* is the
share of attempts that got a usable answer. *Response time* is measured on
answered requests only (a failed attempt can last up to the 30 s deadline).
A task is *lost* when 5 attempts in a row fail.

| Provider / model | Runs | Tasks | Attempts | Retries | Availability | Response time (mean / median / max) | Tasks lost |
|---|---|---|---|---|---|---|---|
| Groq `gpt-oss-120b` | 6, 7, 9, 10, 12–14 | 70 | 146 | 60 | 59 % | **1.5 / 1.2 / 5.1 s** | 4 |
| Groq `gpt-oss-120b`, with fallback | 27, 28, 31, 32, 39–42 | 80 | 164 | 82 | 50 % | **1.4 / 1.2 / 3.5 s** | 0 (4 ↪) |
| Groq `gpt-oss-120b`, no stop sequence | 43, 44 | 20 | 21 | **0** | **100 %** | **1.5 / 1.3 / 3.8 s** | 0 |
| Groq `gpt-oss-120b`, MCP agent | 45, 46 | 20 | 25 | 6 | 76 % | **1.3 / 1.1 / 2.2 s** | 0 (1 ↪) |
| OpenRouter `nemotron-3-super:free` | 5 | 10 | 29 | 13 | 55 % | 15.9 / 16.2 / 29.1 s | 0 |
| OpenRouter `minimax-m3:free` | 8 | 10 | 29 | 1 | 97 % | 8.5 / 5.9 / 25.5 s | 0 |
| OpenRouter `qwen3.8-27b:free` | 11 | 10 | 34 | 22 | 35 % | 11.3 / 9.5 / 27.0 s | 3 |
| NVIDIA `nemotron-3-super` (retired 2026-10-03) | 15, 16 | 20 | 30 | 4 | 87 % | 7.5 / 6.1 / 20.1 s | 0 |
| NVIDIA `nemotron-3-ultra` | 17, 18 | 20 | 55 | 26 | 53 % | 11.4 / 10.5 / 22.8 s | 2 |
| NVIDIA `nemotron-3-ultra`, MCP agent | 53, 54 | 20 | 49 | 20 | 59 % | 11.9 / 11.0 / 28.5 s | 0 |
| Mistral `codestral-2508` | 19, 20, 25, 26, 29, 30, 33, 34 | 80 | 152 | 0 | **100 %** | 3.4 / 3.1 / 15.9 s | 0 |
| Mistral `ministral-14b-2512` | 21, 22, 35, 36 | 40 | 52 | 0 | **100 %** | 6.8 / 5.5 / 21.5 s | 0 |
| Mistral `ministral-8b-2512` | 23, 24, 37, 38 | 40 | 49 | 0 | **100 %** | 5.6 / 4.2 / 23.7 s | 0 |
| Mistral `codestral-2508`, MCP agent | 47, 48 | 20 | 33 | 0 | **100 %** | 3.6 / 2.9 / 14.7 s | 0 |
| Mistral `ministral-14b-2512`, MCP agent | 49, 50 | 20 | 26 | 0 | **100 %** | 6.1 / 5.5 / 13.3 s | 0 |
| Mistral `ministral-8b-2512`, MCP agent | 51, 52 | 20 | 30 | 1 | 97 % | 5.8 / 4.7 / 13.6 s | 0 |
| Groq `gpt-oss-120b`, run_tests agent | 55, 56 | 20 | 23 | 2 | 91 % | **1.2 / 1.0 / 2.9 s** | 0 (1 ↪) |
| Mistral `codestral-2508`, run_tests agent | 57, 58 | 20 | 26 | 0 | **100 %** | 2.3 / 1.9 / 9.7 s | 0 |
| Mistral `ministral-14b-2512`, run_tests agent | 59, 60 | 20 | 24 | 0 | **100 %** | 6.7 / 3.2 / 29.2 s | 0 |
| Mistral `ministral-8b-2512`, run_tests agent | 61, 62 | 20 | 26 | 0 | **100 %** | 5.1 / 3.5 / 21.9 s | 0 |
| NVIDIA `nemotron-3-ultra`, run_tests agent | 63, 64 | 20 | 35 | 7 | 80 % | 7.4 / 5.6 / 22.3 s | 0 |

Causes, where the agent logged them (from run12 on, one line per retry on
stderr):

- **Groq**: all 27 logged retries of run12–14 are an HTTP 200 answer with an
  empty `content` field, the model having put its whole answer in `reasoning`.
  Fast when it answers, but four answers in ten are unusable. Same picture on
  2026-10-03 (run27, 28, 31, 32, 39 to 42): 77 of the 82 failures are an
  empty `content`, 5 are HTTP 429 on the 8,000 tokens/min limit. Four tasks
  reached 5 failures in a row and went to `ministral-14b-2512` through the
  fallback (↪), where they would have been lost before; the attempts above
  count Groq's requests only. **Why `content` is empty**: a
  probe of 14 MBPP prompts on 2026-10-03 got 6 empty answers. In 4 of them
  the reasoning stops mid-sentence ("We must end code with ") exactly where
  the model was about to write `<end_code>`, the agent's stop sequence: the
  provider ends the response before the answer is written. One used up its
  1,500 output tokens reasoning, and only one held the whole answer in its
  reasoning, the case the client now recovers (section 1.1). The same probe
  without `stop` got 1 empty answer out of 14, with its code in the
  reasoning, and nothing written after `<end_code>` in the 13 others. **With
  the stop sequence left out (run43, 44), Groq did not fail once in 21
  attempts**. On the MCP agent (run45, 46), 6 of 25 attempts failed: 4 ×
  HTTP 429 on the 8,000 tokens/min limit, 1 empty `content`, and a new
  error, HTTP 400 "Tool choice is none, but model called a tool": the model
  emitted a native tool call, which the request does not enable. It is
  permanent, so MBPP 94 went straight to the fallback, `ministral-14b-2512`,
  which solved it (↪). It first appeared with the sandbox manual in the
  prompt, which talks about "tools". On the run_tests agent (run55, 56), 2
  failures in 23 attempts: one 429 and the same HTTP 400 tool call, which
  sent MBPP 247 to the fallback again;
- **NVIDIA `nemotron-3-ultra`**: 18 × HTTP 503 "Service temporarily
  overloaded" and 6 × the 30 s deadline (run17, 18); 17 × HTTP 503 and 3 ×
  the deadline on the MCP agent (run53, 54); 5 × HTTP 503 and 2 × the
  deadline on the run_tests agent (run63, 64);
  **`nemotron-3-super`**: 4 × the 30 s deadline. NVIDIA retired it on
  2026-10-03 at 09:00 UTC: every request of run39 and run40 got HTTP 410
  ("has reached its end of life"), and the fallback took all 20 tasks;
- **OpenRouter**: causes were not logged at the time. Bursts of 429
  "temporarily rate-limited upstream" were frequent in our OpenRouter tests,
  on top of the 50 requests/day account quota;
- **Mistral**: no failure at all in 253 attempts, plus the 3 requests
  `ministral-14b-2512` answered as Groq's fallback; on the MCP agent, one
  failure in 89 attempts, a request past its 30 s deadline
  (`ministral-8b-2512`, run52), and none in 76 on the run_tests agent.

### 3.2 SWE-bench runs

Same definitions as section 3.1; the per-call deadline is 60 s for
SWE-bench. Response time is measured on answered requests.

| Provider / model | Runs | Tasks | Attempts | Retries | Availability | Response time (mean / median / max) | Tasks lost |
|---|---|---|---|---|---|---|---|
| Mistral `codestral-2508` | 1 | 3 | 55 | 0 | **100 %** | **1.8 / 1.4 / 8.3 s** | 0 |
| Mistral `ministral-14b-2512` | 2 | 3 | 40 | 0 | **100 %** | 3.6 / 2.8 / 12.9 s | 0 |
| Mistral `ministral-8b-2512` | 3 | 3 | 42 | 0 | **100 %** | 3.0 / 1.8 / 22.0 s | 0 |
| NVIDIA `nemotron-3-ultra` | 4 | 3 | 50 | 0 | **100 %** | 3.5 / 1.9 / 36.2 s | 0 |
| OpenRouter `qwen3.8-27b:free` | 5 | 2 so far | 21 | 3 | 86 % | **1.6 / 1.0 / 7.5 s** | 0 |

**None of the 187 requests of the four first models failed**, and no task
went to a fallback model, although the requests were up to 19,071 input
tokens long. Qwen's only failures are OpenRouter's HTTP 429 (rate
limited), 3 in 21 attempts, each retried after 10 s without losing a task;
the overwritten first run of `sympy-13480` had 2 more out of 7. When it
answers, Qwen is as fast as `codestral`. The three
Mistral models ran one after the other on a single key (the client waits
before a request that would exceed Mistral's tokens-per-minute limit),
while NVIDIA ran at the same time.
NVIDIA's 503 "overloaded" errors and deadline overruns of the MBPP
campaigns (section 3.1) did not occur that evening. Its slowest answer,
36.2 s, would have missed MBPP's 30 s deadline but fits SWE-bench's 60 s.
`codestral` answers twice as fast as the others on average, which
matches the 56,000-token probe below.

A first attempt at the campaign was lost before any request reached a
model: the API keys of the machine's `.env` were swapped between
providers, and every task got HTTP 401, including from the fallback
model. The agent wrote a `success: false` solution with the error for
each task, as it should; the keys were fixed and the campaign rerun, and
those directories were deleted.

Preliminary latency on a single 56,000-token request (synthetic history,
2026-10-02): `nemotron-3-super` (retired since) 44.4 / 13.2 / 8.8 s over three tries,
`nemotron-3-ultra` 15.6 / 9.9 / 8.0 s, `codestral-2508` 2.2 s,
`ministral-14b-2512` 4.1 s, `ministral-8b-2512` 6.0 s. One NVIDIA answer in
six exceeds 30 s: the per-call deadline of SWE-bench was raised to 60 s on
2026-10-02.

**Second campaign** (2026-10-06, section 2.4 and ablation H, both runs of
each model; same definitions; *fallback*: tasks switched to the fallback
model after 5 failed attempts in a row):

| Provider / model | Runs | Tasks | Attempts | Retries | Availability | Response time (mean / median / max) | Tasks lost | Fallback |
|---|---|---|---|---|---|---|---|---|
| Mistral `codestral-2508` | 6, 11 | 12 | 113 | 0 | **100 %** | **1.9 / 1.2 / 42.0 s** | 0 | 0 |
| Mistral `ministral-14b-2512` | 7, 12 | 12 | 199 | 1 | 99 % | 4.0 / 3.5 / 18.5 s | 0 | 0 |
| Mistral `ministral-8b-2512` | 8, 13 | 12 | 219 | 0 | **100 %** | 3.6 / 3.0 / 27.0 s | 0 | 0 |
| Mistral `ministral-3b-2512` | 10, 15 | 12 | 200 | 0 | **100 %** | **1.8 / 1.4 / 29.1 s** | 0 | 0 |
| NVIDIA `nemotron-3-ultra` | 9, 14 | 12 | 295 | 171 | **42 %** | 6.4 / 4.4 / 48.2 s | 0 | **10** |

**NVIDIA was overloaded all afternoon**: 168 of its 171 failures are HTTP
503 "Service temporarily overloaded", the other 3 are 60 s deadline
overruns. 10 of its 12 tasks went to the fallback model, some at the first
step (`django-11066` in run14 was done entirely by `ministral-14b`). No
task was lost, which is what the fallback is for, but these runs measure
`nemotron` only up to the switch (section 2.4). A probe after the campaign
still got three 503 out of five requests. On 2026-10-04 the same model
answered all its 50 requests: availability depends on the hour, not on
the model.

The four Mistral models answered 730 of their 731 attempts; the one failure is
an HTTP 429 (rate limit) of `ministral-14b`, retried. A first
`ministral-14b` run of `sympy-14711`, started at 14:29, hit six 60 s
deadline overruns in a row and switched to `nemotron`; it was stopped and
the model's six tasks rerun from 14:38 (run7), when a 13,000-token prompt
took 1 s. The stopped run is kept in `run7/aborted/`.

## 4. Intermediary metrics

### 4.1 MBPP

The subject's metrics are defined for SWE-bench. The one that carries over to
MBPP is **submission discipline**: the number of iterations between the first
step where the agent's checks pass and the accepted `final_answer` (0 is
ideal). A check is the agent's own asserts running without error or, from
run55 on, a `run_tests()` report printed in the step with only PASS lines.
Two related counts complete it:

- a **blind submission** is a `final_answer` accepted although no check has
  ever run (asserts are found on the AST of the executed code: asserts
  written *inside* the answer string do not count);
- a **loop refusal** is a `final_answer` refused by the loop's own checks
  (invalid Python, or failing `test_list` when run alone). A `final_answer`
  that the code skips because the `run_tests()` report shows a failure is
  not one.

The extended definitions give the same values as before for every run up to
run54.

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
| Groq, current agent, one-line example (run27, 28) | 18 | 0 | 17/18 | 0.06 | 2 | 1 |
| Groq, current agent, multi-line example (run31, 32) | 19 | 0 | 18/19 | 0.11 | 1 | 1 |
| Mistral `codestral-2508`, current agent, one-line example (run29, 30) | 16 | 0 | 9/16 | 0.44 | **9** | 0 |
| Mistral `codestral-2508`, current agent, multi-line example (run33, 34) | 17 | 0 | **17/17** | **0.00** | **0** | 0 |
| Mistral `ministral-14b-2512` (run21, 22) | 16 | 0 | 16/16 | 0.00 | 0 | 1 |
| Mistral `ministral-8b-2512` (run23, 24) | 16 | 0 | 16/16 | 0.00 | 0 | 1 |
| Mistral `ministral-14b-2512`, current agent (run35, 36) | 14 | 0 | 13/14 | 0.07 | 1 | 1 |
| Mistral `ministral-8b-2512`, current agent (run37, 38) | 15 | 0 | 15/15 | 0.00 | 0 | 2 |
| Groq, current agent, as the fallback (run39, 40) | 18 | 0 | 18/18 | 0.00 | 0 | 2 |
| Groq, current agent, rejected tokens counted (run41, 42) | 14 | 0 | 14/14 | 0.00 | 1 | 1 |
| Groq, current agent, no stop sequence (run43, 44) | 19 | 0 | 18/19 | 0.05 | 1 | 1 |
| Groq, MCP agent (run45, 46) | 19 | 0 | **19/19** | **0.00** | 0 | 1 |
| NVIDIA `nemotron-3-ultra`, MCP agent (run53, 54) | 17 | 0 | 16/17 | 0.06 | 0 | 1 |
| Mistral `codestral-2508`, MCP agent (run47, 48) | 15 | 0 | **15/15** | **0.00** | 1 | 0 |
| Mistral `ministral-14b-2512`, MCP agent (run49, 50) | 15 | 0 | **15/15** | **0.00** | 0 | 1 |
| Mistral `ministral-8b-2512`, MCP agent (run51, 52) | 13 | 0 | **13/13** | **0.00** | 0 | 1 |
| Groq, run_tests agent (run55, 56) | 20 | 0 | **20/20** | **0.00** | 0 | 1 |
| NVIDIA `nemotron-3-ultra`, run_tests agent (run63, 64) | 19 | 0 | **19/19** | **0.00** | 0 | 1 |
| Mistral `codestral-2508`, run_tests agent (run57, 58) | 18 | 0 | **18/18** | **0.00** | 0 | 0 |
| Mistral `ministral-14b-2512`, run_tests agent (run59, 60) | 14 | 0 | **14/14** | **0.00** | 0 | 2 |
| Mistral `ministral-8b-2512`, run_tests agent (run61, 62) | 16 | 0 | **16/16** | **0.00** | 0 | 2 |

Blind submissions disappeared when the prompt started asking for the asserts
and `final_answer()` in the same code block: since then `final_answer` only
runs if every assert before it passed. In 2026-09-02's `run6`, MBPP 127 had
been "solved" with the asserts written inside the answer string: they never
ran. `codestral`'s higher discipline after the fix is a side effect of the
fix: a refused answer is corrected one iteration later. With the multi-line
example (ablation E) that cost disappears: no answer refused, discipline 0 on
all 17 submissions.

### 4.2 SWE-bench

Measured on the fourteen `solution.json` of section 2.3:

- **exploration**: the step of the first successful `read_file` of the
  file every passing patch changes, and of its first successful
  `edit_file` (a call that fails on a wrong path or an `old_str` not found
  does not count);
- **submission discipline**: the iterations between the first
  `run_tests()` whose report shows a test summary with no failure and the
  `final_answer` (0 is ideal);
- **blind test runs**: `run_tests()` calls whose report shows **no** test
  summary at all (explained below);
- **repeated steps**: steps whose code is identical to an earlier step's.

| Model | Task | Result | First read | First edit | `run_tests()` (blind) | Green → `final_answer` | Repeated steps |
|---|---|---|---|---|---|---|---|
| `codestral-2508` | `sympy-14711` | **P** | 2 | 9 | 4 (0) | 21 → 22: **1** | 6 |
| `codestral-2508` | `sympy-13480` | F | 7 | never (11 failed) | 12 (**12**) | — | **22** |
| `codestral-2508` | `xarray-4629` | **P** | 1 | 2 | 0 | nothing run after the edit | 0 |
| `ministral-14b-2512` | `sympy-14711` | F | 1 | 25 | 3 (0) | never green | 5 |
| `ministral-14b-2512` | `sympy-13480` | **P** | 1 | 2 | 1 (**1**) | — | 0 |
| `ministral-14b-2512` | `xarray-4629` | **P** | 2 | 6 | 1 (0) | 6 → 7: **1** | 0 |
| `ministral-8b-2512` | `sympy-14711` | F | nothing printed | 30 | 0 | — | 5 |
| `ministral-8b-2512` | `sympy-13480` | **P** | 1 | 2 | 1 (**1**) | — | 0 |
| `ministral-8b-2512` | `xarray-4629` | **P** | 3 | 4 | 0 | reproduction only | 0 |
| `nemotron-3-ultra` | `sympy-14711` | F | 2 | never | 0 | — | 1 |
| `nemotron-3-ultra` | `sympy-13480` | **P** | 1 | 2 | 0 | reproduction only | 0 |
| `nemotron-3-ultra` | `xarray-4629` | **P** | 1 | 6 | 0 | own `pytest` runs | 1 |
| `qwen3.8-27b` | `sympy-13480` | **P** | 2 | 3 | 1 (**1**) | — | 0 |
| `qwen3.8-27b` | `xarray-4629` | **P** | 2 | 4 | 1 (0) | 7 → 8: **1** | 0 |

**Exploration is not the bottleneck.** The statements point at the file
(section 1.3), and in 13 of the 14 runs the agent reads it by step 7, in
11 of them by step 2. The successes edit it 1 to 7 steps later. The `14711`
failures find the file just as fast and then fail to change it: first
edit at step 25 (`ministral-14b`), at the last step (`ministral-8b`), or
never (`nemotron-3-ultra`).

**Submission discipline cannot be judged on most successes.** Only 3 of
the 10 were submitted after a visibly green test run, all one iteration
later (the model runs the tests, reads the report, and submits on the next
turn). 3 were submitted after a `run_tests()` whose report showed no
result: after its blind run, Qwen tried twice to run the tests itself, but
`pytest` is not installed in the sympy image and `sympy.testing` does not
exist in that version, so it fell back on the reproduction. 4 never called
`run_tests()`. Of those, `nemotron-3-ultra` on
`xarray-4629` ran the repository's tests itself (`pytest` through
`run_command`), two runs only reran the problem's reproduction after the
fix, and `codestral` on `xarray-4629` submitted right after its edit,
without running anything.

**The SWE-bench `run_tests()` hides the test results, a defect of our
agent.** 15 of the 24 calls of the campaign are blind, all on
`sympy-13480`. The task's evaluation script begins with `git show`, and
the head commit of the sympy images ("SWE-bench") changes the mode of every
file of the repository, so thousands of `old mode 100644 / new mode 100755`
lines come before any test output. The sandbox caps a tool's output at
its first 20,000 characters, and the cut removes the test summary.
The loop's own truncation keeps the head *and* the tail of an observation
precisely so that test summaries survive, but it now receives text that
has already been cut. On the other sympy task, a summary was visible but
the report printed `exit code: 0` above "0 passed, 4 exceptions": that code
belongs to the script's last command, a `git checkout`, not to the tests.
In the mock exam (section 2.5) the same misleading code cost a task:
`codestral` read it as a pass and submitted a wrong patch. Since
2026-10-05 the SWE-bench prompt warns about it (section 1.1); the tool
itself has returned only the test output since 2026-10-05 (`8db5195`):
see the second campaign below and ablation I.

**Partial progress**, where the summaries are visible: `codestral` on
`sympy-14711` goes from "3 passed, 1 exceptions" (steps 10, 13, 15) to "4
passed" at step 21, and submits at step 22. `ministral-14b` on the same task
goes from 1 to 0 to 2 passing tests out of 4, at steps 26, 28 and 30: its
first edit came too late for its progress to reach the end. Elsewhere,
blind or untested runs leave nothing to measure.

**How the four failures happen** — each model fails in its own way:

- `codestral` / `sympy-13480`: from step 8 on, it sends **the same
  `edit_file` call eleven times**, with an `old_str` indented by 21 spaces
  instead of 20, and rereads lines 589 to 591 between attempts. The tool's
  "old_str not found" never makes it check the indentation, and its twelve
  `run_tests()` calls are all blind (22 repeated steps). It had solved the
  same task in 4 iterations that afternoon.
- `ministral-14b` / `sympy-14711`: it passes Python code to `run_command`
  (a bash syntax error), tries three times to create a file with
  `edit_file`, which cannot create one, and redefines `def __mul__` **in the
  sandbox** three times instead of editing the repository. Its first real
  edit comes at step 25. It ends at 266,950 of the 300,000 input tokens and
  **9,739 of the 10,000 output tokens**, the closest any run came to a
  limit.
- `ministral-8b` / `sympy-14711`: **21 of its 30 steps call tools without
  `print()`**, so 27 observations are empty. Each time, the loop answers
  that "only what you print() appears here", and each time the model
  ignores it.
- `nemotron-3-ultra` / `sympy-14711`: it reads the whole file in
  100-line windows (steps 2 to 7), then **rereads the same parts again
  and again**, `__mul__` (line 141) five more times and lines 55–65 six
  more times, and never edits. Only the last 3 observations stay whole in
  the conversation (`full_observations = 3` in `core/constants.py`), so a
  range read four steps earlier is no longer visible. The elision that
  keeps the input budget in check is the likely reason this model goes
  round in circles.

**Input budget**: the five runs that went to 30 iterations used 164,287 to
266,950 input tokens, 5,476 to 8,898 per iteration. None was cut by the
300,000 limit, which a 2026-10-04 simulation expected around turn 26.


**Second campaign** (section 2.4, the 30 runs of run6 to run10). Same
metrics, plus *unread edits*: steps whose `edit_file` had an `old_str`
line that no earlier observation showed, which this agent refuses to run
(section 1.1). An `edit_file` whose result was not printed counts as an
edit when nothing says it failed. *Blind* now covers every `run_tests()`
call whose report the model did not see a summary of: not printed, in a
block that did not run, or cut.

| Model | Task | Result | First read | First edit | `run_tests()` (blind) | Green → `final_answer` | Repeated steps | Unread edits |
|---|---|---|---|---|---|---|---|---|
| `codestral-2508` | `sympy-14711` | F | 2 | 3 | 2 (0) | never green | 25 | 1 |
| `codestral-2508` | `sympy-13480` | **P** | 1 | 2 | 1 (0) | 2 → 3: **1** | 0 | 0 |
| `codestral-2508` | `xarray-4629` | **P** | 1 | 2 | 1 (0) | 2 → 3: **1** | 0 | 0 |
| `codestral-2508` | `sympy-18189` | **P** | 1 | 2 | 1 (0) | 3 → 4: **1** | 0 | 0 |
| `codestral-2508` | `django-11066` | **P** | 1 | 2 | 1 (0) | 2 → 3: **1** | 0 | 0 |
| `codestral-2508` | `sklearn-13439` | F | 1 | — | 0 (0) | — | 1 | 1 |
| `ministral-14b-2512` | `sympy-14711` | F ✗ | 2 | 3 | 3 (2) | never green | 1 | 0 |
| `ministral-14b-2512` | `sympy-13480` | **P** | 3 | 12 | 3 (0) | 12 → 13: **1** | 2 | 0 |
| `ministral-14b-2512` | `xarray-4629` | **P** | 2 | 3 | 1 (0) | 4 → 5: **1** | 0 | 0 |
| `ministral-14b-2512` | `sympy-18189` | F | 1 | — | 0 (0) | — | 18 | 0 |
| `ministral-14b-2512` | `django-11066` | F | 2 | — | 0 (0) | — | 11 | 0 |
| `ministral-14b-2512` | `sklearn-13439` | **P** | 2 | 9 | 1 (0) | 12 → 13: **1** | 0 | 0 |
| `ministral-8b-2512` | `sympy-14711` | F | — | — | 0 (0) | — | 0 | 0 |
| `ministral-8b-2512` | `sympy-13480` | **P** | 1 | 16 | 1 (0) | 18 → 19: **1** | 8 | 0 |
| `ministral-8b-2512` | `xarray-4629` | **P** | 5 | 6 | 1 (0) | 8 → 9: **1** | 0 | 0 |
| `ministral-8b-2512` | `sympy-18189` | F | 7 | — | 0 (0) | — | 9 | 0 |
| `ministral-8b-2512` | `django-11066` | F | 1 | 10 | 2 (0) | never green | 11 | 0 |
| `ministral-8b-2512` | `sklearn-13439` | **P** | 2 | 7 | 0 (0) | — | 0 | 0 |
| `nemotron-3-ultra` | `sympy-14711` | **P** ↪ | 2 | 11 | 0 (0) | — | 2 | 0 |
| `nemotron-3-ultra` | `sympy-13480` | **P** ↪ | 3 | 7 | 1 (1) | never green | 4 | 0 |
| `nemotron-3-ultra` | `xarray-4629` | **P** ↪ | 5 | 6 | 1 (0) | 7 → 8: **1** | 0 | 0 |
| `nemotron-3-ultra` | `sympy-18189` | F | 1 | 21 | 0 (0) | — | 5 | 0 |
| `nemotron-3-ultra` | `django-11066` | **P** ↪ | 12 | 15 | 2 (1) | 29 → 30: **1** | 0 | 0 |
| `nemotron-3-ultra` | `sklearn-13439` | **P** ↪ | 8 | 12 | 1 (0) | 15 → 16: **1** | 2 | 0 |
| `ministral-3b-2512` | `sympy-14711` | F | 1 | — | 0 (0) | — | 0 | 0 |
| `ministral-3b-2512` | `sympy-13480` | F ✗ | — | 4 | 0 (0) | — | 4 | 0 |
| `ministral-3b-2512` | `xarray-4629` | **P** | 1 | 4 | 0 (0) | — | 0 | 0 |
| `ministral-3b-2512` | `sympy-18189` | **P** | 1 | 2 | 0 (0) | — | 0 | 0 |
| `ministral-3b-2512` | `django-11066` | **P** | 2 | 20 | 0 (0) | — | 3 | 0 |
| `ministral-3b-2512` | `sklearn-13439` | F | — | — | 0 (0) | — | 3 | 0 |

**Submission discipline is the clearest change since the first
campaign.** 12 of the 18 successes were submitted one iteration after a
`run_tests()` whose summary showed no failure, against 3 of 10 on
2026-10-04; 5 never called `run_tests()` (three of them `ministral-3b`),
and one submitted after a call it did not print. Only 4 of the 23 calls
are blind, against 15 of 24: the tool now returns the test output itself
(section 1.1). The cost is small: a passing run adds one test step.

**Repeated steps are now concentrated in the failures**: 88 of the 109
repeated steps of the campaign are in its 12 failures (288 steps). The
note the loop adds when a step repeats both the code and the output of an
earlier one (section 1.1) changes nothing: `codestral` on `sympy-14711`
alternates the same two blocks from step 6 to step 30, and 25 of its 30
steps are repeats.

**Answers with several code blocks** are the main waste of the
`ministral` models. Only the first block runs, and the loop says so after
each such answer ("Your answer had N code blocks: only the first one was
run"). Over both runs of each model, they make 72 % of `ministral-14b`'s
steps and 84 % of its output tokens, 70 % and 87 % for `ministral-8b`,
52 % and 73 % for `ministral-3b`, against 4 % of `codestral`'s steps
and 10 % of `nemotron`'s. The models write a plan as a series of blocks,
then react to the output of the first as if all had run. A related form
ends `codestral`'s `sklearn-13439`: a code block closed without
`<end_code>`, followed by "Step 144", "Thought:" and another block, over
and over, until the answer alone used 6,266 tokens and the task its
10,000. Neither stop sequence (`<end_code>`, `Observation:`) catches it.
These answers explain the six runs that ended on the output cap.

**Unread edits are rare in this campaign**: 2 refusals in 30 runs, both
`codestral`, and none in the 30 runs of ablation H, where the refusal was
off. Section 5 shows what that means for the ablation. One of the two
refusals (`sympy-14711`, step 5) blocked a line the model had written
itself two steps earlier with `edit_file`: the refusal counts the outputs
it has shown, not the `new_str` of a successful edit. The model read the
lines at step 6 and edited them at step 7.

**Hand-written diffs.** `ministral-3b` four times passed `final_answer()`
a diff it typed instead of the output of `get_patch()` (once in run10,
three times in run15). Three do not apply anywhere; the fourth
(`sympy-14711`, run15), with a made-up `index abc1234567…` line, applies
only through the checker's third method (`patch --fuzz=5`) and resolves
the task, although the repository never held the change. The agent checks
that `get_patch()` is not empty, but not that the submitted string is what
`get_patch()` returned.

## 5. Ablation studies

A to G are on MBPP, same task files, same model, one change at a time.
H and I, on SWE-bench, are at the end of the section.

| | Change | Model, tasks | Before | After |
|---|---|---|---|---|
| A | Prompt and feedback messages rewritten (`9c4754a`) | Groq `gpt-oss-120b`, A + B | run6 + 7: **18/20**, input 981 tokens/task, 6 blind | run9 + 10: **17/20**, input 1,375 tokens/task, 5 blind |
| B | Asserts and `final_answer()` in the same code block (prompt) | Groq `gpt-oss-120b`, B | run10: **7/10**, 2 blind, input 1,477 | run12: **6/10**, 0 blind, input 850 |
| C | The loop runs the answer alone against `test_list` before accepting it | Groq `gpt-oss-120b`, B | run12: **6/10**, 2 false successes | run13: **8/10**, 1 false success |
| D | Input limit checked before sending + `SyntaxError` explained on refusal | Mistral `codestral-2508`, A + B | run19 + 20: **11/20**, 17/20 valid | run25 + 26: **17/20**, 20/20 valid |
| E | MBPP example submits on several lines, in a triple-quoted string (prompt) | Mistral `codestral-2508`, A + B | run29 + 30: **16/20**, 7 one-line answers refused, 1.80 iterations and 2,174 input tokens per task | run33 + 34: **17/20**, 0 refused, 1.25 iterations and 1,317 input tokens per task |
| E | idem | Groq `gpt-oss-120b`, A + B | run27 + 28: **17/20**, 3 of them finished by the fallback | run31 + 32: **18/20**, no fallback |
| F | Stop sequence left out for `gpt-oss`, cut by the client (with the reasoning recovery and the rejected tokens counted) | Groq `gpt-oss-120b`, A + B | run41 + 42: **13/20**, 18 failed attempts out of 37, 1,637 input and 814 output tokens per task | run43 + 44: **18/20**, 0 failed out of 21, 941 input and 537 output tokens per task |
| G | Validation through `run_tests(code)` instead of asserts (prompt and example; the tool takes the code and runs it in the sandbox) | 5 models, A + B | run45–54: **75/100**, `run_tests()` called in 0 steps, output 540 to 837 tokens per task | run55–64: **81/100**, `run_tests()` called in 112 of 126 steps, output 198 to 674 tokens per task |

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
- **E** removes the cause D only explained. Both variants were run on the same
  agent (`fb8f224`), one after the other. `codestral`'s seven refused
  one-line answers (MBPP 127, 94, 305, 247, 65, 400, 71) all become accepted
  first submissions, and it spends 31 % fewer iterations and 39 % less input.
  All 42 `final_answer` calls of the two models are now multi-line (13 of 22
  for Groq and 10 of 31 for `codestral` before), and none is invalid Python:
  the trap the one-line form had been chosen against, literal `\n` escapes
  in the answer string (`run5`, MBPP 94), did not come back. Groq is unchanged
  within noise; its only difference, MBPP 252, failed before on the output
  cap.

Ablation E, per task — same marks as section 2.1; ↪ finished by the fallback
model (`ministral-14b-2512`); ‡ at least one one-line answer refused as
invalid Python:

| MBPP task | Groq, one line | Groq, multi-line | `codestral`, one line | `codestral`, multi-line |
|---|---|---|---|---|
| 127 | **P** 1 | **P** 1 | **P** 2 ‡ | **P** 1 |
| 80 | **P** 1 ↪ | **P** 1 | **P** 1 | **P** 1 |
| 252 | F 2 | **P** 3 | **P** 1 | **P** 1 |
| 251 | **P** 1 | **P** 1 | **P** 2 | **P** 1 |
| 264 | **P** 1 | **P** 1 | F 4 | **P** 1 |
| 94 | **P** 1 | **P** 1 | **P** 2 ‡ | **P** 1 |
| 305 | **P** 2 | **P** 1 | **P** 3 ‡ | **P** 2 |
| 247 | **P** 1 | **P** 1 | **P** 2 ‡ | **P** 1 |
| 457 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 65 | **P** 1 ↪ | **P** 1 | **P** 3 ‡ | **P** 1 |
| 451 | **P** 1 | **P** 1 | **P** 2 | **P** 2 |
| 462 | F 0 | F 0 | F 0 | F 2 |
| 266 | **P** 1 | **P** 1 | **P** 1 | **P** 3 |
| 108 | **P** 2 | **P** 1 | F 1 | F 0 |
| 234 | **P** 1 ↪ | **P** 1 | **P** 1 | **P** 1 |
| 400 | F 1 † | F 1 † | **P** 2 ‡ | **P** 1 |
| 431 | **P** 1 | **P** 1 | **P** 2 | **P** 1 |
| 168 | **P** 1 | **P** 1 | **P** 1 | **P** 1 |
| 71 | **P** 1 | **P** 1 | **P** 2 ‡ | **P** 1 |
| 138 | **P** 1 | **P** 1 | F 3 | F 2 |
| **Total** | **17/20** | **18/20** | **16/20** | **17/20** |

- **F** first shows what the uncounted tokens hid. With the stop sequence
  still sent and the rejected tokens now counted (run41 + 42), Groq falls
  from 18/20 (run31 + 32) to 13/20: its empty answers now eat the
  1,500-token output budget, and four tasks run out of it (MBPP 80, 247
  and 168 before any usable answer, 252 at its second step). The reasoning recovery saved one answer
  out of 18 (MBPP 451). Leaving the stop sequence out removes the cause:
  run43 + 44 get no empty answer at all, pass 18/20 with complete token
  counts, and take 1.6 s per task instead of 6.8 s. Only MBPP 462 (output
  cap) and 400 (hidden test) fail, as for nearly every model.

Ablation F, per task — same marks as section 2.1; ⟲ answer recovered from
the reasoning:

| MBPP task | stop sent, rejected tokens not counted (run31, 32) | stop sent, counted (run41, 42) | no stop sequence (run43, 44) |
|---|---|---|---|
| 127 | **P** 1 | **P** 1 | **P** 1 |
| 80 | **P** 1 | F 0 | **P** 1 |
| 252 | **P** 3 | F 1 | **P** 2 |
| 251 | **P** 1 | **P** 1 | **P** 1 |
| 264 | **P** 1 | **P** 1 | **P** 1 |
| 94 | **P** 1 | **P** 1 | **P** 1 |
| 305 | **P** 1 | F 1 | **P** 1 |
| 247 | **P** 1 | F 0 | **P** 1 |
| 457 | **P** 1 | **P** 1 | **P** 1 |
| 65 | **P** 1 | **P** 1 | **P** 1 |
| 451 | **P** 1 | **P** 1 ⟲ | **P** 1 |
| 462 | F 0 | F 0 | F 0 |
| 266 | **P** 1 | **P** 1 | **P** 1 |
| 108 | **P** 1 | **P** 1 | **P** 1 |
| 234 | **P** 1 | **P** 1 | **P** 1 |
| 400 | F 1 † | F 1 † | F 1 † |
| 431 | **P** 1 | **P** 1 | **P** 1 |
| 168 | **P** 1 | F 0 ↪ | **P** 1 |
| 71 | **P** 1 | **P** 1 | **P** 1 |
| 138 | **P** 1 | **P** 1 | **P** 1 |
| **Total** | **18/20** | **13/20** | **18/20** |

Caveat: each task was run **once** per configuration. On 10 to 20 tasks, a
difference of one or two tasks is within noise: `codestral` on the same agent
and the same example scored 17/20 (run25 + 26) then 16/20 (run29 + 30), and
Groq 18/20 (run31 + 32) then 16/20 (run39 + 40). Only
B's blind submissions (2 → 0), C's MBPP 451, D's invalid metrics (3 → 0),
E's refused answers (7 → 0) and F's failed attempts (18 → 0) are clear-cut.

The reruns of 2026-10-04 (run45 to run54) are **not** an ablation: they
changed two things at once, the MCP wiring and the raw-string example. What
they show is in section 2.1: every model copies the raw string, none calls
`run_tests()`, and the scores stay within noise.

- **G** changes one thing for the model: how it checks its code. The tool's
  signature also changed between the two campaigns (`run_tests()` reading a
  file, then `run_tests(code)`), but the first one was never called, so the
  measured effect is the prompt's. Per model: Groq 18 → 19, `codestral`
  15 → 18, `nemotron-3-ultra` 16 → 18, `ministral-8b` 12 → 14,
  `ministral-14b` 14 → 12. Each move is within the noise of a single run;
  the total (+6 of 100, four models up, one down) and the output tokens are
  the clearer signal: without asserts to write, `codestral` writes 2.1 times
  fewer output tokens per task and `nemotron-3-ultra` 2.7 times fewer.
  Discipline stays at 0 for every submission, with no blind submission.

**SWE-bench ablations.** Two, both against the campaigns of sections
2.3 and 2.4.

| | Change | Models, tasks | Before | After |
|---|---|---|---|---|
| H | An `edit_file` whose `old_str` holds a line no earlier observation showed is not run (`5c0fbf3`) | 5 models, the 6 tasks of section 2.4 | run11–15, refusal off: **22/30**, 0 unread edits | run6–10, refusal on: **18/30**, 2 refusals |
| I | The agent of 2026-10-04 (`84d22b1`) against that of 2026-10-06 (`f27644a`): `run_tests()` returning the test output, the exit-code rule, the stop on `Observation:`, the repeated-step note, H | 4 models, the 3 recommended tasks | run1–4: **8/12**, 14 of 22 `run_tests()` blind, 2 of 8 successes submitted after green tests | run6–9: **9/12**, 3 of 15 blind, 7 of 9; run11–14: **10/12**, 0 of 9 blind, 9 of 10 |

**H** was run as the same agent with `Loop.check_unread_edits()`
replaced by a function that never refuses (a wrapper around
`agent_swebench`, outside the repository); everything else, commit,
configuration and tasks, is identical. `META.txt` says which arm a run
belongs to.

| Model, no refusal | `sympy-14711` | `sympy-13480` | `xarray-4629` | `sympy-18189` | `django-11066` | `sklearn-13439` | Pass | Input (mean) | Output (mean) |
|---|---|---|---|---|---|---|---|---|---|
| `codestral-2508` | **P** 7 | **P** 3 | **P** 4 | **P** 4 | **P** 4 | F 30 | **5/6** | 40,822 | 920 |
| `ministral-14b-2512` | **P** 16 | **P** 3 | **P** 5 | F 30 | **P** 19 | **P** 16 | **5/6** | 101,566 | 3,873 |
| `ministral-8b-2512` | F 27 | **P** 5 | F 30 | **P** 4 | **P** 5 | F 30 | **3/6** | 101,501 | 4,403 |
| `nemotron-3-ultra` | **P** 24 ↪ | **P** 6 | **P** 15 ↪ | **P** 22 ↪ | **P** 12 ↪ | F 30 ↪ | **5/6** | 84,920 | 2,235 |
| `ministral-3b-2512` | **P** 20 | F 28 ✗ | **P** 13 | **P** 18 | F 12 ✗ | **P** 20 | **4/6** | 93,052 | 4,148 |
| **Tasks passed** | 4/5 | 4/5 | 4/5 | 4/5 | 4/5 | 2/5 | **22/30** | | |

| Model | With the refusal (run) | Without (run) | Refusals | Unread edits run without it | Verdicts that differ |
|---|---|---|---|---|---|
| `codestral-2508` | 4/6 (run6) | 5/6 (run11) | 2 | 0 | 1: sympy-14711 |
| `ministral-14b-2512` | 3/6 (run7) | 5/6 (run12) | 0 | 0 | 2: sympy-14711, django-11066 |
| `ministral-8b-2512` | 3/6 (run8) | 3/6 (run13) | 0 | 0 | 4: xarray-4629, sympy-18189, django-11066, sklearn-13439 |
| `nemotron-3-ultra` | 5/6 (run9) | 5/6 (run14) | 0 | 0 | 2: sympy-18189, sklearn-13439 |
| `ministral-3b-2512` | 3/6 (run10) | 4/6 (run15) | 0 | 0 | 3: sympy-14711, django-11066, sklearn-13439 |

- **The refusal almost never fires, so H measures the noise.** It refused
  2 steps in 30 runs, both `codestral`, and with the refusal off no model
  wrote a single unread edit in 30 runs. On 2026-10-04 and 2026-10-05,
  19 of 60 edits were unread (section 1.1); on these six tasks, with this
  prompt, the models read before they edit. So in 28 of the 30 pairs the
  two arms ran **the same agent on the same task**, and still **12 of the
  30 verdicts differ** (9 of the 22 pairs of the four Mistral models
  without a refusal). The 18 → 22 gap is the variance of a single run,
  not the effect of the refusal.
- **One run per model and task cannot rank the models.** Between the two
  arms, `ministral-14b` goes from 3/6 to 5/6, `ministral-3b` from 3/6 to
  4/6, `codestral` from 4/6 to 5/6. Pooled over both arms (12 runs each),
  `codestral` passes 9, `ministral-14b` 8, `ministral-3b` 7,
  `ministral-8b` 6, and `nemotron` 10 with most of its tasks finished by
  the fallback. Only `codestral`'s lead in efficiency is stable: its 9
  successes take 3 to 7 iterations.
- **The tasks keep their order better than the models**: over the ten
  runs of each, `xarray-4629` passes 9, `sympy-13480` 8, `django-11066` 7,
  `sympy-18189` 6, `sympy-14711` and `sklearn-13439` 5.
- **I** changes several things at once, so it is a before/after of the
  agent, not of one change. Its pass rate moves within the noise H
  measures (8/12 → 9/12 and 10/12). What moves clearly is what the agent
  shows the model: blind test runs fall from 14 of 22 to 3 of 15 and 0
  of 9, and successes submitted after a visibly green run rise from 2 of 8
  to 7 of 9 and 9 of 10 (section 4.2). The first campaign's false-success
  trap, an exit code of 0 above failing tests (section 2.5), cannot happen
  with the new `run_tests()`.

## 6. Conclusions

### 6.1 MBPP

- **Validating through `run_tests(code)`** (ablation G) is the best agent
  of this report: 81/100 over five models, 19/20 for Groq and 18/20 for
  `codestral` and `nemotron-3-ultra`, every metric valid, with shorter
  answers. The tool runs the candidate in the sandbox, and the string
  tested is the string submitted.
- **Groq `gpt-oss-120b` without the stop sequence** gives the best single
  result: 18/20 (run43, 44), 18/20 on the MCP agent, then 19/20 on the
  run_tests agent, about 3 s per task. Before, 41 to 50 % of its attempts
  failed (empty `content`, mostly cut by the stop sequence) and its token
  figures were understated (section 1.1). It cannot be used for SWE-bench
  (HTTP 413 above 8,000 tokens), its free tier allows 8,000 tokens per
  minute, and since the sandbox manual is in the prompt it twice attempted a
  native tool call (HTTP 400, handled by the fallback).
- **Mistral `codestral-2508`**, the MBPP default of the `Makefile` since
  2026-10-03, went from 11/20 to 17/20 with the loop fixes, then scored
  16/20, 17/20 (multi-line example), 15/20 (MCP agent) and 18/20
  (run_tests agent). No Mistral request failed in its 211 attempts.
- **Mistral `ministral-14b-2512`** scored 15/20, 13/20, 14/20 then 12/20,
  and `ministral-8b-2512` 15/20, 13/20, 12/20 then 14/20, every metric
  valid. Their lost tasks are mostly reasoning that runs into the output
  cap. Over the four agents, `codestral` stays one to six tasks ahead of
  both.
- **NVIDIA `nemotron-3-super`** (15/20 on 2026-10-02) no longer exists: NVIDIA
  retired it on 2026-10-03. `nemotron-3-ultra` replaced it at the end of the
  fallback lists.
- **NVIDIA `nemotron-3-ultra`** scored 16/20 on the MCP agent and 18/20 on
  the run_tests agent, but 27 of its 84 attempts that day failed (HTTP 503
  "overloaded", deadline) and its tasks took 16 to 27 s on average, up to
  114.5 s against the 120 s limit: kept for SWE-bench, where it is one of
  the candidate models, **disregarded for MBPP**.
- **Disregarded** as well: OpenRouter's `:free` models (50 requests/day per
  account, 3 tasks lost to upstream 429 in run11, 4/10 for
  `nemotron-3-super` in run5); `minimax-m3`, no longer free.
- **The sandbox manual stays in the prompt**: the subject requires it, with
  the MCP tools' documentation or how to access it (V.2.6), and `run_tests`
  is a mandatory MBPP tool (V.3.2). It costs about 100 input tokens per
  turn, and since ablation G it pays for itself: the model calls the tool
  it documents.
- On these 20 tasks the ceiling is about 19/20: MBPP 400 (hidden test)
  defeats nearly every model, and MBPP 462 (output cap) only passes with
  short answers.
- **The mock exam** (section 2.5) drew five other tasks and gave 4/5 with
  `codestral-2508`, exactly the bar.

### 6.2 SWE-bench

- **The agent reaches the exam bar with every model, but not on every
  draw.** Over the 60 runs of the second campaign (five models, the six
  tasks the exam can draw, two runs each), 40 pass, and every model passes
  at least half of the tasks in each run. The mock exams with
  `codestral-2508` gave 1/3, 1/3, 2/3 and 2/3 (real verdicts, section
  2.5). Two tasks fail most often, `sympy-14711` and `sklearn-13439`
  (5 passes in 10 runs each, and every exam that drew them).
- **A single run per model and task is mostly noise.** Run twice with an
  agent that, in practice, did not change (ablation H), 12 of 30
  verdicts flip. Model rankings of section 2.3 or 2.4 taken alone are not
  meaningful; pooled over two runs, `codestral` 9/12, `ministral-14b`
  8/12, `ministral-3b` 7/12 and `ministral-8b` 6/12 are within that noise
  of each other. **Mistral `codestral-2508` stays the default** for
  reasons that hold across runs: it answers fastest with
  `ministral-3b` (1.8–1.9 s), it never failed a request (0 retries in 113
  attempts on 2026-10-06, 0 in 55 on 2026-10-04), its successes are the
  shortest (3 to 7 iterations) and it uses the fewest input tokens
  (51,942 per task in section 2.4, against 77,989 to 140,514), it writes
  almost only one block per answer (4 % multi-block answers against 52 to
  72 % for the `ministral` models), and it never submitted a hand-written
  or a wrong patch in the campaigns (it did once, in the first mock exam,
  before the exit-code rule).
- **NVIDIA `nemotron-3-ultra` is good when it answers.** In run9 it wrote
  the fix of three tasks itself, `sympy-14711`, the hardest, among them,
  and failed one; the fallback model finished the other two. But its
  availability fell from 100 % on
  2026-10-04 to 42 % on 2026-10-06 (HTTP 503), and 10 of its 12 tasks
  needed the fallback model: it cannot be the exam model, and its scores
  of section 2.4 are partly `ministral-14b`'s.
- **Model size does not order the `ministral` series** on these tasks
  (14B, 8B, 3B: 8, 6 and 7 passes out of 12). What size changes is
  discipline: the 3B model wrote all four hand-made diffs, and the 14B and
  8B models most of the multi-block answers.
- **The agent changes of 2026-10-05 are visible in what the model sees,
  not yet in the pass rate** (ablation I): blind test runs went from 14 of
  22 to 3 of 15 and 0 of 9, and successes submitted after a green test run
  from 2 of 8 to 7 of 9 and 9 of 10. The refusal of unread edits was
  nearly idle in these runs (2 refusals in 30), unlike in earlier ones (19
  of 60 edits).
- **The next gains are on the agent's side**, from section 4.2: (1) stop a
  model from submitting anything but the output of `get_patch()` (four
  hand-made diffs, one of which "passed" through fuzzy patching); (2) stop
  generation at a second code block or at a line starting a new step, or
  run only answers that end with `<end_code>`, since multi-block answers
  and run-on steps caused all six output-cap failures; (3) break loops
  that the repeated-step note does not break (`codestral` alternating two
  blocks for 25 steps); (4) count the `new_str` of a successful edit as
  seen, so that the refusal of unread edits does not block a line the
  model wrote itself. (1), (4) and most of (2) are in the agent since the
  evening of 2026-10-06, not yet measured (section 1.1).
- **Still missing**: a `nemotron` run without NVIDIA's overload; the
  first campaign's Qwen `sympy-14711`, which can no longer be run for free;
  an official `validate swebench` of the second campaign on a regular
  Docker daemon (its verdicts come from the checker's grading code,
  section 1.2); and more than two runs per model and task before ranking
  models.

## Backing data

All runs are versioned under [`benchmarks/mbpp/`](benchmarks/mbpp/) and
[`benchmarks/swebench/`](benchmarks/swebench/), one directory per run
(`benchmarks/<bench>/runN/`). Each holds `META.txt` (model,
provider, task set, commit, start and end times), `RESUME.json` (one line per
task), `task_XX.json`, `solution_XX.json` and `logs/` (agent stdout/stderr,
checker output). [`benchmarks/README.md`](benchmarks/README.md) describes the
files and which checker output is authoritative for each run.

| Runs | Model |
|---|---|
| run5 | OpenRouter `nemotron-3-super:free` |
| run6, run7, run9, run10, run12, run13, run14, run27, run28, run31, run32, run41–run46, run55, run56 | Groq `gpt-oss-120b` |
| run39, run40 | requested NVIDIA `nemotron-3-super` (retired, HTTP 410); every task done by the fallback, Groq `gpt-oss-120b` |
| run8 | OpenRouter `minimax-m3:free` |
| run11 | OpenRouter `qwen3.8-27b:free` |
| run15, run16 | NVIDIA `nemotron-3-super` |
| run17, run18, run53, run54, run63, run64 | NVIDIA `nemotron-3-ultra` |
| run19, run20, run25, run26, run29, run30, run33, run34, run47, run48, run57, run58 | Mistral `codestral-2508` |
| run21, run22, run35, run36, run49, run50, run59, run60 | Mistral `ministral-14b-2512` |
| run23, run24, run37, run38, run51, run52, run61, run62 | Mistral `ministral-8b-2512` |

| SWE-bench runs | Model |
|---|---|
| swebench/run1 | Mistral `codestral-2508` |
| swebench/run2 | Mistral `ministral-14b-2512` |
| swebench/run3 | Mistral `ministral-8b-2512` |
| swebench/run4 | NVIDIA `nemotron-3-ultra` |
| swebench/run5 | OpenRouter `qwen/qwen3.8-27b:free` (`sympy-14711` not run: the free model was withdrawn) |
| swebench/run6, run11 | Mistral `codestral-2508` (second campaign; run11 without the refusal of unread edits) |
| swebench/run7, run12 | Mistral `ministral-14b-2512` (idem; `run7/aborted/`: the stopped first attempt) |
| swebench/run8, run13 | Mistral `ministral-8b-2512` (idem) |
| swebench/run9, run14 | NVIDIA `nemotron-3-ultra` (idem; most tasks finished by the fallback, section 3.2) |
| swebench/run10, run15 | Mistral `ministral-3b-2512` (idem) |

The mock exams of 2026-10-05 and 2026-10-06 are in `benchmarks/exams/`,
one directory per exam with the output of the four scripts (`sandbox/`,
`mbpp/`, `swebench/`), as the scripts wrote it in `evaluations/`; each
SWE-bench task also has a `grade.txt`, the verdict of the checker's
grading code (section 1.2).

Since 2026-10-05 `--model-name` and `--provider-url` can be left out: the
model defaults to `codestral-2508`, and the provider is the one that
declares the model in `configs/models.json`.

To rerun one SWE-bench task and check it (Docker running, the task's image
is pulled on first use):

```
uv run python -m agent_swebench \
    --task-file benchmarks/swebench/run1/task_01.json \
    --output solution.json --model-name codestral-2508 \
    --provider-url https://api.mistral.ai/v1
cd moulinette && uv run moulinette_eval validate swebench \
    ../benchmarks/swebench/run1/task_01.json ../solution.json
```

To rerun one MBPP task and check it:

```
uv run python -m agent_mbpp --task-file benchmarks/mbpp/run35/task_01.json \
    --output solution.json --model-name ministral-14b-2512 \
    --provider-url https://api.mistral.ai/v1
cd moulinette && uv run moulinette_eval validate mbpp \
    ../benchmarks/mbpp/run35/task_01.json ../solution.json
```
