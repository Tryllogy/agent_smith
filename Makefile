PYTHON_VERSION := 3.10
UV             := uv
CACHE_DIR      := cache
MBPP_MODEL     := ministral-14b-2512
MBPP_URL       := https://api.mistral.ai/v1
SWE_MODEL      := nvidia/nemotron-3-super-120b-a12b
SWE_URL        := https://integrate.api.nvidia.com/v1
.DEFAULT_GOAL := help

.PHONY: help setup install dev sandbox sandbox-mbpp sandbox-swebench \
        mbpp swebench lint format test test-samples test-update \
        clean clean-docker clean-all

help:
	@echo "Agent Smith - cibles disponibles"
	@echo ""
	@echo "  Setup"
	@echo "    setup              Installe Python $(PYTHON_VERSION)"
	@echo "    install            Synchronise les dependances"
	@echo "    dev                Dependances + outils de dev (ruff)"
	@echo ""
	@echo "  Sandbox            (option : CONFIG=sandbox_template.json)"
	@echo "    sandbox            REPL sandbox sans serveur MCP"
	@echo "    sandbox-mbpp       REPL sandbox + MCP MBPP (stdio)"
	@echo "    sandbox-swebench   REPL sandbox + MCP SWE-bench (stdio)"
	@echo ""
	@echo "  Agents             (requis : TASK=... ; option : MODEL=... URL=...)"
	@echo "    mbpp               Lance l'agent MBPP"
	@echo "                       defaut : $(MBPP_MODEL) ($(MBPP_URL))"
	@echo "    swebench           Lance l'agent SWE-bench"
	@echo "                       defaut : $(SWE_MODEL) ($(SWE_URL))"
	@echo ""
	@echo "  Qualite"
	@echo "    lint               Analyse statique (ruff)"
	@echo "    format             Formate le code (ruff)"
	@echo "    test               Tests (extraction + reponses API)"
	@echo "    test-samples       Affiche l'extraction de chaque sample"
	@echo "    test-update        Regenere les snapshots des samples"
	@echo ""
	@echo "  Nettoyage"
	@echo "    clean              Caches Python et artefacts de build"
	@echo "    clean-docker       Conteneurs SWE-bench restants"
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
