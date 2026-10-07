*This project has been created as part of the 42 curriculum by tchemin, ndi-tull.*

# Agent Smith

Autonomous reasoning, code generation and sandboxed execution.

## Description

Agent Smith is a code agent framework. Given a programming task, it lets a
Large Language Model solve it by itself, in a **Thought → Code →
Observation** loop:

1. the model explains its reasoning and writes a block of Python;
2. the block runs in a **sandbox** that restricts what the code can do
   (imports, files, network, time, memory);
3. inside that block, the model calls **tools** as ordinary Python
   functions (`read_file(...)`, `run_tests(...)`). The tools are served by
   an **MCP server** running in its own process;
4. what the code printed comes back to the model as the observation, and
   the loop goes on until the model calls `final_answer(...)` or a limit is
   reached.

Calling tools from code, instead of through JSON tool calls, lets the model
keep variables between steps, use loops and conditions, and chain several
tool calls in one step.

The framework is applied to two benchmarks:

- **MBPP** (Mostly Basic Python Problems): write a Python function from a
  short description and a few assertions;
- **SWE-bench Verified**: fix a real bug in a real repository (sympy,
  django, scikit-learn, xarray...) running in its Docker image, and submit
  the fix as a git patch.

Everything is built from scratch: the agent loop, the LLM client, the
sandbox and the MCP integration. No agent orchestration library is used.
Each run writes a `solution.json` that records every step (raw model
output, code sent to the sandbox, observation, tokens, latency, retries),
so that the evaluator can trace how the task was solved.

## Instructions

### Requirements

- Linux, **Python 3.10** and **[uv](https://docs.astral.sh/uv/)**;
- **Docker** (CLI and daemon) for SWE-bench: the agent pulls the task
  image and runs a container;
- at least one free API key for a provider declared in
  `configs/models.json`: Mistral, Groq, NVIDIA Build or OpenRouter.

### Installation

```bash
make setup      # uv python install 3.10 (if needed)
make install    # uv sync
```

### Configuration

**API keys** are read from environment variables, or from a `.env` file at
the root of the repository (never from the code):

```bash
cp .env.example .env
```

```dotenv
MISTRAL_API_KEY=key1,key2
GROQ_API_KEY=key1
NVIDIA_API_KEY=key1
OPENROUTER_API_KEY=key1
```

Several keys for one provider are separated by commas. The client rotates
through them when one is rate limited or out of quota.

| File | Role |
|---|---|
| `configs/models.json` | Providers (URL, endpoint, auth header, API key variable, response field names, rate-limit headers) and the free models declared for each. Only declared models are accepted. |
| `configs/fallback.json` | Ordered fallback models per benchmark, used when the requested model keeps failing. A fallback whose provider has no key in the environment is skipped. |
| `sandbox_template.json` | A `SandboxConfig`: allowed imports, allowed directories, timeout and memory limit. |

### Sandbox

```bash
uv run sandbox                                                          # interactive sandbox
uv run sandbox sandbox_template.json                                    # with a custom configuration
uv run sandbox --mcp-stdio "python mcp_tools_mbpp.py" sandbox_template.json      # MBPP tools (stdio)
uv run sandbox --mcp-server http://127.0.0.1:8000/mcp                   # tools over streamable HTTP
uv run sandbox --mcp-stdio "python mcp_tools_swebench.py" sandbox_template.json  # SWE-bench tools
```

The sandbox opens a REPL (`>>>`, `...` for unfinished blocks). Each entry
runs in the same restricted namespace, with the connected server's tools
and `final_answer`. Variables persist from one entry to the next. `exit`
or Ctrl+D leaves. Code can also be piped in: `cat prog.py | uv run sandbox`.

To serve the tools over HTTP, start a server first:

```bash
uv run python mcp_tools_swebench.py --transport streamable-http --port 8000
uv run python mcp_tools_mbpp.py --transport streamable-http --port 8000 --task-file task.json
```

### Agents

```bash
# MBPP
uv run python -m agent_mbpp --task-file ../cache/mbpp_task.json \
    --output ../cache/mbpp_solution.json \
    --model-name "codestral-2508" --provider-url "https://api.mistral.ai/v1"

# SWE-bench
uv run python -m agent_swebench --task-file ../cache/swebench_task.json \
    --output ../cache/swebench_solution.json \
    --model-name "codestral-2508" --provider-url "https://api.mistral.ai/v1"
```

`--model-name` defaults to `codestral-2508`. `--provider-url` defaults to
the URL of the provider that declares the model in `configs/models.json`.
Any failure, or an interruption (Ctrl+C, SIGTERM), still writes a valid
`solution.json` with `success: false` and the error. The exit code is then
1. Retries and fallbacks are logged on stderr.

The same runs through the `Makefile`:

```bash
make mbpp TASK=../cache/mbpp_task.json [MODEL=... URL=...]
make swebench TASK=../cache/swebench_task.json [MODEL=... URL=...]
make clean-docker     # removes any leftover sweb-* container
```

With the evaluation tool (`moulinette`), next to this repository:

```bash
cd moulinette
uv run moulinette_eval dump mbpp --output ../cache/mbpp_task.json
cd ../agent_smith
uv run python -m agent_mbpp --task-file ../cache/mbpp_task.json --output ../cache/mbpp_solution.json
cd ../moulinette
uv run moulinette_eval validate mbpp ../cache/mbpp_task.json ../cache/mbpp_solution.json
```

(and the same with `swebench` and `agent_swebench`).

## System architecture

```
 task.json ──► agent_mbpp / agent_swebench (CLI) ──► solution.json
                          │ builds
                          ▼
 ┌──────────────────────── agent process ─────────────────────────┐
 │  Loop ───── conversation ────► FallbackClient ─► LLMClient ────┼──► LLM API
 │   │  ▲                                                         │    (Mistral, Groq,
 │  code  observation                                             │     NVIDIA, OpenRouter)
 │   ▼  │                                                         │
 │  Sandbox ◄─── queues ───► sandbox child process                │
 │   │                       restricted namespace:                │
 │   │                       tool wrappers + final_answer         │
 │   │ tool calls                                                 │
 │   ▼                                                            │
 │  MCPClient ──────────── stdio or streamable HTTP ──────────────┼──► MCP server process
 └────────────────────────────────────────────────────────────────┘    mcp_tools_mbpp.py
                                                                        mcp_tools_swebench.py
                                                                             │ docker exec
                                                                             ▼
                                                                    task container, /testbed
                                                                    mounted from a host copy
```

| Path | Content |
|---|---|
| `agent_mbpp/`, `agent_swebench/` | The two CLIs: load and validate the task, build the LLM clients, start the MCP server (and the Docker container for SWE-bench), run the loop, write `solution.json`, clean up. `agent_swebench/docker.py` manages the task container. |
| `core/agent/` | `loop.py` (the agent loop), `prompt.py` (system prompt and conversation), `extraction.py` (code extraction from the model's answer). |
| `core/llm/` | `client.py` (HTTP calls, API key rotation, token-rate budget), `provider.py` (reads any provider's response through its configured field names), `fallback.py` (ordered list of clients). |
| `core/` | `models.py` (Pydantic task, output and sandbox models), `config_models.py` (models of the JSON configuration), `constants.py` (benchmark limits, stop sequences, prompt examples), `errors.py`, `api_key.py`, `agent_cli_helper.py`. |
| `sandbox/` | `executor.py` (the sandbox), `cli.py` (REPL), `manual.py` (manual generated from the MCP schemas), `mcp_client/` (synchronous MCP client, transports, tool wrappers), `security/` (AST guard, builtins, import, filesystem and network restrictions). |
| `mcp_tools/` | Tool implementations: `tools_fs.py`, `tools_search.py`, `tools_exec.py` (SWE-bench), `tools_mbpp.py` (MBPP), `config.py` (server command line, path mapping). |
| `mcp_tools_mbpp.py`, `mcp_tools_swebench.py` | The two MCP servers (FastMCP), at the root of the repository. |
| `configs/`, `sandbox_template.json` | Models, fallbacks, sandbox configuration. |
| `benchmarks/` | Raw data behind `BENCHMARK_REPORT.md` (tasks, `solution.json` files, logs). |

The boundaries are those of the subject. The **sandbox wraps the MCP
client**: tools are discovered from whatever server is connected and
exposed as Python functions. `final_answer` belongs to the sandbox, not to
any server. The **sandbox and the MCP tools are two security domains**: the
sandbox restricts the model's Python code, while tool actions (reading the
repository, running tests in Docker) happen in the server's process. The
tools work without the agent: each server runs alone, and the sandbox CLI
uses them directly.

### LLM providers

- **Provider-agnostic client.** A provider is a JSON entry: base URL,
  endpoint, header template (`Authorization: Bearer {api_key}`), name of
  the API key variable, names of the response fields (`choices`,
  `message`, `content`, `usage`, `reasoning`...) and of the rate-limit
  headers. Adding an OpenAI-compatible provider needs no code. Per-model
  options (`extra_body`, e.g. to disable reasoning, or `send_stop`) are in
  the same file.
- **Errors are typed.** HTTP 408, 409, 429 and 5xx, timeouts and network
  errors are *transient* and retried, after the provider's `Retry-After`
  when it gives one. 400, 401, 403 and 404 are *permanent*.
- **Several keys per provider.** A 429 moves to the next key, and a 402
  retires the current one. For Mistral, the tokens-per-minute budget read
  from the response headers is tracked per key, so that a request goes to
  a key that can take it.
- **Fallback.** After 5 failed attempts in a row on one step, or on a
  permanent error, the loop switches to the next model of
  `configs/fallback.json` for the rest of the task. Each step records the
  `api_url` and `model_name` that really answered it.
- **Usage tracking.** Each step records its input and output tokens, the
  request time in milliseconds and the number of retries. The totals add
  up the steps, and `total_requests` counts every attempt. Tokens billed
  for a response that was then rejected (e.g. an empty answer) are counted
  too.

## Agent loop

`core/agent/loop.py`, class `Loop`. One task, one conversation, one
sandbox.

1. **Prompt.** The system turn explains the Thought / Code / Observation
   format, embeds the **sandbox manual** generated from the connected MCP
   server, lists the allowed imports and gives the method as rules: read
   before editing, judge the tests by their output, submit
   `final_answer(get_patch())` for SWE-bench and validate with
   `run_tests(code=...)` before `final_answer` for MBPP. It ends with a
   complete worked example on a made-up task. The user turn holds the
   task.
2. **Guards before each request.** The loop stops cleanly, with an error in
   `solution.json`, before it would cross a limit:
   - time: the 5 s margin keeps the whole run under the task timeout;
   - output tokens: `max_tokens` is set to what is left of the output
     budget;
   - input tokens: the next prompt is estimated, using the exact count the
     provider gave for the previous prompt plus the new text at 2.5
     characters per token. The request is not sent if it would go over
     the limit.

   Each LLM call also has its own deadline, 30 s for MBPP and 60 s for
   SWE-bench, never more than the time left.
3. **Thought.** The model answers with **stop sequences** (`<end_code>`,
   `Observation:`, and the end of a code block). It cannot write past its
   code block or invent an observation. A closing fence removed by the
   stop sequence is put back.
4. **Code extraction.** The first ```` ```python ```` block is taken. A
   block tagged with another language, a block without its closing fence,
   or an answer with several blocks is still run when it can be read, and
   the observation says how it was read. An answer without code gets an
   explicit "No code block found".
5. **Execution.** The code runs in the task's persistent sandbox, under its
   timeout, cut down to the time left.
6. **Observation.** The output goes back to the model as the next user
   turn, with explicit feedback:
   - an empty output reminds the model to `print()`;
   - a long output is cut, head and tail kept, and the cut is stated;
   - a step identical to an earlier one is flagged as a repetition.
7. **Final answer.** `final_answer(x)` ends the loop only once `x` is
   checked:
   - MBPP: `x` must parse as Python, and it is run alone against the
     task's `test_imports` and `test_list` in a fresh sandbox (the
     evaluator runs the submitted string alone);
   - SWE-bench: `x` must be exactly what `get_patch()` returns now, never
     a diff typed by the model.

   A refused answer is explained to the model, and the loop goes on.
8. **Output.** A `SolutionOutput`: success, solution, iterations,
   totals, full system prompt, and one `StepMetrics` per iteration with
   `llm_output`, `sandbox_input`, `sandbox_output`, tokens, latency,
   retries, `api_url` and `model_name`.

| Limit | MBPP | SWE-bench |
|---|---|---|
| Iterations | 10 | 30 |
| Input tokens (cumulative) | 6,000 | 300,000 |
| Output tokens (cumulative) | 1,500 | 10,000 |
| Timeout | 120 s | 900 s |

Three mechanisms keep the agent within these budgets and on track. They
come from failures seen in the benchmark runs:

- **Observation budget.** The whole conversation is resent on every turn.
  MBPP observations are capped at 2,000 characters. SWE-bench keeps the 3
  latest observations whole and replaces older ones with a short stub.
- **Stuck MBPP attempts.** When `run_tests` rejects an attempt with the
  same failures as before, the failed attempts are collapsed into one
  summary turn and the next request uses a higher temperature.
- **No edit from memory (SWE-bench).** An `edit_file` whose `old_str`
  holds a line that no earlier observation showed is not run. The model is
  asked to read the lines first. This keeps the fix grounded in the code
  it explored, rather than recited from memory.

## Sandbox design

`sandbox/executor.py`, class `Sandbox`.

**Process isolation.** The model's code never runs in the agent's process.
Each task starts one **child process**, which locks itself down once and
then executes every step in the same namespace, so variables persist
between steps. Three queues connect parent and child:

- the parent sends the code;
- the child streams stdout and stderr as they are written, so the output
  printed before a timeout is not lost;
- tool calls and their results travel between them.

**Timeout.** The parent enforces it. When a step overruns, the child is
terminated (then killed), a new one is started, and the model is told that
the output is partial and that its variables are gone. The time spent
inside MCP tool calls is not counted: the subject applies the sandbox
timeout to the sandboxed code only.

**Restrictions applied in the child**, configured by `SandboxConfig`
(Pydantic, loadable from JSON):

| Restriction | Implementation |
|---|---|
| Imports | `__import__` is replaced by a guard that only allows `authorized_imports`. `pkg.*` allows the submodules of `pkg`. Everything else raises `ImportError`. |
| Filesystem | `open` is replaced by a guard that resolves the path (`realpath`, so `..` and symlinks are followed) and allows it only under one of `allowed_directories`. No module that touches files (`os`, `pathlib`, `io`, `shutil`) is importable. |
| Network | Socket creation is replaced by a function that raises, and no networking module is in the import allowlist. |
| Memory | `RLIMIT_AS` set to `max_memory_mb`: an allocation beyond it raises `MemoryError`. |
| Builtins | An allowlist: types, iteration helpers, math, `print`, `isinstance`, `dir`, exception classes. Absent: `eval`, `exec`, `compile`, `getattr`, `globals`, `vars`, `input`, `breakpoint`, `exit`, the original `open` and `__import__`. |
| Code analysis | Before execution, an AST check rejects access to dunder and private attributes, frame, traceback and generator internals, module objects re-exported by allowed modules, and attribute lookups by string name. |

**Control flow.** `final_answer(answer)` is injected by the sandbox. It
raises an internal exception that the sandbox catches to hand the answer to
the loop. It is present whatever server is connected (or none).
`KeyboardInterrupt` and `SystemExit` are re-raised, never swallowed. In the
agent, termination signals become a `KeyboardInterrupt` in the main
process, which stops the MCP server, removes the container and still writes
`solution.json`.

**MCP tools inside the sandbox.** The `MCPClient` (`sandbox/mcp_client/`)
connects over stdio or streamable HTTP. It keeps the asynchronous MCP
session alive on a background event loop, and lists the server's tools,
resources and prompts. For each tool, a **wrapper** with the tool's name
and its parameters (required first, from the JSON schema) is placed in the
child's namespace. A call is sent to the parent, which calls the server,
and the result comes back as the function's return value. A tool error is
raised in the sandbox as `ToolError`, for the model to read. Any MCP server
works: nothing in the sandbox knows a tool by name.

**Sandbox manual.** `sandbox/manual.py` renders, from the connected
server's schemas, each tool's Python signature (JSON types translated to
Python names) and description, plus `final_answer`. It goes into the system
prompt and is also available in the namespace as `sandbox_manual` and
`get_manual()`. Connecting another server changes the manual.

**Explicit feedback**, so that the model never has to guess:

| Situation | What the model is told |
|---|---|
| No code block in the answer | "No code block found", and the expected format |
| Malformed block run anyway | How it was read (other language tag, missing closing fence, only the first of several blocks) |
| Timeout | "Timeout after N s", the partial output, and that the variables were reset |
| Output too long | The cut, its size, and how to see the rest |
| Edit breaking the syntax | A warning with the line and the error, returned by `edit_file` |
| Tool failure | The tool's error message, raised as `ToolError` |

**SWE-bench.** The sandbox runs on the host and the MCP tools bridge into
Docker (option (b) of the subject). The sandbox restrictions apply in the
same way.

## Tool implementation details

Two FastMCP servers, `mcp_tools_mbpp.py` and `mcp_tools_swebench.py`, serve
the tools over stdio (default) or streamable HTTP
(`--transport streamable-http --host --port`). Tools return text. Errors
are returned as text starting with `Error:`, never as a crash of the server.

### SWE-bench tools

The repository is a host copy of the image's `/testbed`, mounted back on
`/testbed` in the container. The model only ever sees `/testbed` paths: the
file tools map them to the host copy and refuse any path that resolves
outside the repository.

| Tool | Behaviour |
|---|---|
| `read_file(filepath, start_line, end_line)` | Lines `start_line` to `end_line` (1-based, inclusive), each as `<line_number>: <content>`. |
| `edit_file(filepath, old_str, new_str)` | Replaces `old_str`, which must occur exactly once (0 or several occurrences is an error, with the count). On a `.py` file, warns when the result no longer compiles. |
| `list_files(directory, pattern)` | Recursive glob, one absolute path per line. |
| `search_code(pattern, file_pattern)` | Literal search over the files matching `file_pattern`, skipping `.git`, `.venv` and binary files. Output: `/absolute/path.py:<line> <content>`. |
| `search_function_or_class_definition_in_code(name)` | `def`, `async def` or `class` followed by exactly `name` (so `add` does not match `address`), same output format. |
| `find_references(name, filepath, line)` | Checks that `name` is at `filepath:line`, then lists every whole-word use in the Python files, same output format. |
| `run_tests()` | Runs the task's evaluation script inside the container (`docker exec ... bash -l`, so the repository's conda environment is active), killed after 600 s. Returns the test output between `>>>>> Start Test Output` and `>>>>> End Test Output`, keeping the end, where the summary is. The script's own exit code is that of its final `git checkout`, so it is not shown as the test result. |
| `get_patch()` | The unified diff of all changes, built on the host copy with `core.fileMode=false`, so mode changes never enter the patch. New files are included. |
| `run_command(command, workdir, timeout=60)` | Runs a shell command inside the container, in `workdir` (default `/testbed`), and returns the exit code, stdout and stderr. |

**Docker lifecycle** (`agent_swebench/docker.py`):

1. The image is pulled if missing, and `/testbed` is copied out of it to a
   temporary directory.
2. The container is started with `docker run --rm -i` on a process that
   reads its stdin, a pipe the agent holds. If the agent dies, even with
   `kill -9`, the pipe closes, the container exits and `--rm` removes it.
3. On a normal exit, an error, SIGINT or SIGTERM, the agent removes the
   container and the host copy itself.

Containers are named `sweb-<instance_id>-<random>`.

### MBPP tool

| Tool | Behaviour |
|---|---|
| `run_tests(code, test_list=None)` | Runs the task's `test_list` (or the given one) against `code`. Each assertion runs alone, with the task's `test_imports`, in a fresh sandbox (5 s each, 30 s in total). The report starts with `success: true/false (N of M tests passed)`, then one line per assertion: `PASS`, `FAIL` with the value the function returned, or `ERROR` with the exception. |

The model passes its candidate as a string, and the string it tested is the
string it submits.

## Benchmark results and analysis

The full report, with every table, the method and the raw data, is in
[BENCHMARK_REPORT.md](BENCHMARK_REPORT.md). The backing `solution.json`
files are under [`benchmarks/`](benchmarks/).

### MBPP

20 tasks, same agent (validation through `run_tests(code)`), one run per
model:

| Model (provider) | Pass | Mean input tokens | Mean output tokens | Mean time per task |
|---|---|---|---|---|
| `openai/gpt-oss-120b` (Groq) | **19/20** | 1,110 | 447 | 3.0 s |
| `codestral-2508` (Mistral) | **18/20** | 1,466 | 289 | 4.4 s |
| `nemotron-3-ultra` (NVIDIA) | **18/20** | 1,573 | 198 | 16.5 s |
| `ministral-8b-2512` (Mistral) | 14/20 | 1,544 | 526 | 7.7 s |
| `ministral-14b-2512` (Mistral) | 12/20 | 1,331 | 674 | 8.9 s |

Every run stayed within the limits. Solved tasks take 1 or 2 iterations
and about 1,000 input tokens. The failures are mostly a model resubmitting
the same wrong function until the 6,000-token input budget runs out. This
is why the loop now collapses stuck attempts.

### SWE-bench

**Five models × the six tasks the exam can draw, run twice** (60 runs,
`codestral-2508`, `ministral-14b-2512`, `ministral-8b-2512`,
`ministral-3b-2512`, `nemotron-3-ultra`). The first campaign also covers
the three recommended tasks with Qwen as the fifth model.

| Model | Run 1 | Run 2 | Pooled |
|---|---|---|---|
| `codestral-2508` (Mistral) | 4/6 | 5/6 | 9/12 |
| `ministral-14b-2512` (Mistral) | 3/6 | 5/6 | 8/12 |
| `ministral-3b-2512` (Mistral) | 3/6 | 4/6 | 7/12 |
| `ministral-8b-2512` (Mistral) | 3/6 | 3/6 | 6/12 |
| `nemotron-3-ultra` (NVIDIA) | 5/6 | 5/6 | 10/12, mostly finished by the fallback |

| Task | Passes out of 10 runs |
|---|---|
| `pydata__xarray-4629` | 9 |
| `sympy__sympy-13480` | 8 |
| `django__django-11066` | 7 |
| `sympy__sympy-18189` | 6 |
| `sympy__sympy-14711` | 5 |
| `scikit-learn__scikit-learn-13439` | 5 |

**Provider reliability (2026-10-06).** The four Mistral models answered
730 of 731 requests, with mean response times from 1.8 s
(`ministral-3b`) and 1.9 s (`codestral-2508`) to 4.0 s (`ministral-14b`). NVIDIA was
overloaded that afternoon: only 42 % of its requests were answered
(HTTP 503), and 10 of its 12 tasks switched to the fallback model. No task
was lost.

**Intermediary metrics.**

- *Exploration is not the bottleneck*: the agent reads the file that the
  final patch changes by step 7 in 13 of 14 runs, and by step 2 in 11.
- *Submission discipline improved*: after `run_tests()` was changed to
  return the real test output, successes submitted right after a visibly
  green test run went from 2 of 8 to 9 of 10.
- *Failures are mostly caps, not wrong fixes*: most failed runs end on the
  30-iteration or the output cap without a patch, often while repeating
  steps.

**Ablations** (seven on MBPP, two on SWE-bench). Two examples:

- validating through `run_tests(code)` instead of raw asserts took MBPP
  from 75/100 to 81/100 over five models, with shorter answers;
- not sending the stop sequence to `gpt-oss-120b` (the client cuts the
  answer itself) took it from 13/20 to 18/20.

Running the same SWE-bench agent twice changed 12 of 30 verdicts: one run
per model and task measures noise more than a model ranking.

**Mock exams** (the evaluation scripts, `codestral-2508`): the sandbox
tests pass 14/14 since 2026-10-05; MBPP passed 3 of 4 exams (16/20 tasks);
SWE-bench reached 2/3 in the last two exams.

**Selected pipeline.** `codestral-2508` (Mistral) is the default for both
benchmarks. It is among the fastest models to answer, it never failed a request in
the campaigns, and its SWE-bench successes are the shortest (3 to 7
iterations) and use the fewest input tokens. Fallbacks:

- MBPP: Groq `gpt-oss-120b`, then `ministral-14b-2512`, then
  `nemotron-3-ultra`;
- SWE-bench: `ministral-14b-2512`, then `nemotron-3-ultra`.

**Disregarded models:**

- Groq for SWE-bench: its free tier rejects requests above 8,000 tokens;
- `nemotron-3-ultra` for MBPP: too slow, close to the 120 s limit;
- OpenRouter `:free` models: 50 requests a day, and some of them were no
  longer free during the campaigns.

## Resources

### References

- J. Austin et al., *Program Synthesis with Large Language Models* (MBPP),
  2021 — [arXiv:2108.07732](https://arxiv.org/abs/2108.07732)
- C. E. Jimenez et al., *SWE-bench: Can Language Models Resolve Real-World
  GitHub Issues?*, 2023 — [arXiv:2310.06770](https://arxiv.org/abs/2310.06770)
- OpenAI, *Introducing SWE-bench Verified*, 2024 —
  [openai.com/index/introducing-swe-bench-verified](https://openai.com/index/introducing-swe-bench-verified/)
- S. Yao et al., *ReAct: Synergizing Reasoning and Acting in Language
  Models*, 2022 — [arXiv:2210.03629](https://arxiv.org/abs/2210.03629)
- X. Wang et al., *Executable Code Actions Elicit Better LLM Agents*
  (CodeAct), 2024 — [arXiv:2402.01030](https://arxiv.org/abs/2402.01030)
- J. Yang et al., *SWE-agent: Agent-Computer Interfaces Enable Automated
  Software Engineering*, 2024 — [arXiv:2405.15793](https://arxiv.org/abs/2405.15793)
- Hugging Face *smolagents* documentation, for the Thought / Code /
  Observation format and the `<end_code>` marker of code agents (the
  library itself is not used) —
  [huggingface.co/docs/smolagents](https://huggingface.co/docs/smolagents)
- Model Context Protocol specification and Python SDK —
  [modelcontextprotocol.io](https://modelcontextprotocol.io)
- Python documentation: [`multiprocessing`](https://docs.python.org/3.10/library/multiprocessing.html),
  [`resource`](https://docs.python.org/3.10/library/resource.html),
  [`ast`](https://docs.python.org/3.10/library/ast.html)
- Provider API documentation: [Mistral](https://docs.mistral.ai),
  [Groq](https://console.groq.com/docs), [NVIDIA Build](https://build.nvidia.com),
  [OpenRouter](https://openrouter.ai/docs)

### Use of AI

AI assistants, including Claude through Claude Code, were used for:

- **Debugging and research**: analysing failing runs and error traces, and
  looking up provider APIs and free-tier limits, the MCP Python SDK and
  Docker behaviour;
- **Code generation**: drafting parts of the code, which we then reviewed,
  adapted and tested on benchmark runs;
- **Code review and refactoring**: reviewing the code against the subject,
  renaming, translating comments and messages to English, cleaning up;
- **Documentation**: drafting this README, the benchmark report and our
  working notes.

The design decisions were ours: the architecture, the sandbox isolation
model, the prompts and the model selection. Every AI-produced change was
reviewed and checked against benchmark runs before being kept.
