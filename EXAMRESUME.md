# Agent Smith — Résumé de l'examen blanc

*Les quatre scripts de `exams/` lancés comme le ferait un correcteur, le 2026-10-04 à 22 h 10,
sur le commit `4d0a580` (arbre propre). Résultats bruts dans `evaluations/` (non versionné).*

## Verdict

| Examen | Résultat | Seuil | Statut |
|---|---|---|---|
| Sandbox (`exam_sandbox.sh`) | **8/14** + bonus layer 1 réussi | tous les tests | ❌ **FAIL** |
| MBPP (`exam_mbpp.sh`) | **4/5** | 4/5 | ✅ PASS |
| SWE-bench (`exam_swebench.sh`) | **1/3**, nettoyage des conteneurs OK | 2/3 | ❌ **FAIL** |
| Anti-triche (`exam_anticheat.sh`) | 4 avertissements sur 6 | aucun | ⚠️ REVIEW |

**En l'état, le projet ne passe pas.** Le sandbox est un critère éliminatoire, et ses 6 échecs
viennent de 5 causes, toutes corrigeables (voir plus bas). SWE-bench rate le seuil d'une tâche,
dont l'une est un faux succès provoqué par notre outil `run_tests`.

## Conditions

- **Commande** : `./exams/exam_<type>.sh --student-path . --moulinette-path ./moulinette
  --env-file .env`, avec `--model-name codestral-2508 --provider-url https://api.mistral.ai/v1`
  pour MBPP et SWE-bench (le défaut du `Makefile`). MBPP et SWE-bench ont tourné en parallèle,
  comme le prévoit le guide du correcteur.
- **Docker classique** (utilisateur dans le groupe `docker`), donc pas le problème `lchown` du
  Docker rootless.
- **Deux réglages du poste** : image `python:3.11-slim` tirée (sans elle, toute validation MBPP
  sort FAILED sans message), et un fichier `.pth` ajouté dans `moulinette/.venv`. Notre
  `.gitignore` (`moulinette/`) fait exclure tous les fichiers du paquet `moulinette` à son
  installation : `uv run moulinette_eval` échouait sur `No module named 'moulinette'`. Le
  correcteur, dont la moulinette n'est pas dans notre dépôt, n'aura pas ce problème.
- **Images SWE** : celles de `sympy-13480` et `sympy-14711` étaient déjà là ; celle de
  `scikit-learn-13439` a été tirée pendant l'examen, et sa durée compte dans le temps mesuré par
  le script.

## Sandbox — 8/14

| # | Test | Résultat | Cause |
|---|---|---|---|
| 1 | Imports autorisés | ✅ | |
| 2 | Imports bloqués | ✅ | |
| 3 | Accès fichiers | ✅ | |
| 4 | Builtins bloqués | ✅ | |
| 5 | Réseau bloqué | ✅ | |
| 6 | Outils MBPP (MCP) | ❌ | causes 1 et 3 |
| 7 | Outils SWE-bench (MCP) | ❌ | causes 1, 4 et 5 |
| 8 | MCP HTTP | ❌ | cause 1 (la connexion, elle, fonctionne) |
| 9 | MCP stdio | ❌ | cause 2 |
| 10 | Timeout | ✅ | |
| 11 | Mémoire | ✅ | |
| 12 | Découverte dynamique | ❌ | cause 2 |
| 13 | Manuel du sandbox | ❌ | cause 2 |
| 14 | Retours explicites | ✅ | |
| bonus | Isolation layer 1 | ✅ | |

**Les 5 causes**, toutes de notre côté :

1. **`dir()` n'existe pas dans le sandbox** (`NameError: name 'dir' is not defined`). Les tests
   vérifient la présence des outils par `'add' in dir()`. *Correctif* : ajouter `dir` aux builtins
   autorisés ; sans argument, il doit lister le namespace.
2. **`mcp` 2.0.0 dans notre `uv.lock`.** Le serveur de test du correcteur
   (`simple_mcp_server.py`) importe `mcp.server.fastmcp.FastMCP`, qui n'existe plus en 2.0
   (renommé `MCPServer`). Notre sandbox le lance avec notre Python : il meurt au démarrage
   (`ModuleNotFoundError`). *Correctif* : figer `mcp>=1.22,<2` (la moulinette a 1.26) et remettre
   `mcp_tools_mbpp.py` et `mcp_tools_swebench.py` sur `FastMCP`.
3. **`run_tests` MBPP** est appelé en `run_tests(code=..., test_list=[...])` ; le nôtre ne prend
   que `code` (`TypeError: unexpected keyword argument 'test_list'`). *Correctif* : accepter un
   `test_list` optionnel, prioritaire sur celui de la tâche.
4. **Le serveur SWE ignore `TESTBED_PATH`.** Le script désigne le dépôt par cette variable
   d'environnement ; notre serveur ne lit que `--repo-root`, et `list_files("/testbed")` ne
   trouve rien. *Correctif* : prendre `TESTBED_PATH` comme racine quand `--repo-root` est absent.
5. **`cat test.py | uv run sandbox` coupe les blocs aux lignes vides.** Notre REPL se comporte
   comme le REPL Python interactif : une ligne vide ferme le bloc, et la suite d'un `else:` qui en
   contient part en dizaines d'`unexpected indent`. *Correctif* : quand l'entrée n'est pas un
   terminal, exécuter le fichier d'un seul tenant.

Le test 13 cherche aussi un manuel dans le namespace (`sandbox_manual`, `tool_manual` ou
`get_manual()`). Sans lui, il se contente de vérifier les outils via `dir()` ; en exposer un
reste plus sûr.

## MBPP — 4/5

| Tâche | Résultat | Itérations | Tokens entrée / sortie | Temps agent |
|---|---|---|---|---|
| 92 | ✅ | 1 | 935 / 253 | 2,7 s |
| 290 | ✅ | 1 | 984 / 241 | 2,4 s |
| 116 | ✅ | 1 | 939 / 147 | 2,1 s |
| 235 | ❌ | 4 | 5 242 / 746 | 9,4 s |
| 441 | ✅ | 1 | 929 / 131 | 1,9 s |

MBPP 235 (`even_bit_set_number`) : pas de solution en 4 itérations, et l'agent s'arrête avant
une requête qui dépasserait le plafond d'entrée, sans rien soumettre. Échec du modèle, pas de
l'agent ; métriques valides.

## SWE-bench — 1/3

Tirage au hasard par la moulinette parmi les 6 tâches du pool.

| Tâche | Résultat | Itérations | Tokens entrée / sortie | Temps agent | Durée totale |
|---|---|---|---|---|---|
| `sympy__sympy-13480` | ✅ `RESOLVED_FULL` | 3 | 13 271 / 358 | 13,5 s | 16 s |
| `sympy__sympy-14711` | ❌ `RESOLVED_NO` | 11 | 55 869 / 1 333 | 23,7 s | 26 s |
| `scikit-learn__scikit-learn-13439` | ❌ pas de patch | 30 | 172 882 / 4 733 | 48,3 s | 135 s (pull compris) |

Les conteneurs ont été supprimés après chaque tâche (`CLEANUP: OK` trois fois).

- **`sympy-14711` est un faux succès**, le premier depuis le début des campagnes SWE.
  L'agent annonce `success: true` et soumet un patch de `_check_vector` qui renvoie
  `Vector([(other, None)])` pour un scalaire, faux. Juste avant, `run_tests()` affichait
  `exit code: 0` en tête, et « 3 passed, 1 exceptions » plus bas, bien visible. Le modèle a écrit
  « The fix now works correctly ». Ce `exit code: 0` est celui du dernier `git checkout` de
  l'`eval_script`, pas celui des tests : le défaut est noté dans le TODO, et il coûte ici une
  tâche.
- **`scikit-learn-13439` va au plafond de 30 itérations** : deux `edit_file` avec un `old_str`
  inventé, jamais lu (tours 5 et 11), puis 19 tours de `read_file` (12 à 30) qui parcourent
  `pipeline.py` par fenêtres de 20 lignes, sans nouvelle tentative d'édition.

## Anti-triche — 4 avertissements

Le script cherche des motifs dans tous les `.py` du dépôt. Rien de suspect, mais il faudra
l'expliquer au correcteur, et une partie du bruit s'évite.

| Vérification | Ce qui sort | Lecture |
|---|---|---|
| GitHub URLs | `exams/sandbox_tests/test_network_blocked.py` | **`exams/` est versionné** (commit `4d0a580`) : ce sont les tests du correcteur. À retirer du dépôt |
| PR/issue/commit dans les prompts | « Fix the issue described… » (`core/constants.py`), « FORBIDDEN to git commit » (`core/agent/prompt.py`), `PROMPT = ">>> "` (`sandbox/cli.py`, motif « PR ») | Faux positifs ; renommer `PROMPT` en enlève un |
| Requêtes HTTP externes | `httpx` dans `core/llm/client.py` ; `requests.get(` dans `sandbox/executor.py` | Le client LLM, légitime ; `requests` est une file d'attente, pas la bibliothèque : la renommer supprime l'alerte |
| Accès au dataset SWE-bench | noms `agent_swebench`, `SWE = "swebench"` | Imposés par le sujet ; inévitable |
| Historique git dans les prompts | — | ✅ |
| Bibliothèques interdites | — | ✅ |

Les correspondances dans `moulinette/` ne comptent pas : chez le correcteur, la moulinette n'est
pas dans le dépôt de l'étudiant.

## Risque hors scripts : les arguments du CLI

Les scripts MBPP et SWE-bench ne passent `--model-name` et `--provider-url` que si le
correcteur les donne (`[--model-name MODEL] [--provider-url URL]`, optionnels). Nos deux CLI les
déclarent `required=True` : sans eux, chaque tâche meurt sur l'erreur d'argparse, avant tout
appel au LLM. Le sujet les passe dans ses exemples, mais rien n'empêche un correcteur de les
oublier. *Correctif* : des valeurs par défaut, celles du `Makefile` (`codestral-2508` sur
Mistral).

## À faire, par ordre d'impact

1. **Sandbox (éliminatoire)** : `dir()`, `mcp<2` avec retour à `FastMCP`, `run_tests(code,
   test_list)`, `TESTBED_PATH`, entrée redirigée exécutée d'un bloc. Puis relancer
   `exam_sandbox.sh` (≈ 2 min).
2. **`run_tests` SWE** : rendre le résultat réel des tests (la section entre les marqueurs
   `>>>>> Start Test Output` et `>>>>> End Test Output`, avec la ligne de résumé), plus le code de
   sortie du `git checkout`. Il a coûté `sympy-14711` ici, et rendait 15 appels sur 24 aveugles
   dans la campagne du rapport.
3. **Valeurs par défaut** pour `--model-name` et `--provider-url`.
4. **Retirer `exams/` du dépôt**, renommer la file `requests` d'`executor.py` et la constante
   `PROMPT` de `sandbox/cli.py`.
5. Relancer `exam_swebench.sh` après le point 2 : le tirage change à chaque fois, et 3 des 6
   tâches du pool (`django-11066`, `scikit-learn-13439`, `sympy-18189`) ne figurent dans aucune
   campagne du rapport (`scikit-learn-13439` n'a été tentée qu'ici, une fois).

## Relancer

```bash
./exams/exam_sandbox.sh   --student-path . --moulinette-path ./moulinette --env-file .env
./exams/exam_mbpp.sh      --student-path . --moulinette-path ./moulinette --env-file .env \
    --model-name codestral-2508 --provider-url https://api.mistral.ai/v1
./exams/exam_swebench.sh  --student-path . --moulinette-path ./moulinette --env-file .env \
    --model-name codestral-2508 --provider-url https://api.mistral.ai/v1
./exams/exam_anticheat.sh --student-path .
```
