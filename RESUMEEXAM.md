# Agent Smith — Résumé des examens blancs du 2026-10-07

*Deux batteries complètes des quatre scripts de `exams/`, lancées comme le ferait un correcteur,
le 2026-10-07 :*

- *la **batterie 1** à 14 h 12, sur le commit `858daff` plus le README, la traduction des
  commentaires et le renommage de `get_llm_reponse` ;*
- *la **batterie 2** à 14 h 34, sur le même état plus la correction des avertissements
  anti-triche (`exams/` retiré du suivi git, imports relatifs, `BenchName` dans
  `core/models.py`, client LLM sur `requests`). C'est l'état actuel du dépôt, non commité.*

*Les résultats bruts sont dans `evaluations/` (non versionné). Le déroulé question par question
de la grille est dans [RESUMEEVAL.md](RESUMEEVAL.md).*

## Verdict

| Examen | Batterie 1 (14 h 12) | Batterie 2 (14 h 34, état actuel) | Seuil |
|---|---|---|---|
| Sandbox (`exam_sandbox.sh`) | ✅ **14/14** + bonus | ✅ **14/14** + bonus | tous les tests |
| MBPP (`exam_mbpp.sh`) | ✅ **4/5** | ✅ **5/5** | 4/5 |
| SWE-bench (`exam_swebench.sh`) | ✅ **2/3**, nettoyage OK | ✅ **2/3**, nettoyage OK | 2/3 |
| Anti-triche (`exam_anticheat.sh`) | ⚠️ 3 avertissements | ✅ **6/6**, aucun avertissement | aucun |

**Les deux batteries passent.** SWE-bench reste au seuil exact (2/3), et `sklearn-13439` a
échoué à ses 5 tirages en examen blanc : c'est le risque principal de la correction.

## Conditions

- **Copie propre** : seuls les fichiers suivis par git ont été copiés dans un dossier vide (sans
  `.env`, `moulinette/`, `evaluations/`, `exams/` ni fichiers non suivis), puis `uv sync`, comme
  le demande la grille. Les clés viennent uniquement du `--env-file`.
- **Commandes** : celles de la grille, **sans `--model-name` ni `--provider-url`**, donc le
  modèle par défaut, `codestral-2508` sur Mistral :
  `./exams/exam_<type>.sh --student-path <copie> --moulinette-path ./moulinette --env-file .env`
- MBPP, SWE-bench et sandbox ont tourné en parallèle, comme dans le déroulé du correcteur.
- **Docker classique** (pas rootless) : la validation officielle `validate swebench` fonctionne.
- **Images** : celles de `sympy-18189` (batterie 1) et de `django-11066` (batterie 2) n'étaient
  pas présentes. L'agent les a tirées lui-même, sur son propre temps (64 s au total pour
  `django-11066`).

## Sandbox — 14/14 + bonus (les deux batteries)

Tous les tests passent : imports autorisés et bloqués, accès fichiers, builtins, réseau, outils
MBPP et SWE par MCP, transports HTTP et stdio, timeout, mémoire, découverte dynamique, manuel,
retours explicites. Le bonus Layer 1 (isolation par sous-processus) passe aussi.

Vérifications à la main dans le REPL (`uv run sandbox`, via un pseudo-terminal) :

- `print("hello world")` s'affiche et `final_answer("test")` est appelable ;
- `import os` est refusé (`ImportError`) ;
- `open("/etc/passwd")` et `open("../../../etc/passwd")` sont refusés (`PermissionError`) ;
- les variables persistent d'une entrée à l'autre, et `exit` quitte proprement ;
- `uv run sandbox sandbox_template.json` charge la configuration ;
- `--mcp-stdio "python mcp_tools_mbpp.py"` : `run_tests` renvoie PASS/FAIL avec la valeur
  obtenue ;
- `--mcp-stdio "python mcp_tools_swebench.py"` : `dir()` montre les 9 outils obligatoires,
  plus `final_answer`, `sandbox_manual` et `get_manual` ;
- `--mcp-server http://127.0.0.1:8765/mcp` (batterie 2), avec `mcp_tools_swebench.py` lancé en
  `--transport streamable-http` : `list_files` répond par HTTP.

## MBPP

**Batterie 2 — 5/5**

| Tâche | Résultat | Itérations | Tokens entrée / sortie | Temps agent |
|---|---|---|---|---|
| 264 | ✅ PASS | 4 | 4 876 / 943 | 13,9 s |
| 238 | ✅ PASS | 1 | 996 / 153 | 2,1 s |
| 445 | ✅ PASS | 2 | 2 728 / 336 | 4,9 s |
| 266 | ✅ PASS | 1 | 992 / 139 | 2,2 s |
| 296 | ✅ PASS | 1 | 1 002 / 778 | 6,6 s |

**Batterie 1 — 4/5**

| Tâche | Résultat | Itérations | Tokens entrée / sortie | Temps agent |
|---|---|---|---|---|
| 127 | ✅ PASS | 1 | 989 / 151 | 2,7 s |
| 389 | ✅ PASS | 1 | 988 / 239 | 5,7 s |
| 462 | ❌ FAIL | 2 | 4 261 / 344 | 5,1 s |
| 80 | ✅ PASS | 1 | 986 / 145 | 2,4 s |
| 117 | ✅ PASS | 1 | 1 138 / 144 | 2,1 s |

- Toutes les métriques restent dans les limites, sans retry ni fallback. Sur chaque
  `solution.json`, les totaux sont égaux à la somme des étapes.
- **MBPP 264 : la détection de blocage a fonctionné.** À l'étape 2, le modèle a resoumis
  exactement le code de l'étape 1, qui avait les mêmes échecs (« got 71 », « got 107 »). La
  boucle a résumé les essais ratés (l'entrée redescend de 1 259 à 1 138 tokens à l'étape 3) et
  relevé la température. Le modèle a changé d'approche et réussi à l'étape 4.
  `moulinette_eval display` signale « WARN: Steps 1 and 2: identical sandbox_input
  (copy-paste?) » sur cette tâche : c'est ce renvoi du modèle, et c'est à savoir expliquer. Les
  quatre autres tâches donnent « All checks passed ».
- **MBPP 462 (batterie 1) échoue à chaque tirage** : son `test_list` pèse environ 1 000 tokens.
  Après un premier essai raté, la 2e itération porte le cumul à 4 261 tokens d'entrée, et la
  requête suivante (~3 778) ferait dépasser 6 000. La boucle s'arrête donc proprement avant la
  limite.

## SWE-bench

**Batterie 2 — 2/3**

| Tâche | Résultat | Itérations | Tokens entrée / sortie | Temps agent | Nettoyage |
|---|---|---|---|---|---|
| `django__django-11066` | ✅ PASS | 4 | 15 852 / 412 | 64 s (image tirée comprise) | OK |
| `pydata__xarray-4629` | ✅ PASS | 3 | 12 684 / 505 | 14 s | OK |
| `scikit-learn__scikit-learn-13439` | ❌ FAIL | **30** | 157 373 / 2 991 | 40 s | OK |

**Batterie 1 — 2/3**

| Tâche | Résultat | Itérations | Tokens entrée / sortie | Temps agent | Nettoyage |
|---|---|---|---|---|---|
| `scikit-learn__scikit-learn-13439` | ❌ FAIL | 15 | 72 549 / **10 000** | 124 s | OK |
| `sympy__sympy-18189` | ✅ PASS | 4 | 15 412 / 364 | 39 s (image tirée comprise) | OK |
| `sympy__sympy-13480` | ✅ PASS | 3 | 9 838 / 386 | 13 s | OK |

Les quatre succès sont validés par la moulinette officielle. Les patchs ne touchent que le
fichier corrigé, sauf `18189`, qui contient un changement de mode d'un fichier de test (voir
« Constats secondaires »).

**Pourquoi `sklearn-13439` échoue : l'agent lit le fichier par petites fenêtres et n'édite
jamais.** Il suffit d'ajouter `__len__` à `Pipeline`, à côté de `__getitem__` (ligne 202 de
`sklearn/pipeline.py`).

- **Batterie 2 : plafond des 30 itérations.**
  - Des étapes 6 à 30, le modèle lit `pipeline.py` **10 lignes à la fois**.
  - Il passe sur `__getitem__` à l'étape 23 et continue de défiler.
  - À l'étape 1, il avait aussi essayé `import sklearn` dans le sandbox au lieu de
    `run_command` (refusé, avec un message explicite).
- **Batterie 1 : plafond des 10 000 tokens de sortie.** Après 13 étapes de lecture par
  fenêtres de 5 lignes, les réponses s'emballent : 10, puis 30, puis 47 blocs de code par
  réponse (3 685 tokens pour la dernière).
  - Aucune stop sequence ne se déclenche, car le modèle ferme son bloc par
    `` ```Step 128 ``, sans retour à la ligne après la fence.
  - `max_tokens` vaut tout le budget restant (`core/agent/loop.py:681`).
- Les petites fenêtres imitent sans doute l'exemple du prompt SWE, qui lit les lignes 1 à 6
  (`core/constants.py:94`).

`sklearn-13439` a échoué à ses **5 tirages en examen blanc** (04/10, 05/10 ×2, 07/10 ×2). Avec
`sympy-14711`, c'est la tâche à risque du pool de 6.

## Anti-triche

**Batterie 2 : 6/6, STATUS: PASS.** Les 3 avertissements de la batterie 1 étaient des faux
positifs, corrigés entre les deux batteries :

| Contrôle | Batterie 1 | Cause | Correction |
|---|---|---|---|
| GitHub URLs | ⚠️ | Uniquement les scripts `exams/` copiés dans le dépôt | `exams/` retiré du suivi git (gardé en local, dans le `.gitignore`) |
| Requêtes HTTP | ⚠️ | `httpx` dans le client LLM | Client LLM sur `requests.post` |
| Accès au dataset SWE-bench | ⚠️ | Le mot `swebench` dans des imports absolus, une variable, un commentaire et `BenchName` | Imports relatifs, variable renommée, commentaire reformulé, `BenchName` dans `core/models.py` |
| Les 3 autres | ✅ | | |

Dans les `sandbox_input` des 6 tâches SWE : aucun `curl`, `wget`, URL, `git log` ou `git show`.
Le prompt système ne cite aucun dépôt ni aucune tâche.

## Cycle de vie Docker (Q15)

Testé après chaque batterie, sur `sympy-13480` puis sur `xarray-4629`, une fois le conteneur
démarré :

| Interruption | Conteneur | `solution.json` | Processus restants | Copie `/tmp` |
|---|---|---|---|---|
| `kill -9` de l'agent | ✅ supprimé en moins d'1 s | absent (normal) | aucun | laissée (normal) |
| Ctrl+C (SIGINT au groupe) | ✅ supprimé en moins d'1 s | ✅ `success: false`, « Interrupted by SIGINT » | aucun | supprimée |
| SIGTERM à l'agent | ✅ supprimé en moins d'1 s | ✅ `success: false`, « Interrupted by SIGTERM » | aucun | supprimée |
| SIGTERM à l'enfant du sandbox | conteneur gardé, la tâche continue | ✅ `success: true` | aucun | — |

La dernière ligne vient d'une erreur de ciblage dans le premier test SIGTERM de la batterie 2 :
l'enfant du sandbox a la même ligne de commande que l'agent. Reproduit exprès ensuite, le
résultat est bon : l'enfant meurt, le sandbox le relance, et la tâche se termine normalement.

## Constats secondaires

- **Fuite dans `/tmp` en fin normale.** Chaque tâche SWE menée à son terme laisse sa copie
  `/tmp/agent_smith_*`, avec des centaines de fichiers appartenant à root : le conteneur, qui
  tourne en root, écrit dans la copie montée (`pip install -e .` du script d'évaluation, cache
  Python), et `shutil.rmtree(..., ignore_errors=True)` ne peut pas les supprimer. C'est hors
  grille, mais 9 dossiers (131 Mo) se sont accumulés dans la journée.
- **Des fichiers de test dans certains patchs, mais seulement leur mode.** Le patch de `18189`
  contient `sympy/solvers/tests/test_diophantine.py`, que le modèle n'a jamais touché : c'est un
  changement de mode seul (`100755 → 100644`), sans contenu. Les 21 hunks de fichiers de test
  de nos patchs (rapport et examens) sont tous de ce type.
  - Cause : le `git checkout` du script d'évaluation, lancé en root dans le conteneur, réécrit
    l'index. `core.fileMode=false` ne s'applique pas à la comparaison index / `HEAD` faite par
    `diff --cached`.
  - Effet : aucun sur la validation, mais un correcteur qui inspecte le patch voit des fichiers
    de test.
- **`hints_text` de `sympy-18189`** : il contient le correctif sous forme de diff. L'agent a lu
  les lignes 182 à 185, fait l'édition `permute=permute`, lancé les tests (43 passés, 2 échecs
  attendus), puis soumis `get_patch()`. C'est légitime, puisque l'indice fait partie de l'entrée
  officielle de la tâche, mais il faut savoir l'expliquer.

## Progression

| | 2026-10-04 ([EXAMRESUME.md](EXAMRESUME.md)) | 2026-10-07, batterie 1 | 2026-10-07, batterie 2 |
|---|---|---|---|
| Sandbox | 8/14 ❌ | 14/14 + bonus ✅ | **14/14** + bonus ✅ |
| MBPP | 4/5 (avec `--model-name`) | 4/5 ✅ | **5/5** ✅ |
| SWE-bench | 1/3, dont un faux succès ❌ | 2/3 ✅ | **2/3** ✅ |
| Anti-triche | 4 avertissements | 3 avertissements | **0** ✅ |
| `kill -9` / SIGTERM | conteneur orphelin ❌ | conteneur supprimé ✅ | conteneur supprimé ✅ |

## Pour reproduire

```bash
./exams/exam_sandbox.sh   --student-path <copie> --moulinette-path ./moulinette --env-file .env
./exams/exam_mbpp.sh      --student-path <copie> --moulinette-path ./moulinette --env-file .env
./exams/exam_swebench.sh  --student-path <copie> --moulinette-path ./moulinette --env-file .env
./exams/exam_anticheat.sh --student-path <copie>
```

| Batterie | Sandbox | MBPP | SWE-bench |
|---|---|---|---|
| 1 | `evaluations/sandbox/2026-10-07_14-12-37/` | `evaluations/mbpp/2026-10-07_14-12-29/` | `evaluations/swebench/2026-10-07_14-12-29/` |
| 2 | `evaluations/sandbox/2026-10-07_14-34-16/` | `evaluations/mbpp/2026-10-07_14-34-16/` | `evaluations/swebench/2026-10-07_14-34-16/` |
