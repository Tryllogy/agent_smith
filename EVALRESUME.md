# Agent Smith — Où on en est face au barème de correction

*Le barème de correction d'Agent Smith (17 questions, page intra enregistrée le 2026-10-04),
croisé avec l'examen blanc du même soir ([EXAMRESUME.md](EXAMRESUME.md)) et des vérifications
faites à la main sur le commit `4d0a580`. Le barème est celui que suivra le correcteur ; les
scripts de `exams/` n'en couvrent qu'une partie.*

## En une phrase

**En l'état, la correction échouerait sur 5 questions (Q2, Q6, Q15, Q16 et Q17 par voie de
conséquence) et 3 sont à risque (Q3, Q5, Q13)** ; presque tout se corrige sans toucher à
l'intelligence de l'agent, et le premier correctif (valeurs par défaut du modèle) en débloque
trois à lui seul.

## Les consignes générales qui pèsent

Le barème pose, avant les questions :

- **« If a crash occurs during execution, the final grade is 0. »**
- **« No modification of student code is allowed. »** Le correcteur lance les scripts tels
  quels : il ne pourra pas ajouter ce qui manque.
- **« Docker containers must be cleaned even after forced termination. »** Non tenu (Q15).
- « The student solution must NEVER import moulinette packages » : tenu, `core/models.py` est
  une copie, pas un import.
- Clés lues depuis l'environnement ou le `.env`, aucune bibliothèque d'orchestration interdite,
  aucune solution récupérée à l'extérieur : tenus.

## Question par question

| # | Question | Aujourd'hui | Pourquoi |
|---|---|---|---|
| Q1 | Clés API, offre gratuite | ✅ | Clés lues depuis `.env`, aucune en dur. Les deux `grep` du barème ne remontent que des faux positifs (`--task-file` contient « sk- », `index_api_key`). Mistral (crédits offerts, validés par l'équipe péda), NVIDIA, OpenRouter et Groq sont gratuits |
| Q2 | Lancement MBPP + SWE en arrière-plan | ❌ | Les commandes du barème ne passent **ni `--model-name` ni `--provider-url`**. Nos deux CLI les déclarent obligatoires : chaque tâche s'arrête sur l'erreur d'`argparse` (code 2), sans `solution.json`, et SWE ne tire jamais d'image (vérifié) |
| Q3 | Interface CLI | ⚠️ | `agent_mbpp --help`, `agent_swebench --help`, `sandbox`, `sandbox config.json`, `--mcp-stdio` avec nos serveurs et `--mcp-server URL` fonctionnent. Mais la référence citée (tests MCP stdio et HTTP de `exam_sandbox.sh`) échoue, à cause de `dir()` et de `mcp` 2.0 |
| Q4 | Modèles Pydantic | ✅ | Tous les champs demandés présents ; totaux égaux à la somme des étapes, `iterations` égal au nombre d'étapes, timestamps ISO (vérifié sur les 8 `solution.json` de l'examen) |
| Q5 | Sécurité du sandbox | ✅ ⚠️ | Tests 1 à 5 réussis. En direct : `print`, `final_answer("test")`, refus de `os`, `shutil`, `pickle`, `marshal`, `importlib`, `__import__("os")`, `os.path`, `from os import path` et `/etc/passwd`. **Mais `import random; random._os.getcwd()` passe** : le module `os` complet reste joignable (évasion notée dans le TODO). Un correcteur qui la cherche fait tomber la question |
| Q6 | MCP et découverte des outils | ❌ | Les 6 tests MCP de `exam_sandbox.sh` en échec (outils MBPP, outils SWE, HTTP, stdio, découverte dynamique, manuel) : 5 causes, détaillées plus bas |
| Q7 | Limites et retours du sandbox | ✅ | Timeout, mémoire et retours explicites réussis ; bonus « layer 1 » (isolation par sous-processus) réussi |
| Q8 | Résultats MBPP | ✅ | 4/5 à l'examen blanc, **avec** les arguments de modèle (0/5 sans, voir Q2). Limites du barème (6 000 / 1 500 / 120 s) identiques aux nôtres. Nos campagnes donnent environ 85 à 90 % de chances d'avoir 4/5 ou plus |
| Q9 | Excellence MBPP | 2★ | 4/5 plafonne à 2★. Un 5/5 donnerait 4 à 5★ : les tâches réussies le sont en 1 itération et ~950 tokens d'entrée |
| Q10 | Suivi des métriques | ✅ | `StepMetrics` complet à chaque étape, `api_url` et `model_name` par étape, totaux cohérents |
| Q11 | 4 modifications en direct | ⚠️ à préparer | Faisable, mais chacune doit tenir en 2 à 5 min (sinon « they don't understand their own codebase — fail ») : voir « Q11 : où intervenir » |
| Q12 | Anti-triche | ✅ ⚠️ | 4 avertissements de `exam_anticheat.sh`, tous explicables (voir EXAMRESUME.md). L'exemple du prompt SWE porte sur un dépôt fictif (`acme/shopcart`) ; aucun appel externe dans les `sandbox_input` ; démarche lire → reproduire → éditer → tester |
| Q13 | Rapport de benchmark | ⚠️ | Structure complète (setup, tableau, fiabilité, 3 métriques intermédiaires, ablations, conclusions, données). Mais la règle est « 5 modèles sur les **mêmes** 3 tâches » et Qwen n'a pas encore `sympy-14711`. Les 7 ablations portent sur MBPP, aucune sur SWE : un correcteur strict peut le reprocher |
| Q14 | Profondeur du rapport | 2★ | 5 modèles et 3 tâches SWE, plus de 2 métriques interprétées, ablations sur MBPP seulement. Le 3★ demande 7+ modèles **ou** 5+ tâches, 3+ métriques et 2+ ablations |
| Q15 | Cycle de vie Docker | ❌ | Testé sur `sympy-13480` : voir « Q15 : le test d'interruption » |
| Q16 | Résultats SWE-bench | ❌ | 1/3 à l'examen blanc : `13480` ✅, `14711` faux succès (le `exit code: 0` de `run_tests`), `scikit-learn-13439` au plafond de 30 itérations |
| Q17 | Excellence SWE | 1★ | Automatique quand Q16 échoue. Un 2/3 avec moins de 20 itérations en moyenne donnerait 2★ |

## Q6 : les 5 causes

1. **`dir()` absent du sandbox** : les tests vérifient les outils par `'add' in dir()`
   (`NameError`). Seule cause de l'échec du test HTTP, dont la connexion fonctionne.
2. **`mcp` 2.0.0 dans `uv.lock`** : le serveur de test du correcteur importe
   `mcp.server.fastmcp`, qui n'existe plus en 2.0. Notre sandbox le lance avec notre Python et il
   meurt au démarrage. Correctif : `mcp>=1.22,<2` (la moulinette a 1.26), nos deux serveurs
   repassés de `MCPServer` à `FastMCP`.
3. **`run_tests` MBPP** appelé en `run_tests(code=..., test_list=[...])`, le nôtre ne prend que
   `code`.
4. **`TESTBED_PATH` ignoré** par `mcp_tools_swebench.py`, qui ne lit que `--repo-root`.
5. **`cat test.py | uv run sandbox`** : une ligne vide ferme le bloc en cours, comme dans le REPL
   interactif. Correctif : quand l'entrée n'est pas un terminal, exécuter le fichier d'un bloc.

Le test du manuel cherche aussi `sandbox_manual`, `tool_manual` ou `get_manual()` dans le
namespace ; à défaut il se rabat sur `dir()`. En exposer un reste plus sûr.

## Q15 : le test d'interruption

Le barème : démarrer une tâche SWE, attendre le conteneur, tuer l'agent (« kill -9 or Ctrl+C »),
vérifier qu'aucun conteneur ne reste. Fait sur `sympy-13480`, état relevé après l'envoi :

| Interruption | Agent | Conteneur | Remarque |
|---|---|---|---|
| Fin normale | — | ✅ supprimé | `CLEANUP: OK` sur les 3 tâches de l'examen |
| Ctrl+C (SIGINT au groupe) | arrêté | ✅ supprimé | `uv` relaie un second SIGINT qui interrompt la suppression de la copie `/tmp` : trace `KeyboardInterrupt`, copie laissée, pas de `solution.json` |
| SIGTERM | arrêté | ❌ **orphelin** | aucun gestionnaire de SIGTERM |
| `kill -9` | arrêté | ❌ **orphelin** | aucun code ne peut s'exécuter : il faut que le conteneur meure de lui-même |

Correctif possible : lancer le conteneur avec `docker run --rm -i` sur un processus qui lit une
entrée standard tenue ouverte par l'agent ; à la mort de l'agent, même par `kill -9`, l'entrée se
ferme, le conteneur s'arrête et `--rm` le supprime. Plus un gestionnaire de SIGTERM qui passe par
le nettoyage normal.

**Fuite côté hôte** : 23 dossiers `/tmp/agent_smith_*` (~450 Mo) restaient le 2026-10-04 au
soir, laissés par la plupart des runs SWE de la journée, y compris en sortie normale (dont 5 par
les tests d'interruption). Certains fichiers, écrits par le conteneur, appartiennent peut-être à
root. Hors barème, mais à corriger et à nettoyer.

## Q11 : où intervenir

| Modification demandée | Où |
|---|---|
| 1. `[CORRECTION MARKER 42]` en tête du prompt système | `core/agent/prompt.py`, message `"role": "system"` (ligne 163 pour MBPP, 88 pour SWE) |
| 2. `print('SANDBOX_MARKER_42')` avant le code utilisateur | `sandbox/executor.py`, `execute()` (ligne 356) |
| 3. `# CORRECTOR_CHECK` en tête du code envoyé au sandbox | `core/agent/loop.py:156` (`self.sandbox_input = self.code["code"]`) |
| 4. `model_name` journalisé à `correction-model-42` | `core/llm/client.py:228` (`model_name=` du `LLMResponse`) |

À répéter avant la soutenance, sur une tâche MBPP, puis `git checkout`.

## Ce qu'il faut faire, par ordre d'impact

| # | Correctif | Questions débloquées |
|---|---|---|
| 1 | Valeurs par défaut pour `--model-name` et `--provider-url` (celles du `Makefile`, `codestral-2508` sur Mistral) | Q2, Q8, Q16 ; évite qu'un arrêt d'`argparse` passe pour un crash |
| 2 | Les 5 causes de Q6 | Q6, Q3 |
| 3 | Conteneur lié à la vie de l'agent + gestionnaire de SIGTERM + suppression fiable de la copie `/tmp` | Q15 et la consigne générale |
| 4 | `run_tests` SWE qui rend le vrai résultat des tests (section entre `>>>>> Start Test Output` et `>>>>> End Test Output`, avec le résumé) | Q16, Q17 |
| 5 | `sympy-14711` pour Qwen (quota OpenRouter remis à zéro à minuit UTC), puis une ablation SWE (avant/après le n° 4) et 2 tâches SWE de plus | Q13, Q14 (3★) |
| 6 | Fermer l'évasion `random._os` (et `typing.sys`, signalée dans le TODO, pas revérifiée ici) | Q5 |
| 7 | Retirer `exams/` du dépôt ; renommer la file `requests` d'`executor.py` et la constante `PROMPT` de `sandbox/cli.py` | Q12 (moins d'avertissements) |
| 8 | Répéter les 4 modifications de Q11 | Q11 |

Après les n° 1 à 4, il reste un aléa sur Q16 : le tirage se fait parmi 6 tâches, et
`django__django-11066` et `sympy__sympy-18189` n'ont encore jamais été tentées.

## Pour vérifier après correction

```bash
./exams/exam_sandbox.sh   --student-path . --moulinette-path ./moulinette --env-file .env
./exams/exam_mbpp.sh      --student-path . --moulinette-path ./moulinette --env-file .env
./exams/exam_swebench.sh  --student-path . --moulinette-path ./moulinette --env-file .env
./exams/exam_anticheat.sh --student-path .
```

Sans `--model-name` ni `--provider-url`, comme dans le barème : c'est ce qui vérifie le n° 1.
Pour Q15, lancer une tâche SWE, attendre `docker ps | grep sweb`, puis `kill -9` le processus
Python de l'agent : `docker ps -a | grep sweb` doit rester vide.
