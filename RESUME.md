# Agent Smith — Résumé du sujet

*Autonomous reasoning, code generation, and execution — résumé de `en.subject.pdf`.*

## Objectif

Construire un **framework agentique** qui résout seul des tâches de code : le LLM raisonne,
écrit du Python, l'exécute dans un **sandbox**, observe le résultat et itère.

```
THOUGHT → CODE → OBSERVATION → (répéter) → final_answer()
```

Particularité : **code-based tool calling**. Le LLM génère du Python appelant directement les
outils, au lieu de produire du JSON de tool call. Il gagne des variables persistantes entre
étapes, des conditions et des boucles.

Deux benchmarks à résoudre :
- **MBPP** — petits problèmes Python algorithmiques ;
- **SWE-bench (Verified)** — vrais bugs dans de vrais dépôts, dans des conteneurs Docker.

## Architecture

```
LLM API ⇄ Orchestrator → extraction de code → [ Sandbox : interpréteur Python ⇄ client MCP ]
                                                                ↓ stdio / HTTP
                                                           Serveur(s) MCP
```

| Composant | Rôle |
|---|---|
| Orchestrator | boucle agent : appel LLM → extraction → exécution → observation |
| Extraction | transforme la réponse du LLM en code exécutable |
| Sandbox | frontière d'exécution **et de sécurité** ; héberge le client MCP |
| `final_answer()` | primitive **du sandbox**, pas un outil MCP ; termine la boucle |
| Serveur MCP | processus séparé, fournit les outils (fichiers, recherche, exécution) |

## Contraintes générales

- Python **3.10**, gestionnaire **uv**.
- Toute exécution passe par le sandbox. Toutes les erreurs gérées — un crash pendant
  l'évaluation = échec.
- Support de **plusieurs providers et modèles**, avec suivi d'usage (tokens, retries, latence).
- Les outils doivent fonctionner **indépendamment** de la boucle agent.
- ❌ Interdit : `smolagents`, `langgraph`, `crewai`, `autogen`, `llama-index` — la boucle agent
  doit être notre propre code. Le multi-agent est permis, mais l'orchestration reste maison.

## Boucle agent

À implémenter : la boucle Thought/Code/Observation, l'extraction du code depuis la réponse du
modèle, son exécution en sandbox, le renvoi du résultat au LLM, et le **system prompt**
(doc des outils, slots structurés, exemples de raisonnement).

Formats à savoir convertir en Python (le sandbox reste agnostique) :
blocs ` ```python ` + `<end_code>`, XML tool calls, `<tool_call>{…}</tool_call>` (Hermes/JSON),
et ReAct (`Action:` / `Action Input:`).

**Feedback explicite obligatoire** — le LLM ne doit jamais deviner. Signaler : aucun bloc de code
trouvé, bloc malformé mais interprété (et comment), timeout avec sortie partielle, sortie d'outil
tronquée, édition ayant cassé la syntaxe ou le lint. Les échecs silencieux produisent des
observations hallucinées.

**`stop_sequences`** (`<end_code>`, `</tool_call>`…) sont essentielles : sans elles, le modèle
continue de générer et **invente** les résultats d'exécution.

## Sandbox

### CLI

```bash
uv run sandbox                                                        # REPL interactif
uv run sandbox sandbox_template.json                                  # config custom
uv run sandbox --mcp-stdio "python mcp_tools_mbpp.py" sandbox_template.json
uv run sandbox --mcp-server <URL>                                     # transport HTTP
```

Le mode interactif est un REPL : lecture de code au clavier, exécution dans le namespace du
sandbox avec les mêmes restrictions, wrappers MCP et `final_answer` disponibles, affichage du
résultat ou de l'erreur, sortie propre sur `exit` ou `Ctrl+D`.

### `final_answer`

Fonction injectée par le sandbox dans le namespace. `final_answer(answer)` capture l'argument et
signale la fin de la tâche à la boucle agent, qui produit le `SolutionOutput`.
**Ce n'est pas un outil MCP** : elle reste présente quel que soit le serveur connecté.

- MBPP : `final_answer(your_solution_code)`
- SWE-bench : `final_answer(get_patch())`

Le namespace ne contient donc que deux familles de callables : les **wrappers MCP** (découverts
dynamiquement) et **`final_answer`** (fourni par le sandbox).

**Exceptions** : `KeyboardInterrupt` et `SystemExit` ne doivent pas être capturés silencieusement —
ils doivent remonter à la boucle agent pour un arrêt propre.

### Sécurité

Le sandbox est une **frontière de sécurité** entre un système autonome et le monde réel.

- **Imports** : allowlist stricte.
- **Filesystem** : allowlist de répertoires (`allowed_directories`), évalués *dans* le sandbox.
  Plusieurs entrées pour séparer l'espace de travail (`/testbed`) d'une zone scratch (`/tmp/agent`).
- **Réseau** : aucun accès, entrant ou sortant.
- **Timeout** d'exécution — s'applique **uniquement** au code sandboxé, pas aux actions MCP.
- **Mémoire** : limite RAM.
- **Builtins restreints** : supprimer/surcharger les builtins dangereux.

> ⚠️ Uniquement la **stdlib et les builtins** Python. Pas de `RestrictedPython` ni équivalent.

Question ouverte laissée au design : exécuter le code non fiable dans le processus courant ou dans
un processus séparé ? Impacts sur la frontière de sécurité, la façon de tuer du code emballé, et
la récupération des résultats.

### Configuration (Pydantic + JSON)

```python
class SandboxConfig(BaseModel):
    authorized_imports: List[str] = [...]   # math, collections, itertools, re, json, typing,
                                            # functools, operator, heapq, bisect, copy, string,
                                            # random, datetime, array, cmath (+ .*)
    allowed_directories: List[str] = ["/testbed", "/tmp/agent"]
    max_execution_time_seconds: int = 30
    max_memory_mb: int = 512
```

### MCP

- Exposer **tools, resources et prompts** ; outils appelables comme fonctions Python.
- Transports **stdio et HTTP streamable** tous deux supportés.
- Le système sera testé avec un **serveur MCP inconnu** → découverte dynamique obligatoire.
- `mcp_tools_mbpp.py` et `mcp_tools_swebench.py` **à la racine du dépôt**.
- Le **manuel du sandbox** injecté dans le prompt doit être **généré dynamiquement** depuis les
  schémas d'outils du serveur connecté (noms, descriptions, types) : changer de serveur change
  le manuel.

## Agents

### MBPP

```bash
uv run moulinette_eval dump mbpp --output ../cache/mbpp_task.json
uv run python -m agent_mbpp --task-file ../cache/mbpp_task.json \
  --output ../cache/mbpp_solution.json --model-name "model/name" --provider-url "https://…/v1"
uv run moulinette_eval validate mbpp ../cache/mbpp_task.json ../cache/mbpp_solution.json
```

Outil minimal : `run_tests`. Entrée `MBPPTaskInput` (`task_id`, `task_definition`,
`function_definition`, `test_imports`, `test_list`). `max_iterations` doit être configurable.

### SWE-bench

Même schéma de CLI avec `agent_swebench`, plus le **nettoyage des conteneurs à notre charge**.

Deux approches valides : (a) sandbox **dans** le conteneur, ou (b) sandbox sur l'hôte avec les
outils MCP faisant le pont vers Docker. Dans les deux cas, les contraintes de sécurité tiennent.

Patch produit via `git -c core.fileMode=false diff`. Monter `${TESTBED_PATH}` dans le conteneur
peut être nécessaire. Installation de dépendances supplémentaires autorisée (`ruff`, `jedi`, `tree`).

Entrée `SWEBenchTaskInput` : `instance_id`, `problem_statement`, `docker_image`, `eval_script`,
`hints_text`, `repo`.
Tâches suggérées pour démarrer : `sympy__sympy-14711`, `sympy__sympy-13480`, `pydata__xarray-4629`.

### Sortie commune

`SolutionOutput` → `solution.json` : `task_id`, `benchmark`, `success`, `solution` (code ou patch),
`iterations`, `total_requests`, `total_input_tokens`, `total_output_tokens`, `total_time_seconds`,
`system_prompt`, `error`, `timestamp`, et `steps: List[StepMetrics]`.

`StepMetrics` (un par itération LLM → sandbox) : `step`, `input_tokens`, `output_tokens`,
`request_time_ms`, `timestamp`, `api_url`, `model_name`, `llm_output` (réponse brute avant
extraction), `sandbox_input` (code envoyé), `sandbox_output` (résultat), `retries`.

Ces champs sont **inspectés à l'évaluation** pour vérifier que la tâche a été résolue par
exploration et raisonnement légitimes.

## Outils obligatoires (exposés par MCP, testés indépendamment)

**Fichiers**
- `read_file(filepath, start_line, end_line)` → format `cat -n` : `<line_number>: <line_content>`
- `edit_file(filepath, old_str, new_str)` — remplacement de chaîne exacte
- `list_files(directory, pattern)`

**Recherche** — format commun : `/absolute/path.py:<line_number> <line_content>`
- `search_code(pattern, file_pattern)` — grep-like
- `search_function_or_class_definition_in_code(name)`
- `find_references(name, filepath, line)`

**Exécution**
- `run_tests()` — lance le script d'évaluation
- `get_patch()` — `git diff` unifié des modifications
- `run_command(command, workdir)` — stdout, stderr, code de sortie

## Providers LLM

Exemples cités (liste non contractuelle) : OpenRouter, Together AI, Groq (compatibles OpenAI) ;
Google AI Studio, Mistral, Cohere ; Fireworks, Perplexity, Anyscale.

- ✅ **Offres gratuites exclusivement** — aucun plan payant, crédit acheté ou compte facturé.
  Le projet doit tourner entièrement sur les quotas gratuits au moment de l'évaluation.
- ✅ **Multi-tokens obligatoire** : plusieurs clés par provider + **rotation** pour gérer les
  rate limits et l'épuisement de quota. Fallback entre providers recommandé.
- ✅ Abstraction suffisante pour changer de provider sans refonte.

> Le choix du provider **n'est pas noté** — la qualité de l'abstraction, la gestion d'erreurs et
> l'architecture le sont.

## `BENCHMARK_REPORT.md`

À la racine : **≥ 5 modèles** sur **≥ 3 tâches SWE-bench** communes.

1. **Setup** : modèles/providers, tâches et justification du choix.
2. **Tableau** par modèle × tâche : Pass/Fail, itérations, tokens in/out, temps mur.
3. **Fiabilité provider** : temps de réponse moyen, retries (rate limits, timeouts, erreurs),
   disponibilité.
4. **Métriques intermédiaires** (≥ 2) : étape du premier accès au fichier du patch final
   (efficacité d'exploration) ; étape où les échecs de tests commencent à baisser (progrès
   partiel) ; itérations entre « tests au vert » et `final_answer` (discipline — zéro est l'idéal).
   Mesure manuelle acceptée : c'est l'analyse qui compte, pas l'outillage.
5. **Ablation** : ≥ 1 comparaison avant/après d'un changement (prompt, outils, paramètres) sur les
   mêmes tâches et le même modèle.
6. **Conclusions** : modèles retenus / écartés, justifiés par les données.

Les `solution.json` correspondants doivent être présents dans le dépôt.

## Évaluation

```bash
./exam_TYPE.sh --student-path ./student --moulinette-path ./moulinette --env-file /path/to/.env
```

La CLI charge les clés depuis l'environnement (ex. `OPENROUTER_API_KEY`).

| `exam_mbpp.sh` | `exam_swebench.sh` | `exam_sandbox.sh` |
|---|---|---|
| 5 tâches aléatoires — **4/5** | 3 tâches aléatoires — **2/3** | tests de sécurité — **tous** |
| dump → run → validate | dump → run → validate → cleanup conteneur | import, builtin, réseau, chemin, timeout, mémoire, protocole MCP |

### Limites strictes (dépassement = tâche échouée)

| Métrique | MBPP | SWE-bench |
|---|---|---|
| Itérations | 10 | 30 |
| Tokens d'entrée | 6 000 | 300 000 |
| Tokens de sortie | 1 500 | 10 000 |
| Timeout | 120 s | 900 s |

Les tokens sont **cumulatifs** sur toutes les itérations d'une tâche, **tokens de raisonnement
inclus** — si ça devient trop juste, préférer un modèle non-reasoning.
**Aucun retry autorisé pendant l'examen.**

### Validation

Toutes les conditions doivent être remplies : seuils MBPP **et** SWE-bench atteints, limites
respectées, outils obligatoires validés par leurs tests indépendants, sandbox validé par les tests
d'isolation et de sécurité.

> ⚠️ **Clés API en dur = échec de sécurité.** Variables d'environnement ou `.env` uniquement ;
> toute clé trouvée dans le code source est signalée.

### En soutenance

Correction des outils, boucle de raisonnement, garanties d'isolation, résultats de benchmark et
statistiques de tokens, qualité du code et architecture.

**Modifications à chaud** : de petites modifications de l'agent seront demandées, à relancer sur
une tâche MBPP — **2 à 5 minutes chacune**. Ne pas savoir où intervenir signale une méconnaissance
de son propre code. Tout est ensuite annulé (`git checkout`).

### 🚨 Sécurité IA — violation = note de 0

L'agent ne doit pas : récupérer des solutions depuis des PR/issues/sources externes ; réutiliser
des patches mémorisés sans exploration réelle ; contourner le sandbox ; accéder à des ressources
hors du contexte de la tâche. Les champs `system_prompt`, `llm_output`, `sandbox_input` et
`sandbox_output` existent pour rendre le raisonnement traçable.

Logs d'évaluation :
`./evaluations/EVAL_TYPE/YYYY-MM-DD_HH-MM-SS/task_id/{task.json, solution.json, stdout.log, stderr.log}`

## README (en anglais, à la racine)

- Première ligne en italique : *This project has been created as part of the 42 curriculum by
  \<login1\>[, \<login2\>[, …]].*
- **Description** : objectif et vue d'ensemble.
- **Instructions** : installation, exécution.
- **Resources** : références du domaine **et** description de l'usage de l'IA (quelles tâches,
  quelles parties du projet).
- Sections spécifiques exigées : architecture du système, explication de la boucle agent, design
  du sandbox, détails d'implémentation des outils, résultats de benchmark et analyse.

## Rendu

Dépôt Git avec l'arborescence de notre choix, les fichiers de configuration (sandbox et modèles)
et le `README.md`.
**Ne pas inclure** : images Docker, poids de modèles, sorties générées.

### Checklist

| Livrable | Où |
|---|---|
| `mcp_tools_mbpp.py`, `mcp_tools_swebench.py` | racine |
| `BENCHMARK_REPORT.md` | racine |
| `README.md` (anglais) | racine |
| `solution.json` du benchmark | dépôt |
| Configs sandbox JSON + modèles Pydantic | dépôt |
| CLI `uv run sandbox` + mode REPL | — |
| Modules `agent_mbpp`, `agent_swebench` | — |

## Conseils du sujet

**Démarrage** — attaquer le benchmark le plus simple d'abord ; tester avec le modèle le plus
capable disponible avant de s'imposer des contraintes ; vérifier que le système résout la tâche la
plus facile **sans** limites de tokens/itérations — sinon les contraintes ne feront qu'empirer.

**Débogage** — regarder ce qui se passe dans les 3–5 premières itérations (appels d'outils ratés ?
observations hallucinées ?). Résoudre la tâche **soi-même, à la main**, avec seulement les outils
de l'agent : ce processus de raisonnement **est** la méthodologie que le prompt doit enseigner au
LLM. Chercher les signaux de progrès partiel quand les tests échouent encore.

**Montée en charge** — une tâche résolue ne prouve pas la généralisation ; ne pas optimiser
(tokens, modèle) avant d'avoir prouvé l'approche ; travailler *avec* les préférences de format du
modèle plutôt que contre elles.

**SWE-bench** — découper le script d'éval en objectifs plus petits, suivre les tests individuels
plutôt que le script entier, et se demander quel est l'agent le plus simple qui résout la tâche la
plus facile.
