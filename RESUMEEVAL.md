# Agent Smith — Parallèle avec le barème de correction (2026-10-05, `1453d0c`)

*Le barème de l'intra (`test.html`) croisé avec l'examen complet de 16 h 18
([RESUMEEXAM.md](RESUMEEXAM.md)) et des vérifications faites à la main. La page enregistrée est
**tronquée** au milieu de « Benchmark Report Depth » (« 17 Ko restants »). Les trois dernières
questions (cycle de vie Docker, résultats SWE, excellence SWE) sont reprises de
`EVALRESUME.md`, qui avait la page complète. La numérotation suit l'ordre de la page.*

## En une phrase

**Sur cet examen, la correction échouerait sur Q8 (MBPP 3/5), donc Q9, et sur Q16 en officiel
(la moulinette ne valide pas SWE en Docker rootless).** Sur un poste à Docker classique, SWE
atteindrait 2/3 et Q16 passerait. Trois questions restent à risque : Q5 (évasion du sandbox
encore possible), Q15 (`kill -9`) et Q11 (à répéter). Le point faible commun à MBPP et SWE est
le même : **le modèle resoumet le même code faux** jusqu'au plafond.

---

## Les consignes générales

| Consigne | État | Preuve |
|---|---|---|
| *« If a crash occurs during execution, the final grade is 0 »* | ✅ | Aucun crash sur les 4 examens, `stderr.log` vides |
| *« No modification of student code is allowed »* | ✅ | Les scripts tournent sans `--model-name` |
| *« Docker containers must be cleaned even after forced termination »* | ⚠️ | SIGTERM et Ctrl+C nettoient ; **`kill -9` laisse le conteneur** (P1). Les `CLEANUP: FAILED` du jour viennent de la moulinette en rootless (voir Q15) |
| *« The student solution must NEVER import moulinette packages »* | ✅ | Aucun import ; le `grep "moulinette"` du guide trouve 4 docstrings, à expliquer |
| Clés depuis l'environnement / `.env` | ✅ | |
| Aucune bibliothèque d'orchestration | ✅ | `exam_anticheat.sh` : PASS sur ce point |
| Résolution par raisonnement, rien d'externe | ✅ | 0 `curl`, `wget`, URL ou `git log`/`git show` dans les `sandbox_input` |

---

## Question par question

| # | Question | Statut | Preuve | Risque / action |
|---|---|---|---|---|
| Q1 | Clés API, offre gratuite | ✅ | Les 2 `grep` du barème : faux positifs seulement (`--task-file`, `index_api_key`) | Tableaux de bord prêts ; générer une clé en direct ; justifier `codestral-2508` |
| Q2 | Lancement MBPP + SWE | ✅ | Les deux scripts démarrent sans argument de modèle ; `.env` chargé ; image `django-11066` tirée pendant l'examen | — |
| Q3 | Interface CLI | ✅ | `--help` des deux agents ; `sandbox`, `sandbox <config>`, `--mcp-stdio` (nos 2 serveurs), `--mcp-server` (test 8) | — |
| Q4 | Modèles Pydantic | ✅ | Champs, types et défauts identiques à `models_public.py` ; JSON ; horodatages ISO ; `iterations` égal au nombre d'étapes depuis `1453d0c` | — |
| Q5 | Sécurité du sandbox | ✅ ⚠️ | Tests 1-5 ✅ ; en direct : `print("hello world")`, `final_answer("test")`, `import os` refusé, `/etc/passwd` refusé | **`operator.attrgetter('_os')(random)` et `string.Formatter().get_field(...)` donnent encore `os`** (P1) |
| Q6 | MCP, découverte | ✅ | Tests 6-10 et 12-13 ✅ ; nos serveurs uniquement ; `final_answer` est une primitive du sandbox ; le manuel suit le serveur connecté | — |
| Q7 | Limites et retours | ✅ | Timeout et mémoire ✅ ; aucun bloc, bloc mal formé, sortie partielle, troncature ✅ (tests 10-11, 14, bonus) | — |
| Q8 | Résultats MBPP | **❌ sur ce tirage** | **3/5** : 245 et 430 échouent, toutes métriques valides, aucun crash | Les 3 examens donnent 4/5, 5/5, 3/5 = 12/15 : pile sur le seuil. **Action P2 n° 1 et 2** |
| Q9 | Excellence MBPP | 1★ ici | « If Q8 did not pass, give 1 star » | Avec 5/5 (examen de 15 h 37 : 1,2 itération, ~21 % de l'entrée) : 4-5★ |
| Q10 | Suivi des métriques | ✅ | 8/8 `solution.json` cohérents : totaux = somme des étapes, `iterations` = étapes, `api_url`, `model_name`, `request_time_ms` à chaque étape | Corrigé par `1453d0c` (avant : 7 itérations pour 8 étapes) |
| Q11 | 4 modifications en direct | ⚠️ à répéter | Emplacements ci-dessous | Le `model_name` journalisé est en `loop.py:596`, **pas** en `client.py:228` |
| Q12 | Anti-triche | ✅ ⚠️ | A : 3 avertissements dans le dépôt rendu, 2 sans `exams/`. B : prompt sans indice propre à une tâche, exemple sur un dépôt fictif. C/D : démarche propre sur les 2 tâches résolues (lecture, édition de la ligne lue, `run_tests()`, patch) | Sur `18189`, le modèle lit directement les lignes 180-190 alors que la recherche ne montrait que la ligne 101 : savoir le défendre. `display` affiche 2 WARN « copy-paste? » sur MBPP 245 |
| Q13 | Rapport de benchmark | ⚠️ | Structure complète : 5 modèles, 3 tâches, tableau, fiabilité, 3 métriques, 7 ablations MBPP, conclusions, données | Case Qwen / `sympy-14711` en attente ; aucune ablation **SWE** |
| Q14 | Profondeur du rapport | 2★ | 5 modèles, 3 tâches, 3 métriques, ablations MBPP | 3★ : 7+ modèles ou 5+ tâches, 3+ métriques, 2+ ablations |
| Q15 | Cycle de vie Docker | ⚠️ | SIGTERM, Ctrl+C : aucun conteneur ni copie restants. `CLEANUP: FAILED` ×2 aujourd'hui **sur exactement les 2 tâches où la moulinette a créé son conteneur de validation**, puis échoué sur `lchown` avant de le supprimer ; tâche sans patch : OK | **`kill -9` : le conteneur reste** (P1). Sur Docker classique, le nettoyage était OK ×3 |
| Q16 | Résultats SWE | ❌ officiel, ✅ réel | **2/3 réel** : `sympy-18189` et `django-11066` `RESOLVED_FULL` (code de notation de la moulinette) ; `scikit-learn-13439` au plafond | Passerait sur Docker classique. Fragile : sur 3 examens, 1/3, 1/3, 2/3 |
| Q17 | Excellence SWE | 2★ si Q16 passe | Moyenne de 12,7 itérations (4, 4, 30) | 2★ visé d'après `EVALRESUME.md` : 2/3 avec moins de 20 itérations en moyenne |

### Q11 : où intervenir (`1453d0c`)

| Modification | Où | Attention |
|---|---|---|
| 1. `[CORRECTION MARKER 42]` en tête du prompt système | `core/agent/prompt.py`, chaîne `"content"` sous `"role": "system"` (ligne 88 SWE, 170 MBPP) | Au tout début de la chaîne : `system_prompt` doit **commencer** par le marqueur |
| 2. `print('SANDBOX_MARKER_42')` avant le code | `Sandbox.run()`, `sandbox/executor.py:320` | **Pas `execute()`**, que la boucle n'appelle plus. Une étape sans bloc de code n'exécute rien, donc pas de marqueur |
| 3. `# CORRECTOR_CHECK` en tête du code envoyé | `core/agent/loop.py:165` (`self.sandbox_input = ...`) | — |
| 4. `model_name` à `correction-model-42` | `core/agent/loop.py:596`, dans `make_step_metrics()` | **Pas `core/llm/client.py:228`** : c'est le `LLMResponse`, que les `StepMetrics` n'utilisent pas |

### Q12 partie D : la tâche SWE à présenter

`django__django-11066` (résolue, 4 itérations) :
1. trouve `RenameContentType` et lit les lignes 1-30 du fichier ;
2. modifie la ligne 27 lue (`content_type.save(using=db, update_fields={'model'})`) et la
   relit ;
3. lance `run_tests()` ;
4. prend le patch, vérifie qu'il n'est pas vide, et soumet.

---

## Ce qu'il faut faire, par ordre d'impact

| # | Action | Côté | Questions |
|---|---|---|---|
| 1 | **Casser les boucles sur un même code.** 3 échecs sur 3 aujourd'hui : MBPP 245 (3 fois le même code), MBPP 430 (2 paires), `scikit-learn-13439` (14 fois le même `edit_file`). La note « Repeated step » est ignorée par `codestral`. Forme à choisir et à mesurer : message plus ferme et plus précis, ou refus d'exécuter un code identique déjà essayé | P2 | Q8, Q16 |
| 2 | **Dire au modèle pourquoi il échoue.** `run_tests` MBPP : sur un FAIL, la valeur obtenue (`sum_div(12)` rend 28, pas 16). `edit_file` : pourquoi l'`old_str` est introuvable (lignes proches, indentation) | P2 (MBPP), P1 (`edit_file`) | Q8, Q16 |
| 3 | **Imposer « n'éditer que ce qu'on a lu ».** 19 éditions sur 60 dans les runs SWE portent un `old_str` jamais vu : 16 échouent, 3 réussissent de mémoire (`sympy-14711`). Refuser une telle édition avec un message clair sert la qualité (Q16) et la provenance (Q12) | P2 | Q16, Q12 |
| 4 | Fermer l'évasion par `operator.attrgetter` / `methodcaller` et `string.Formatter` | P1 | Q5 |
| 5 | `kill -9` : conteneur lié à la vie de l'agent | P1 | Q15 |
| 6 | Rejouer `exam_swebench.sh` **sur un poste à Docker classique**, pour un verdict officiel et un nettoyage mesuré sans artefact | ensemble | Q15, Q16 |
| 7 | Rapport : `sympy-14711` pour Qwen, une ablation SWE (1 ou 3, avant/après, mêmes tâches), et les tâches du tirage d'examen (`sympy-18189`, `django-11066`, `scikit-learn-13439`) | P2 | Q13, Q14 |
| 8 | Répéter les 4 modifications de Q11 avec le tableau ci-dessus | ensemble | Q11 |
| 9 | Décider du retrait d'`exams/` (3 → 2 avertissements) ; préparer les explications (client HTTP, noms imposés, docstrings « moulinette ») | ensemble | Q12 |

Détails P1 encore ouverts : `get_patch` embarque les changements de mode (sans effet sur les
verdicts jusqu'ici), et `run_tests` SWE ne garde que le début de sa sortie.
