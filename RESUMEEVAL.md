# Agent Smith — Où on en est face à la grille de correction (2026-10-07)

*La grille de correction d'Agent Smith (page intra enregistrée dans `test.html`, tronquée après
Q13 ; Q14 à Q17 d'après [EVALRESUME.md](EVALRESUME.md)), déroulée deux fois le 2026-10-07 sur
une copie propre du dépôt :*

- *la batterie 1 à 14 h 12 ;*
- *la batterie 2 à 14 h 34, sur l'état actuel : commit `858daff` plus les modifications non
  commitées du jour.*

*Les résultats détaillés des scripts d'examen sont dans [RESUMEEXAM.md](RESUMEEXAM.md). Ce
fichier remplace EVALRESUME.md (2026-10-04), dont les constats et les numéros de ligne sont
périmés.*

## En une phrase

**Toutes les questions vérifiables passent, deux fois de suite.** Sandbox 14/14, MBPP 5/5 à la
dernière batterie (4/5 à la première), anti-triche sans avertissement. **SWE-bench reste au
seuil exact (2/3)** : un échec de plus fait tomber Q16, donc le correctif prioritaire vise
`sklearn-13439`, qui a échoué à ses 5 tirages.

## Les consignes générales de la grille

| Consigne | État |
|---|---|
| « If a crash occurs during execution, the final grade is 0 » | ✅ Aucun crash. Toute erreur, ou une interruption, écrit un `solution.json` avec `success: false` |
| « No modification of student code is allowed » | ✅ Tout tourne sans argument de modèle (défaut `codestral-2508`) |
| « Docker containers must be cleaned even after forced termination » | ✅ Testé deux fois avec `kill -9`, Ctrl+C et SIGTERM |
| « The student solution must NEVER import moulinette packages » | ✅ Aucun import ; `moulinette` n'apparaît que dans des docstrings |
| Clés lues depuis l'environnement ou le `.env` | ✅ |
| Aucune bibliothèque d'orchestration interdite | ✅ |
| Pas de solution récupérée à l'extérieur | ✅ Aucun accès externe dans les traces des 6 tâches SWE |

## Question par question

Verdicts de la batterie 2 (état actuel), avec la batterie 1 quand elle diffère.

| # | Question | Verdict | Détail |
|---|---|---|---|
| Q1 | Clés API, offre gratuite | ✅ | Les deux `grep` de la grille ne trouvent que des faux positifs (`--task-file` contient « sk- », `index_api_key`). **À faire en soutenance** : montrer les dashboards et générer les clés en direct |
| Q2 | Lancement MBPP + SWE en arrière-plan | ✅ | Les deux scripts démarrent sans `--model-name`, le `.env` est chargé, l'image manquante est tirée par l'agent |
| Q3 | Interface CLI | ✅ | Les deux `--help` ; `uv run sandbox` sans argument, avec `sandbox_template.json`, en `--mcp-stdio` MBPP et SWE, et en `--mcp-server` sur un serveur HTTP lancé à la main : tout testé en direct |
| Q4 | Modèles Pydantic | ✅ | Champs, types et caractère obligatoire identiques à `moulinette/models_public.py`. Les défauts de `SandboxConfig` suivent le sujet (la moulinette publique a des listes vides) |
| Q5 | Sécurité du sandbox | ✅ | Tests 1 à 5 de l'examen ; en REPL : `print`, `final_answer("test")`, refus de `import os`, de `/etc/passwd` et de `../../../etc/passwd` |
| Q6 | MCP et découverte des outils | ✅ | Tests 6 à 9, 12 et 13 : stdio, HTTP, outils MBPP et SWE, `simple_mcp_server.py` découvert, manuel généré |
| Q7 | Limites et retours du sandbox | ✅ | Timeout, mémoire et retours explicites (tests 10, 11 et 14), bonus Layer 1 réussi |
| Q8 | Résultats MBPP | ✅ **5/5** | 264, 238, 445, 266 et 296, de 1 à 4 itérations, toutes les métriques dans les limites. Batterie 1 : 4/5 (462 échoue sur la limite d'entrée) |
| Q9 | Excellence MBPP | **3★** (4★ si le correcteur est indulgent) | 5/5 ; 1,8 itération en moyenne ; entrée moyenne 2 119 tokens (35 % de la limite), sortie moyenne 470 (31 %). Le 4★ demande moins de 30 % ; le 3★ demande moins de 5 itérations et 50 % |
| Q10 | Suivi des métriques | ✅ | Totaux égaux à la somme des étapes ; `api_url`, `model_name`, `request_time_ms` par étape. `moulinette_eval display` : « All checks passed » sauf 264 (« identical sandbox_input », voir plus bas) |
| Q11 | 4 modifications en direct | ✅ | Faites et vérifiées dans les deux batteries, une ligne chacune. Avec les 4 appliquées, la tâche passe toujours la moulinette. Emplacements ci-dessous |
| Q12 | Anti-triche | ✅ | `exam_anticheat.sh` : **6/6, aucun avertissement** (3 à la batterie 1, corrigés depuis). Traces propres, prompt générique. Préparer l'indice de `sympy-18189` |
| Q13 | Rapport de benchmark | ✅ | Toutes les sections ; les chiffres de run1, run6 et run7 correspondent exactement à leurs `solution.json`, run12 au tableau de l'ablation H |
| Q14 | Profondeur du rapport | **≥ 3★** (estimation) | 5 modèles, 6 tâches, 4 métriques intermédiaires, 9 ablations dont 2 sur SWE (le 3★ demande 7+ modèles **ou** 5+ tâches, 3+ métriques et 2+ ablations ; le haut de l'échelle manque dans `test.html`) |
| Q15 | Cycle de vie Docker | ✅ | `kill -9`, Ctrl+C et SIGTERM : conteneur supprimé en moins d'1 s, aucun processus orphelin ; `solution.json` écrit pour Ctrl+C et SIGTERM |
| Q16 | Résultats SWE-bench | ✅ **2/3** | `django-11066` (4 itérations) et `xarray-4629` (3 itérations) validés officiellement ; `sklearn-13439` échoue sur les 30 itérations. Batterie 1 : 2/3 aussi (`18189` et `13480`, sklearn au plafond de sortie) |
| Q17 | Excellence SWE | **2★** (estimation) | 2/3, mais le 3/3 n'a jamais été atteint en examen blanc, faute de résoudre `sklearn-13439` |

## Q11 : où intervenir (vérifié deux fois le 2026-10-07)

| Modification demandée | Où | Changement |
|---|---|---|
| 1. `[CORRECTION MARKER 42]` en tête du prompt système | `core/agent/prompt.py:89` (SWE) et `:171` (MBPP) | `"content": "[CORRECTION MARKER 42] You are an expert assistant who can"` |
| 2. `print('SANDBOX_MARKER_42')` avant le code utilisateur | `sandbox/executor.py:132`, dans `run_one`, juste avant le `exec` | `print('SANDBOX_MARKER_42')` |
| 3. `# CORRECTOR_CHECK` en tête du code envoyé au sandbox | `core/agent/loop.py:196` | `self.sandbox_input = "# CORRECTOR_CHECK\n" + self.code["code"]` |
| 4. `model_name` journalisé à `correction-model-42` | `core/agent/loop.py:856`, dans `make_step_metrics` | `"model_name": "correction-model-42",` |

**Attention au n° 4.** `StepMetrics.model_name` vient de `self.client.model_name`, et
`LLMResponse.model_name` (dans `client.py`) n'est jamais lu : modifier `client.py` ne changerait
rien au `solution.json`. EVALRESUME.md indiquait `client.py`, ce qui était faux. Après l'exercice,
`git checkout` des trois fichiers.

## À préparer pour la soutenance

- **Q1** : les dashboards des providers (Mistral, Groq, NVIDIA, OpenRouter) en offre gratuite,
  la génération de clés en direct, et pourquoi `codestral-2508` (rapport, section 6).
- **Q10** : si le correcteur voit « identical sandbox_input (copy-paste?) » sur une tâche MBPP,
  c'est le modèle qui renvoie le même code. La boucle le détecte (`check_stuck`), résume les
  essais ratés (`collapse_attempts`) et relève la température pour la requête suivante :
  sur 264, le modèle a changé d'approche et réussi.
- **Q11** : refaire les 4 modifications une fois, chrono en main (2 à 5 minutes chacune).
- **Q12, partie A** : `exam_anticheat.sh` passe sans avertissement. Si la question vient, le
  client LLM appelle l'API avec `requests.post` (`core/llm/client.py`), et c'est le seul code
  qui fait du HTTP.
- **Q12, partie D** : le `hints_text` de `sympy-18189` contient le correctif sous forme de diff.
  L'agent a lu les lignes avant d'éditer, puis lancé les tests avant de soumettre. L'indice fait
  partie de l'entrée officielle (`SWEBenchTaskInput.hints_text`). Savoir aussi expliquer la
  structure du prompt et la règle « pas d'édition sans lecture » (`check_unread_edits`).
- **Q13, partie C** : une métrique intermédiaire (l'exploration n'est pas le goulot), une
  ablation (G : `run_tests(code)`, de 75/100 à 81/100) et le choix des modèles.
- **Patchs** : si un correcteur voit un fichier de test dans un patch, il s'agit d'un changement
  de mode seul (voir le n° 3 ci-dessous).

## Ce qu'il faut corriger, par ordre d'impact

| # | Correctif | Où | Gain |
|---|---|---|---|
| 1 | **Lire par grandes fenêtres.** `sklearn-13439` (0/5 en examen blanc) échoue parce que le modèle lit `pipeline.py` 5 ou 10 lignes à la fois, pendant 13 à 25 étapes, sans éditer. Pistes : élargir la fenêtre de l'exemple SWE, qui lit les lignes 1 à 6 ; dire dans le prompt de lire 100 lignes ou plus ; signaler dans l'observation les lectures successives de fenêtres contiguës | `core/constants.py:94`, `core/agent/prompt.py`, `core/agent/loop.py` | Q16, Q17 : sort SWE du seuil exact |
| 2 | **Plafonner `max_tokens` par requête** (par exemple 1 500 pour SWE) au lieu de tout le budget de sortie restant. Le modèle écrit `` ```Step N `` sans retour à la ligne, aucune stop sequence ne se déclenche, et une seule réponse enchaîne jusqu'à 47 étapes (batterie 1 : 10 000 tokens de sortie à l'itération 15) | `core/agent/loop.py:681` | Q16, Q17 |
| 3 | **`git reset -q` avant `git add -A`** dans `get_patch`, pour que les changements de mode écrits dans l'index par le script d'évaluation (21 hunks `100755 → 100644` sur des fichiers de test) ne sortent plus dans les patchs | `mcp_tools/tools_exec.py:232` | Q12 : plus de fichiers de test suspects dans les patchs |
| 4 | **MBPP 462** échoue à chaque tirage (limite d'entrée dès la 2e itération, `test_list` d'environ 1 000 tokens) : alléger le prompt système ou les observations MBPP | `core/agent/prompt.py`, `core/constants.py` | Q8, Q9 : marge sur MBPP |
| 5 | **Retirer du dépôt** `test.html` (page intra du barème, avec un login), `moulinette.zip` et `en.subject.pdf` (`exams/` est déjà retiré) | racine | Hygiène du rendu |
| 6 | **Fichiers appartenant à root dans `/tmp/agent_smith_*`** : `docker exec <conteneur> chown -R <uid>:<gid> /testbed` dans `TaskContainer.stop()` avant la fermeture du conteneur | `agent_swebench/docker.py:256` | Hors grille : 9 copies (131 Mo) laissées dans la journée |

## Hors grille, mais demandé par le sujet

La grille demande de « vérifier la conformité à toute la spécification technique ». Ces points,
relevés lors de la relecture du 2026-10-07, ne sont testés par aucun script :

| Point | État | Où |
|---|---|---|
| Extraction des formats XML `<invoke>`, Hermes `<tool_call>` et ReAct `Action:` (§V.1.2) | ❌ seuls les blocs ```` ``` ```` sont gérés | `core/agent/extraction.py` |
| Retour « lint violation » après une édition | ⚠️ syntaxe seulement | `mcp_tools/tools_fs.py:91` |
| Configuration JSON du sandbox utilisée par les agents | ❌ `SandboxConfig()` est codé en dur | `agent_mbpp/cli.py:47`, `agent_swebench/cli.py:52` |
| `get_patch` avec la commande du sujet (`git -c core.fileMode=false diff`) | ⚠️ fait `add -A` + `diff --cached` (fichiers de reproduction dans certains patchs) | `mcp_tools/tools_exec.py:217` |
| Resources et prompts MCP « exposés » | ⚠️ listés par le client et la bannière, absents du manuel | `sandbox/manual.py` |
| `api_url` = URL de base | ⚠️ inclut `/chat/completions` | `core/llm/client.py:49` |
| Appels d'outils bornés par le temps restant de la tâche | ❌ un `run_tests` tardif peut dépasser 900 s | `sandbox/executor.py:240`, `agent_swebench/cli.py:87` |
| Fallback si la clé du provider principal manque | ❌ la tâche échoue | `agent_mbpp/cli.py:57`, `agent_swebench/cli.py:62` |
| `--provider-url` avec un `/` final | ❌ refusé | `core/agent_cli_helper.py:128` |
| `qwen/qwen3.8-27b:free`, devenu payant | ❌ encore déclaré | `configs/models.json` |
| Définition de classes dans le sandbox | ❌ `__build_class__` absent (aucune tâche MBPP n'en a besoin) | `sandbox/security/builtins.py` |
| `make test` | ❌ pointe vers un dossier `tests/` inexistant | `Makefile` |

## Fait le 2026-10-07 (non commité)

- `README.md` écrit en anglais, aux normes du sujet (première ligne, Description, Instructions,
  Resources avec l'usage de l'IA, architecture, boucle, sandbox, outils, résultats). La section
  sur l'usage de l'IA reste à valider par l'équipe.
- Commentaires en français supprimés et messages traduits en anglais (`builtins.py`,
  `network.py`, aide du `Makefile`).
- `get_llm_reponse` renommé en `get_llm_response`, `get_reponses` en `get_responses`.
- **Avertissements anti-triche corrigés, 6/6** :
  - `exams/` n'est plus suivi par git (gardé en local, ajouté au `.gitignore`) ;
  - imports relatifs dans `agent_swebench` et `agent_mbpp` ;
  - `BenchName` déplacé dans `core/models.py` ;
  - le client LLM utilise `requests.post` au lieu de `httpx` (dépendance `requests` dans
    `pyproject.toml`).

  Vérifié par les cas d'erreur du client sur un serveur local (429, 401, 500, JSON invalide,
  timeout, connexion refusée), par ruff, puis par la batterie 2 complète.
- **Deux batteries d'examen blanc complètes** (voir [RESUMEEXAM.md](RESUMEEXAM.md)).
