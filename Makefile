PYTHON_VERSION := 3.10
UV             := uv
CACHE_DIR      := cache
.DEFAULT_GOAL := help

.PHONY: help setup install dev sandbox sandbox-mbpp sandbox-swebench \
        mbpp swebench test lint format check clean clean-docker clean-all

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

setup:
	$(UV) python install $(PYTHON_VERSION)
	$(UV) python pin $(PYTHON_VERSION)

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
		--model-name "$(MODEL)" \
		--provider-url "$(URL)"

swebench:
	@mkdir -p $(CACHE_DIR)
	$(UV) run python -m agent_swebench \
		--task-file $(TASK) \
		--output $(CACHE_DIR)/swebench_solution.json \
		--model-name "$(MODEL)" \
		--provider-url "$(URL)"

test:
	$(UV) run pytest -v

lint:
	$(UV) run ruff check .

format:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

check: lint test

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache build dist

clean-docker:
	@docker ps -aq --filter "name=sweb" | xargs -r docker rm -f

clean-all: clean clean-docker
	rm -rf .venv $(CACHE_DIR)
