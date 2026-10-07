PYTHON_VERSION := 3.10
UV             := uv
CACHE_DIR      := cache
MBPP_MODEL     := codestral-2508
MBPP_URL       := https://api.mistral.ai/v1
SWE_MODEL      := codestral-2508
SWE_URL        := https://api.mistral.ai/v1
.DEFAULT_GOAL := help

.PHONY: help setup install dev sandbox sandbox-mbpp sandbox-swebench \
        mbpp swebench lint format test test-samples test-update \
        clean clean-docker clean-all

help:
	@echo "Agent Smith - available targets"
	@echo ""
	@echo "  Setup"
	@echo "    setup              Install Python $(PYTHON_VERSION)"
	@echo "    install            Sync the dependencies"
	@echo "    dev                Dependencies + dev tools (ruff)"
	@echo ""
	@echo "  Sandbox            (optional: CONFIG=sandbox_template.json)"
	@echo "    sandbox            Sandbox REPL without an MCP server"
	@echo "    sandbox-mbpp       Sandbox REPL + MBPP MCP server (stdio)"
	@echo "    sandbox-swebench   Sandbox REPL + SWE-bench MCP server (stdio)"
	@echo ""
	@echo "  Agents             (required: TASK=... ; optional: MODEL=... URL=...)"
	@echo "    mbpp               Run the MBPP agent"
	@echo "                       default: $(MBPP_MODEL) ($(MBPP_URL))"
	@echo "    swebench           Run the SWE-bench agent"
	@echo "                       default: $(SWE_MODEL) ($(SWE_URL))"
	@echo ""
	@echo "  Quality"
	@echo "    lint               Static analysis (ruff)"
	@echo "    format             Format the code (ruff)"
	@echo "    test               Tests (extraction + API responses)"
	@echo "    test-samples       Show the extraction of each sample"
	@echo "    test-update        Regenerate the sample snapshots"
	@echo ""
	@echo "  Cleanup"
	@echo "    clean              Python caches and build artifacts"
	@echo "    clean-docker       Leftover SWE-bench containers"
	@echo "    clean-all          clean + clean-docker + .venv + $(CACHE_DIR)"

setup:
	$(UV) python install $(PYTHON_VERSION)

install:
	$(UV) sync

dev:
	$(UV) sync --extra dev

sandbox:
	$(UV) run sandbox $(CONFIG)

sandbox-mbpp:
	$(UV) run sandbox --mcp-stdio "python mcp_tools_mbpp.py" $(CONFIG)

sandbox-swebench:
	$(UV) run sandbox --mcp-stdio "python mcp_tools_swebench.py" $(CONFIG)

mbpp:
	@mkdir -p $(CACHE_DIR)
	$(UV) run python -m agent_mbpp \
		--task-file $(TASK) \
		--output $(CACHE_DIR)/mbpp_solution.json \
		--model-name "$(or $(MODEL),$(MBPP_MODEL))" \
		--provider-url "$(or $(URL),$(MBPP_URL))"

swebench:
	@mkdir -p $(CACHE_DIR)
	$(UV) run python -m agent_swebench \
		--task-file $(TASK) \
		--output $(CACHE_DIR)/swebench_solution.json \
		--model-name "$(or $(MODEL),$(SWE_MODEL))" \
		--provider-url "$(or $(URL),$(SWE_URL))"

lint:
	$(UV) run ruff check .

format:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

test:
	$(UV) run pytest

test-samples:
	$(UV) run pytest tests/test_samples.py -s -k dump

test-update:
	$(UV) run pytest --update-snapshots

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
	rm -rf .ruff_cache build dist

clean-docker:
	@docker ps -aq --filter "name=sweb" | xargs -r docker rm -f

clean-all: clean clean-docker
	rm -rf .venv $(CACHE_DIR)
