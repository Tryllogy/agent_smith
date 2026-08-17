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

*(maj : 2026-08-16 — MBPP end-to-end, 9/10 mesure sur taches reelles)*

- [x] `en.subject.pdf` + `RESUME.md` → RESUME complete (section MCP ajoutee :
      definition, "les outils MCP sont les mains de l'agent", qui ecrit quoi)
- [x] `core/models.py` → les 5 models Pydantic sont ecrits
      (ex-`src/validators.py`, deplace en flat)
- [x] `pyproject.toml` → rempli (2 cles a corriger, voir plus bas)
- [x] `Makefile` → rempli
- [x] Python 3.10 → `.venv` en 3.10.20, `requires-python` OK
- [x] Arborescence flat layout → creee
- [ ] `README.md` → toujours VIDE
- [~] `.gitignore` → `.env`, `__pycache__`, `cache`, `moulinette`, `tests` OK ;
      il manque toujours `evaluations/`

### Qui a du code, au 2026-08-16

| Ecrit | Encore vide |
|---|---|
| `core/models.py`, `core/constants.py`, `core/errors.py` | `core/llm/keyring.py` |
| `core/api_key.py` (nouveau) | `sandbox/cli.py`, `manual.py`, `security/limits.py` |
| `core/llm/client.py`, `core/llm/response.py` | tout `sandbox/mcp_client/` |
| `core/agent/` : `loop.py`, `prompt.py`, `extraction.py` | tout `mcp_tools/`, les 2 `mcp_tools_*.py` racine |
| `agent_mbpp/` : `cli.py`, `__main__.py` | tout `agent_swebench/` (4 fichiers) |
| `sandbox/executor.py` | `configs/models.json`, `sandbox_template.json` |
| `sandbox/security/` : `imports`, `builtins`, `filesystem`, `network`, `ast_guard` | `BENCHMARK_REPORT.md`, `README.md` |

**Cote P1 (ndi-tull) : demarre.** L'executeur et cinq modules de securite
existent ; le sandbox execute du code et remonte `final_answer`, ce qui a
debloque la boucle de P2. Restent le CLI/REPL, le manual, et tout MCP.

**`core/llm/usage.py` supprime** (decision du 2026-08-14) : le suivi d'usage
vit dans `Loop` (`usage_input` / `usage_output` / `requests`), un module
separe aurait duplique l'etat sans proprietaire clair.

### Arborescence (`+` ecrit, `.` encore vide)

```
racine         . mcp_tools_mbpp.py  . mcp_tools_swebench.py
               . sandbox_template.json  . BENCHMARK_REPORT.md  . README.md
core/          + models.py  + errors.py  + constants.py  + api_key.py
  agent/       + loop.py  + extraction.py  + prompt.py
  llm/         + client.py  + response.py  . keyring.py   (usage.py supprime)
sandbox/       . cli.py  + executor.py  . manual.py
  security/    + imports.py  + filesystem.py  + builtins.py  + network.py
               + ast_guard.py  . limits.py
  mcp_client/  . client.py  . transports.py
mcp_tools/     . tools_fs.py  . tools_search.py  . tools_exec.py
agent_mbpp/    + __main__.py  + cli.py
agent_swebench/. __main__.py  . cli.py  . docker.py
configs/       . models.json
tests/         + banc d'essai local, gitignore, hors rendu (158 tests)
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
- [x] Makefile (install / run / lint / clean)
- [~] `.gitignore` (`.env`, `__pycache__`, `cache`, `tests` OK) → ajouter
      `evaluations/`
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
- [x] **Interface Sandbox ↔ Orchestrateur figee et en service :**
  - `execute(code, config)` → `(stdout, stderr, error, is_final, answer)`
  - `sandbox_input` = le bloc extrait, `sandbox_output` = `stdout + stderr`
    (+ `error` s'il y en a un), remis a zero en tete de chaque tour
  - `final_answer()` remonte par `is_final` / `answer` — un **fait
    d'execution**, jamais une relecture du source. La boucle exige en plus que
    `answer` soit une `str`
  - la config part en `model_copy()` : le budget du tour n'ecrase pas le
    reglage injecte
- [x] Chargement `.env` (`OPENROUTER_API_KEY`, liste separee par virgules)
- [ ] Chargement de la config JSON des modeles (cf. P2.5 bis)

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

- [x] Boucle Thought → Code → Observation → complete et verifiee sur taches
      reelles (15 taches MBPP, 2 modeles)
- [x] `max_iterations` parametrable → via `constants.Bench.iterations`,
      injecte dans `Loop` (MBPP 10 / SWE 30)
- [x] Arret sur `final_answer()` / limite atteinte / erreur fatale
  - [x] limites tokens + timeout testees en tete de `run()`
  - [x] `final_answer()` detecte via `is_final` / `answer` rendus par
        `execute()` — un fait d'execution, pas une relecture du source
  - [x] la reponse finale doit etre une `str`, sinon observation au modele
  - [x] erreur fatale : `Transient` → retry, `Permanent` → abandon propre.
        Rien ne sort des deux familles (16 cas parametres en test)
- [x] Construction de l'historique → assistant apres chaque `thought()`,
      observation apres chaque execution
- [x] Gestion de la taille du contexte → `max_tokens` de chaque requete
      derive du budget restant, arret propre a l'epuisement
- [x] Aucun crash possible : 158 tests, dont 16 sur l'etancheite de la
      hierarchie d'exceptions

**Corrige le 2026-08-16 — message d'observation.** Le rappel "aucun
`final_answer` capture" n'existait que dans la branche "sortie vide" : un code
qui affichait quelque chose recevait sa propre sortie sans un mot sur
`final_answer`, et le modele concluait qu'il avait fini. Constate sur la tache
MBPP 453 (3 tours perdus a renvoyer le meme bloc). Les deux faits — la sortie
du programme et le rappel — se composent maintenant dans un seul message.

**Corrige le 2026-08-16 — comptabilite des etapes.** Une sortie par garde
posterieure a une requete aboutie n'enregistrait pas son `StepMetrics` : les
totaux ne valaient plus la somme des `steps`. Invariants tenus desormais sur
les quatre familles de sortie : une etape par iteration, numerotation depuis 1
sans trou ni doublon, totaux egaux a la somme des etapes, et **aucune** etape
pour une sortie anterieure a la premiere requete.

→ **Reste :** les `retries` d'un tour qui sort par une garde ne sont comptes
nulle part (un rendu peut afficher `total_requests: 9` avec `steps: []`, sans
dire ce qui a echoue).

### P2.2 — Extraction de code

- [x] Blocs Python ` ```python ... ``` ` + `<end_code>` (format primaire)
- [x] Retour a 3 cles : `code`, `found` (un bloc repere ?), `format`
      (`"python"` si le bloc parse, `""` sinon, `None` si aucun bloc)
- [x] Validation par `ast.parse` sans exception : une sortie tronquee ressort
      en `found=True` / `format=""`, le code invalide est conserve pour etre
      renvoye au modele en observation

**Decision du 2026-08-12 : un seul format supporte.** Les trois autres sont
abandonnes, pas reportes.

- [-] ~~XML tool calls (style Anthropic `<invoke>`)~~
- [-] ~~JSON / Hermes (`<tool_call>{...}</tool_call>`)~~
- [-] ~~ReAct (`Action:` / `Action Input:`)~~
- [-] ~~Conversion des formats non-Python → appels de fonction Python~~
      (plus d'objet : sans format structure en entree, il n'y a rien a
      convertir — la fonction `generate()` est devenue morte)

Raisons, a savoir redire en soutenance :

1. Le prompt systeme impose un format unique (bloc + `<end_code>` +
   `final_answer`). Parser quatre formats quand on n'en demande qu'un est une
   robustesse decorative.
2. Deux des trois etaient **inatteignables par construction** :
   `</tool_call>` et `<invoke>` sont dans `LLM_STOP_SEQUENCE`, donc la
   generation s'arrete avant que la balise soit emise.
3. Le troisieme etait **nuisible** : le motif `Action:` matchait n'importe ou
   dans la prose et faisait tomber une reponse par ailleurs valide.
4. La robustesse au format passe desormais par la boucle : format non
   reconnu → observation renvoyee au modele → nouvelle iteration.

→ [x] Consequence traitee : `LLM_START_SEQUENCE` et `LLM_STOP_SEQUENCE`
(`core/constants.py`) ne contiennent plus que ` ```python ` et `<end_code>`.

### P2.3 — Couche LLM

- [x] Abstraction provider → `LLMClient` (`core/llm/client.py`) est le **seul**
      module qui importe `httpx`. Injecte dans `Loop`, donc testable sans
      reseau ni `monkeypatch` de `httpx`
- [x] Multi-tokens par provider + **rotation** → 429 fait tourner sans
      condamner, 402 marque la cle epuisee et saute les mortes, vivier vide
      remonte en `Permanent`. Verifie sur 5 situations limites
- [ ] Fallback entre providers (un seul provider en service)
- [x] `stop_sequences` → `constants.LLM_STOP_SEQUENCE` envoye dans le payload
- [~] Retry comptabilise dans `StepMetrics.retries` ; le **backoff** se limite
      a `sleep(retry_after)` quand l'en-tete est present, sinon 0
- [x] Cles API depuis env vars uniquement → `load_dotenv()` sans test de
      retour (le fichier est un confort local, pas une obligation), la seule
      question posee est `os.getenv`. L'import ne leve plus jamais
- [x] Liste de cles : `OPENROUTER_API_KEY=cle1,cle2,...`, entrees vides
      filtrees, convention declaree dans `.env.example`
- [x] Tracking complet : `usage_input` / `usage_output`, `request_time_ms`,
      `total_requests`, `retries` par etape
- [x] Erreurs API traduites en exceptions Python typees (champ `error` en
      HTTP 200, `choices` vide, `content` null des modeles de raisonnement,
      `usage` absent, corps non-JSON, timeout, erreur de transport)
- [x] `reasoning` capture depuis `message.reasoning` et joint a `llm_output`

**`core/api_key.py` (2026-08-16).** Une cle est un objet `APIKey` avec son
drapeau `usable`, pas une chaine. Trois raisons : une `str` passee au lieu
d'une liste etait indexee **caractere par caractere** (chaque requete partait
avec `Bearer c`, et le serveur repondait 401 — diagnostic impossible) ;
marquer une cle epuisee plutot que la supprimer garde la taille du vivier
stable, donc la rotation n'a plus de rattrapage d'indice ; et `__repr__` ne
divulgue rien. Le constructeur de `LLMClient` refuse tout ce qui n'est pas une
`list[APIKey]`.

**Echeance reelle sur les appels (2026-08-16).** Le `timeout` de `httpx` est
**par phase d'E/S, pas une duree totale** : mesure, un serveur qui envoie un
octet par seconde traverse un `timeout=2` pendant 6 secondes. En conditions
reelles, un appel a dure 98 s sous un plafond de 30 s, et une tache MBPP a
fini a 135,8 s — au-dela de la limite de 120 s, donc `Metrics valid: NO`.

L'appel bloquant part maintenant dans un `threading.Thread(daemon=True)` et
`join(timeout=...)` fait office d'echeance. On n'interrompt pas le thread —
c'est impossible en Python — on l'**abandonne** ; le drapeau `daemon` est ce
qui empeche l'interpreteur de l'attendre a la sortie (mesure : 8,65 s contre
3,47 s sans). L'exception du thread est stockee puis **relevee dans le meme
`try`**, sinon les gestionnaires `httpx.*` ne voient plus rien passer.
Le `timeout=` de `httpx` est conserve **en plus** : il coupe les serveurs
muets, l'echeance borne les serveurs lents.

#### Modeles gratuits OpenRouter (releve du 2026-08-16)

**19 gratuits sur 413** (contre 17 sur 399 le 2026-08-10). Apparus depuis :
`nvidia/nemotron-3.5-lightning:free`, `dots-studio/dots-3-note-preview:free`,
`liquid/lfm-2.5-2.6b:free`, `nvidia/nemotron-nano-12b-v2-vl:free`.
La note "liste volatile" se verifie en six jours.

**Les 19 annoncent tous `reasoning` dans `supported_parameters`.** Ce champ
dit "sait raisonner", pas "raisonne par defaut" : le catalogue ne permet donc
**aucun** tri. Le seul critere fiable est la mesure de
`usage.completion_tokens_details.reasoning_tokens` sur une requete de
controle. Sonde du 2026-08-16, meme requete pour tous (bloc ```python
demande) :

| Modele | tokens sortie | dont raisonnement | temps | bloc ? |
|---|---|---|---|---|
| `openai/gpt-oss-20b:free` | **371** | 218 | 38,4 s | oui |
| `nvidia/nemotron-3.5-lightning:free` | 1500 | 1088 | 9,8 s | oui |
| `cohere/north-mini-code:free` | 1499 | 1246 | 52,8 s | non |
| `poolside/laguna-s-2.1:free` | 1500 | 1500 | 34,2 s | non |
| `google/gemma-4-31b-it:free` | — | — | — | 429 fournisseur |

Trois sur cinq epuisent le plafond MBPP de 1500 tokens **des la premiere
requete**, sur un exercice trivial, dont deux sans ecrire une seule ligne de
code. `gpt-oss-20b` est le seul a s'arreter de deliberer pour repondre.
`gpt-oss` expose en plus un `reasoning_effort` (`low`/`medium`/`high`), levier
disponible avant d'avoir a changer de modele.

**Quota : 50 requetes/jour et par compte** sur les modeles `:free`
(`limit_source: openrouter_free_tier_daily`, reset a 02:00 locales). 4 cles en
service, epuisees le meme jour par ~30 requetes de campagne chacune. La
rotation multi-cles n'est donc pas un confort : c'est ce qui rend une campagne
de benchmark realisable. A prevoir pour les 5 modeles x 3 taches SWE-bench.

→ Un 429 `free-models-per-day` n'est **pas** un rate limit passager (8 h
d'attente). La boucle le traite comme transitoire, ce qui est correct tant
qu'une cle survit ; quand toutes sont dans cet etat, la tache brule son budget
en reessais. Le corps de la reponse porte pourtant `limit_source`, de quoi
distinguer "ralentis" de "reviens demain".

#### Releve precedent (2026-08-10) — conserve pour comparaison

Le sujet impose les **offres gratuites exclusivement** : aucun plan payant,
credit achete ou compte facture. Verifier `usage.cost == 0` sur une requete
de controle avant de lancer une campagne de benchmark.

Comment relister : `GET https://openrouter.ai/api/v1/models` (public, sans
auth), garder les entrees ou `pricing.prompt` **et** `pricing.completion`
valent `"0"`. Filtrer sur le prix, pas sur le suffixe `:free` : certaines
entrees gratuites ne le portent pas.

17 gratuits sur 399 au releve. Utilisables pour du code :

| Identifiant | Contexte |
|---|---|
| `nvidia/nemotron-3-ultra-550b-a55b:free` | 1 000 000 |
| `poolside/laguna-s-2.1:free` | 262 144 |
| `poolside/laguna-xs-2.1:free` | 262 144 |
| `google/gemma-4-31b-it:free` | 262 144 |
| `google/gemma-4-26b-a4b-it:free` | 262 144 |
| `nvidia/nemotron-3-super-120b-a12b:free` | 262 144 |
| `inclusionai/ling-3.0-tiny:free` | 262 144 |
| `cohere/north-mini-code:free` | 256 000 |
| `nvidia/nemotron-3-nano-30b-a3b:free` | 256 000 |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | 256 000 |
| `openai/gpt-oss-20b:free` | 131 072 |
| `nvidia/nemotron-nano-9b-v2:free` | 128 000 |

A ecarter (gratuits mais hors sujet) : `google/lyria-3-pro-preview` et
`google/lyria-3-clip-preview` (audio), `nvidia/nemotron-3.5-content-safety`
(classifieur de moderation). `openrouter/free` est un routeur automatique,
pas un modele identifiable — inutilisable pour un benchmark reproductible.

Criteres de choix :

- **Commencer par le plus capable** (`nemotron-3-ultra-550b`), sans limites.
  Le sujet : si ca ne passe pas sans contraintes, les contraintes n'aideront pas.
- **Eviter le modele `reasoning`** : ses tokens de raisonnement comptent dans
  la limite de sortie, or MBPP n'en autorise que 1 500 au total.
- **Ignorer la taille de contexte** comme critere : la vraie contrainte est
  6 000 tokens d'entree cumules (MBPP), tres en dessous de tous ces modeles.
- **Quotas journaliers** sur le tier gratuit → c'est la raison d'etre du
  multi-cles + rotation ci-dessus. 5 modeles x 3 taches SWE-bench pour le
  rapport, plus les iterations de dev, les atteindront.
- **Liste volatile** : les modeles gratuits apparaissent et disparaissent chez
  OpenRouter. Ne jamais figer un identifiant dans le code — `--model-name` est
  deja un parametre impose par le sujet. Relister avant chaque campagne.

### P2.4 — System prompts

- [~] Injection du sandbox manual (fourni par P1) → le slot existe dans
      `Prompt` (`tools` + `allowed_imports`), mais `agent_mbpp/cli.py:30`
      passe toujours `tools=None` : le prompt affiche litteralement "None" au
      modele. En attente du manual MCP de P1
- [x] Slots structures Thought / Code / Observation avec exemples
- [x] Message d'observation revu (2026-08-16) : `Observation:` en tete dans
      **tous** les cas, sortie du programme transmise **verbatim** (pas de
      `strip()` : un saut de ligne final est une donnee), et rappel
      `final_answer` compose avec la sortie au lieu de l'exclure. Mesure de
      l'effet : la tache 453 perdait 3 tours a renvoyer le meme bloc
- [x] Exemples de boucles de raisonnement efficaces → l'exemple `smallest_abs`
      montre un premier essai **faux**, l'observation, puis la correction
- [x] Prompt MBPP (court, contrainte 6k tokens d'entree au total)
- [ ] Prompt SWE-bench (methodologie d'exploration : chercher, lire, editer,
      tester, relire l'echec)
- [x] `allowed_imports` alimente depuis `SandboxConfig().authorized_imports`

→ **Methode :** resoudre une tache a la main avec seulement les outils de
l'agent, et transcrire ce raisonnement dans le prompt.

### P2.5 — Les deux agents

- [x] `agent_mbpp` : les 4 options du sujet, `--output` corrige (plus
      d'abreviation `argparse`), tache chargee + validee contre `MBPPTaskInput`
- [ ] `agent_swebench` : memes options → les 4 fichiers sont toujours vides
- [x] Ecriture du `solution.json` conforme → `model_dump_json(indent=4)`
      (`json.dump` ne sait pas serialiser un `BaseModel`).
      `validate_metrics` repond **YES** sur toutes les taches mesurees
- [x] `final_answer(code)` pour MBPP
- [ ] `final_answer(get_patch())` pour SWE-bench
- [x] Respect strict des limites → arret propre sur chacune des quatre
      (iterations, tokens entree, tokens sortie, temps)
- [x] Remplissage de **tous** les champs de `StepMetrics`

### P2.5 bis — `configs/models.json` (exige au rendu, VIDE)

Sujet chap. VIII p.38 : *"Configuration files for sandbox and models"*. Le
sujet **n'impose aucun schema** pour le versant modeles — a nous de le definir
et de le defendre. Fichier de 0 octet, lu par personne.

Forme decidee le 2026-08-16 : `--model-name` reste la CLI imposee et devient
la **cle de recherche** dans le JSON. Trouve → on prend sa config ; absent →
profil par defaut conservateur (aucun parametre exotique : un modele inconnu
est un modele dont on ignore les capacites).

- [ ] Y mettre : URL/endpoint du fournisseur, reglages propres au modele
      (ex. `reasoning_effort`, que `gpt-oss` comprend et Nemotron non)
- [ ] **Ne PAS y mettre** les limites du benchmark (1500 tokens, 10 iterations,
      120 s) : ce sont des proprietes de MBPP, pas du modele. Elles vivent dans
      `constants.MBPP`. Deux sources de verite = divergence garantie
- [ ] **Ne PAS y mettre** les mesures (ratio de raisonnement, latences) :
      ce sont des observations, leur place est dans `BENCHMARK_REPORT.md`
- [ ] Regle de precedence a fixer : l'argument CLI l'emporte sur le fichier.
      Piege : avec des defauts `argparse` en dur, "passe par l'utilisateur" et
      "valeur par defaut" sont indistinguables → defauts a `None`
- [ ] Cle = identifiant exact OpenRouter, prefixe et suffixe `:free` compris
- [ ] Validation par un model Pydantic, par symetrie avec `SandboxConfig`
- [ ] Lecture dans `cli.py` (meme frontiere que `get_api_keys()`), **jamais**
      dans `LLMClient` : le client recoit une config, il ne va pas la chercher
- [ ] Trois echecs distincts, trois reponses : modele inconnu → repli
      silencieux ; fichier absent ou JSON invalide → bruyant, au demarrage
- [ ] Aucune cle dedans. Le JSON dit *quels* modeles et *comment* les appeler,
      le `.env` fournit *avec quoi*

### P2.6 — `BENCHMARK_REPORT.md`

*Racine du repo — fichier cree, vide.*
**≥ 5 modeles × ≥ 3 taches SWE-bench communes.**
Candidats : voir la table des modeles gratuits en P2.3 (12 utilisables).

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

#### Campagnes MBPP deja faites (matiere pour le rapport)

Taches figees dans `cache/run2/task_*.json`, solutions dans `cache/run{2,3,4}/`.
Reussites **verifiees en executant les `test_list`**, pas d'apres le rapport de
l'agent — les deux verdicts ont toujours concorde.

| Serie | Modele | reel | sortie mediane | max | duree des 10 |
|---|---|---|---|---|---|
| `run2` | `nemotron-3-ultra-550b` | **9/10** | 446 | 730 | 229 s |
| `run3` | `gpt-oss-20b` | **8/10** | 226 | 624 | 473 s |
| `run4` | `gpt-oss-20b` (apres correctifs) | **8/10** | 221 | 624 | 461 s |

Barre du sujet : 4/5, soit 80 %. Sur 25 executions distinctes (5 + 10 + 10),
21 reussites, soit 84 % — on passe, sans marge.

Les trois echecs, et ce qu'ils ont appris :

1. **MBPP 453** (nemotron) — la bonne fonction etait ecrite des le tour 1, mais
   un appel de 98,3 s a mange 82 % du budget ; le `final_answer` correct du
   tour 4 est arrive avec 0,08 s de budget sandbox restant. Deux causes :
   le message d'observation muet sur `final_answer` (3 tours perdus) et
   l'absence d'echeance reelle. **Les deux corrigees.**
2. **MBPP 87** (nemotron) — 1500 tokens de sortie **entierement en
   raisonnement**, aucun bloc de code emis, alors que la reponse figurait a la
   fin de la deliberation. `finish_reason: length`, garde declenchee. Cause
   irreductible cote modele. `gpt-oss` passe cette tache du premier coup.
3. **MBPP 59 et 413** (gpt-oss) — rafales de 429 *"temporarily rate-limited
   upstream"* du fournisseur, reproduites a l'identique. 0 iteration, 5 et 9
   requetes, toutes rejetees. La 413 a fini a **135,8 s** → `Metrics valid: NO`.
   Le depassement etait imputable a la boucle, **corrige** ; l'instabilite du
   fournisseur ne l'est pas.

→ Les deux modeles echouent pour des raisons **independantes** : verbosite
d'un cote, instabilite du fournisseur de l'autre. Sur 20 executions la boucle
n'a commis qu'une seule faute qui lui soit imputable. Avec des taux si
proches, le choix ne se tranchera pas sur 10 taches — d'ou l'interet d'un
basculement de modele sur echec repete, a etudier (chantier, pas correctif).

→ Statistiques d'appel sur les 15 premieres taches (28 appels) : duree mediane
6,3 s, **moyenne 14,8 s, max 98,3 s** ; 5 appels sur 28 depassent les 30 s du
plafond nominal. C'est cette distribution qui a motive l'echeance par thread.

#### `run4` — les memes 10 taches apres les correctifs (2026-08-16)

Meme modele, memes taches, meme ordre que `run3`. Resultat reel **8/10**, avec
les **memes deux echecs** (59 et 413). Ce que le rejeu a change :

- **`Metrics valid: YES` sur les 10** (`run3` : 9/10). Les deux echecs
  s'arretent a **115,0 s exactement** au lieu de 118,6 s et 135,8 s.
  L'echeance par thread tient la limite des 120 s : c'est la seule faute
  imputable a la boucle sur 20 executions, et elle a disparu.
- **Le plafond de 30 s mord maintenant** : 87, 17 et 244 ont demande un appel
  de plus qu'en `run3` (1 → 3, 1 → 2, 1 → 2). Un appel abandonne a 30 s puis
  rejoue coute une requete de plus ; il evite l'appel de 98 s qui avait tue la
  tache 453. Compromis accepte, et documente pour le rapport.
- Les deux echecs **ne sont plus les memes 429** : `run3` recevait des rafales
  *"temporarily rate-limited upstream"* (limite du fournisseur du modele),
  `run4` a bute sur le **quota journalier OpenRouter** — `limit_source:
  openrouter_free_tier_daily`, `X-RateLimit-Limit: 50`, `Remaining: 0`, les
  4 clefs epuisees. Ce n'est pas un echec de l'agent : **8/8 hors quota.**

**Defaut mis au jour, non corrige : aucun recul entre deux tentatives.**
La 413 a emis **2069 requetes en 115 s** (18/s), la 59 en a emis 188. Cause :
OpenRouter renvoie son 429 en 0,07 s et **sans en-tete `Retry-After`** ; la
boucle fait donc `time.sleep(0)` et repart aussitot. Le seul signal utilisable
est ailleurs — `X-RateLimit-Reset` (epoch **en millisecondes**), present a la
fois en en-tete HTTP et dans `error.metadata.headers`. Deux manques distincts :
la reprise n'a pas de recul minimal, et la seule source de delai lue est un
en-tete que ce fournisseur n'envoie pas.

- [x] Rejouer les 10 taches **apres** l'echeance et le message d'observation,
      pour mesurer l'effet des deux correctifs a jeu egal → `cache/run4/`
- [ ] Etendre a plus de taches : 10 ne separent pas deux modeles a 87 %

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

1. [x] **Phase 0 ensemble** — setup, structure, flat layout, models **faits**.
   `.env` charge dans `agent_mbpp/cli.py` (plus dans `loop.py`). Reste le
   chargement de la config JSON des modeles (cf. P2.5 bis).
2. [x] **En parallele** — sandbox qui execute du code + `final_answer`
   (ndi-tull) et boucle agent avec provider injecte (tchemin) : les deux
   moities se parlent, l'interface `execute()` est stabilisee.
3. [x] **Premier jalon : MBPP end-to-end.** Fait, et au-dela — 15 taches
   reelles mesurees avec les limites branchees, pas seulement sans contraintes.
4. [~] Mesurer et optimiser le prompt → 3 correctifs issus des mesures
   (observation, echeance, comptabilite). **Reste : rejouer a jeu egal.**
5. [ ] Durcir le sandbox (P1.7) pendant que P2 attaque SWE-bench.
6. [ ] SWE-bench sur les 3 taches conseillees :
   `sympy__sympy-14711` / `sympy__sympy-13480` / `pydata__xarray-4629`
7. [ ] `BENCHMARK_REPORT.md` une fois les 2 benchmarks fonctionnels
   (la matiere MBPP existe deja, cf. P2.6).
8. [ ] `README.md` + relecture croisee.

### Prochaines actions concretes (cote tchemin)

- [x] Rejouer les 10 taches a jeu egal → `cache/run4/`, 8/10, metriques
      valides sur les 10 (cf. P2.6)
- [ ] **Recul entre deux tentatives** : 2069 requetes en 115 s sur la 413.
      Prevoir un delai minimal quand `Retry-After` est absent, et lire
      `X-RateLimit-Reset` (ms) — en-tete HTTP ou `error.metadata.headers`
- [ ] `configs/models.json` — livrable exige, aujourd'hui vide (P2.5 bis)
- [ ] Dette `ruff` : 9 `B904` (`raise ... from`), 1 `I001`, 1 `SIM102`
- [ ] `agent_mbpp/cli.py:30` passe encore `tools=None` → le prompt affiche
      litteralement "None" au modele (attend le manual MCP de P1)
- [ ] `core/llm/keyring.py` : vide et sans emploi depuis que `APIKey` porte
      l'etat du vivier → a supprimer ou a justifier
- [ ] `.gitignore` : ajouter `evaluations/`
- [ ] `README.md` (usage reel de l'IA sur le projet, exige par le sujet)

---

## Points de synchro

- Format `sandbox_input` / `sandbox_output` : a caler tot, c'est l'interface entre
  les deux moities du projet.
- Le **sandbox manual** est produit par P1 et consomme par P2 : definir sa forme
  des que la decouverte MCP marche.
- MBPP end-to-end **avant** de toucher a Docker.
- Ne pas optimiser (tokens, choix de modele) avant que l'approche soit prouvee sur
  une tache.
