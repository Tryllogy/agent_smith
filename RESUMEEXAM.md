# Agent Smith — Examen complet du 2026-10-05, 16 h 18 (`1453d0c`)

*Les quatre scripts de `exams/` lancés comme le ferait le correcteur, sur `1453d0c` :
`thomas` avec les correctifs de ndi-tull, la détection des étapes répétées, `Observation:` en
séquence d'arrêt et `iterations` égal au nombre d'étapes. Troisième examen en deux jours.
Sorties brutes dans `evaluations/` (non versionné).*

## Verdict

| Examen | 10-04 soir (`4d0a580`) | 10-05 15 h 37 (`90ef54a`) | **10-05 16 h 18 (`1453d0c`)** | Seuil |
|---|---|---|---|---|
| Sandbox | 8/14 ❌ | 14/14 + bonus ✅ | **14/14 + bonus ✅** | tous |
| MBPP | 4/5 ✅ | 5/5 ✅ | **3/5 ❌** | 4/5 |
| SWE-bench, officiel | 1/3 ❌ | 0/3 ❌ (rootless) | **0/3 ❌ (rootless)** | 2/3 |
| SWE-bench, réel | 1/3 | 1/3 | **2/3** | 2/3 |
| Anti-triche (dépôt rendu) | 4 avertissements | 3 | **3** | aucun |

**Le sandbox passe, SWE-bench atteint 2/3 en réel, mais MBPP rate le seuil sur ce tirage.**
Les deux échecs MBPP ne viennent pas des modifications du jour : le modèle resoumet le même
code faux jusqu'au plafond d'entrée. Sur les trois examens, MBPP fait **12/15, exactement le
seuil** : il dépend du tirage. Côté SWE, les deux tâches résolues le sont avec une démarche
propre (lecture, édition de la ligne lue, `run_tests()`, patch). La troisième tourne en rond
14 fois sur la même édition ratée.

---

## Conditions

- `./exams/exam_<type>.sh --student-path . --moulinette-path ./moulinette --env-file .env`,
  **sans `--model-name`** : l'agent prend `codestral-2508`.
- MBPP et SWE-bench en parallèle. **Aucun autre conteneur lancé pendant l'examen SWE**
  (correction de procédure par rapport à l'examen de 15 h 37).
- Docker rootless (`DOCKER_HOST` exporté pour la moulinette). La validation SWE officielle y
  échoue (`lchown`) : les patchs soumis sont notés avec le code de notation de la moulinette
  (voir « SWE-bench »).
- `django-11066` tirée pour la première fois : son image est tirée pendant l'examen, et la
  durée compte dans le temps de l'agent.

---

## Sandbox — 14/14, bonus compris

Les 14 tests passent, et le bonus layer 1 aussi, comme à 15 h 37. Sortie :
`evaluations/sandbox/2026-10-05_16-18-40/`.

---

## MBPP — 3/5

| Tâche | Résultat | Itérations | Tokens entrée / sortie | Temps agent | Cause de l'échec |
|---|---|---|---|---|---|
| 68 | ✅ PASSED / VALID | 1 | 975 / 246 | 3,6 s | |
| 16 | ✅ PASSED / VALID | 1 | 977 / 157 | 5,5 s | |
| 245 | ❌ FAILED / VALID | 3 | 4 806 / 1 343 | 22,0 s | **même code 3 fois** (somme maximale de sous-séquence bitonique, calculée sur des sous-tableaux), arrêt avant le plafond d'entrée |
| 430 | ❌ FAILED / VALID | 4 | 5 838 / 820 | 12,1 s | **deux paires d'étapes identiques** ; formule de la directrice attendue par MBPP atypique (`-2336` pour `(9, 8, 4)`) |
| 269 | ✅ PASSED / VALID | 1 | 953 / 127 | 7,7 s | |

- Métriques valides partout, aucun retry, `stderr.log` vide, et `iterations` égal au nombre
  d'étapes.
- **Les modifications du jour ne sont pas en cause** : aucune réponse ne contient
  `Observation:`, toutes se terminent normalement.
- Dans les deux échecs, la note « Repeated step » a été émise et **ignorée**. Le rapport de
  `run_tests` dit « FAIL » **sans la valeur obtenue**, qui aurait pu montrer l'erreur au
  modèle.
- Sur les 3 examens : 4/5, 5/5, 3/5, soit 12/15. Les tâches réussies le sont en 1 itération ;
  les échecs sont des boucles sur un même code.

Sortie : `evaluations/mbpp/2026-10-05_16-19-13/`.

---

## SWE-bench — 0/3 officiel, 2/3 réel

| Tâche | Agent | Itérations | Tokens entrée / sortie | Temps agent | Officiel | Notation de secours | Cleanup |
|---|---|---|---|---|---|---|---|
| `scikit-learn__scikit-learn-13439` | pas de patch | 30 | 249 883 / 5 661 | 158,2 s | ❌ pas de patch | ❌ | OK |
| `sympy__sympy-18189` | succès annoncé | 4 | 15 987 / 457 | 55,4 s | ❌ `lchown` | ✅ **`RESOLVED_FULL`** (F2P 1/1, P2P 41/41) | FAILED* |
| `django__django-11066` | succès annoncé | 4 | 16 425 / 437 | 69,1 s (pull compris) | ❌ `lchown` | ✅ **`RESOLVED_FULL`** (F2P 1/1, P2P 3/3) | FAILED* |

\* `CLEANUP: FAILED` vient de la moulinette, pas de l'agent (voir plus bas).

Métriques valides partout, `stderr.log` vide, `iterations` égal au nombre d'étapes.

### Ce qui a marché

- **Plus aucune observation inventée** : 0 réponse avec `Observation:`, 277 tokens au plus
  par réponse (contre 6 260 pour la réponse qui avait épuisé le budget à 15 h 37).
- **`django-11066` et `sympy-18189`** suivent la même démarche en 4 étapes :
  1. `search_function_or_class_definition_in_code` et `read_file` de la zone (lignes 1-30 du
     fichier de django, 180-190 de `diophantine.py`) ;
  2. `edit_file` de la ligne lue (`content_type.save(using=db, …)` ;
     `diophantine(eq, param, permute=permute)`) ;
  3. `run_tests()` ;
  4. `get_patch()`, puis `final_answer`.

  Le patch de `18189` embarque encore un changement de mode sur un fichier de test
  (`get_patch`, P1), sans effet sur le verdict.

### Ce qui n'a pas marché

- **`scikit-learn-13439`** alterne 14 fois `read_file` des lignes 29-35, puis le **même
  `edit_file`** dont l'`old_str` (`def __repr__(self): …`) n'est pas dans le fichier, jusqu'au
  plafond de 30 itérations. La note « Repeated step » est émise à chaque fois. Le message
  « old_str not found » ne dit pas pourquoi.
- Un rejeu isolé de la même tâche, juste avant l'examen, l'avait résolue (15 itérations). Le
  résultat dépend du tirage.

### `CLEANUP: FAILED` — l'artefact est confirmé

Cette fois, aucun autre conteneur ne tournait. Les deux `CLEANUP: FAILED` (« 1 > 0 ») tombent
**exactement sur les deux tâches où la moulinette a démarré son conteneur de validation**, puis
échoué sur `lchown` **avant** de le supprimer. La tâche sans patch, sans conteneur de
validation, est `CLEANUP: OK`. Aucun conteneur de l'agent ne reste. Sur Docker classique
(examen du 10-04), le nettoyage était OK trois fois.

Sortie : `evaluations/swebench/2026-10-05_16-19-13/`.

---

## Anti-triche

Mêmes 3 avertissements qu'à 15 h 37 dans le dépôt rendu :
- URL GitHub dans `exams/` ;
- `httpx` dans le client LLM (`core/llm/client.py`, `provider.py`) ;
- noms `swebench` imposés par le sujet.

Sans `exams/`, il en resterait 2, inévitables. Les autres correspondances viennent de `tests/`
et `moulinette/`, absents du dépôt rendu.

---

## Ce que cet examen apprend

1. **`Observation:` en séquence d'arrêt fonctionne** : aucune observation inventée en SWE ni en
   MBPP, et les réponses restent courtes.
2. **Les boucles sur un même code sont la cause commune des échecs** : 3 échecs sur 3 aujourd'hui
   (MBPP 245, MBPP 430, `scikit-learn-13439`). La note « Repeated step » ne suffit pas, avec
   `codestral` en tout cas.
3. **Le modèle ne voit pas pourquoi il échoue** : `run_tests` MBPP ne donne pas la valeur
   obtenue, et `edit_file` ne dit pas pourquoi l'`old_str` est introuvable.
4. **Éditer sans avoir lu** : sur les 60 éditions des runs SWE (campagnes et examens), **19
   portent un `old_str` jamais vu dans une observation antérieure**. 16 échouent, et 3 réussissent
   de mémoire (`sympy-14711`, examen de 15 h 37). La règle anti-récitation du prompt n'est pas
   respectée, et rien ne l'impose.
5. **MBPP n'a pas de marge** : 12/15 sur trois tirages, pile sur le seuil.
