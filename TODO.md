# Agent Smith — TODO & repartition du travail

| | Qui | Domaine |
|---|---|---|
| **Personne 1** | ndi-tull | Execution & Outils (sandbox, MCP, tools, Docker) |
| **Personne 2** | tchemin | Agent & Intelligence (boucle, LLM, prompts, bench) |

> Le projet n'est **pas** "faire generer du code par un LLM". C'est construire un
> **runtime securise et instrumente** pour un agent de code. MBPP / SWE-bench sont
> le banc d'essai, pas l'objet. Voir [RESUME.md](RESUME.md).

---

## Etat actuel

*(maj : arborescence flat creee)*

- [x] `en.subject.pdf` + `RESUME.md` → RESUME complete (section MCP ajoutee :
      definition, "les outils MCP sont les mains de l'agent", qui ecrit quoi)
- [x] `core/models.py` → les 5 models Pydantic sont ecrits
      (ex-`src/validators.py`, deplace en flat)
- [x] `pyproject.toml` → rempli (2 cles a corriger, voir plus bas)
- [x] `Makefile` → rempli (pas de cible test, cf. PYTEST)
- [x] Python 3.10 → `.venv` en 3.10.20, `requires-python` OK
- [x] Arborescence flat layout → creee, tous les `.py` sont VIDES
- [ ] `README.md` → toujours VIDE
- [~] `.gitignore` → `.env` et `__pycache__` OK, il manque `cache/` et `evaluations/`

### Arborescence en place (fichiers vides, a remplir)

```
racine           mcp_tools_mbpp.py   mcp_tools_swebench.py
                 sandbox_template.json   BENCHMARK_REPORT.md
core/            models.py  errors.py
  agent/         loop.py  extraction.py  prompt.py
  llm/           client.py  keyring.py  usage.py
sandbox/         cli.py  executor.py  manual.py
  security/      imports.py  filesystem.py  builtins.py  limits.py
  mcp_client/    client.py  transports.py
mcp_tools/       tools_fs.py  tools_search.py  tools_exec.py
agent_mbpp/      __main__.py  cli.py
agent_swebench/  __main__.py  cli.py  docker.py
configs/         models.json
tests/           test_sandbox_security.py  test_extraction.py  test_mcp_tools.py
```

### Flat layout coherent (3 corrections faites)

- [x] 1. `[project.scripts]` = `"sandbox.cli:main"` (plus de prefixe `src`)
- [x] 2. `[tool.hatch...]` packages = `core`, `sandbox`, `agent_mbpp`,
       `agent_swebench`, `mcp_tools`
- [x] 3. `src/` supprime : `validators.py` → `core/models.py` (`git mv`),
       `__main__.py` vide supprime.

**Reste a verifier :** `uv run sandbox` ne marchera qu'une fois
`sandbox/cli.py:main()` ecrit (le fichier est encore vide).


## Rappel des limites

**Strictes — depassement = tache echouee.**

| Metrique | MBPP | SWE-bench |
|---|---|---|
| Iterations max | 10 | 30 |
| Input tokens | 6 000 | 300 000 |
| Output tokens | 1 500 | 10 000 |
| Timeout | 120 s | 900 s |
| Seuil reussite | 4 / 5 | 2 / 3 |

- Tokens **cumulatifs** sur toute la tache, reasoning tokens inclus.
- Aucun retry autorise pendant l'examen.
- Cles API en dur dans le code = flag securite.
- Solutions recuperees depuis PR / issues / sources externes = **note de 0**.

---

## Dependances & imports

### `pyproject.toml`

*(ECRIT — relire les 2 cles signalees en Etat actuel)*

```toml
[project]
name = "agent-smith"
requires-python = "==3.10.*"
dependencies = [
    "pydantic>=2.0",        # models imposes par le sujet
    "mcp>=1.2",             # SDK officiel MCP (serveur + client)
    "httpx>=0.27",          # appels HTTP vers les APIs LLM
    "python-dotenv>=1.0",   # chargement du .env passe a l'eval
    "docker>=7.0",          # containers SWE-bench (ou subprocess docker CLI)
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.6"]

[project.scripts]
sandbox = "sandbox.cli:main"   # -> uv run sandbox  (flat layout :
                               #    PAS "src.sandbox.cli:main")

[tool.hatch.build.targets.wheel]
packages = ["core", "sandbox", "agent_mbpp", "agent_swebench", "mcp_tools"]
```

**Optionnel selon les choix :**

| Paquet | Quand |
|---|---|
| `openai>=1.0` | si on passe par le SDK OpenAI plutot que httpx brut (tous les providers vises sont OpenAI-compatible) |
| `psutil` | si on veut mesurer la RAM autrement que par `resource` |
| `tiktoken` | fallback de comptage de tokens (normalement inutile : l'API renvoie `usage.prompt_tokens` / `completion_tokens`) |

**INTERDIT** (reimplementent l'orchestration d'agents) : `smolagents`,
`langgraph`, `crewai`, `autogen`, `llama-index`, `langchain-agents`.

### Imports stdlib pour le SANDBOX

Securite = **stdlib uniquement**.

| Module | Usage |
|---|---|
| `ast` | parsing/validation du code avant exec, detection des imports |
| `builtins` | construction du dict de builtins restreints |
| `importlib` | hook d'import custom pour l'allowlist |
| `sys` | `sys.modules`, `sys.path`, redirection stdout/stderr |
| `os`, `os.path` | resolution des chemins (`realpath`) pour l'allowlist FS |
| `pathlib` | manipulation de chemins |
| `resource` | `RLIMIT_AS` (memoire), `RLIMIT_CPU` → limites dures |
| `signal` | `SIGALRM` / `SIGKILL` pour le timeout |
| `multiprocessing` | isolation dans un process separe (approche recommandee) |
| `subprocess` | lancement du serveur MCP stdio, commandes docker |
| `socket` | neutralisation du reseau (monkeypatch avant exec) |
| `io` | `StringIO` pour capturer la sortie |
| `contextlib` | `redirect_stdout` / `redirect_stderr` |
| `traceback` | formatage des erreurs renvoyees au LLM |
| `types` | construction de modules/namespaces |
| `threading`, `queue` | communication et watchdog |
| `tempfile` | zone scratch |
| `json` | configs, serialisation |
| `time`, `datetime` | metriques et timestamps |

### Imports MCP (SDK officiel)

**Serveur :**

```python
from mcp.server.fastmcp import FastMCP
```

**Client** (les DEUX transports sont obligatoires) :

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
```

Session : `list_tools()` / `call_tool()` / `list_resources()` / `list_prompts()`
→ c'est `list_tools()` qui alimente la generation dynamique du manuel.
*(verifier la signature exacte selon la version du SDK installee)*

### Dependances a installer DANS le container SWE-bench (optionnel)

| Paquet | Pourquoi |
|---|---|
| `jedi` | tres utile pour `find_references` / resolution de symboles |
| `ruff` | verification syntaxe/lint apres un `edit_file` |
| `tree` | exploration rapide de l'arborescence |

---

## Phase 0 — a faire ensemble, en premier (BLOQUANT)

Tant que ce n'est pas fige, chacun code contre du vide.

- [x] Setup uv + `pyproject.toml` + Python 3.10 + structure de dossiers
- [x] Makefile (install / run / lint / clean) → pas de cible test
- [~] `.gitignore` (`.env`, `__pycache__` OK) → ajouter `cache/` + `evaluations/`
- [x] **FIGER TOUS les models Pydantic** (`core/models.py`) :
  - [x] `SandboxConfig` — `authorized_imports`, `allowed_directories`,
        `max_execution_time_seconds`, `max_memory_mb`
  - [x] `MBPPTaskInput` — `task_id`, `task_definition`, `function_definition`,
        `test_imports`, `test_list`
  - [x] `SWEBenchTaskInput` — `instance_id`, `problem_statement`, `docker_image`,
        `eval_script`, `hints_text`, `repo` (l'heritage `BaseException` est corrige)
  - [x] `StepMetrics` — `step`, `input_tokens`, `output_tokens`, `request_time_ms`,
        `timestamp`, `api_url`, `model_name`, `llm_output`, `sandbox_input`,
        `sandbox_output`, `retries`
  - [x] `SolutionOutput` — `task_id`, `benchmark`, `success`, `solution`,
        `iterations`, `total_requests`, `total_input_tokens`, `total_output_tokens`,
        `total_time_seconds`, `steps`, `system_prompt`, `error`, `timestamp`

  **Reste :** relire champ par champ contre le sujet (V.3 / V.4) avant de coder
  dessus. Une signature fausse ici casse les deux moities du projet et n'est
  detectee qu'a la validation moulinette.
- [ ] **FIGER l'interface Sandbox ↔ Orchestrateur :**
  - signature de `execute(code)` → `(stdout, stderr, error, is_final, answer)`
  - qui remplit `sandbox_input` / `sandbox_output`
  - comment `final_answer()` remonte la reponse a la boucle
- [ ] Chargement config JSON + `.env` (`OPENROUTER_API_KEY`, etc.)

---

## Personne 1 — ndi-tull : Execution & Outils

Domaine : tout ce qui execute du code et touche au systeme.
Livrables : le sandbox, le serveur MCP, les 9 outils, l'integration Docker.

### P1.1 — Sandbox (coeur du projet, priorite absolue)

- [ ] Choisir l'approche d'isolation (process separe recommande : timeout et
      limites RAM applicables proprement)
- [ ] Allowlist d'imports (`authorized_imports`, support des motifs `module.*`)
- [ ] Allowlist filesystem (`allowed_directories`, chemins resolus DANS le sandbox)
- [ ] Blocage reseau total (entrant + sortant)
- [ ] Timeout d'execution (uniquement le code sandboxe, **pas** les actions MCP)
- [ ] Limite RAM (`max_memory_mb`)
- [ ] Builtins restreints (retirer/surcharger les dangereux)
- [ ] Propagation de `KeyboardInterrupt` / `SystemExit` (jamais captures en silence)
- [ ] Injection de `final_answer()` dans le namespace
      → primitive **du sandbox**, pas un outil MCP, toujours presente
- [ ] Namespace = wrappers MCP decouverts dynamiquement + `final_answer`, rien d'autre

### P1.2 — Feedback au LLM

*Souvent oublie, mais explicitement exige.*

- [ ] aucun bloc de code trouve
- [ ] bloc malforme mais interprete quand meme → expliquer comment
- [ ] timeout atteint → renvoyer la sortie partielle
- [ ] sortie tronquee (limite de taille) → le dire
- [ ] edit ayant casse la syntaxe / le lint

→ **Aucun echec silencieux** : sinon le LLM hallucine ses observations.

### P1.3 — CLI sandbox

- [ ] `uv run sandbox` (REPL interactif)
- [ ] `uv run sandbox sandbox_template.json` (config custom)
- [ ] `uv run sandbox --mcp-stdio "python mcp_tools_mbpp.py" sandbox_template.json`
- [ ] `uv run sandbox --mcp-server <URL>` (HTTP streamable)
- [ ] REPL : memes restrictions, sortie propre sur `exit` et Ctrl+D (EOF)

### P1.4 — MCP

- [ ] Serveur MCP : transports stdio **et** HTTP streamable
- [ ] Client MCP integre dans le sandbox
- [ ] Decouverte dynamique → doit marcher avec un serveur MCP **inconnu**
- [ ] Exposition des tools + resources + prompts
- [ ] Wrappers Python generes automatiquement depuis les schemas
- [ ] Generation dynamique du "sandbox manual" (noms, descriptions, params)
      → change automatiquement si on branche un autre serveur MCP

### P1.5 — Les 9 outils obligatoires

*Testes independamment de la boucle.*

**Filesystem :**

- [ ] `read_file(filepath, start_line, end_line)` → format `cat -n` :
      `"<line_number>: <content>"`
- [ ] `edit_file(filepath, old_str, new_str)` → remplacement exact
- [ ] `list_files(directory, pattern)`

**Recherche** (format commun : `/abs/path.py:<line> <content>`) :

- [ ] `search_code(pattern, file_pattern)`
- [ ] `search_function_or_class_definition_in_code(name)`
- [ ] `find_references(name, filepath, line)`

**Execution :**

- [ ] `run_tests()` → lance l'`eval_script`
- [ ] `get_patch()` → git diff unifie
- [ ] `run_command(command, workdir)` → stdout, stderr, exit code

- [~] `mcp_tools_mbpp.py` **a la racine** du repo (fichier cree, vide)
- [~] `mcp_tools_swebench.py` **a la racine** du repo (fichier cree, vide)

→ la logique des 9 outils va dans le package `mcp_tools/` (`tools_fs.py`,
`tools_search.py`, `tools_exec.py`) ; les 2 fichiers racine ne sont que des
points d'entree fins, l'emplacement racine etant impose par le sujet.

### P1.6 — Docker / SWE-bench

- [ ] Choisir : sandbox **dans** le container, ou sandbox sur l'hote + outils MCP
      faisant le pont vers Docker (les 2 sont valides)
- [ ] Pull / run de l'image (`docker_image` de la tache)
- [ ] Montage de `${TESTBED_PATH}` si necessaire
- [ ] `git -c core.fileMode=false diff` pour `get_patch()`
- [ ] **Cleanup des containers** apres execution (a notre charge, exige)

### P1.7 — Tests de securite

`exam_sandbox.sh` : **tout** doit passer.

- [ ] blocage d'import
- [ ] blocage de builtin
- [ ] blocage reseau
- [ ] restriction de chemin
- [ ] timeout
- [ ] limite memoire
- [ ] protocole MCP

→ Ecrire nos propres tests pour chacun **avant** l'eval.

---

## Personne 2 — tchemin : Agent & Intelligence

Domaine : tout ce qui parle au LLM et pilote le raisonnement.
Livrables : la boucle agent, la couche providers, les prompts, les 2 CLI,
le rapport de benchmark.

### P2.1 — Boucle agentique

*100% maison, frameworks interdits.*

- [ ] Boucle Thought → Code → Observation
- [ ] `max_iterations` parametrable
- [ ] Arret sur `final_answer()` / limite atteinte / erreur fatale
- [ ] Construction de l'historique de conversation envoye au LLM
- [ ] Gestion de la taille du contexte (budget tokens sur toute la tache)
- [ ] Aucun crash possible : toutes les erreurs gerees

### P2.2 — Extraction de code

- [ ] Blocs Python ` ```python ... ``` ` + `<end_code>` (format primaire)
- [ ] XML tool calls (style Anthropic `<invoke>`)
- [ ] JSON / Hermes (`<tool_call>{...}</tool_call>`)
- [ ] ReAct (`Action:` / `Action Input:`)
- [ ] Conversion des formats non-Python → appels de fonction Python
      (le sandbox doit rester agnostique du format)

### P2.3 — Couche LLM

- [ ] Abstraction provider (changer de provider sans refacto majeure)
- [ ] Multi-tokens par provider + **rotation** (rate limits, quotas epuises)
- [ ] Fallback entre providers
- [ ] `stop_sequences` (`<end_code>`, `</tool_call>`...) → **essentiel**, sinon le
      modele invente les resultats d'execution
- [ ] Retry avec backoff, comptabilise dans `StepMetrics.retries`
- [ ] Cles API depuis env vars uniquement (`OPENROUTER_API_KEY`, ...)
- [ ] Tracking : tokens in/out, `request_time_ms`, `total_requests`, latence

### P2.4 — System prompts

- [ ] Injection du sandbox manual (fourni par P1)
- [ ] Slots structures Thought / Code / Observation avec exemples
- [ ] Exemples de boucles de raisonnement efficaces
- [ ] Prompt MBPP (court, contrainte 6k tokens d'entree au total)
- [ ] Prompt SWE-bench (methodologie d'exploration : chercher, lire, editer,
      tester, relire l'echec)

→ **Methode :** resoudre une tache a la main avec seulement les outils de
l'agent, et transcrire ce raisonnement dans le prompt.

### P2.5 — Les deux agents

- [ ] `agent_mbpp` : `uv run python -m agent_mbpp --task-file X --output Y
      --model-name "..." --provider-url "..."`
- [ ] `agent_swebench` : memes options
- [ ] Ecriture du `solution.json` conforme (`SolutionOutput` complet)
- [ ] `final_answer(code)` pour MBPP / `final_answer(get_patch())` pour SWE-bench
- [ ] Respect strict des limites (compteur + arret propre avant depassement)
- [ ] Remplissage de **tous** les champs de `StepMetrics` (`llm_output` brut,
      `sandbox_input`, `sandbox_output`, `retries`) → tracabilite exigee

### P2.6 — `BENCHMARK_REPORT.md`

*Racine du repo — fichier cree, vide.*
**≥ 5 modeles × ≥ 3 taches SWE-bench communes.**

- [ ] Setup : modeles/providers, taches choisies + justification
- [ ] Tableau modele × tache : pass/fail, iterations, tokens in/out, temps mur
- [ ] Fiabilite provider : temps de reponse moyen, retries, disponibilite
- [ ] ≥ 2 metriques intermediaires parmi :
  - etape du 1er acces au fichier du patch final (exploration)
  - etape ou les echecs de tests commencent a baisser (progres partiel)
  - iterations entre "tests au vert" et `final_answer` (discipline, 0 ideal)
- [ ] Etude d'ablation : avant/apres un changement (prompt, outils, params)
      sur les memes taches et le meme modele
- [ ] Conclusions : modeles retenus / ecartes, justifies par les donnees
- [ ] Les `solution.json` de backing presents dans le repo

→ Mesure manuelle acceptee, c'est l'analyse qui compte.

---

## A faire ensemble (fin de projet)

- [ ] **`README.md` en anglais**, a la racine :
  - [ ] 1ere ligne en italique : *"This project has been created as part of the
        42 curriculum by tchemin, ndi-tull."*
  - [ ] Description / Instructions / Resources (+ usage de l'IA detaille)
  - [ ] System architecture
  - [ ] Agent loop explanation
  - [ ] Sandbox design
  - [ ] Tool implementation details
  - [ ] Benchmark results and analysis
- [ ] Verifier le repo : configs sandbox + modeles, `mcp_tools_*.py` a la racine,
      `BENCHMARK_REPORT.md`, `solution.json`
- [ ] **Ne pas inclure :** images Docker, poids de modeles, outputs generes
- [ ] Relire le code de l'autre : en soutenance, on doit savoir modifier l'agent
      en 2-5 min sur une tache MBPP. Prevoir 2 sessions de passation.

---

## Ordre de travail recommande

1. **Phase 0 ensemble** (models + interface + setup) — *bloquant*
   → setup, structure, flat layout et models **faits**. Reste : l'interface
   Sandbox ↔ Orchestrateur, et le chargement config JSON / `.env`.
2. **En parallele :**
   - `ndi-tull` → sandbox minimal qui execute du code + `final_answer`
   - `tchemin` → boucle agent minimale + 1 provider en dur
3. **Premier jalon :** MBPP end-to-end avec le modele le plus capable disponible
   et **sans** limites de tokens/iterations. Si ca ne passe pas la, ajouter des
   contraintes n'aidera pas.
4. Brancher les vraies limites, mesurer, optimiser le prompt.
5. Durcir le sandbox (P1.7) pendant que P2 attaque SWE-bench.
6. SWE-bench sur les 3 taches conseillees :
   `sympy__sympy-14711` / `sympy__sympy-13480` / `pydata__xarray-4629`
7. `BENCHMARK_REPORT.md` une fois les 2 benchmarks fonctionnels.
8. `README.md` + relecture croisee.

---

## Points de synchro

- Format `sandbox_input` / `sandbox_output` : a caler tot, c'est l'interface entre
  les deux moities du projet.
- Le **sandbox manual** est produit par P1 et consomme par P2 : definir sa forme
  des que la decouverte MCP marche.
- MBPP end-to-end **avant** de toucher a Docker.
- Ne pas optimiser (tokens, choix de modele) avant que l'approche soit prouvee sur
  une tache.
