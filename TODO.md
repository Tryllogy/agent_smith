# Agent Smith — TODO & repartition du travail

| | Qui | Domaine |
|---|---|---|
| **Personne 1** | ndi-tull | Execution & Outils (sandbox, MCP, tools, Docker) |
| **Personne 2** | tchemin | Agent & Intelligence (boucle, LLM, prompts, bench) |

> Le projet n'est **pas** "faire generer du code par un LLM". C'est construire un
> **runtime securise et instrumente** pour un agent de code. MBPP / SWE-bench sont
> le banc d'essai, pas l'objet. Voir [RESUME.md](RESUME.md).

---

## Etat actuel — 2026-10-03

**Cote P2 (tchemin) : tout ce qui pouvait etre fait sans MCP l'est.** Boucle,
extraction, couche LLM, provider, prompts MBPP et SWE, les deux CLI, la config
modeles. **493 tests verts.** `ruff check` : 0 cote P2, **9 erreurs dans
`mcp_tools/`** depuis le merge (code P1, 8 corrigeables par `--fix`).

**Fournisseurs SWE : il en manque un depuis le 2026-10-03.** NVIDIA a
retire `nemotron-3-super` ce jour-la (HTTP 410, « end of life ») : restent 4
modeles utilisables pour SWE, `nemotron-3-ultra` (NVIDIA) et `codestral-2508`,
`ministral-14b-2512`, `ministral-8b-2512` (Mistral), tous passes par le vrai
CLI SWE le 2026-10-02. Le sujet en demande **au moins 5** (*« at least 5
models »*, ch. VI). **Mistral valide par l'equipe pedagogique le 2026-10-02**
(credits mensuels offerts, sans carte ; le sujet le range d'ailleurs parmi
les *« Cloud providers with free access »*, § V.6.1).

**`Makefile` : un modele par defaut par benchmark** (2026-10-02,
`e0a7737`) — MBPP `ministral-14b-2512` (Mistral), SWE `codestral-2508`
(Mistral) depuis le 2026-10-03 (`560a18f`), a la place de `nemotron-3-super`
retire. **Seuls les modeles declares
dans `configs/models.json` sont acceptes** (`c7727cc`) : un modele payant
non declare est refuse avant toute requete.

**MBPP : 4 modeles a 15-17/20, au niveau de Groq (16/20).** Campagne des 5
modeles sur les 20 taches de reference (`run15` a `run24`), puis deux
defauts de la boucle corriges et `codestral` rejoue : 11/20 → **17/20**,
metriques valides 17/20 → 20/20 (`run25`/`run26`). Le 2026-10-03,
**l'exemple MBPP passe en multiligne** (ablation E, `run27` a `run34`) :
`codestral` 16/20 → 17/20, 7 refus `SyntaxError` → 0, entree par tache
−39 % ; Groq 17/20 → 18/20. Puis **rejeu des autres sur l'agent actuel**
(`run35` a `run40`) : `ministral-14b` et `ministral-8b` 15/20 → 13/20
(taches perdues : raisonnement jusqu'au plafond de sortie, dans le bruit
d'un tirage), `nemotron-3-super` impossible a rejouer (retire). Detail en
P2.6.

**`BENCHMARK_REPORT.md` : partie MBPP ecrite** (2026-10-02, en anglais ;
mis a jour le 2026-10-03 : ablation E, rejeu sur l'agent actuel, retrait de
`nemotron-3-super`, tokens Groq sous-estimes), sur les 36 campagnes `run5` a
`run40`,
**versionnees dans `benchmarks/mbpp/`**
avec leurs `solution.json`. Les sections SWE gardent la structure du sujet et
attendent les outils (P2.6).

**Repli entre fournisseurs : fait** (2026-10-02, `19e17be`). Une erreur
permanente, ou 5 transients de suite sur le meme modele, ne terminent plus la
tache : elle continue sur le modele suivant de `configs/fallback.json` (une
liste par benchmark), puis echoue proprement. Verifie en reel sur deux taches
MBPP validees par la moulinette (P2.3, « Repli de provider »).

**Limite de tokens par minute de Mistral respectee avant l'envoi**
(2026-10-02, `36e071b`) : une requete qui ne tiendrait pas dans les tokens
restants de la minute n'est plus envoyee (P2.3, « Limite de tokens par
minute »).

**Reponse vide : reprise depuis `reasoning`, et tokens des reponses rejetees
comptes** (2026-10-03, non commite). Quand `content` est vide et que
`reasoning` porte un bloc de code ferme, c'est la reponse. Les tokens d'une
reponse rejetee par le client vont dans les totaux **et** dans l'etape : les
totaux Groq publies jusqu'ici sont donc sous-estimes. Detail en P2.3.

**Sandbox manual dans le prompt, cote `Prompt`** (2026-10-03, `fb8f224`) :
le manuel de ndi-tull (`sandbox/manual.py`) est insere tel quel par
`Prompt(manual=)`, et ce qu'il dit deja n'est plus repete par nos consignes.
**Les deux CLI passent encore `manual=None`** : `render_manual()` attend le
client MCP connecte, qui n'existe pas encore (P1.4). Detail en P2.4.

**Cote P1 (ndi-tull) : demarre.** L'executeur et cinq modules de securite
existent, le sandbox execute du code et remonte `final_answer` — c'est ce qui a
debloque la boucle. Les 9 outils sont **merges dans `thomas`** depuis le
2026-10-01 (`70207ab`), mais leurs signatures ne suivent pas le § V.5 (voir la
revue ci-dessous). Le **manuel** (`sandbox/manual.py`, `2b4ddb3`) et les
**transports** stdio et HTTP du client MCP (`49b7d9a`) sont dans `thomas`
depuis le 2026-10-03 (`c4cff46`). Restent le CLI/REPL, le client MCP lui-meme
(`sandbox/mcp_client/client.py` est vide), les wrappers des outils dans le
namespace du sandbox, et Docker.

> **Le chemin critique est cote P1.** Sans client MCP et sans Docker, ni
> SWE-bench ni le rapport de benchmark ne peuvent avancer. Le prompt SWE n'a
> jamais tourne contre un vrai depot.

**Dettes qui bloquent la mesure** (la 2 et la 3 sont reglees) :

0. **Il manque un 5e modele SWE** (2026-10-03) : `nemotron-3-super` retire
   par NVIDIA, 4 modeles restent pour un minimum de 5 (« Prochaines
   actions », 4 bis)

1. **Les outils MCP sont merges mais non conformes** : `origin/ndi-tull`
   (`9c8c4b2` → `64f06cc`) est rapatrie dans `thomas` le 2026-10-01
   (`70207ab`). Les signatures restent a caler sur le § V.5 avant de brancher
   quoi que ce soit dessus (voir la revue).
2. ~~**Le modele par defaut du `Makefile` (`MODEL :=`) est inutilisable.**~~
   **Reglee le 2026-10-02** : `nemotron-3-ultra-550b-a55b:free` (OpenRouter,
   27 a 40 s par reponse) remplace par un defaut par benchmark, voir
   « Prochaines actions », 4 quater
3. ~~**L'echeance de 30 s par appel est trop courte pour SWE.**~~
   **Reglee le 2026-10-02** : l'echeance depend du benchmark
   (`Bench.llm_timeout`), 60 s pour SWE, 30 s pour MBPP. Voir « Prochaines
   actions », 4 ter

### Revue du 2026-10-01 (sujet relu en entier, code relu, tout verifie a l'execution)

**Corrige le jour meme (P2) :**

- [x] **Aucune tache SWE ne pouvait reussir.** Le `ast.parse(answer)` ajoute
      par `845e54e` s'appliquait aux deux benchs ; or un `git diff` n'est
      jamais du Python valide (verifie : `SyntaxError`), donc
      `final_answer(get_patch())` etait **toujours** refuse. Le controle vit
      maintenant dans `Loop.check_final_answer()` : `ast.parse` pour MBPP,
      marqueurs de patch pour SWE (`constants.PATCH_MARKERS`, les **memes**
      que `_validate_swebench_patch` de la moulinette), chaine non vide pour
      les deux. Effet de bord voulu : une reponse MBPP **vide** passait
      (`ast.parse("")` reussit), elle est refusee. 4 tests ajoutes, qui
      echouent tous sur l'ancien code

- [x] **Erreur de config = aucun `solution.json`** — corrige. `main()` des deux
      `__main__.py` ecrit desormais un rendu d'echec
      (`write_failure_output()`, `success=false`, `error` rempli, `task_id`
      relu au mieux dans la tache, `""` sinon) puis sort en 1. Un plantage
      **pendant** la boucle est rattrape dans `cli.run()` par
      `loop.make_solution_output()`, qui garde les steps deja enregistres —
      un rendu a zero aurait menti sur les requetes parties. Un chemin de
      sortie non inscriptible est signale sur `stderr`, sans trace
- [x] **Etape fantome sur sortie par garde** — corrigee. Le `llm_output` du
      tour vit dans `self.llm_output`, remis a zero avec `request_time_ms` en
      tete de chaque passage ; les sorties par garde passent par
      `exit_on_guard()`, qui n'enregistre le tour **que si une requete est
      partie** (`turn_requests`, retries compris). Au passage, `llm_output`
      ne commence plus par une espace pour un modele sans raisonnement
- [x] `ruff format --check` propre (la ligne `loop.py:180` a ete reecrite)

13 tests ajoutes pour ces deux points, qui echouent tous sur l'ancien code.

**Constate cote P1 (a transmettre, rien n'a ete touche) :**

- [ ] **Evasion du sandbox** : `random._os`, `typing.sys.modules['os']`,
      `typing.sys.modules['builtins'].open('/etc/hostname')` et `_socket`
      passent tous. `ast_guard` ne bloque que les `__x` ; `typing.sys` est un
      attribut **public**, il faut filtrer les attributs des modules importes
- [ ] **Sortie > 64 Ko = faux timeout** : interblocage `Queue` / `join`
      (`executor.py:57-71`), l'enfant attend que le parent lise, le parent
      attend que l'enfant finisse. Et aucune troncature (exigee, V.1)
- [ ] **Timeout = sortie partielle perdue** (`StringIO` dans l'enfant tue) ;
      le sujet exige de la renvoyer
- [ ] `sandbox_template.json` fait 0 octet : `uv run sandbox
      sandbox_template.json` plantera au parsing
- [ ] **Signatures des outils `ndi-tull` non conformes au § V.5** — critere
      eliminatoire (*"All mandatory tools pass independent tests"*) :

| Outil | Sujet | `mcp_tools/` (merge `70207ab`) |
|---|---|---|
| `find_references` | `(name, filepath, line)` | `(name, file_pattern)` |
| `search_function_or_class_definition_in_code` | `(name)` | `(name, file_pattern)` |
| `run_command` | `(command, workdir)` | `(command, timeout, cwd, raw)`, **sans shell** |
| `run_tests` | lance l'`eval_script` | lance `pytest` |
| `get_patch` | `git -c core.fileMode=false diff` | `git add -A` + `diff --cached` |

  `run_command` passe par `shlex.split` sans shell : le `<<'PY'` et le `&&`
  de **notre** exemple SWE ne marcheront pas. Les recherches partent de
  `Path(".")`, pas de `/testbed`. Le serveur MBPP n'expose aucun outil (le
  § V.3.2 exige `run_tests`).

**Risque de planning — les quotas gratuits face a SWE :**

- [x] **Groq gratuit est inutilisable pour SWE — verifie le 2026-10-01.**
      Une requete unique de 9 096 tokens rend **HTTP 413** « Request too
      large… on tokens per minute (TPM): Limit 8000, Requested 9096 » : toute
      requete au-dela de 8 000 tokens est refusee d'office. Le prompt SWE en
      fait deja ~2 700 a vide, quelques `read_file` suffiront. Le 413 tombe
      dans la branche « Unexpected error » de `check_status_error` → abandon
      `Permanent` : traitement juste (rejouer ne sert a rien), message
      imprecis. Meme sous le plafond, a ~3 500 tokens par requete, le seau TPM
      impose des 429 de ~20 s (vu sur le run SWE du meme jour, P2.4)
- [~] OpenRouter : 50 req/jour. **≥ 5 modeles × 3 taches SWE** ≈ 225 a 450
      requetes, soit 5 a 9 jours de quota. Chercher d'autres fournisseurs
      gratuits **maintenant** : c'est le vrai chemin critique du rapport.
      **Releve fait le 2026-10-01** (P2.3, « Fournisseurs pour SWE »), **cles
      posees et fournisseurs branches le 2026-10-02** : NVIDIA (2 modeles) +
      Mistral (3 modeles) = 5. **Mistral valide par l'equipe pedagogique le
      2026-10-02**

**Rendu :**

- [x] `.gitignore` ignore `cache/` **et** `solution.json` partout, or les
      `solution.json` de backing doivent etre dans le repo (V.7) — **regle le
      2026-10-02** (`0faae67`) : campagnes copiees dans `benchmarks/mbpp/`,
      et `!benchmarks/**/*.log` + `!benchmarks/**/solution.json` en fin de
      `.gitignore` (sans la premiere, `*.log` ignorait les logs d'agent, seule
      trace des causes de retries citees dans le rapport)
- [ ] `moulinette.zip` (250 Ko) est versionne, sans utilite pour le rendu

### Journal condense

**2026-09-01, jour** (`15aff15` → `0e86329`, 714 insertions / 13 fichiers) :
prompt SWE fini avec son tour `user`, `agent_swebench/` ecrit et **lance pour de
vrai** (`solution.json` conforme sur `sympy__sympy-14711`), helpers CLI
factorises dans `core/agent_cli_helper.py` (les deux `cli.py` tombent a 63
lignes, MBPP en faisait 163), dette ruff 13 → 0.

**2026-09-01, soir** (`b2bcaa4`) : `core/validators.py` → `core/config_models.py`
(+ 6 imports), `RootModelConfig` et `core/llm/keyring.py` supprimes, exemple MBPP
nettoye, `evaluations/` gitignore, et surtout **le trou de tests comble** —
`tests/test_agent_cli.py`, aucun autre ne construisait `AgentMBPP` ni
`AgentSWEBENCH`.

**2026-09-02** (`97091ce` → `3fb1d4f`) : `ModelConfig` supprime,
`is_reasoning` retire partout, consigne d'`assert` rendue dependante du bench,
`retry_after` propre a chaque bench, `retries` affiches sans le +1. Detail en
P2.5 bis et P2.1.

**2026-10-01** : revue complete, bug `ast.parse` / SWE corrige, rendu d'echec
ecrit meme sans boucle, etape fantome supprimee (`6a05df8`). Puis **merge de
`origin/ndi-tull`** (`70207ab`) : un seul conflit, `sandbox/executor.py`, ou
la logique etait identique des deux cotes — garde le `return` reformate par
ruff (`thomas`) et la suppression du bloc de demo `__main__` (`ndi-tull`).
Verifie apres merge : 323 tests verts, les deux serveurs se chargent sous
`mcp` 2.0.0 (`list_tools()` : 9 outils cote SWE, 0 cote MBPP). Ensuite :
docstrings sur tout le code P2 (`0b356ae`), prompts et relances corriges
(`9c4754a`), **trois campagnes MBPP** (`run9`, `run10`, `run11`, voir P2.6),
et deux bugs de la boucle reveles par ces campagnes corriges dans la foulee
(attente non plafonnee, cause des retries perdue — voir P2.1, `2f7b56b`).
Puis, **non commite** : prompt MBPP (tests caches, `assert` + `final_answer`
dans le meme bloc), campagne `run12`, et **verification du `final_answer`
MBPP par la boucle** contre `test_list` (voir P2.1, P2.4, P2.6) — commites
dans `4c8d206`. Campagnes `run13`/`run14` avec la verification (16/20, 0
soumission a l'aveugle, 2 refus justes). Premiere tache **SWE** lancee
(`sympy__sympy-14711`, 5 iterations) : outils non branches, modele qui
**recite le correctif** de memoire, Groq **413 confirme** au-dela de 8 000
tokens. D'ou la regle anti-recitation dans le prompt SWE et l'exemple SWE mis
en conformite (P2.4). Enfin **NVIDIA branche** et `ModelConfig` revenu avec
`extra_body` (P2.5 bis) — le tout commite dans `ccbbe79`.

**2026-10-02** : sondage du catalogue NVIDIA (19 candidats, 2 retenus),
Cerebras et Together ecartes, **cle Mistral posee et 3 modeles branches**. Les
5 modeles ont tourne 5 iterations chacun par le vrai CLI SWE. Detail en P2.3
« Fournisseurs pour SWE ». **Non commite** : `configs/models.json`
(`nemotron-3-ultra` et le fournisseur `mistral`), `.env.example` — commites
dans `94539e7`. Puis **campagne MBPP des 5 modeles** (`run15` a `run24`) :
5 metriques INVALID (entree cumulee > 6 000) et 9 echecs de `codestral` sur
des `final_answer` d'une ligne cassee par des `;`. D'ou **deux correctifs de
la boucle** (P2.1) et le rejeu de `codestral` (`run25`/`run26`, 17/20).
Correctifs commites dans `c21b0ce`. Enfin **`BENCHMARK_REPORT.md`, partie
MBPP**, et les 22 campagnes versionnees dans `benchmarks/mbpp/` (`0faae67`).
La revalidation de `run5` a `run8` par la moulinette fait passer **`run7` de
9/10 a 8/10** (MBPP 400, test cache) : chiffres corriges ci-dessous
(`1a2a024`). Puis le **repli entre fournisseurs** (P2.3, `19e17be`), et la
**limite de tokens par minute de Mistral verifiee avant l'envoi** (P2.3,
`36e071b`). Puis **seuls les modeles declares dans `models.json` sont
acceptes** (`c7727cc`) : OpenRouter avait servi `openai/gpt-4o-mini`, payant,
sur un compte sans credit (P2.5 bis). Relecture du sujet sur le payant
(P2.3, « Ce que dit le sujet du payant »). **Mistral valide** par l'equipe
pedagogique, d'ou le defaut MBPP du `Makefile` sur `ministral-14b-2512`
(`e0a7737`). Puis **l'echeance par appel propre a SWE** (60 s, 4 ter,
`11cae12`).

**2026-10-03** : merge d'`origin/ndi-tull` (`c4cff46`), qui apporte
`sandbox/manual.py` et les transports MCP. **Manuel insere dans le prompt**
et doublons retires (P2.4, 4 decies), commite dans `fb8f224`. Puis
**l'exemple MBPP passe en multiligne**, mesure contre l'ancien sur Groq et
`codestral` (`run27` a `run34`, P2.4, P2.6, ablation E du rapport).
Commite dans `e13feb3`. Puis le **rejeu** de `ministral-14b`, `ministral-8b`
et `nemotron-3-super` sur l'agent actuel (`run35` a `run40`, P2.6), qui
revele le **retrait de `nemotron-3-super`** par NVIDIA : defaut SWE passe a
`codestral-2508`, `nemotron-3-ultra` a sa place dans les listes de repli
(`560a18f`). Puis la **reprise de `reasoning`** quand `content` est vide et
le **comptage des tokens des reponses rejetees** (P2.3). **Non commite** :
`core/` (6 fichiers), `BENCHMARK_REPORT.md`, `benchmarks/README.md`,
`benchmarks/mbpp/run35` a `run40`, `TODO.md`.

### Trois bugs du 2026-09-01 qui valent d'etre sus

1. **Les appels d'outils nus ne produisaient aucune observation.** L'exemple SWE
   appelait `run_command(...)` sans `print()`. Or `executor.py:38` fait
   `exec(code, ns)` : en `exec`, la valeur d'une expression isolee est **jetee**,
   ce n'est pas un REPL. Un modele imitant l'exemple aurait lu des fichiers sans
   rien voir et lance les tests sans resultat. **Echec silencieux total.**
2. **`SWE_PROMPT_EXEMPLE` etait une `"""` ordinaire** : les `\n` et `\"` etaient
   interpretes a la compilation de `constants.py`, donc 3 blocs sur 4 arrivaient
   au modele en Python invalide. Corrige par `r"""`, verifie a l'`ast`.
3. **`get_task_from_file()` appelee avec 1 argument sur 2, dans les deux CLI** :
   `TypeError` a la construction, invisible parce qu'**aucun test ne construisait
   les agents**. C'est ce trou qu'a comble `tests/test_agent_cli.py`.

### Qui a du code

| Ecrit | Encore vide |
|---|---|
| `core/` : `models.py`, `config_models.py`, `errors.py`, `constants.py`, `api_key.py`, `agent_cli_helper.py` | `sandbox/cli.py`, `security/limits.py` |
| `core/agent/` : `loop.py`, `prompt.py`, `extraction.py` | `sandbox/mcp_client/client.py` |
| `core/llm/` : `client.py`, `provider.py` | |
| `mcp_tools/` + les 2 `mcp_tools_*.py` racine (merges le 2026-10-01, **signatures non conformes**) | |
| `agent_mbpp/`, `agent_swebench/` (sauf `docker.py`) | `agent_swebench/docker.py` |
| `sandbox/executor.py`, `sandbox/manual.py`, `sandbox/mcp_client/transports.py`, `configs/models.json` | `sandbox_template.json` |
| `sandbox/security/` : `imports`, `builtins`, `filesystem`, `network`, `ast_guard` | `BENCHMARK_REPORT.md`, `README.md` |

Trois modules supprimes, avec leur raison : **`usage.py`** (le suivi d'usage vit
dans `Loop`, un module separe aurait duplique l'etat sans proprietaire),
**`response.py`** (`LLMResponse` a demenage dans `config_models.py`),
**`keyring.py`** (sans emploi depuis qu'`APIKey` porte l'etat du vivier).

```
racine         . mcp_tools_mbpp.py  . mcp_tools_swebench.py
               . sandbox_template.json  . BENCHMARK_REPORT.md  . README.md
core/          + models.py  + config_models.py  + errors.py  + constants.py
               + api_key.py  + agent_cli_helper.py
  agent/       + loop.py  + extraction.py  + prompt.py
  llm/         + client.py  + provider.py
sandbox/       . cli.py  + executor.py  + manual.py
  security/    + imports.py  + filesystem.py  + builtins.py  + network.py
               + ast_guard.py  . limits.py
  mcp_client/  . client.py  + transports.py
mcp_tools/     . tools_fs.py  . tools_search.py  . tools_exec.py
agent_mbpp/    + __main__.py  + cli.py
agent_swebench/+ __main__.py  + cli.py  . docker.py
configs/       + models.json
tests/         + banc d'essai local, gitignore, hors rendu (295 tests)
```

### Deux fichiers de models Pydantic — le critere est « qui possede le schema »

| Fichier | Schema possede par | Ce qu'on a le droit d'y ecrire |
|---|---|---|
| `core/models.py` | la moulinette (`models_public.py`) | rien de neuf : c'est une copie, un `diff` doit le prouver |
| `core/config_models.py` | nous (`LLMResponse`, `ProviderConfig`) | ce qu'on veut, ca bouge a chaque fournisseur ajoute |

Le premier ne bouge jamais et un champ ajoute casse l'evaluation en silence ; le
second vit. C'est ce critere qu'on defend, pas « les models d'un cote, les
validateurs de l'autre » — qui ne dit rien de ce qu'on peut ecrire dans chaque.

- [ ] **`SandboxConfig` est a cheval sur cette frontiere** : forme imposee par
      `models_public.py`, valeurs par defaut a nous (imports, `/testbed`, 30 s,
      512 Mo). C'est le seul des cinq models **jamais echange** avec la
      moulinette. Trois sorties, par ordre de preference — sous-classer comme le
      fait la moulinette elle-meme (`moulinette/moulinette/models.py:23`),
      externaliser les valeurs dans `sandbox_template.json` (**vide
      aujourd'hui**, alors que le `Makefile` le propose en `CONFIG=`), ou assumer
      la divergence en la commentant.

---

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

## Phase 0 — faite

Setup uv, `pyproject.toml`, Python 3.10 (`.venv` en 3.10.20), Makefile,
`.gitignore` (`.env`, `__pycache__`, `cache`, `tests`, `moulinette`,
`evaluations/`), flat layout (`src/` supprime, `[project.scripts]` et
`[tool.hatch]` corriges), les **5 models Pydantic** figes, l'interface
`execute(code, config) → (stdout, stderr, error, is_final, answer)` stabilisee et
en service, chargement du `.env` et de `configs/models.json` dans les CLI.

- [ ] **Relire `core/models.py` champ par champ contre le sujet (V.3 / V.4)**
      avant d'aller plus loin. Une signature fausse casse les deux moities du
      projet et n'est detectee qu'a la validation moulinette.
- [ ] `uv run sandbox` ne marchera qu'une fois `sandbox/cli.py:main()` ecrit.

### Dependances

`pydantic>=2`, `mcp>=1.2`, `httpx>=0.27`, `python-dotenv>=1`, `docker>=7` ;
dev : `pytest>=8`, `ruff>=0.6`.
**INTERDIT** (reimplementent l'orchestration) : `smolagents`, `langgraph`,
`crewai`, `autogen`, `llama-index`, `langchain-agents`.
Optionnels selon les choix : `openai` (si SDK plutot que httpx brut), `psutil`
(RAM), `tiktoken` (fallback de comptage — normalement inutile, l'API renvoie
`usage`).

**Sandbox = stdlib uniquement.** `ast` (validation avant exec), `builtins` +
`importlib` (allowlists), `sys`, `os.path`/`pathlib` (`realpath` pour l'allowlist
FS), `resource` (`RLIMIT_AS`/`RLIMIT_CPU`), `signal`, `multiprocessing`
(isolation, approche recommandee), `subprocess` (serveur MCP stdio, docker),
`socket` (neutralisation reseau), `io`/`contextlib` (capture de sortie),
`traceback`, `types`, `threading`/`queue`, `tempfile`, `json`, `time`.

**MCP** — serveur : `from mcp.server import MCPServer` (**`mcp` 2.0.0 installe** :
`mcp.server.fastmcp` n'existe plus, verifie le 2026-10-01). Client (les **deux**
transports sont obligatoires) : `ClientSession`, `StdioServerParameters`,
`mcp.client.stdio.stdio_client`, `mcp.client.streamable_http.streamablehttp_client`.
C'est `list_tools()` qui alimente la generation du manuel. **Verifie le
2026-10-03** : en `mcp` 2.0.0, `Tool.input_schema` est en snake_case, ce que
lit `manual.py`, et le client HTTP s'appelle `streamable_http_client`.

Dans le container SWE-bench (optionnel) : `jedi` (`find_references`), `ruff`
(verification apres `edit_file`), `tree`.

---

## Personne 1 — ndi-tull : Execution & Outils

### P1.1 — Sandbox (priorite absolue)

- [ ] Approche d'isolation (process separe recommande : timeout et RAM
      applicables proprement)
- [ ] Allowlist d'imports (`authorized_imports`, motifs `module.*`)
- [ ] Allowlist filesystem (`allowed_directories`, chemins resolus **dans** le
      sandbox)
- [ ] Blocage reseau total, timeout d'execution, limite RAM, builtins restreints
- [ ] Propagation de `KeyboardInterrupt` / `SystemExit` — **exigee par le
      sujet**, deja tenue par `executor.py`, a garder sous test
- [ ] Namespace = wrappers MCP decouverts dynamiquement + `final_answer`, rien
      d'autre. `final_answer` est une primitive **du sandbox**, pas un outil MCP

#### Qui contient qui — tranche par le sujet (p. 16)

```
Sandbox  ⊃  client MCP  --stdio/HTTP-->  serveur MCP (autre processus)  -->  outils
```

> *"The sandbox wraps the MCP client, not the other way around."*

**Deux domaines de securite independants**, et c'est le point de soutenance :

| | Ce qui est contraint | Par quoi |
|---|---|---|
| Code Python du LLM | imports, chemins, RAM, timeout | notre sandbox |
| Actions des outils MCP | rien de tout ca | le serveur, ailleurs |

Ce n'est **pas** un trou de securite, c'est ce qui rend le projet realisable :
`run_command` doit pouvoir lancer un processus et `edit_file` ecrire dans
`/testbed` — deux choses que le sandbox interdit formellement au code du modele.

- [ ] **Le timeout du sandbox ne borne pas les appels MCP** (*"Actions performed
      by the MCP server are not subject to the sandbox timeout"*).
      `max_execution_time_seconds = 30` ne coupe pas un `run_tests()` qui lance
      une suite sympy pendant 3 minutes, alors que SWE-bench plafonne a 900 s.
      **Il faut une echeance cote appel d'outil** — meme probleme que P2 a resolu
      cote LLM (thread + `join(timeout=...)`, cf. P2.3), solution transposable

### P1.2 — Feedback au LLM

*Souvent oublie, explicitement exige.* Aucun echec silencieux, sinon le LLM
hallucine ses observations.

- [ ] aucun bloc trouve / bloc malforme interprete quand meme (dire comment) /
      timeout atteint (renvoyer la sortie partielle) / sortie tronquee (le dire) /
      edit ayant casse la syntaxe ou le lint

### P1.3 — CLI sandbox

- [ ] `uv run sandbox` (REPL), `... sandbox_template.json` (config custom),
      `--mcp-stdio "python mcp_tools_mbpp.py"`, `--mcp-server <URL>` (HTTP)
- [ ] REPL : memes restrictions, sortie propre sur `exit` **et** Ctrl+D (EOF)

### P1.4 — MCP

- [ ] Serveur : transports stdio **et** HTTP streamable
- [ ] Client integre dans le sandbox, decouverte dynamique, tools + resources +
      prompts, wrappers generes depuis les schemas
- [x] Generation dynamique du **sandbox manual** depuis les schemas du serveur
      — `sandbox/manual.py` (ndi-tull, `2b4ddb3`). Verifie le 2026-10-03 sur
      les deux vrais serveurs : 9 outils cote SWE (signature, puis docstring),
      aucun cote MBPP

```
prompt (manuel)      <- decouverte <- serveur MCP
namespace du sandbox -> wrapper    -> client MCP -> serveur -> outil
```

Un maillon sur cinq reste vide depuis le 2026-10-03 : le client MCP
(`sandbox/mcp_client/client.py`). Le manuel et les transports sont arrives.
`mcp_tools/` est merge (signatures a caler, voir la revue en tete).
Le namespace d'`executor.py:32` ne contient toujours que `final_answer` :
**aucun outil n'est encore appelable depuis le sandbox**.

- [x] Le manuel contient le **contrat** (nom, description, types), **jamais le
      code** : l'implementation peut changer sous le modele. Verifie le
      2026-10-03 : signature typee, puis la docstring de l'outil
- [ ] **A transmettre a ndi-tull** (constate le 2026-10-03, rien touche) :
  - avec le serveur MBPP, qui n'a aucun outil, le manuel annonce *« the
    tools below »* sans rien en dessous
  - le manuel annonce `run_command(command, timeout, cwd, raw)`, notre
    exemple SWE ecrit `workdir`, comme le sujet (§ V.5). Une fois le manuel
    branche, le modele lira deux signatures contradictoires : c'est la
    signature de l'outil qu'il faut caler (voir la revue en tete)
- [ ] Une liste d'outils **ecrite en dur** passerait nos 3 taches et
      **echouerait a l'evaluation** (*"The system will be tested with an unknown
      MCP server"*). La decouverte n'est pas un confort, c'est la condition de la
      note
- [ ] Le wrapper est une entree du dict `ns` d'`executor.py` : **aucune magie**,
      donc un `def run_tests():` ecrit par le modele **ecrase le wrapper**. Vu
      pour de vrai dans un ancien exemple, ou le modele redefinissait
      `get_patch()` et fabriquait son propre diff (cf. P1.7)

**Interface avec P2 : tranchee le 2026-10-03.** `render_manual(client)` rend
**un texte deja mis en forme**, que `Prompt(manual=)` insere tel quel : P2
insere, il ne compose pas. Reste a convenir **comment l'agent le recupere** :
`render_manual` attend le client connecte, et ce client vit dans le sandbox
(§ IV : *« The sandbox wraps the MCP client »*). D'ici la, les deux CLI
passent `manual=None`.

### P1.5 — Les 9 outils obligatoires

*Testes independamment de la boucle.*

- [~] **FS** : `read_file(filepath, start_line, end_line)` (format `cat -n` :
      `"<line>: <content>"`), `edit_file(filepath, old_str, new_str)`
      (remplacement exact), `list_files(directory, pattern)`
- [~] **Recherche** (format commun `/abs/path.py:<line> <content>`) :
      `search_code`, `search_function_or_class_definition_in_code`,
      `find_references`
- [~] **Execution** : `run_tests()` (lance l'`eval_script`), `get_patch()` (git
      diff unifie), `run_command(command, workdir)`

  `[~]` sur les trois : ecrits et merges, mais **3 signatures sur 9 sont
  incompatibles** (`find_references`, `search_function_or_class_definition_in_code`,
  `run_command`) et le **comportement** de `run_tests` (lance `pytest`, pas
  l'`eval_script`) et de `get_patch` (sans `core.fileMode=false`) s'ecarte du
  sujet. Tableau dans la revue en tete. `run_tests()` reste appelable sans
  argument ; les 5 autres ont la bonne signature.
- [~] `mcp_tools_mbpp.py` et `mcp_tools_swebench.py` a la **racine** (merges) :
      le serveur SWE enregistre les 9 outils, le serveur MBPP **aucun**

La logique va dans `mcp_tools/` (`tools_fs`, `tools_search`, `tools_exec`) ; les
2 fichiers racine ne sont que des points d'entree fins, l'emplacement etant
impose.

- [ ] **`run_tests` MBPP** — exige par le § V.3 point 2, souvent oublie parce que
      les 9 outils sont annonces "in the context of SWE-bench". **Aucune
      signature ni format imposes**, donc liberte de conception et charge de la
      defendre. **A trancher avec P2** : le `run_tests()` du § V.5.3 lance
      l'`eval_script` du conteneur ; cote MBPP il n'y a pas d'`eval_script`, la
      specification ce sont les `test_list`. Meme nom, deux sources de verite —
      un outil parametre ou deux implementations ?

### P1.6 — Docker / SWE-bench

- [ ] **LA decision d'architecture** — elle change l'implementation des 9 outils
      en entier. Ce qui ne bouge pas dans les deux cas : le serveur MCP reste un
      processus distinct, le client reste dans le sandbox
  - **(a) sandbox + serveur MCP DANS le conteneur** : chemins locaux,
    implementation simple. Prix : installer `mcp`, `pydantic`... dans l'image,
    **dans l'environnement conda `testbed`**
  - **(b) sandbox sur l'hote, serveur MCP faisant le pont par `docker exec`** :
    l'image reste intacte, mais chaque outil devient un aller-retour
- [ ] Pull / run de l'image, montage de `${TESTBED_PATH}` si necessaire
- [ ] `git -c core.fileMode=false diff` pour `get_patch()`
- [ ] **Cleanup des containers** apres execution (exige)

### P1.7 — Tests de securite

`exam_sandbox.sh` : **tout** doit passer. Ecrire nos propres tests **avant**
l'eval.

- [ ] import, builtin, reseau, chemin, timeout, memoire, protocole MCP
- [ ] **Masquage d'un wrapper MCP** (`def run_tests(): ...` ecrase l'entree du
      dict `ns`). Decider : on laisse (le modele se sabote seul), on detecte, ou
      on refuse. Dans tous les cas, savoir le dire
- [ ] `KeyboardInterrupt` / `SystemExit` non avales — sous test pour ne pas
      regresser

---

## Personne 2 — tchemin : Agent & Intelligence

### P2.1 — Boucle agentique *(faite)*

Boucle Thought → Code → Observation complete, verifiee sur 15 taches MBPP
reelles et 2 modeles. `max_iterations` parametrable via `constants.Bench`.
Arret sur `final_answer()` (detecte par `is_final`/`answer` rendus par
`execute()` — un **fait d'execution**, jamais une relecture du source), sur
limite atteinte, ou sur erreur fatale (`Transient` → retry, `Permanent` →
abandon propre ; rien ne sort des deux familles, 16 cas parametres).
`max_tokens` de chaque requete derive du budget restant.

**Deux corrections issues de la mesure (2026-08-16), a savoir redire :**

- **Message d'observation.** Le rappel "aucun `final_answer` capture" n'existait
  que dans la branche "sortie vide" : un code qui affichait quelque chose
  recevait sa propre sortie sans un mot sur `final_answer`, et le modele
  concluait qu'il avait fini. Constate sur MBPP 453, **3 tours perdus**. Les deux
  faits se composent maintenant dans un seul message.
- **Comptabilite des etapes.** Une sortie par garde posterieure a une requete
  aboutie n'enregistrait pas son `StepMetrics`. Invariants tenus desormais : une
  etape par iteration, numerotation depuis 1 sans trou, totaux egaux a la somme
  des etapes, aucune etape avant la premiere requete.

- [x] **Consigne d'`assert` rendue dependante du bench** (2026-09-02). Le message
      *"Make SURE to make AND print the asserts"* etait en dur dans
      `observation()` et partait pour **les deux** benchmarks — cote SWE il
      reclamait des asserts dont le prompt ne parle jamais. Il est desormais
      ajoute seulement si `name_bench == BenchName.MBPP`
- [x] **Les `retries` d'un tour qui sort par une garde sont comptes** : depuis
      le 2026-10-01, `exit_on_guard()` enregistre le tour des qu'une requete est
      partie, retries compris (`llm_output` vide, puisque rien n'est revenu).
      Plus de `total_requests: 9` avec `steps: []`
- [x] **Une attente avant retry ne franchit plus la deadline** (2026-10-01).
      Constate en `run11` (MBPP 247) : requete coupee a son echeance (115 s)
      puis 5 s d'attente par defaut, sortie a **120,03 s → metriques
      invalides**. Deux corrections : sur le plafond de retries la boucle sort
      **sans dormir** (ce sommeil ne precedait qu'une sortie) ; une attente
      qui finirait apres `limite - MARGIN_EXECUTION_TIME` fait sortir tout de
      suite sur `Timeout limit exceeded`. Aucune requete perdue : dans les
      deux cas l'ancienne boucle sortait au tour suivant sans appeler.
      Rejoue en temps reel (limite ramenee a 12 s) : ancienne boucle 12,01 s
      (invalide), nouvelle 7,01 s
- [x] **La cause des retries est enregistree** (2026-10-01). En `run11`, trois
      taches sont sorties sur 5 retries sans qu'on puisse dire si c'etait 429,
      timeout ou 5xx. Desormais : `error` se termine par `; last LLM error:
      <message> (HTTP <code>)` quand le tour qui sort a vu un transient (oublie
      des qu'un tour aboutit), et chaque retry ecrit une ligne `LLM retry N on
      step S: <cause>; waiting X.Xs` sur **stderr** — archive par
      l'evaluation dans `stderr.log`. Rien dans `steps` : le schema de
      `StepMetrics` est impose par la moulinette
- [x] **La boucle verifie le `final_answer` MBPP contre `test_list`**
      (2026-10-01, `4c8d206`). La moulinette execute la chaine soumise
      **seule**, puis les tests ; la boucle fait pareil
      (`Loop.run_answer_tests()`, parametre `answer_tests`, que l'agent MBPP
      remplit avec `test_imports` puis `test_list`). Echec → refus, et
      l'observation donne l'erreur : un `assert` nu recoit son propre source
      comme message (`label_assert()`), donc le test qui casse est nomme.
      Borne par le temps restant, saute s'il n'en reste plus. Cause :
      `run12/451`, ou le bloc teste commencait par `import re` et la chaine
      soumise ne contenait que la fonction. **Rejeu des 45 soumissions
      reelles** de `run6/7/9/10/12` : 42 acceptees et validees par la
      moulinette, **0 refus a tort**, 1 vrai refus (451), 2 acceptees a tort
      (MBPP 400, le test cache que la boucle ne voit pas)
- [x] **L'entree cumulee est verifiee avant l'envoi** (2026-10-02,
      `c21b0ce`). Constate sur la campagne `run15`-`run24` : **5 metriques
      INVALID**, toutes pour une entree cumulee de 6 163 a 7 513 tokens sur
      6 000. Le controle n'avait lieu qu'apres la reponse : la requete qui
      debordait etait deja partie et comptee. Desormais
      `Loop.estimate_next_input()` estime la requete suivante — compte exact
      du fournisseur pour le prompt precedent (`last_prompt_tokens`), plus les
      caracteres ajoutes depuis divises par `ESTIMATED_CHARS_PER_TOKEN = 2.5`
      (`constants.py`) — et la boucle sort sur `Input token limit exceeded:
      the next request (~N tokens) would go over` sans rien envoyer. Le 2,5 est
      pris sous les ratios mesures sur 55 tours de la campagne (mediane 3,44,
      10e centile 2,89, minimum 2,25) : l'estimation se trompe vers le haut.
      Le controle apres reponse reste en filet. Prix assume : une tache peut
      s'arreter alors que la requete aurait tenu (2 fois sur 20 au rejeu, aux
      tours 4 et 5). En SWE (300k), la garde ne joue qu'en fin de tache
- [x] **Le refus d'un `final_answer` MBPP invalide dit quoi corriger**
      (2026-10-02, `c21b0ce`). Il disait « NOT a valid Python expression »,
      sans l'erreur ni le remede. Il donne maintenant `SyntaxError: <msg>
      (line L, column C)` et la consigne : `for`, `if` et `while` ne suivent
      pas un `;`, ecrire la fonction sur plusieurs lignes dans
      `final_answer("""...""")`. Cause : 5 des 9 echecs de
      `codestral-2508` (P2.6), qui recommencait la meme erreur jusqu'au
      plafond de sortie.
      12 tests ajoutes pour ces deux points, dont 10 echouent sur l'ancien
      `loop.py`

### P2.2 — Extraction de code *(faite)*

Blocs ` ```python ... ``` ` + `<end_code>`. Retour a 3 cles : `code`, `found`,
`format` (`"python"` si le bloc parse, `""` sinon, `None` si aucun bloc).
Validation par `ast.parse` sans exception : une sortie tronquee ressort en
`found=True` / `format=""`, le code invalide est conserve pour etre renvoye au
modele en observation.

**Decision du 2026-08-12 : un seul format supporte.** XML `<invoke>`, JSON/Hermes
et ReAct sont **abandonnes, pas reportes**. Quatre raisons :

1. Le prompt systeme impose un format unique. Parser quatre formats quand on n'en
   demande qu'un est une robustesse decorative.
2. Deux des trois etaient **inatteignables par construction** : `</tool_call>` et
   `<invoke>` sont dans `LLM_STOP_SEQUENCE`, la generation s'arrete avant.
3. Le troisieme etait **nuisible** : `Action:` matchait n'importe ou dans la prose
   et faisait tomber une reponse valide.
4. La robustesse au format passe par la boucle : format non reconnu →
   observation → nouvelle iteration.

→ Consequence traitee : `LLM_START_SEQUENCE` / `LLM_STOP_SEQUENCE` ne contiennent
plus que ` ```python ` et `<end_code>`.

### P2.3 — Couche LLM *(faite)*

`LLMClient` est le **seul** module qui importe `httpx`, injecte dans `Loop`, donc
testable sans reseau. **`core/llm/provider.py`** : le client ne connait plus la
*forme* des reponses — chaque champ (`choices`, `message`, `content`, `usage`,
`reasoning`, `error`, `finish_reason`, en-tetes de delai) est designe par un nom
lu dans `configs/models.json`. Brancher un second fournisseur devient une entree
JSON, pas une branche `if`. Quatre declares : `openrouter`, `groq`, `nvidia`,
`mistral` (les deux derniers branches sans une ligne de code, 2026-10-01 et
2026-10-02). Un reglage propre a un modele (couper le raisonnement) passe par
`extra_body`, fusionne dans le corps de la requete (P2.5 bis). Depuis le
2026-10-02, **repli entre fournisseurs** : une chaine de clients par
benchmark (`FallbackClient`, voir « Repli de provider » ci-dessous).

Multi-tokens + **rotation** : 429 fait tourner sans condamner, 402 marque la cle
epuisee, vivier vide remonte en `Permanent`. Cles depuis env vars uniquement
(`load_dotenv()` sans test de retour — le fichier est un confort local, la seule
question posee est `os.getenv`). Erreurs API traduites en exceptions typees
(champ `error` en HTTP 200, `choices` vide, `content` null des modeles de
raisonnement, `usage` absent, corps non-JSON, timeout, erreur de transport).

**`core/api_key.py`.** Une cle est un objet, pas une chaine. Trois raisons : une
`str` passee au lieu d'une liste etait indexee **caractere par caractere** (chaque
requete partait avec `Bearer c` → 401, diagnostic impossible) ; marquer une cle
epuisee plutot que la supprimer garde le vivier a taille stable, donc plus de
rattrapage d'indice ; et `__repr__` ne divulgue rien.

**Echeance reelle sur les appels.** Le `timeout` de `httpx` est **par phase
d'E/S, pas une duree totale** : mesure, un serveur qui envoie un octet par
seconde traverse un `timeout=2` pendant 6 s. En reel, un appel a dure 98 s sous
un plafond de 30 s et une tache MBPP a fini a 135,8 s → `Metrics valid: NO`.
L'appel part maintenant dans un `threading.Thread(daemon=True)` + `join(timeout=)`.
On n'interrompt pas le thread — impossible en Python — on l'**abandonne** ; le
drapeau `daemon` empeche l'interpreteur de l'attendre a la sortie (8,65 s contre
3,47 s sans). L'exception du thread est relevee **dans le meme `try`**, sinon les
gestionnaires `httpx.*` ne voient plus rien passer. Le `timeout=` de `httpx` est
conserve **en plus** : il coupe les serveurs muets, l'echeance borne les lents. Depuis le 2026-10-02,
l'echeance depend du benchmark (`Bench.llm_timeout`) : 30 s pour MBPP, 60 s
pour SWE (« Prochaines actions », 4 ter).

**Recul entre deux tentatives (2026-08-22).** Trois pieces : `Provider.get_retry_after()`
lit `X-RateLimit-Reset` — un **instant** epoch en millisecondes, pas une duree —
et le convertit (format et echelle de chaque en-tete declares dans le JSON) ;
`APIKey` porte un `next_retry_time` ; `get_next_api_key()` refuse toute clef dont
le delai depasse le budget de la tache, la condamne, et recommence. Le piege
etait dans l'ordre des tests : tant que le delai n'etait verifie que sur le
candidat **immediat**, une clef atteinte en sautant une morte passait sans
controle — avec 4 clefs, deux n'etaient jamais examinees.

**Reponse sans `content` : reprise depuis `reasoning` (2026-10-03, non
commite).** Sonde du jour sur Groq `gpt-oss-120b`, 14 prompts MBPP avec le
vrai payload (`stop: ["<end_code>"]`, `max_tokens: 1500`) : **6 reponses sans
`content`**.

| Cas | Nombre | Ce que porte `reasoning` |
|---|---|---|
| reponse entiere dans `reasoning` | 1 (MBPP 108) | Thought + bloc de code + `final_answer` |
| coupee par la sequence d'arret | 4 (94, 305, 457, 451) | reflexion arretee net : « We must end code with », « Use », « Ensure » |
| plafond de sortie | 1 (462) | 1 500 tokens de reflexion, pas de code |

Le client reprend donc `reasoning` **seulement s'il porte un bloc de code
ferme** (`reasoning_holds_code()`, motif partage avec l'extraction dans
`constants.CODE_BLOCK_PATTERN`) ; sinon, retry comme avant, avec un message
plus precis (« …nor a code block in its reasoning »). La reprise est signalee
sur stderr (« LLM content empty on step S: answer taken from the
reasoning ») ; le texte repris devient le message assistant, `llm_output` ne
le double pas. 10 tests (8 client, 2 boucle), mutations detectees. Rejoue sur
les 6 reponses reelles : seule MBPP 108 est reprise.

- [ ] **La vraie cause est la sequence d'arret** (4 cas sur 6) : en
      raisonnant sur le format, le modele ecrit `<end_code>` dans son
      raisonnement, et le fournisseur coupe avant la reponse. Piste : un
      reglage par modele dans `models.json` pour ne pas envoyer `stop` a
      `gpt-oss`, l'extraction ne gardant que le premier bloc. Risque : une
      « Observation » inventee apres le code, donc des tokens de sortie. A
      tester sur la meme sonde avant de **decider**

**Tokens des reponses rejetees (2026-10-03, non commite).** Une reponse
HTTP 200 rejetee par le client (`content` vide sans code, `message` absent,
schema invalide) avait ete facturee, mais ses tokens n'etaient comptes nulle
part : la sonde a vu MBPP 462 bruler 1 500 tokens de sortie dans une reponse
vide. Les erreurs portent maintenant `input_tokens` / `output_tokens` (lus
dans `usage`, 0 si absents ou non entiers), et la boucle les ajoute aux
totaux **et a l'etape du tour** (`turn_input_tokens` /
`turn_output_tokens`, remis a zero en fin d'etape et non plus a chaque
essai) : les totaux restent la somme des etapes, comme le definit le schema.
**Effet voulu** : les plafonds voient la vraie depense ; une reponse vide de
1 500 tokens termine la tache sur « Output token limit exceeded » au lieu de
relancer. Restent a 0, faute d'information : erreurs HTTP, delais depasses,
erreurs dans le corps d'un 200 (OpenRouter). 8 tests, 3 mutations
detectees, 493 tests verts.

#### Repli de provider — ce que dit le sujet (releve du 2026-09-02)

§ V.6.1 : *"Ensure your implementation supports multiple API keys per provider
**and consider implementing provider fallback**."* Le contraste des verbes est
tout le message :

| Mecanisme | Formulation | Statut |
|---|---|---|
| Plusieurs cles par provider | *"multi-token management is **mandatory**"*, *"token rotation **must** be implemented"* | obligatoire — **fait** |
| Repli de provider | *"**consider** implementing"* | suggere — **fait le 2026-10-02** |

Trois contraintes tranchent a sa place :

1. § IV.1 : *"All errors must be handled gracefully — crashes during evaluation
   will result in failure."* Sortir en notifiant est acceptable, **une stack
   trace ne l'est pas**.
2. `SolutionOutput.error` existe precisement pour dire "j'ai echoue, voila
   pourquoi". Le chemin d'echec attendu n'est ni un crash ni un silence : un
   `solution.json` valide, `success=false`, `error` rempli, `steps` accumules.
3. `StepMetrics` impose `api_url` et `model_name` **par step** : un repli est
   legal a condition que chaque step porte l'endpoint reellement utilise.

→ **La politique retenue** (a defendre telle quelle) : ce n'est pas « sortir ou
switcher » mais « switcher **puis** sortir ». Panne de **configuration** avant
tout appel (URL inconnue, cle absente, modele vide) → il n'y a rien sur quoi se
replier, sortie immediate avec message sur `stderr`. Se replier ici masquerait
une erreur de config, et `--provider-url` est un **argument explicite de la
moulinette** : y substituer autre chose serait desobeir. Panne d'**execution** en
cours de tache (429, 503, timeout) → escalade : retry avec backoff, puis rotation
de cles, puis repli de provider s'il est configure, puis **echec gracieux**.

- [x] **Repli entre providers — fait le 2026-10-02** (`19e17be`). La
      politique ci-dessus, telle quelle : erreur de config au demarrage →
      sortie ; panne en cours de tache → retries, rotation de cles, **puis
      modele suivant**, puis echec gracieux. En cinq pieces :
  - **`configs/fallback.json`** : une liste ordonnee par benchmark, chaque
    entree = un fournisseur **nomme** comme dans `models.json` (pas d'URL,
    donc pas le piege de l'egalite stricte) + un modele. Fichier a part :
    les cles de premier niveau de `models.json` sont des fournisseurs,
    parcourus par `find_provider_by_url` et par les tests. Valide par
    `FallbackConfig` / `FallbackTarget` (`config_models.py`), en
    `extra="forbid"`. Ordre choisi d'apres la campagne MBPP (P2.6) : MBPP =
    Groq `gpt-oss-120b`, `ministral-14b-2512`, `nemotron-3-super` ; SWE =
    `nemotron-3-super`, `ministral-14b-2512` (Groq exclu, 413)
  - **`core/llm/fallback.py`, `FallbackClient`** : enveloppe une liste de
    `LLMClient` et presente a la boucle la meme interface
    (`get_llm_reponse`, `url`, `model_name` du client en cours). Chaque step
    porte donc le modele qui a **reellement** repondu (exigence de
    `StepMetrics`). `fall_back()` passe au suivant, jamais de retour en
    arriere. `LLMClient` reste mono-fournisseur avec sa rotation de cles
  - **`get_fallback_clients()`** (`agent_cli_helper.py`) : saute le modele
    demande lui-meme et **tout fournisseur sans cle dans l'environnement**
    (le `.env` decide quels replis existent ; un `.env` d'evaluation avec une
    seule cle ne doit pas faire planter le demarrage). Fournisseur inconnu
    ou fichier invalide → erreur au demarrage ; fichier absent → pas de
    repli. `make_llm_client()` factorise la construction d'un client, que
    les deux CLI dupliquaient
  - **Les CLI** gardent `self.llm_client` (le modele demande) et passent a
    la boucle `self.client = FallbackClient([llm_client, *replis])`
  - **La boucle decide *quand*, la chaine *vers quoi*.** Erreur permanente
    → bascule immediate, sans attente, la tentative comptant comme retry.
    Plafond de transients atteint → bascule au lieu de sortir. Chaque
    tentative HTTP passe par la boucle, donc reste comptee dans
    `total_requests` et bornee par le budget de temps : une chaine qui
    retenterait seule cacherait des requetes. **Deux compteurs** : `retries`
    reste la metrique du step (toutes les tentatives ratees du tour),
    `backend_retries` est le plafond **par modele**, remis a 0 a chaque
    bascule. Une ligne stderr par bascule : `LLM fallback on step S:
    <cause>; switching to <modele> at <url>`
  - Les deux pieges notes ici avant : le budget de tokens **reste cumule**
    sur la tache (teste : 900 + 1 200 sur deux modeles) ; la verbosite d'un
    modele de repli se regle dans la config (NVIDIA sans raisonnement,
    `gpt-oss-120b` a 534 tokens de sortie en moyenne sur MBPP)

  **Verifie** : 34 tests ajoutes (`tests/test_fallback.py`,
  `tests/test_agent_cli.py`), 9 echouent sur l'ancienne boucle ; les 391
  anciens passent sans changement (seuls les faux clients ont gagne
  `fall_back()`) : **sans repli disponible, comportement identique**. Deux
  runs reels valides par la moulinette (PASSED, VALID) : Groq
  `openai/does-not-exist` → 404 → Groq `gpt-oss-120b`, MBPP 80 ; NVIDIA
  `nvidia/does-not-exist` → 404 → Groq `gpt-oss-120b`, **4 `content` vides
  puis succes au 5e essai**, MBPP 65 — avec un compteur unique par tour, la
  404 + 4 vides auraient atteint le plafond et abandonne la tache
- [ ] **A decider : quelles erreurs declenchent le repli.** Aujourd'hui
      toutes les permanentes, 404 (modele inconnu) et 401 (cle refusee)
      comprises : un mauvais `--model-name` est remplace en silence par un
      autre modele (seul le step et la ligne stderr le disent). Les exclure
      si on prefere une erreur franche
- [ ] **A decider : l'ordre des listes de repli** (Mistral valide le
      2026-10-02 : sa presence n'est plus en question)
- [ ] **A decider : le repli en milieu de tache.** `moulinette_eval display`
      (l'outil d'inspection du correcteur) affiche en rouge `WARN: Multiple
      model_names across steps` des que les steps d'un `solution.json`
      portent plusieurs modeles (`moulinette/__main__.py:426-429`). Sans
      effet sur le verdict de `validate`, mais visible en soutenance. Soit
      l'assumer et l'expliquer, soit ne replier **qu'avant la premiere
      reponse obtenue** (tous les steps portent alors le meme modele, au
      prix de moins de robustesse en cours de tache)
- [ ] Le repli SWE n'a pas tourne en reel (outils non branches)
- [ ] Cosmetique : la cause d'une 404 NVIDIA s'ecrit sur deux lignes dans
      stderr (message de `httpx` repris tel quel)

#### Limite de tokens par minute — verifiee avant l'envoi (2026-10-02)

**Pourquoi.** `codestral` peut etre payant : ne pas depasser ce que le compte
autorise. **Ou est la limite** (verifie sur une vraie reponse) : **pas dans le
JSON**, qui ne donne que la consommation de la requete (`usage` :
`prompt_tokens`, `completion_tokens`, `total_tokens`, `service_tier:
"standard"`), mais dans les **en-tetes HTTP** :
`x-ratelimit-limit-tokens-minute: 625000`,
`x-ratelimit-remaining-tokens-minute`, `x-ratelimit-tokens-query-cost`, et
les memes par requete (`-req-minute`). C'est une limite **par minute** ;
**aucune reponse ne donne le credit mensuel restant ni un cout**.

- [x] **Fait (`36e071b`)**, en quatre pieces :
  - `configs/models.json` : bloc facultatif `token_rate_limit` du fournisseur
    (nom des deux en-tetes, fenetre de 60 s), declare **pour `mistral`
    seulement** ; valide par `TokenRateLimitConfig` (`extra="forbid"`,
    fenetre > 0). Sans ce bloc, rien ne change pour un fournisseur
  - `Provider.get_token_rate(headers)` → `(limite, restant)`, `None` si un
    en-tete manque ou n'est pas un nombre (casse indifferente)
  - `APIKey.set_token_budget()` / `get_token_budget()` : budget memorise
    **par cle** (limite, restant, heure de la mesure) — les quotas sont
    attaches aux cles
  - `LLMClient` : `record_token_rate()` apres chaque reponse reussie ;
    `check_token_rate()` **avant** l'envoi, sur un cout estime par exces
    (`estimate_cost()` : prompt a `ESTIMATED_CHARS_PER_TOKEN` + `max_tokens`
    entier). Budget inconnu ou fenetre ecoulee → la requete part ; elle tient
    → elle part ; sinon → **cle suivante** qui a assez ; aucune →
    **rien n'est envoye**, `Transient` avec l'attente jusqu'a la fin de
    fenetre la plus proche (la boucle la traite comme un 429) ; requete
    plus grosse que la limite elle-meme → `Permanent`, donc repli sur le
    modele suivant
- Effet : nul sur MBPP (7 500 tokens au plus par tache contre 625k/min) ;
  peut jouer en SWE (`codestral` a ~2 s par requete de 56k ≈ 1,7M tokens/min
  s'il enchainait)
- **Verifie** : 15 tests (`tests/test_llm_client.py`), dont 6 echouent avec
  le controle desactive ; 440 tests verts, `ruff` propre. En reel contre
  Mistral : budget lu `limit=625000`, `remaining=624991` ; restant force a
  50 → requete de ~103 tokens retenue, attente 60 s, **0 envoi HTTP** ;
  requete de ~640 100 tokens → `Permanent`, **0 envoi HTTP**
- [ ] **Ne protege pas du « payant »** : le credit mensuel n'est expose
      nulle part. Ce qui borne deja la depense : les plafonds par tache
      (MBPP 6 000 / 1 500, SWE 300 000 / 10 000) et un compte **sans carte**,
      qui ne peut pas etre facture (avec carte : interdit par le sujet). Un
      plafond mensuel demanderait de compter nous-memes la consommation
      entre les runs
- [ ] Plusieurs cles Mistral d'un meme espace de travail partagent sans doute
      le quota : changer de cle n'y aidera pas, le 429 classique prendra le
      relais
- [ ] Non couverts : la limite par requete (`x-ratelimit-*-req-minute`), et
      Groq, qui a des en-tetes du meme genre (8 000 tokens/min)

#### Ce que dit le sujet du payant (relu le 2026-10-02)

- § V.6, p. 28 : *« You are free to use other providers as long as your
  system complies with the project requirements. (it must be free, must
  support multiple API tokens per provider) »*
- § V.6.1, « Important », p. 29 : *« The entire solution must rely
  exclusively on free tiers. »* — *« No paid plans, purchased credits, or
  billing-enabled accounts are allowed. »* — *« The project must be fully
  executable using only free quotas at evaluation time. »*
- Meme section : Mistral AI figure parmi les *« Cloud providers with free
  access »* ; la liste est *« not exhaustive and not contractual »*
  (Together y est, alors qu'il exige aujourd'hui un achat)
- Chap. VI, p. 33 : `./exam_TYPE.sh --student-path … --moulinette-path …
  --env-file /path/to/.env`, **sans argument de modele** ; *« API keys and
  configuration are provided via a .env file »*. Les scripts d'examen ne
  sont pas dans `moulinette/`

**Lecture.** Les trois interdits visent d'abord le **compte** : un modele
gratuit appele avec la cle d'un compte qui a une carte enfreint la regle.
Le code ne peut pas le verifier (sauf OpenRouter, via `/key` →
`is_free_tier`) : c'est une discipline sur les cles du `.env`.

| Risque | Couvert ? |
|---|---|
| Modele payant non declare | **Oui** : refuse au demarrage (`c7727cc`) |
| Repli vers un modele payant | **Oui** : les replis doivent etre declares |
| Modele payant **declare** dans `models.json` | **Non** — aujourd'hui aucun (OpenRouter : variantes `:free` seulement) |
| Cle d'un compte avec facturation | **Non**, invisible pour le code |
| Credits gratuits Mistral epuises | En partie : plafonds par tache, compte sans carte non facturable |
| Rester dans les quotas gratuits a l'evaluation | En partie : rotation, repli, limite par minute Mistral |

- [ ] Un test qui exige le suffixe `:free` pour toute entree OpenRouter de
      `models.json` (protege le depot d'un ajout par erreur)
- [ ] Optionnel : verifier au demarrage, pour OpenRouter, `is_free_tier` via
      `/key` (une requete de plus par run)
- [ ] **Le fournisseur est retrouve par egalite stricte d'URL**
      (`find_provider_by_url`) : un `/` final de trop dans `--provider-url` et
      rien ne matche. Normaliser, ou chercher par nom

#### Modeles gratuits — releve du 2026-09-02 (les deux fournisseurs)

> **A lire avec la section suivante.** Ce releve sonde avec une requete
> **triviale** : sa colonne « bloc : oui » ne prevaut pas sous le vrai prompt
> MBPP. Voir *« Modeles OpenRouter gratuits et utilisables »* (2026-09-03).

Sonde : meme requete pour tous (une fonction triviale, bloc `python` demande),
`max_tokens=1500`. Methode pour relister OpenRouter :
`GET https://openrouter.ai/api/v1/models` (public, sans auth), garder
`pricing.prompt` **et** `pricing.completion` a `"0"` — filtrer sur le prix, pas
sur le suffixe `:free`. Cote Groq : `GET /openai/v1/models` avec la cle (et un
`User-Agent`, sinon 403).

**OpenRouter : 21 gratuits sur 423, dont 17 testables** (retires : 2 modeles
audio `lyria`, le classifieur `content-safety`, et `openrouter/free` qui est un
routeur — inutilisable pour un benchmark reproductible).

| Modele | out | raisonnement | temps | bloc |
|---|---|---|---|---|
| `liquid/lfm-2.5-2.6b:free` | 166 | 147 | 1,9 s | oui |
| `inclusionai/ling-3.0-flash-fin:free` | 45 | 33 | 2,0 s | oui |
| `poolside/laguna-xs-2.1:free` | 414 | 394 | 2,9 s | oui |
| `nvidia/nemotron-3-super-120b-a12b:free` | 61 | 47 | 4,4 s | oui |
| `dots-studio/dots-3-note-preview:free` | 382 | 403 | 5,1 s | oui |
| `minimax/minimax-m2.7:free` | 191 | 195 | 6,5 s | oui |
| `minimax/minimax-m3:free` | 18 | 0 | 8,6 s | oui |
| `nvidia/nemotron-3.5-lightning:free` | 358 | 353 | 10,7 s | oui |
| `cohere/north-mini-code:free` | 294 | 312 | 13,1 s | oui |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | 227 | 240 | **27,2 s** | oui |

**7 injoignables** le meme jour : `google/gemma-4-31b-it:free` et
`gemma-4-26b-a4b-it:free`, `z-ai/glm-5.2:free`, `poolside/laguna-s-2.1:free`
(« Provider returned error »), `nvidia/nemotron-3-nano-omni-...-reasoning:free`
(`ResourceExhausted`), et les deux `thinkingmachines/inkling*:free`
(« only available on agentic harnesses »). **Etre au catalogue ne veut pas dire
etre joignable** : un releve par le prix ne suffit pas, il faut sonder.

**Groq : 14 au catalogue, 8 testables** (retires : 2 `whisper`, 2 `orpheus`
audio, 2 `prompt-guard` classifieurs).

| Modele | out | raisonnement | temps | bloc |
|---|---|---|---|---|
| `qwen/qwen3.8-27b` | 20 | 0 | **0,1 s** | oui |
| `openai/gpt-oss-20b` | 111 | 83 | 0,3 s | oui |
| `openai/gpt-oss-120b` | 80 | 44 | 0,4 s | oui |
| `openai/gpt-oss-safeguard-20b` | 58 | 32 | 0,4 s | oui |
| `qwen/qwen3.6-27b` | 231 | 0 | 0,6 s | oui |
| `groq/compound-mini` | 79 | 0 | 0,7 s | oui |
| `groq/compound` | 814 | 0 | 4,7 s | oui |
| `allam-2-7b` | 18 | 0 | 0,1 s | **NON** |

**Groq est un ordre de grandeur plus rapide** — 0,1 a 4,7 s contre 1,9 a 27,2 s.
Sur MBPP, ou 120 s couvrent 10 iterations, c'est decisif : `LLM_TIMEOUT_SECONDS`
(aujourd'hui `MBPP.llm_timeout`) vaut 30 s, donc un modele a 27 s comme `nemotron-3-ultra` est hors-jeu en
pratique (mesure a **39,8 s** le meme jour sur une autre requete : c'est lui qui
a fait echouer le run pilote de `run5` a 0 iteration).

**Nuance a savoir dire en soutenance :** chez OpenRouter la gratuite est une
propriete du **modele** (`pricing` a 0, `usage.cost` verifiable a chaque
reponse) ; chez Groq c'est une propriete du **compte** — le free tier, avec ses
quotas. Groq ne renvoie aucun champ `cost`, donc `usage.cost == 0` n'est pas
verifiable cote reponse. La preuve de gratuite y est l'absence de facturation
activee sur le compte.

**Quotas mesures (2026-09-02) :**

| | OpenRouter | Groq |
|---|---|---|
| Requetes | 50 / jour / compte (`:free`) | 1000 / jour |
| Tokens | — | **8000 / minute** |
| Reset | 02:00 locales | `x-ratelimit-reset-*`, en duree |
| Cles dans `.env` | 2 (**1** au 2026-10-01) | **1** |

Chez Groq la contrainte mordante n'est pas le nombre de requetes mais les
**8000 tokens par minute** : une tache MBPP consomme ~750 en entree et ~500 en
sortie par tour, soit 5 a 6 requetes par minute au plus. Et il n'y a **qu'une
seule cle Groq** : la rotation multi-cles, obligatoire au sujet, n'a rien a
faire tourner de ce cote.

- [ ] **`get_retry_after` ne sait pas lire les en-tetes de Groq.**
      `provider.py:32-39` teste `retry_after_value.isdigit()`, or Groq renvoie
      `x-ratelimit-reset-tokens: 30.795s` et
      `x-ratelimit-reset-requests: 5m45.6s`. Verifie : les deux rendent `None`.
      Un `Retry-After: 1.5` (decimal simple) est rejete de la meme facon —
      `isdigit()` n'accepte que des entiers. Les trois entrees declarees pour
      Groq dans `configs/models.json` sont donc **decoratives** : le delai
      retombe toujours sur le plancher du bench. Il faut un format de duree qui
      accepte le decimal et le suffixe (`s`, `m`), sinon la rotation de cles
      Groq travaille a l'aveugle
- [ ] Un 429 `free-models-per-day` (OpenRouter) n'est **pas** un rate limit
      passager : 8 h d'attente. La boucle le traite comme transitoire, correct
      tant qu'une cle survit ; quand toutes y sont, la tache brule son budget.
      Le corps porte `limit_source`, de quoi distinguer « ralentis » de
      « reviens demain »
- [ ] **Ajouter des cles Groq** : une seule aujourd'hui, contre deux chez
      OpenRouter. Le sujet exige le multi-token *par fournisseur*

#### Modeles OpenRouter gratuits **et utilisables** — releve du 2026-09-03

Le releve du 2026-09-02 ci-dessus sonde avec une requete **triviale** et conclut
a 10 modeles joignables. C'est trompeur : sous le **vrai prompt systeme MBPP**
(~800 tokens d'entree, `max_tokens=1500`, meme tache pour tous), la plupart
s'effondrent. « Gratuit » et « au catalogue » ne disent rien ; « utilisable »
se mesure.

**Les quatre conditions cumulatives d'utilisabilite sur MBPP :**

1. **Joignable** — pas de 403 / 502 structurel.
2. **Emet un bloc ` ```python ` dans `content`** — et non la totalite du budget
   dans le canal `reasoning`, qui laisse `content: null`.
3. **Latence < 30 s** par appel (`LLM_TIMEOUT_SECONDS` a l'epoque,
   `MBPP.llm_timeout` depuis le 2026-10-02).
4. **Sortie < 1500 tokens** (`MBPP.output_max_token`).

> **Fiabilite de ce releve — a lire avant de s'en servir.** La sonde de
> screening envoyait `content: p.prompt`, or `Prompt.prompt` est **deja une
> liste de messages** : la charge utile etait malformee. OpenRouter l'a
> acceptee sans broncher (Groq, lui, rend un 400 — c'est comme ca que le bug a
> ete trouve, le 2026-09-03). **Ce qui reste sur : `run8` (9/10) et les trois
> pilotes**, tous passes par `agent_mbpp` et donc par la vraie charge utile —
> soit `minimax-m3` (utilisable), `minimax-m2.7` (`Timeout limit exceeded`,
> 0 iteration) et `ling-3.0-flash-fin` (`LLM max retries exceeded`). **A
> reverifier : les 6 autres** (`gemma-4-31b-it`, `glm-5.2`, `lfm-2.5-2.6b`,
> `dots-3-note-preview`, `north-mini-code`, `nemotron-nano-...-reasoning`),
> classes sur la seule foi de la sonde. Le quota jour etait epuise au moment
> de la decouverte, d'ou le report.

Le point 2 est le discriminant, et il est contre-intuitif : **les 18 modeles
`:free` du catalogue exposent tous le parametre `reasoning`.** L'etiquette ne
trie rien. Ce qui trie, c'est `usage.completion_tokens_details.reasoning_tokens`
dans la reponse — un modele qui deliberate dans un canal separe brule le plafond
de 1500 avant d'ecrire la moindre ligne de code.

**Utilisables — les trois qui passent les quatre conditions :**

| Modele `:free` | latence | out | dont reasoning | note |
|---|---|---|---|---|
| `minimax/minimax-m3` | 5,4–11,6 s | 318–1408 | **0** | **valide sur 10 taches : `run8`, 9/10** — **plus gratuit au 2026-10-01** |
| `google/gemma-4-31b-it` | 4,9–7,8 s | 159–254 | **0** | non teste en campagne |
| `minimax/minimax-m2.7` | 17–23 s | 782–937 | 269–459 | **marge nulle**, voir plus bas |

`minimax-m3` est le seul verifie sur une campagne complete. `gemma-4-31b-it`
a le meme profil sain (`reasoning_tokens: 0`, bloc emis, rapide) mais n'a
jamais tourne 10 taches. `m2.7` est **a la limite** : il tient sur une tache
courte, mais le pilote sur MBPP 160 a depasse les 30 s a chaque appel — 4
tentatives, **0 iteration**, `Timeout limit exceeded` a 120 s, exactement
l'echec de `run5`.

**Inutilisables — le canal `reasoning` mange le plafond de sortie :**

| Modele `:free` | out | dont reasoning | `content` |
|---|---|---|---|
| `liquid/lfm-2.5-2.6b` | 1500 | 1498 | **vide** |
| `z-ai/glm-5.2` | 1500 | 1459 | tronque (150 car.) |
| `dots-studio/dots-3-note-preview` | 1500 | 1408 | **vide** |
| `cohere/north-mini-code` | 1500 | 1350 | **null** |
| `inclusionai/ling-3.0-flash-fin` | 1500 | 1094–1500 | **vide** |

Tous finissent en `finish_reason: length`. La boucle n'a rien a extraire, part
en retry, et sort sur `LLM max retries exceeded (5)` — verifie en pilote sur
`ling-3.0-flash-fin`. **Ce sont les modeles que le releve du 2026-09-02
classait « bloc : oui »** : sur une question triviale ils repondent, sur le
prompt MBPP ils n'y arrivent plus.

**Inutilisables — trop lents pour l'echeance de 30 s :**

| Modele `:free` | latence | out | note |
|---|---|---|---|
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | **55–63 s** | 2763–2897 | + `502 ResourceExhausted (16/16)` sur 2 appels sur 4 |
| `nvidia/nemotron-3-ultra-550b-a55b` | **27–40 s** | — | deja identifie comme la cause de `run5` |

**Structurellement hors-jeu :**

- `thinkingmachines/inkling` et `inkling-small` — **403 permanent**,
  « only available on agentic harnesses ». Jamais appelables via l'API.
- `nvidia/nemotron-3.5-content-safety` — classifieur, pas un generateur (400).
- Les 2 `lyria` (audio) et `openrouter/free` (routeur non reproductible),
  deja ecartes au releve precedent.

**Non conclus** (le quota jour a saute pendant le releve, voir ci-dessous) :
`nvidia/nemotron-3.5-lightning`, `poolside/laguna-s-2.1`, `laguna-xs-2.1`,
`google/gemma-4-26b-a4b-it`, `nvidia/nemotron-3-super-120b-a12b`. Leurs 429 ne
prouvent **rien** sur eux — c'est notre compte qui etait a sec, pas eux. A
resonder. `nemotron-3-super-120b` a par ailleurs deja tourne une campagne
(`run5`, 4/10).

**Le quota est la contrainte qui structure toute mesure OpenRouter.**
Confirme le 2026-09-03 sur les deux cles :

```
x-ratelimit-limit: 50        x-ratelimit-remaining: 0
limit_source: openrouter_free_tier_daily
"Rate limit exceeded: free-models-per-day. Add 10 credits to unlock 1000"
reset: 2026-09-04T02:00:00+02:00
```

**50 requetes / jour / compte**, et les deux cles du `.env` tapent dans le
**meme seau** — la rotation multi-cles n'y gagne rien, contrairement a ce
qu'on pourrait croire. Une campagne de 10 taches en consomme ~29 (`run8`) :
**une seule campagne et demie par jour**, sondages compris. Il y a en plus un
plafond court de ~20 req/min sur les modeles gratuits : un balayage de 36
appels d'affilee part integralement en 429 (constate).

→ Consequence pratique : **sonder avant de lancer**, jamais l'inverse. Trois
pilotes d'une tache (~3 requetes) coutent moins cher qu'une campagne a
0 iteration (~29 requetes brulees). C'est ce qui a sauve `run8`.

- [ ] **Resonder les 6 modeles marques « a reverifier » ci-dessus** avec la
      charge utile corrigee (`list(p.prompt) + [{"role": "user", ...}]`), plus
      les 5 « non conclus » — soit 11 en tout, apres le reset du 2026-09-04
- [ ] Verifier `google/gemma-4-31b-it:free` sur une campagne complete : c'est
      le seul second candidat au profil sain, et il est plus rapide que `m3`
- [ ] Le `limit_source: openrouter_free_tier_daily` distingue « ralentis » de
      « reviens demain ». La boucle traite les deux comme transitoires — deja
      note plus haut, ce releve en donne la trace exacte

#### Modeles Groq gratuits **et utilisables** — releve du 2026-09-03

Meme methode que la section OpenRouter ci-dessus : **vrai prompt systeme MBPP**,
`max_tokens=1500`, meme tache pour tous, 2 appels par modele, espaces de 22 s
pour ne pas saturer le seau TPM.

Chez Groq la gratuite est une propriete du **compte** (free tier), pas du
modele : les 14 entrees du catalogue sont toutes accessibles avec la cle. La
question « lequel est gratuit » n'a donc pas de sens ici — **seule celle de
l'utilisabilite en a une.**

**Les conditions d'utilisabilite, avec une de plus que chez OpenRouter :**

1. **Ne pas rendre 400** sur le prompt MBPP.
2. **Emet un bloc ` ```python `.**
3. **Sortie < 1500 tokens** (`MBPP.output_max_token`).
4. **Entree < 6000 tokens** (`MBPP.input_max_token`) — c'est ce critere,
   inoffensif chez OpenRouter, qui elimine la moitie du catalogue Groq.
5. La latence n'est jamais un probleme : **0,5 a 4,0 s**, contre 30 s
   d'echeance. Aucun modele Groq n'approche la limite.

**Utilisables — les trois qui passent :**

| Modele | latence | in | out | note |
|---|---|---|---|---|
| `openai/gpt-oss-120b` | 0,67–0,80 s | 933 | 191–250 | **18/20 sur `run6`+`run7`** (19/20 avant la revalidation du 2026-10-02) — la reference |
| `qwen/qwen3.8-27b` | 0,66–2,08 s | 956 | 243–933 | profil sain, jamais teste en campagne |
| `qwen/qwen3.6-27b` | 2,32–3,27 s | 950 | 1036–**1500** | creve le plafond **1 fois sur 2** |

`gpt-oss-120b` reste nettement le meilleur : entree la plus compacte (933) et
sortie la plus econome (~200 tokens), soit **~1120 tokens par appel** — c'est
exactement ce qui lui permet de tenir dans les 8000 tokens/minute. Les deux
`qwen` consomment 2 a 3 fois plus en sortie pour le meme travail.

**Inutilisables — 400 reproductible sur le prompt MBPP :**

| Modele | echec |
|---|---|
| `openai/gpt-oss-20b` | `HTTP 400: Tool choice is none, but model called a tool` — **2 appels sur 2** |
| `openai/gpt-oss-safeguard-20b` | meme 400, **1 appel sur 2** |

Le modele emet un appel d'outil au format harmony alors que la requete ne
declare aucun outil, et **Groq rejette sa propre reponse**. Le `120b` ne le
fait jamais avec le meme prompt : c'est propre aux variantes 20b. A noter que
`gpt-oss-20b` est le modele de `run3`/`run4` (8/10) — **cote OpenRouter il
fonctionne**, l'echec est specifique a Groq.

**Inutilisables — crevent le budget d'entree :**

| Modele | in appel 1 | in appel 2 | cause |
|---|---|---|---|
| `groq/compound` | 3813 | **7521** | injecte son propre contexte agentique |
| `groq/compound-mini` | 2159 | 2159 | idem, plus modere |
| `allam-2-7b` | 1071 | 1071 | `context_window` = **4096** en tout |

Les deux `compound` ne sont pas des modeles mais des **systemes agentiques** :
ils ajoutent leur propre echafaudage au prompt. Pour le meme prompt exactement,
`compound` est passe de 3813 a 7521 tokens d'entree d'un appel a l'autre — il
**depasse a lui seul les 6000 tokens** du bench, sans qu'aucune iteration ait
eu lieu. Non reproductible, donc inutilisable pour une mesure.

`allam-2-7b` a un contexte total de 4096 tokens, **inferieur au budget d'entree
MBPP de 6000**. Il tokenise en plus moins bien (1071 en entree la ou les autres
sont a 933). Il a sorti 1500 tokens — le plafond — aux deux appels.

**Structurellement hors-jeu** (6 des 14, deja ecartes au releve du 2026-09-02) :
`whisper-large-v3` et `-turbo` (transcription, ctx 448), les 2
`canopylabs/orpheus` (synthese vocale), les 2 `meta-llama/llama-prompt-guard-2`
(classifieurs, ctx 512).

**Quotas mesures le 2026-09-03** (en-tetes d'une reponse 200) :

```
x-ratelimit-limit-requests: 1000     x-ratelimit-remaining-requests: 995
x-ratelimit-limit-tokens:   8000     x-ratelimit-remaining-tokens:   7923
x-ratelimit-reset-requests: 7m12s    x-ratelimit-reset-tokens:       577ms
```

**1000 requetes/jour, 8000 tokens/minute.** La contrainte mordante est la
seconde : a ~1120 tokens par appel, `gpt-oss-120b` tient **7 appels par
minute** ; les `qwen`, deux a trois fois moins. C'est deja ce qui a fait
echouer MBPP 462 en `run7`.

Comparaison directe avec OpenRouter, qui tranche le choix de fournisseur :

| | OpenRouter (`:free`) | Groq (free tier) |
|---|---|---|
| Requetes | **50 / jour / compte** | **1000 / jour** |
| Tokens | — | 8000 / minute |
| Latence observee | 4,9 – 63 s | **0,5 – 4,0 s** |
| Modeles utilisables | 3 sur 18 | 3 sur 8 testables |
| Cles dans `.env` | 2 (**meme seau** ; **1** au 2026-10-01) | **1** |

→ **Groq gagne sur tout sauf le nombre de cles.** 20x plus de requetes par
jour, un ordre de grandeur plus rapide, et aucun modele elimine par la latence
ou par le canal `reasoning`. Les echecs Groq sont d'une autre nature : 400
protocolaire (`gpt-oss-20b`) ou budget d'entree (`compound`, `allam`).

- [ ] **`x-ratelimit-reset-tokens` peut valoir `577ms`** — une **troisieme**
      unite, apres `s` et `m` deja notees plus haut. Le parseur de duree a
      ecrire pour `get_retry_after` (`provider.py:32-39`) doit couvrir `ms`,
      `s`, `m`, et le decimal (`30.795s`, `5m45.6s`), sinon il retombera
      toujours sur le plancher du bench
- [ ] Tester `qwen/qwen3.8-27b` sur une campagne complete : seul second
      candidat sain cote Groq, utile pour une **ablation a modele change,
      taches et agent identiques** — exactement ce que le sujet demande
- [ ] Ne **pas** retenir `gpt-oss-20b` cote Groq malgre ses 8/10 sur
      OpenRouter : le 400 est reproductible et vient du fournisseur, pas de
      nous. Si on veut le comparer, ce sera sur OpenRouter
- [ ] **Ajouter des cles Groq** (rappel) : une seule, et c'est desormais le
      seul avantage restant a OpenRouter

#### Fournisseurs pour SWE — releve du 2026-10-01, sondes du 2026-10-02

**Le besoin.** Une tache SWE, c'est ~30 requetes dont le contexte grossit
jusqu'a plusieurs dizaines de milliers de tokens (300 000 cumules autorises),
en 900 s. Il faut donc, **gratuitement** et sans carte : un contexte par
requete ≥ ~60k, assez de requetes par minute et **par jour** (examen : 3
taches ; rapport : ≥ 5 modeles × 3 taches), une API au format OpenAI (une
entree dans `configs/models.json`, pas de code), et plusieurs cles possibles.

**Releve par recherche web** (2026-10-01, guides tiers surtout), **verifie
avec une cle le 2026-10-02** pour NVIDIA et Mistral, et dans la doc officielle
pour Cerebras et Together :

| Fournisseur | Gratuit | Limites | Contexte | Verdict |
|---|---|---|---|---|
| **NVIDIA Build** (API NIM) | permanent, sans carte ni telephone, credits **supprimes** en 2026 | **40 RPM**, pas de plafond journalier | 128k a 1M selon modele | **branche** : 2 modeles retenus sur 19 sondes |
| **Mistral** | depuis le **14/08/2026** : **10 $ de credits/mois** offerts, sans carte ; entrees/sorties utilisees pour l'entrainement sauf opt-out | par modele, lues dans les en-tetes : 30 a 750 req/min, 625k a 1,3M tokens/min | 131k-262k | **branche** : 3 modeles, **valide par l'equipe pedagogique le 2026-10-02** |
| OpenRouter `:free` | oui, cle deja dans le `.env` | **50 req/jour/compte**, ~20 req/min | 262k | trop peu de requetes : 1-2 taches SWE/jour ; 429 « upstream » frequents (encore le 2026-10-01 sur un test a ~30k tokens) |
| Groq | oui | 8 000 tokens/min | — | **exclu** : 413 au-dela de 8 000 tokens par requete (verifie) |
| Cerebras | **non** : moyen de paiement exige pour activer l'API (doc officielle), 5 $ d'essai une seule fois, valables 30 jours. Ancien palier gratuit fini le **21/07/2026** selon des guides tiers (le 01/09/2026 note ici le 2026-10-01 n'est pas confirme) | essai : 5 req/min, 30k tokens/min hors cache, par modele | — | **exclu** (« billing-enabled accounts », et l'essai serait expire le jour de l'evaluation) |
| Together AI | **non** : « Together AI does not currently offer free trials », achat minimum de 5 $, plateforme prepayee (doc officielle). Les endpoints `-Free` a 0 $ exigent quand meme un solde positif | — | — | **exclu** (« purchased credits ») |
| Gemini (AI Studio) | oui | ~**20 req/jour** sur 2.5 Flash depuis le 06/12/2025, Pro retire du gratuit | 1M | **exclu** pour SWE (une tache = ~30 requetes) |

**NVIDIA Build — sondage du 2026-10-02.** Base URL
`https://integrate.api.nvidia.com/v1`, cles `nvapi-...`, `NVIDIA_API_KEY`.
Hausse a 200 RPM « sur demande » selon un guide, mais NVIDIA repond sur son
forum ne pas relever les limites des comptes personnels gratuits. Le
catalogue `/v1/models` liste 81 modeles ; 19 candidats sondes sur le vrai
prompt SWE (3 164 tokens), chacun en 3 variantes (sans reglage,
`chat_template_kwargs.enable_thinking=false`,
`chat_template_kwargs.thinking=false`), 4 requetes en parallele, echeance de
120 s :

| Resultat | Modeles |
|---|---|
| **retenus** | `nemotron-3-super-120b-a12b` (`enable_thinking: false`, 5-8 s ; **retire par NVIDIA le 2026-10-03**, HTTP 410), `nemotron-3-ultra-550b-a55b` (`thinking: false`, 7-19 s) |
| satures : plus de 120 s sur les 3 variantes | `deepseek-v4.1-flash`, `kimi-k3`, `glm-5.3`, `glm-5.3-flash`, `gemma-4-31b-it` |
| sature : 503 « worker limit 212/32 », 82 s quand il repond | `poolside/laguna-xs-2.1` |
| protocole incompatible : `content` vide, appels d'outils au format natif dans le raisonnement | `gpt-oss-20b` (meme avec `reasoning_effort: low`, meme sans `stop`), `meta/muse-glimmer-30b` |
| sortie degeneree | `nemotron-3.5-lightning-30b-a3b` : boucle de `>>`, ou `print(get_patch())` des le 1er tour |
| 404 bien que listes au catalogue | `kimi-k2.6`, `nemotron-nano-3-30b-a3b`, `mistral-large`, `mistral-large-2-instruct`, `llama-3.1-nemotron-ultra-253b-v1`, `llama-3.1-nemotron-70b-instruct`, `jamba-1.5-large-instruct`, `phi-3.5-moe-instruct` |

Le reglage qui coupe le raisonnement **depend du modele** : `nemotron-3-super`
prend `enable_thinking`, `nemotron-3-ultra` prend `thinking` (sa variante
`enable_thinking` n'a pas pu etre testee : 503 deux fois). Sans reglage,
`nemotron-3-super` passe de 5 s a 17 s et bute sur le plafond de 1 500 tokens.

**Contexte de 56 082 tokens** (16 tours d'historique synthetique), 3 essais :
`nemotron-3-super` 44,4 / 13,2 / 8,8 s, `nemotron-3-ultra` 15,6 / 9,9 / 8,0 s.
Accepte par les deux, mais **un appel sur six depasse l'echeance de 30 s**.
L'historique etait repetitif et les modeles l'ont recopie : la mesure vaut
pour la latence, pas pour la qualite.

**Mistral — sondage du 2026-10-02.** Base URL `https://api.mistral.ai/v1`,
`MISTRAL_API_KEY`. `/v1/models` liste 46 modeles, **pas de Devstral**. Pas
d'en-tete `retry-after` ni de reset sur les 429, seulement
`x-ratelimit-limit-*` / `x-ratelimit-remaining-*` : la boucle attend son
delai par defaut (10 s en SWE).

| Modele | Prompt SWE (3 153 tokens) | 56k tokens | Limites du compte | Verdict |
|---|---|---|---|---|
| `codestral-2508` | 1,0 s, bon format | 2,2 s | 125 req/min, 625k tokens/min | **branche** |
| `ministral-14b-2512` | 5,2 s, un « ### Plan: » en markdown avant le code | 4,1 s | 30 req/min, 937k tokens/min | **branche** |
| `ministral-8b-2512` | 2,8 s, idem | 6,0 s | 188 req/min, 625k tokens/min | **branche** |
| `ministral-3b-2512` | 2,3 s, bon format | 9,4 s, **coupe a 1 500 tokens** | 750 req/min, contexte 131k | ecarte |
| `mistral-medium-2604`, `mistral-small-2603` | **429 des la 1re requete** | 429 | `x-ratelimit-limit-req-minute: 0` | fermes sur ce compte |

**Mistral, le point tranche** (valide par l'equipe pedagogique le
2026-10-02). Le sujet interdit les « purchased credits » et les
« billing-enabled accounts ». Des credits **offerts** chaque mois ne sont ni
l'un ni l'autre, et le sujet range Mistral parmi les *« Cloud providers with
free access »* (§ V.6.1). Reste a s'y tenir : verifier aussi
qu'aucune carte n'est liee au compte, et suivre la consommation des 10 $ dans
la console (le sondage a envoye ~240k tokens d'entree). La console est le
seul endroit ou la voir : l'API ne donne que la limite **par minute**, pas le
credit restant (« Limite de tokens par minute », plus haut).

**Runs reels par le CLI SWE** (`sympy__sympy-14711`, 5 iterations, outils non
branches donc `NameError` a chaque appel d'outil) :

| Modele | Requetes / retries | Tokens in / out | Duree | Comportement |
|---|---|---|---|---|
| Groq `gpt-oss-120b` (2026-10-01, reference) | 11 / 6 | 16 009 / 3 326 | 91 s | recite le correctif de memoire |
| `nemotron-3-super` | 5 / 0 | 16 777 / 402 | 18 s | explore (`find`, `ls`, README) en chemins `/testbed` |
| `nemotron-3-ultra` | 8 / 3 (1 echeance de 30 s, 2 × 503) | 17 567 / 742 | 103 s | alterne `run_command` et `import subprocess` / `sys`, refuses par le sandbox |
| `codestral-2508` | 5 / 0 | 17 083 / 525 | 5,0 s | alterne les deux memes appels `read_file` / `search_code` |
| `ministral-14b-2512` | 5 / 0 | 18 884 / 1 091 | 13,9 s | explore avec des outils varies |
| `ministral-8b-2512` | 5 / 0 | 21 878 / 3 301 | 36,6 s | ecrit un correctif de `__mul__` de memoire des le tour 2 : **ignore la regle anti-recitation**. Bon point de comparaison faible, mauvais candidat pour l'examen |

- [x] **Creer une cle NVIDIA Build** et la poser dans le `.env`
      (`NVIDIA_API_KEY`) — fait le 2026-10-01
- [x] Entree `nvidia` dans `configs/models.json`, sondage avec une requete de
      56k tokens, relance de `sympy__sympy-14711` — fait (ci-dessus)
- [x] Cle Mistral posee, meme protocole, 3 modeles branches — 2026-10-02
- [x] **Faire valider les credits mensuels Mistral par l'equipe
      pedagogique** — **valide le 2026-10-02**
- [x] Echeance par appel propre a SWE — fait le 2026-10-02, 60 s (4 ter)
- [ ] Non verifie : GitHub Models (plafond d'entree par requete repute bas
      sur le gratuit), Cohere (cle d'essai a ~1000 appels/mois), SambaNova.
      Utile seulement si Mistral est refuse

Sources : [yangmao.ai — NVIDIA Build](https://yangmao.ai/en/providers/nvidia-build/),
[pasqualepillitteri.it — NVIDIA Build 2026](https://pasqualepillitteri.it/en/news/1621/nvidia-build-free-api-100-ai-models-2026),
[forum NVIDIA — 40 RPM](https://forums.developer.nvidia.com/t/request-to-increase-nvidia-nim-api-rate-limit-from-40-rpm-to-250-300-rpm/372594),
[agentdeals.dev — Mistral](https://agentdeals.dev/vendor/mistral-ai),
[mistral.ai — Devstral 2](https://mistral.ai/news/devstral-2-vibe-cli/),
[docs Cerebras — rate limits](https://inference-docs.cerebras.ai/support/rate-limits),
[toolfreebie.com — Cerebras](https://toolfreebie.com/cerebras-free-api/),
[aifreeapi.com — Gemini, decembre 2025](https://www.aifreeapi.com/en/posts/gemini-api-free-tier-rate-limits),
[docs Together — billing](https://docs.together.ai/docs/billing),
[pricepertoken.com — Together free](https://pricepertoken.com/endpoints/together/free),
[morphllm.com — Cerebras pricing](https://www.morphllm.com/cerebras-pricing).

### P2.4 — System prompts

- [x] Slots Thought / Code / Observation avec exemples ; l'exemple `smallest_abs`
      montre un premier essai **faux**, l'observation, puis la correction
- [x] Message d'observation revu : `Observation:` en tete dans **tous** les cas,
      sortie transmise **verbatim** (pas de `strip()` : un saut de ligne final est
      une donnee)
- [x] Prompt MBPP (court, 6k tokens d'entree au total)
- [x] **Prompt SWE-bench fini** (2026-09-01) : methodologie d'exploration, les 9
      outils, les regles, un exemple complet. La conversation a **deux tours**
      (`system` + `user`) comme MBPP — sans le tour `user`, l'agent SWE serait
      parti resoudre le probleme de l'exemple, seul enonce sous ses yeux
- [x] Les **5 regles**, chacune adossee a un mode d'echec observe : envelopper
      les appels d'outils dans `print()` (`exec()` jette la valeur d'une
      expression isolee → observation vide) ; les prefixes `<n>: ` de `read_file`
      ne font pas partie du fichier (1er motif d'echec d'`edit_file`, qui compare
      a l'exact) ; ne pas modifier les tests (l'`eval_script` les restaure, donc
      l'edition ne sert a rien et pollue le patch) ; pas de `git commit` ni de
      patch vide ; un seul bloc par tour (`extraction.py:20` ne garde que le
      premier)
- [~] **Premier run SWE reel (2026-10-01)** : `sympy__sympy-14711`, Groq
      `gpt-oss-120b`, plafonne a 5 iterations — 91 s, 11 requetes (dont 6
      retries), 16 009 tokens en entree. La chaine tient de bout en bout
      (`solution.json` conforme, causes des retries sur stderr, `retry-after`
      de Groq respecte), mais **les 5 tours finissent en `NameError`** : le
      namespace du sandbox ne contient toujours que `final_answer` (P1.4).
      Ce que le modele a fait quand meme :
  - **il recite le correctif** : au tour 5, « decommenter `#if other == 0:
    return self` » — le correctif reel de l'issue — sans avoir jamais pu lire
    `vector.py`, ancien code ecrit de memoire dans un `old_str`. Le § VI.4.1
    sanctionne d'un **0** les « memorized patches without genuine
    exploration »
  - il explore et edite **dans le meme bloc** des le tour 1
  - chemins relatifs au lieu de `/testbed/...`, `list_files()` sans
    arguments (le manuel devrait y remedier)
- [x] **Regle anti-recitation** (2026-10-01, `ccbbe79`) : « Never edit code
      you have not read: every old_str must be copied from a read_file()
      observation of an EARLIER step, never written from memory, and never
      call edit_file() in the same code block as the read_file() it relies
      on. Do not apply a fix you remember for this repository: find the cause
      in the code, then fix it. » (~240 tokens de plus par tour). **Notre
      exemple SWE violait la regle** : deux `old_str` du tour 2 reprenaient
      des lignes de `fields.py` jamais lues (`self.schema = schema`
      n'apparaissait dans aucune observation). Le tour 1 lit desormais les
      lignes 298-311 ; numeros des editions corriges au passage (92 et 300,
      pas 91 et 301). Un test verifie que chaque ligne de chaque `old_str` de
      l'exemple a ete vue dans un `read_file` d'un tour **anterieur**.
      **Effet non mesure** : impossible tant que les outils ne sont pas
      appelables. Premier indice le 2026-10-02 (P2.3, « Runs reels ») : 4
      des 5 nouveaux modeles explorent sans reciter, `ministral-8b` ecrit un
      correctif de memoire des le tour 2
- [~] **Injection du sandbox manual** — cote `Prompt`, faite le 2026-10-03
      (`fb8f224`). `Prompt(tools=list)` devient `Prompt(manual=str)` : le
      texte de `render_manual` est insere **tel quel**, avant les imports
      autorises, et omis s'il est vide. **Doublons retires** : avec un
      manuel, le prompt ne repete plus ce que le manuel dit deja — la regle
      `print()` des appels d'outils (SWE), la description de `final_answer`
      (les deux benchs) et celle de `get_patch` (SWE). **Sans manuel, ces
      lignes restent** : le prompt est alors identique octet pour octet a
      celui d'avant (compare a celui de `HEAD`). Gardees, car propres au
      bench : *« Call get_patch() first, check the patch is not empty… »*,
      *« Code inside final_answer MUST BE the EXACT code… »*, et la regle des
      prefixes de `read_file` (1er motif d'echec d'`edit_file`)
  - **Cout mesure** avec les manuels reels : MBPP +230 caracteres
    (~60 a 90 tokens par tour), SWE +5 412 (~1 350 a 2 170 tokens par
    tour, soit 40k a 65k sur les 300k en 30 tours)
  - **Verifie** : 21 tests ajoutes et 1 remplace (`tests/test_prompt.py`),
    dont un qui lance le vrai `mcp_tools_swebench.py` avec les transports et
    `render_manual` de ndi-tull, et retrouve la signature des 9 outils dans
    le prompt SWE ; en desactivant l'insertion, 6 tests echouent, en
    desactivant le retrait des doublons, 7 ; 474 tests verts, `ruff` propre
  - [ ] **Brancher le manuel dans les deux CLI** : attend le client MCP
        (P1.4). Les outils ne sont de toute facon pas appelables d'ici la
  - [ ] **Nuance a mesurer** : pour `print()`, le manuel dit *« A bare
        expression's value is discarded, so print() whatever you need to
        see »*, plus general que notre *« A tool call alone prints
        NOTHING »*, adosse a un echec constate. Verifier au premier run avec
        outils que les appels nus ne reviennent pas
- [x] **Exemple MBPP** : coquilles corrigees (`Obvservation`, virgule du second
      `assert` passee apres le saut de ligne, cloture ``` ``` ``` recollee,
      indentation du corps). **Le piege principal est corrige** (constate le
      2026-10-01) : `final_answer("def smallest_abs(a): return min(map(abs,a))")`
      tient sur une ligne. **Puis passe en multiligne le 2026-10-03 :**
- [x] **Ce `final_answer` d'une ligne est imite a tort par `codestral-2508`**
      (2026-10-02). Sur une fonction a boucles, il colle tout avec des `;`
      (`final_answer("def lps(s): n = len(s); for i in ...")`), une
      `SyntaxError` : 9 refus de la boucle sur 20 taches, en `run19`/`run20`
      comme en `run25`/`run26`. Depuis le refus explicite (P2.1), il se
      corrige au tour suivant (6 soumissions en `"""..."""`), mais chaque
      erreur coute un tour et ~420 tokens de sortie sur 1 500 (moyenne des 18
      tours refuses, 257 a 595). **A decider** :
      passer l'exemple en multiligne (`final_answer("""def ...\n    ...""")`)
      eviterait l'erreur des le premier essai, mais change le prompt de tous
      les modeles — le format d'une ligne avait ete choisi contre le piege des
      `\n` litteraux (`run5`, MBPP 94). A remesurer sur au moins Groq et
      `codestral` si on le change
  - **Tranche le 2026-10-03 : exemple passe en multiligne.** Il finit par
    `final_answer("""def smallest_abs(a):` / `    return min(map(abs,a))""")`,
    sur deux lignes ; la constante est delimitee par `r'''...'''`, puisqu'elle
    contient desormais `"""`. Mesure contre l'ancien sur le meme agent (P2.6,
    « Ablation E ») : `codestral` ne fait plus aucun refus `SyntaxError` (7 → 0),
    et le piege des `\n` litteraux n'est pas revenu (0 reponse invalide sur
    42). Test ajoute : l'exemple soumet, sur plusieurs lignes, le code qu'il
    vient de tester (echoue sur l'ancien exemple) ; 475 tests verts
- [x] **Prompts et relances corriges (2026-10-01, `9c4754a`)**, mesures le
      meme jour en `run9`/`run10` (voir P2.6) :
  - exemple MBPP : les `assert` sont suivis de `print('all tests passed')`,
    l'observation montree est celle que le code produit vraiment (un test
    l'execute dans le vrai sandbox) ; fini le `Observation: True` fictif
  - relance « make AND print the asserts » (qui poussait au
    `print(assert ...)`, une `SyntaxError`) remplacee par « passing asserts
    print nothing: print a confirmation after them »
  - relance apres une sortie sans `final_answer` : « in the next response »
    poussait SWE a soumettre pendant l'exploration (presque chaque tour y
    affiche quelque chose). Desormais par bench : MBPP garde « call
    final_answer() in your next step » si les verifications passent, SWE dit
    « once the fix is verified »
  - un run qui n'ecrit que sur stderr n'est plus annonce comme « sans
    sortie » (la branche se decide sur stdout + stderr)
  - plus de prefixe `Observation: Output: ...` : la forme est celle des
    exemples, `Observation: <sortie>`
  - exemple SWE : `search_code(pattern="_default_cache|_defaults")` scinde en
    deux recherches litterales — le sujet dit « grep-like » sans preciser, et
    l'implementation de ndi-tull est litterale : l'alternative ne trouvait rien
  - coquilles : « how work a tool », `\n.` mal place, espaces en tete de ligne

- [x] **Les `test_list` du dump sont incomplets** (2026-10-01, `4c8d206`).
      Lu dans le code de la moulinette : le dump livre `test_list[1:]`, la
      validation tourne avec `skip_first_k_tests=0` → **le premier test est
      toujours cache**. Le prompt dit desormais que `test_list` n'est qu'un
      echantillon et qu'il faut ajouter ses propres `assert` pour chaque
      exigence de `task_definition` ; l'exemple le montre (un `assert` absent
      de son `test_list`). **Mesure sur MBPP 400, 5 essais par version : 0/5
      avant, 0/5 apres.** Le modele ajoute bien ses `assert` (doublons, liste
      vide) mais lit « order irrespective » comme « l'ordre de la liste »
      alors que le test cache veut `(3, 4) == (4, 3)`. Erreur de lecture
      systematique, que le prompt ne corrige pas en general ; nommer ce cas
      dans l'exemple serait du sur-ajustement. Cout : +80 tokens par tour
- [x] **`assert` + `final_answer` dans le meme bloc** (2026-10-01,
      `4c8d206`). L'exemple MBPP tient en 2 tours, le bloc de soumission
      execute ses `assert` puis `final_answer` (qui ne tourne que s'ils
      passent) ; la consigne et la relance « sans sortie » disent la meme
      chose. Cause : sur MBPP 400, 2 essais sur 5 de `gpt-oss-120b` avaient
      ecrit le code, les `assert` **et une observation inventee** dans le
      canal `reasoning` ; le `content` ne portait que `final_answer`, les
      tests n'ont jamais tourne. `<end_code>` n'y peut rien : la sequence
      d'arret ne s'applique pas au raisonnement (et le modele a ecrit
      `<end_code<|message|>`). Effet mesure en `run12` : **0 soumission a
      l'aveugle sur 8** (2 a 3 par campagne avant), mais un nouvel echec —
      l'import oublie de 451, rattrape depuis par la boucle (P2.1)

→ **Methode :** resoudre une tache a la main avec seulement les outils de
l'agent, et transcrire ce raisonnement dans le prompt.

### P2.5 — Les deux agents *(faits)*

Les 4 options du sujet dans chacun, taches validees contre `MBPPTaskInput` /
`SWEBenchTaskInput`, `instance_id` (et non `task_id`) passe a `Loop.run` cote
SWE, `solution.json` ecrit par `model_dump_json(indent=4)` (`json.dump` ne sait
pas serialiser un `BaseModel`), **tous** les champs de `StepMetrics` remplis,
arret propre sur chacune des quatre limites. `validate_metrics` repond **YES**
sur toutes les taches mesurees.

**Helpers factorises** dans `core/agent_cli_helper.py` — la frontiere se defend :
le helper lit l'environnement et les fichiers, les CLI cablent les objets.

- [ ] `final_answer(get_patch())` est enseigne dans le prompt mais **non teste en
      execution** : `get_patch()` est un outil MCP de P1.5, pas encore branche.
      Jusqu'au 2026-10-01 la boucle l'aurait de toute facon **refuse**
      (`ast.parse` sur un diff) — corrige, voir la revue en tete

### P2.5 bis — `configs/models.json`

Chap. VIII p.38 : *"Configuration files for sandbox and models"*. Le sujet
**n'impose aucun schema** pour le versant modeles — a nous de le definir et de le
defendre.

**Schema retenu : deux niveaux par fournisseur.** `provider` decrit **comment
parler** au fournisseur (URL, endpoint, en-tetes, `api_key_env_var`, le nom de
chaque champ de reponse, la table `retry_after.names`) ; `models` decrit **ce que
sait faire** chaque modele. Le fournisseur est retrouve par son URL, le modele par
`--model-name`.

Ce qu'on n'y met **pas**, et pourquoi : les limites du benchmark (1500 tokens,
10 iterations, 120 s) sont des proprietes de MBPP, pas du modele — elles vivent
dans `constants.MBPP` ; les mesures (ratio de raisonnement, latences) sont des
observations, leur place est dans `BENCHMARK_REPORT.md` ; et **aucune cle** — le
JSON dit *quels* modeles et *comment* les appeler, le `.env` fournit *avec quoi*,
`api_key_env_var` fait le lien. Lecture dans les CLI
(`get_provider_and_model_config`, meme frontiere que `get_api_keys`), **jamais**
dans `LLMClient` : le client recoit une config, il ne va pas la chercher.

#### `ModelConfig` supprime (2026-09-02), revenu avec un vrai reglage (2026-10-01)

Le champ `reasoning: bool` cote `models` a vecu trois etats, puis `ModelConfig`
est revenu sous une autre forme des qu'un reglage reel est apparu :

1. **2026-08-18** — cree, valide par un model Pydantic `ModelConfig`, avec un
   repli conservateur `{"reasoning": False}` pour un modele absent du JSON
   (2026-08-22). **Mais jamais lu** : `LLMClient` le stockait sans s'en servir,
   le corps de requete est construit en dur. Un champ mort dans un JSON est
   inerte ; un champ mort qui a son parametre de constructeur **ressemble a un
   champ vivant**.
2. **2026-09-01 soir** — renomme `is_reasoning` pour lever une vraie collision :
   dans le meme fichier, `reasoning` cote `provider` designe le **nom du champ** a
   lire dans la reponse (`provider.py:99`), cote `models` c'etait un **booleen**.
   Le renommage a laisse `agent_cli_helper.py:34` derriere lui, qui validait
   encore `{"reasoning": False}` : Pydantic etant en `extra="ignore"` par defaut,
   la cle etait **silencieusement jetee** et le repli rendait `True` — l'inverse
   du profil conservateur. **Attrape par `tests/test_agent_cli.py` une heure
   apres son ecriture.**
3. **2026-09-02 — supprime.** `ModelConfig`, `is_reasoning`, et les 3 valeurs du
   JSON. `get_provider_and_model_config` rend maintenant
   `tuple[ProviderConfig, dict]` : le `.get(model_name, {})` de la ligne 30 fait
   le repli tout seul, il n'y a plus de branche a ecrire ni de defaut a accorder.
   Les entrees `"models"` sont des dicts vides — elles ne servent plus qu'a lister
   les modeles connus par fournisseur, et de point d'accroche pour de futurs
   reglages.
4. **2026-10-01 — revenu, avec `extra_body` (`ccbbe79`).** NVIDIA exige de
   couper le raisonnement par un champ du corps de requete
   (`chat_template_kwargs`), et ce champ change d'un modele a l'autre
   (`enable_thinking` pour `nemotron-3-super`, `thinking` pour
   `nemotron-3-ultra`). `ModelConfig` (`config_models.py`) n'a qu'un champ,
   `extra_body: dict`, **fusionne tel quel** dans le corps par `LLMClient` ;
   un validateur refuse qu'il fixe `model`, `messages`, `stop` ou
   `max_tokens`, que la boucle calcule. `extra="forbid"` : une coquille dans
   une entree arrete le demarrage. Le helper rend
   `tuple[ProviderConfig, ModelConfig]`, `ModelConfig()` pour un modele absent
   du JSON. Cette fois le champ est **lu** a chaque requete, et un test verifie
   qu'il arrive dans le corps envoye.

**Ce qu'on defend :** une abstraction a un seul champ jamais lu ne portait rien,
et sa suppression supprime avec elle la classe de bug qui venait de mordre. Elle
est revenue le jour ou un reglage reel l'a justifiee, avec la validation stricte
que l'etape 2 reclamait.

- [x] **Le typage avait perdu en precision** (`model_config: dict`, rien ne
      validait ce qui sortait du JSON) — regle le 2026-10-01 : la validation est
      revenue avec la premiere cle (`extra_body`), en `extra="forbid"`, comme
      prevu ici. Teste : coquille `extra_bodi` → erreur au demarrage,
      `extra_body: {"max_tokens": ...}` → refuse
- [x] **Le repli sur modele inconnu etait silencieux** — **regle le
      2026-10-02 (`c7727cc`) en sens inverse : un modele absent de
      `models.json` est desormais refuse au demarrage.** Constate le meme
      jour : OpenRouter a **servi `openai/gpt-4o-mini`, payant**, sur un
      compte `is_free_tier: true` a 0 credit (757 tokens en entree, 180 en
      sortie, tache reussie ; compteurs du compte inchanges quelques minutes
      apres, cout theorique ~0,0002 $). `models.json` devient la **liste
      blanche des modeles gratuits** : `get_declared_model()`
      (`agent_cli_helper.py`) refuse, avant toute requete, un `--model-name`
      non declare chez le fournisseur vise (exit 1, `solution.json` en echec,
      `total_requests: 0`), et un modele de repli non declare (erreur au
      demarrage). Erreur de configuration, donc pas de repli. 9 tests
      ajoutes, 8 echouent sur l'ancien code ; verifie en reel
  - Consequence voulue : un modele **declare** est accepte, payant ou non.
    `models.json` est la frontiere de confiance ; le code ne peut pas savoir
    si un modele est gratuit (seul OpenRouter expose un prix, dans
    `/models`)
  - Consequence assumee : si l'evaluation passe un modele gratuit **non
    declare**, chaque tache echoue au demarrage. Les scripts d'examen ne
    sont pas fournis et la commande (`exam_TYPE.sh --env-file`) n'a pas
    d'argument de modele : **demander a l'equipe pedagogique comment ils
    choisissent `--model-name`**
  - Desormais refuses car non declares : `qwen/qwen3.8-27b:free` (`run11`)
    et `minimax/minimax-m3:free` (plus gratuit). A declarer si on veut
    rejouer `run11`
- [ ] Regle de precedence CLI > fichier : sans objet tant qu'aucun reglage n'est
      expose en double. A rouvrir des qu'un l'est

### P2.6 — `BENCHMARK_REPORT.md` *(partie MBPP ecrite, SWE a faire)*

**≥ 5 modeles × ≥ 3 taches SWE-bench communes.**

**Modeles retenus (2026-10-02)** — declares dans `configs/models.json` et
passes par le vrai CLI SWE, detail en P2.3 « Fournisseurs pour SWE » :
`nvidia/nemotron-3-super-120b-a12b`, `nvidia/nemotron-3-ultra-550b-a55b`
(NVIDIA), `codestral-2508`, `ministral-14b-2512`, `ministral-8b-2512`
(Mistral, **valide le 2026-10-02**). **Le 2026-10-03, NVIDIA retire
`nemotron-3-super`** (entree supprimee de `models.json`, `560a18f`) : 4
modeles, **il en faut un 5e**. Le releve de ce qui a ete ecarte
(19 modeles NVIDIA sondes, Groq, Cerebras, Together, Gemini) est deja de la
matiere pour la partie « Setup ».

**Ecrit le 2026-10-02 (`0faae67`), en anglais, partie MBPP.** Les 6 points
du sujet, chacun avec une partie MBPP remplie et une partie SWE *to be
completed* : setup (agent, validation par la moulinette, jeux de taches A/B/C
et leurs seeds, 9 couples modele/fournisseur, fournisseurs ecartes),
comparatif des 6 modeles + matrice tache par tache, historique `run5`-`run14`,
fiabilite par fournisseur (tentatives, disponibilite, temps de reponse,
causes), metriques intermediaires adaptees a MBPP (discipline de soumission,
soumissions a l'aveugle, refus de la boucle, faux succes), 4 ablations, et
conclusions MBPP provisoires (`ministral-14b` retenu, `nemotron-3-super` en
repli). Tous les chiffres sont recalcules par script depuis les
`solution.json`, pas recopies de ce TODO.

**Revalidation de `run5` a `run8` par la moulinette** (2026-10-02) : ils
n'avaient ete verifies qu'en executant les `test_list` en local. Seul ecart,
**`run7` passe de 9/10 a 8/10** : MBPP 400 echoue au test cache, invisible
localement. Corrige partout dans ce TODO ; sorties dans
`benchmarks/mbpp/run5..8/logs/checker_2026-10-02_XX.txt`.

**Backing data** : `benchmarks/mbpp/runN/` (META, RESUME, taches,
solutions, logs), 22 runs, 1 031 fichiers, 5,1 Mo dont 1,9 Mo de logs ;
`benchmarks/README.md` dit quel verdict fait foi pour chaque run. Scan des
cles d'API avant versionnage : aucune.

- [~] Setup (modeles/providers, taches + justification) — MBPP fait, taches
      SWE a justifier
- [~] Tableau modele × tache : pass/fail, iterations, tokens in/out, temps mur
      — MBPP fait (6 modeles × 20 taches, plus les 4 modeles encore
      disponibles sur l'agent du 2026-10-03), SWE vide
- [~] Fiabilite provider : temps de reponse moyen, retries, disponibilite —
      MBPP fait ; SWE : seules les latences a 56k tokens
- [~] ≥ 2 metriques intermediaires : etape du 1er acces au fichier du patch final
      (exploration) / etape ou les echecs de tests baissent (progres partiel) /
      iterations entre "tests au vert" et `final_answer` (discipline, 0 ideal)
      — la discipline est mesuree sur MBPP ; les deux autres n'existent que
      sur SWE
- [~] **Etude d'ablation** avant/apres un changement, memes taches, meme modele
      — 5 sur MBPP (E le 2026-10-03). Le sujet ne dit pas qu'elle doit porter sur SWE ; en
      faire une sur SWE reste plus sur
- [~] Conclusions justifiees par les donnees + les `solution.json` de backing
      **presents dans le repo** — conclusions MBPP provisoires ; backing MBPP
      versionne dans `benchmarks/mbpp/`

→ Mesure manuelle acceptee, c'est l'analyse qui compte.

#### Campagnes MBPP deja faites (matiere pour le rapport)

Reussites **verifiees en executant les `test_list`**, pas d'apres le rapport de
l'agent — les deux verdicts ont toujours concorde.

| Serie | Fournisseur / modele | reel | requetes | duree des 10 |
|---|---|---|---|---|
| `run2` | OpenRouter `nemotron-3-ultra-550b` | 9/10 | — | 229 s |
| `run3` | OpenRouter `gpt-oss-20b` | 8/10 | — | 473 s |
| `run4` | OpenRouter `gpt-oss-20b` (apres correctifs) | 8/10 | — | 461 s |
| `run5` | OpenRouter `nemotron-3-super-120b` | 4/10 | 29 | 480 s |
| `run6` | **Groq `gpt-oss-120b`** | **10/10** | 16 | **48 s** |
| `run7` | **Groq `gpt-oss-120b`**, 10 taches neuves | **8/10** (9/10 en local, MBPP 400 echoue au test cache) | 18 | **53 s** |
| `run8` | OpenRouter `minimax-m3:free`, 10 taches neuves | 9/10 | 29 | 274 s |
| `run9` | Groq `gpt-oss-120b`, taches de `run6`, **nouveau prompt** | **10/10** | 18 | 42 s |
| `run10` | Groq `gpt-oss-120b`, taches de `run7`, **nouveau prompt** | **7/10** | 33 | 137 s |
| `run11` | OpenRouter `qwen3.8-27b:free`, taches de `run6` | **7/10** | 34 | 520 s |
| `run12` | Groq `gpt-oss-120b`, taches de `run7`, `assert` + `final_answer` dans le meme bloc | **6/10** | 25 | 123 s |
| `run13` | Groq `gpt-oss-120b`, taches de `run7`, + verification par la boucle | **8/10** | 17 | 56 s |
| `run14` | Groq `gpt-oss-120b`, taches de `run6`, + verification par la boucle | **8/10** | 19 | 59 s |

`run9` a `run11` (2026-10-01) sont valides par la **vraie moulinette**
(`moulinette_eval validate mbpp`, Docker), plus par execution locale des
`test_list` — et c'est ce qui a revele le test cache de MBPP 400.

**18/20 sur deux jeux de taches independants** (seeds 1..10 et 11..20, aucun
recouvrement) : le meilleur resultat de Groq. On l'a cru longtemps a 19/20
sans faux positif ; la revalidation par la moulinette du 2026-10-02 y trouve
le faux positif de MBPP 400. Rapports complets dans `cache/run5..7/RAPPORT.md`
(non versionnes).

Le basculement vers Groq explique l'essentiel : `run5` et `run6` portent sur
**les memes 10 taches** avec le meme agent, 4/10 contre 10/10. Les quatre
echecs `run5` par plafond de sortie crevé passent tous en un seul tour chez
Groq. Matiere directe pour le `BENCHMARK_REPORT.md`.

Les deux echecs de `run7` : **MBPP 400** (test cache, voir plus haut) et
**MBPP 462**, un **echec de quota, pas de raisonnement** : l'enonce porte un `test_list` de ~1000 tokens, la tache
consomme 2961 tokens d'un coup, le seau Groq (8000/min) tombe a 2438 et les
cinq tentatives suivantes partent en 429. Les deux gardes ont joue leur role —
le plafond a coupe la rafale, les metriques restent valides sur les 10.

Barre du sujet : 4/5 (80 %). Sur les campagnes OpenRouter, 84 % ; sur Groq,
**90 % (18/20)**.

Les trois echecs, et ce qu'ils ont appris :

1. **MBPP 453** (nemotron) — la bonne fonction ecrite des le tour 1, mais un appel
   de 98,3 s a mange 82 % du budget ; le `final_answer` correct du tour 4 est
   arrive avec 0,08 s restantes. Deux causes, **les deux corrigees** : message
   d'observation muet sur `final_answer`, et absence d'echeance reelle.
2. **MBPP 87** (nemotron) — 1500 tokens de sortie **entierement en raisonnement**,
   aucun bloc emis, alors que la reponse figurait a la fin de la deliberation.
   `finish_reason: length`. Cause irreductible cote modele ; `gpt-oss` passe la
   tache du premier coup.
3. **MBPP 59 et 413** (gpt-oss) — rafales de 429 *"temporarily rate-limited
   upstream"*, reproduites a l'identique. La 413 a fini a 135,8 s →
   `Metrics valid: NO`. Le depassement etait imputable a la boucle, **corrige** ;
   l'instabilite du fournisseur ne l'est pas.

→ Les deux modeles echouent pour des raisons **independantes** : verbosite d'un
cote, instabilite du fournisseur de l'autre. Sur 20 executions la boucle n'a
commis qu'**une seule faute** qui lui soit imputable. Avec des taux si proches,
le choix ne se tranchera pas sur 10 taches.

→ Statistiques d'appel (28 appels) : mediane 6,3 s, **moyenne 14,8 s, max 98,3 s**
— 5 sur 28 depassent les 30 s du plafond nominal. C'est cette distribution qui a
motive l'echeance par thread.

**`run4` — memes 10 taches apres les correctifs.** Meme resultat (8/10, memes deux
echecs), mais **`Metrics valid: YES` sur les 10** (`run3` : 9/10) : les deux
echecs s'arretent a 115,0 s exactement au lieu de 118,6 et 135,8 s. Le plafond de
30 s mord maintenant — 3 taches ont demande un appel de plus. Compromis accepte :
un appel abandonne puis rejoue coute une requete, il evite l'appel de 98 s qui
avait tue la 453. Et les deux echecs ne sont plus les memes 429 : `run4` a bute
sur le **quota journalier** (4 clefs epuisees), pas sur l'agent — **8/8 hors
quota**.

**Defaut mis au jour le 2026-08-16, corrige le 2026-08-22 : aucun recul entre
tentatives.** La 413 a emis **2069 requetes en 115 s** (18/s). Cause : OpenRouter
renvoie son 429 en 0,07 s et **sans `Retry-After`**, la boucle faisait donc
`time.sleep(0)`. Le seul signal utilisable etait `X-RateLimit-Reset` (epoch **en
millisecondes**). Traite en P2.3.

> **Traces perdues.** `cache/run1..4` n'existent plus : `cache/` est gitignore,
> rien n'a jamais ete commite. Les chiffres ci-dessus sont tout ce qu'il reste —
> suffisant au recit, pas a une verification. **Fait le 2026-10-02 pour
> `run5` a `run26` (`run27` a `run34` le 2026-10-03) : `benchmarks/mbpp/`.** Le sujet exige les fichiers de
> backing dans le repo.

- [ ] Rejouer 59 et 413 en quota epuise pour verifier le nombre de requetes
      emises : le correctif est teste unitairement, pas en campagne
- [ ] Etendre a plus de taches — 10 ne separent pas deux modeles a 87 %

#### Campagnes du 2026-10-01 : ablation du prompt et second fournisseur

**Protocole.** Memes fichiers de taches que `run6`/`run7` (copies dans chaque
dossier), meme modele, seul le prompt change (`9c4754a`) → ablation a jeu
egal. Pause Groq apres chaque tache = tokens consommes / (8000/60) s.
OpenRouter : pilote d'une tache par candidat avant de lancer. Dossiers
`cache/run9..11` : `META.txt` (modele, commit, horaires), `RESUME.json`,
taches, solutions, `logs/agent_XX.log` et `logs/validate_XX.txt`.

**Ablation (Groq `gpt-oss-120b`, 20 taches) : 17/20 avec le nouveau prompt
contre 18/20 avec l'ancien** (19/20 avant la revalidation du 2026-10-02, qui
fait echouer la 400 de `run7`). Non significatif sur un tirage par tache :
les deux prompts echouent sur 462 et 400, **seule MBPP 138 les separe** :

| Tache | Ancien | Nouveau | Cause |
|---|---|---|---|
| MBPP 462 | echec | echec | 1500 tokens de sortie des la 1re reponse (`test_list` de ~1000 tokens) ; en `run7` c'etait le seau TPM |
| MBPP 400 | **FAIL (faux positif)** | **FAIL (faux positif)** | test cache « order irrespective » ignore — seul echec de raisonnement. L'ancien PASS venait de l'execution locale des `test_list`, qui ne voit pas le test cache |
| MBPP 138 | PASS | FAIL | bonne fonction au tour 1, tests **rejoues** au tour 2 au lieu de soumettre, puis 5 retries au tour 3 (cause non enregistree a l'epoque) |

**Le cout du nouveau prompt est une vraie validation.** +1 iteration sur 7
taches sur 20, entree moyenne +40 % (890 → 1274 sur `run9`, 1071 → 1477 sur
`run10`, max 2331 sur 6000). En `run6`, sur MBPP 127, l'ancien prompt avait
obtenu un `final_answer` contenant les `assert` **dans la chaine** : ils n'ont
jamais tourne. Les reussites en 1 iteration etaient des soumissions a
l'aveugle ; le nouveau prompt fait executer les tests avant de soumettre.

**Second fournisseur (OpenRouter `qwen3.8-27b:free`, taches de `run6`) :
7/10, les 3 echecs sont des pannes fournisseur** (5 retries, 0 iteration,
MBPP 252, 264, 247). Quand il repond, **7/7**. Latence mediane 9,5 s (max
27 s, pour 30 s d'echeance) contre 1,2 s chez Groq ; 520 s pour 10 taches
contre 42 s. MBPP 247 a fini a 120,03 s → **metriques invalides** : c'est le
bug d'attente corrige en P2.1.

**Constats du jour sur les fournisseurs :**

- `minimax/minimax-m3:free` (`run8`) **n'est plus gratuit** : 404 « unavailable
  for free », seul le slug payant existe
- `google/gemma-4-31b-it:free` : 429 « temporarily rate-limited upstream »
  (Google AI Studio) au pilote — inutilisable ce jour-la
- `qwen/qwen3.8-27b:free` : seul candidat passe au pilote (2 iterations, 20 s,
  mais 1302 tokens de sortie sur 1500 — marge faible)
- 20 modeles gratuits au catalogue (463 au total), `gpt-oss-20b:free` en est
  sorti
- **Une seule cle OpenRouter dans le `.env`** (deux au releve du 2026-09-02).
  ~44 requetes OpenRouter consommees ce jour-la sur 50

**Pour rejouer une validation MBPP :**

- Docker est **rootless** sur ce poste : le SDK de la moulinette cherche
  `/var/run/docker.sock` et prend un `PermissionError`. Il faut
  `DOCKER_HOST=unix:///run/user/103977/docker.sock`
- l'image `python:3.11-slim` doit etre presente (`docker pull`, faite le
  2026-10-01) ; sans elle la validation rend `Correctness: FAILED` **sans
  message** — piege : on croit a une mauvaise solution

#### `run12` : `assert` + `final_answer` dans le meme bloc (2026-10-01)

Groq `gpt-oss-120b`, taches de `run7`, prompt avec la consigne « tests
caches » et le bloc unique (P2.4). Soumission « a l'aveugle » = `final_answer`
execute sans qu'aucun `assert` ait tourne avant ou dans le meme bloc, mesure
sur l'**AST** du `sandbox_input` (des `assert` ecrits *dans la chaine* de
`final_answer` ne comptent pas — c'etait le cas de MBPP 127 en `run6`) :

| Serie | Prompt | reel | soumis | meme bloc | **a l'aveugle** | it. moy. | entree moy. | req |
|---|---|---|---|---|---|---|---|---|
| `run6` | ancien | 10/10 | 10 | 6 | **3** | 1,1 | 890 | 16 |
| `run9` | 2026-10-01 matin | 10/10 | 10 | 5 | **3** | 1,5 | 1274 | 18 |
| `run7` | ancien | 8/10 | 9 | 5 | **3** | 1,2 | 1071 | 18 |
| `run10` | 2026-10-01 matin | 7/10 | 8 | 1 | **2** | 1,5 | 1477 | 33 |
| `run12` | meme bloc | 6/10 | 8 | 8 | **0** | 0,8 | 850 | 25 |
| `run13` | meme bloc + verification | 8/10 | 9 | 9 | **0** | 1,0 | 1032 | 17 |
| `run14` | meme bloc + verification | 8/10 | 8 | 8 | **0** | 1,1 | 1105 | 19 |

Les 4 echecs de `run12` : **451** (import oublie dans la chaine soumise —
**nouveau**, cause par le bloc unique, rattrape depuis par la boucle), **400**
(test cache, comme partout), **462** (plafond de sortie, comme partout),
**168** (5 reponses sans `content` du fournisseur). Sur 10 taches a un tirage,
6/10 contre 7/10 n'est pas significatif.

**Premiere campagne avec la cause des retries enregistree** : les 15 retries
de `run12` sont tous `The LLM response does not contain the expected
'content' field. (HTTP 200)` — `gpt-oss` met toute sa reponse dans
`reasoning` et laisse `content` vide. Avant, ces retries etaient anonymes.

#### `run13` / `run14` : avec la verification par la boucle (2026-10-01)

Groq `gpt-oss-120b`, taches de `run7` puis de `run6`, code = `HEAD` +
`code.diff` (le diff exact est dans chaque dossier, rien n'etait commite).
**16/20, 0 soumission a l'aveugle sur 17**, metriques valides sur les 20.
Contre 18/20 avec l'ancien prompt (`run6`+`run7`, apres revalidation) et
17/20 avec celui du matin (`run9`+`run10`) — non significatif a un tirage par
tache.

**Les 2 refus de la boucle, rejoues contre la liste complete des tests du
jeu de donnees, etaient tous les deux justes** :

- `run13/451` : `import re` oublie → refuse, corrige au tour 2, **PASS** —
  l'echec de `run12` est rattrape
- `run14/252` : `import cmath` oublie → refuse ; au tour 2 le modele utilise
  `math` sans l'importer, au tour 3 il creve le plafond cumule de 1500 tokens
  de sortie → echec

(Un premier comptage en annoncait 4 : les 2 autres etaient des blocs du
modele qui plantaient avant d'atteindre `final_answer` — un `assert`, un
`AttributeError` — pas des refus de la boucle.)

Les 4 echecs : **462** (plafond de sortie des la 1re reponse, comme
partout), **400** (test cache, comme partout), **80** (5 `content` vides de
Groq), **252** (budget de sortie epuise apres le refus). **Le fournisseur
pese plus que le prompt** : les 12 retries de ces deux campagnes sont tous
`content` vide en HTTP 200, et ce defaut a coute 2 taches sur `run12` a
`run14` (168, 80).

- [ ] **Piste : `reasoning_effort: low` pour `gpt-oss` chez Groq** (parametre
      a verifier). Moins de raisonnement → moins de `content` vides et moins
      de plafonds de sortie (462, 252). C'est un reglage **du modele** : sa
      place est dans les entrees `models` de `configs/models.json`. **Faisable
      sans code depuis le 2026-10-01** : `extra_body` et sa validation existent
      (P2.5 bis)
- [ ] Recommencer l'ablation de facon plus large : 10 taches a un tirage ne
      separent pas des taux de 60 a 90 %
- [x] Les campagnes vivent dans `cache/`, gitignore : a sortir dans un dossier
      versionne avec le reste des `solution.json` de backing — fait le
      2026-10-02, `benchmarks/mbpp/` (`0faae67`)

#### Campagne multi-modeles du 2026-10-02 (`run15` a `run24`)

**Protocole.** Les 5 modeles branches le jour meme, sur les 20 taches de
`run13`/`run14` (fichiers de `run6` et `run7`, copies dans chaque dossier),
code `94539e7` sans modification, verification par la boucle active. Un fil
par modele, les 5 en parallele ; chaque solution validee par
`moulinette_eval validate` (Docker). « Faux succes » : `success: true` dans
le rendu, `FAIL` a la moulinette.

| Modele | Runs | PASS | Metriques valides | Faux succes | Temps moyen / max | Retries |
|---|---|---|---|---|---|---|
| Groq `gpt-oss-120b` (reference) | `run14` + `run13` | **16/20** | 20/20 | 1 | 5,7 / 27,7 s | 13 |
| `nemotron-3-super` | `run15` + `run16` | 15/20 | 20/20 | 1 | 16,8 / 79,9 s | 4 |
| `nemotron-3-ultra` | `run17` + `run18` | 14/20 | 19/20 | 2 | 34,9 / 94,2 s | **26** |
| `codestral-2508` | `run19` + `run20` | **11/20** | 17/20 | 0 | 8,8 / 17,3 s | 0 |
| `ministral-14b-2512` | `run21` + `run22` | 15/20 | 20/20 | 1 | 8,1 / 21,5 s | 0 |
| `ministral-8b-2512` | `run23` + `run24` | 15/20 | 19/20 | 1 | 8,2 / 26,7 s | 0 |

**Ce qui vaut pour tous :** **0 soumission a l'aveugle**, sur aucun modele.
**400** echoue partout (6/6, le test cache ; 4 modeles s'annoncent en
succes), **462** aussi (6/6, plafond de sortie), **108** n'est reussie que
par Groq. Un ecart de 1/20 ne separe rien.

**Par modele :**

- `ministral-14b` : au niveau des meilleurs, le plus rapide, aucun retry.
  **Modele MBPP par defaut du `Makefile` depuis le 2026-10-02**, Mistral
  etant valide
- `nemotron-3-super` : meme score, 2 fois plus lent, quelques retries.
  **Le repli si Mistral est refuse**
- `nemotron-3-ultra` : 26 retries (echeances de 30 s, 503), 2 taches perdues
  sur 5 retries sans une seule reponse. Pas un candidat MBPP
- `codestral` : ses 9 echecs sont tous un plafond de sortie atteint. **5**
  (247, 65, 400, 71, 138) viennent de refus repetes du meme `final_answer`
  d'une ligne casse par des `;` (voir P2.4) — c'est ce qui a mene au second
  correctif ci-dessous ; les 4 autres (264, 305, 462, 108) sont des `assert`
  qui echouent en boucle

**Les 5 metriques INVALID** : toutes une entree cumulee au-dela de 6 000
(6 163, 6 216, 6 665, 7 103, 7 513), la requete fautive etant deja partie
quand la boucle s'en apercevait. Corrige le jour meme (P2.1).

#### `run25` / `run26` : `codestral` apres les deux correctifs (2026-10-02)

Memes 20 taches, memes conditions, code = `94539e7` + les deux correctifs de
P2.1 (garde d'entree avant envoi, refus `SyntaxError` explicite), commites
depuis dans `c21b0ce`.

| `codestral-2508` | Avant (`run19`/`run20`) | Apres (`run25`/`run26`) |
|---|---|---|
| PASS | 11/20 | **17/20** |
| Metriques valides | 17/20 | **20/20** |
| Refus de la boucle | 9 | 9 |
| Soumissions acceptees en `"""..."""` | 0 | 6 |
| Sorties par la garde d'entree | — | 2 (264, 138), metriques valides |

Le modele fait **toujours** l'erreur du premier coup (9 refus des deux
cotes) : le correctif ne la previent pas, il permet d'en sortir au tour
suivant. Premiere reussite de la **400** par un modele. **Un seul tirage** :
une part de l'ecart peut etre du hasard.

- [x] Rejouer les 4 autres modeles avec les correctifs — fait le
      2026-10-03 pour Groq et `codestral` (ablation E), puis les deux
      `ministral` (ci-dessous). `nemotron-3-super` impossible (retire),
      `nemotron-3-ultra` laisse de cote (deja ecarte)

#### Ablation E : exemple MBPP multiligne (2026-10-03, `run27` a `run34`)

**Protocole.** Memes 20 taches (`run6` + `run7`), meme agent (`fb8f224`,
avec les correctifs de la boucle et le repli). D'abord l'ancien exemple
(`run27`/`run28` Groq, `run29`/`run30` `codestral`), **puis** le nouveau
(`run31` a `run34`) : `core/constants.py` n'a ete modifie qu'entre les deux,
pour qu'aucune tache ne tourne sur un melange. La reference Groq existante
(`run13`/`run14`) datait d'avant les correctifs, d'ou le rejeu de l'ancien
exemple sur les deux modeles. `META.txt` porte `exemple_mbpp=`, `RESUME.json`
un champ `fallback`.

| | Groq une ligne | Groq multiligne | `codestral` une ligne | `codestral` multiligne |
|---|---|---|---|---|
| PASS | 17/20 (dont 3 par le repli) | **18/20** | 16/20 | **17/20** |
| Metriques valides | 20/20 | 20/20 | 20/20 | 20/20 |
| Refus `SyntaxError` | 0 | 0 | 7 (7 taches) | **0** |
| `final_answer` multilignes | 13 sur 22 | 21 sur 21 | 10 sur 31 | 21 sur 21 |
| Iterations (total) | 22 | 21 | 36 | **25** |
| Entree par tache | 1 132 | 1 004 | 2 174 | **1 317** |
| Sortie par tache | 636 | 517 | 741 | 524 |
| Discipline = 0 | 17/18 | 18/19 | 9/16 | **17/17** |

- **Net sur `codestral`** : les 7 taches refusees (127, 94, 305, 247, 65,
  400, 71) passent sans refus, −31 % d'iterations, −39 % d'entree
- **Le taux de reussite reste dans le bruit** : `codestral`, meme agent, meme
  exemple, a fait 17/20 (`run25`/`run26`) puis 16/20 (`run29`/`run30`)
- **Groq inchange** a une tache pres (MBPP 252, echouee avant sur le plafond
  de sortie). Echecs communs aux deux versions : 462 (plafonds), 400 (test
  cache, Groq), 108 et 138 (plafond de sortie, `codestral`)
- **Le repli a servi pour de vrai** : 3 taches Groq de `run27`/`run28` ont
  recu 5 reponses HTTP 200 sans `content` et ont ete finies par
  `ministral-14b-2512` (avant le repli, elles etaient perdues : `run13`/`run14`
  perdait la 80 ainsi). 47 des 52 echecs Groq du jour sont ce `content` vide,
  5 des 429 sur la limite de 8 000 tokens/min
- Methode des chiffres : les scripts du rapport, reverifies sur les lignes
  deja publiees (`run13`/`run14`, `run19`/`run20`, `run25`/`run26`,
  identiques au chiffre pres)
- [ ] **Identifiant d'organisation Groq** (`org_…`) dans 4 logs de
      `run27`/`run28` (message du 429) : ce n'est pas une cle, mais aucun log
      deja versionne ne le contient. A masquer ou non avant le commit

#### Rejeu sur l'agent actuel (2026-10-03, `run35` a `run40`)

Memes 20 taches, agent `e13feb3` (correctifs, repli, exemple multiligne).
Mistral en sequence (`ministral-14b` puis `ministral-8b`, meme cle), NVIDIA
en parallele.

| | Agent du 2026-10-02 | Agent actuel |
|---|---|---|
| `ministral-14b` (`run21`/`22` → `run35`/`36`) | 15/20, 20/20 valides | **13/20**, 20/20 valides, 1,05 it., 1 522 entree/tache, 9,7 s |
| `ministral-8b` (`run23`/`24` → `run37`/`38`) | 15/20, 19/20 valides | **13/20**, 20/20 valides, 0,90 it., 1 179 entree/tache, 5,5 s |
| `nemotron-3-super` (`run15`/`16` → `run39`/`40`) | 15/20 | **non mesure** : 20 × HTTP 410, les 20 taches faites par Groq via le repli (16/20) |

- **Les deux `ministral` perdent 2 taches, sans rapport avec l'exemple** :
  3 des 4 taches perdues (264 pour les deux, 305 pour 14b) finissent le
  Thought au plafond de 1 500 tokens avant tout code (264 : formule apres
  formule pour l'age du chien) ; la 4e (71, 8b) echoue au test cache.
  Tous les `final_answer` sont multilignes, aucun invalide
- **Bruit mesure** : Groq, meme agent, 18/20 (`run31`/`32`) puis 16/20
  (`run39`/`40`). Un ecart de 2 taches ne separe pas deux modeles
- **`nemotron-3-super` retire le 2026-10-03 a 09:00 UTC** (« has reached its
  end of life »). Le 410 a declenche le repli des le 1er essai : aucune
  tache perdue. Consequences traitees le jour meme (`560a18f`) : defaut SWE
  → `codestral-2508`, entree retiree de `models.json`, `nemotron-3-ultra`
  en dernier dans les deux listes de repli
- [ ] **Decider du modele MBPP par defaut** : sur l'agent actuel,
      `codestral-2508` 17/20 (1,25 it., aucun echec en 152 tentatives)
      contre `ministral-14b-2512` 13/20, le defaut du `Makefile`. Seul ecart
      entre modeles Mistral au-dela du bruit mesure
- [ ] `META.txt` de `run39`/`run40` : nomme le modele demande ; une note
      dirait que Groq a repondu (le `README` des benchmarks le dit deja)

---

## A faire ensemble (fin de projet)

- [ ] **`README.md` en anglais** (encore vide) : 1ere ligne en italique *"This
      project has been created as part of the 42 curriculum by tchemin,
      ndi-tull."*, puis Description / Instructions / Resources (+ **usage reel de
      l'IA detaille — exige par le sujet**), architecture, boucle agent, design du
      sandbox, implementation des outils, resultats de benchmark
- [ ] Verifier le repo : configs sandbox + modeles, `mcp_tools_*.py` a la racine,
      `BENCHMARK_REPORT.md`, `solution.json`
- [ ] **Ne pas inclure :** images Docker, poids de modeles, outputs generes
- [ ] **Relire le code de l'autre** : en soutenance on doit savoir modifier
      l'agent en 2-5 min sur une tache MBPP. Prevoir 2 sessions de passation

---

## Ordre de travail

1. [x] Phase 0 ensemble
2. [x] En parallele — sandbox qui execute + boucle avec provider injecte
3. [x] **MBPP end-to-end**, et au-dela : 15 taches reelles avec les limites
       branchees
4. [~] Mesurer et optimiser le prompt → 4 correctifs issus des mesures, rejeu a
       jeu egal fait (`run4`). **Reste : une campagne apres la couche `Provider`**
5. [ ] **Durcir le sandbox (P1.7) pendant que P2 attaque SWE-bench.** Cote P2,
       SWE-bench est pret a etre branche — le chemin critique est cote P1
6. [ ] SWE-bench sur les 3 taches conseillees : `sympy__sympy-14711` /
       `sympy__sympy-13480` / `pydata__xarray-4629`
7. [ ] `BENCHMARK_REPORT.md` une fois les 2 benchmarks fonctionnels
8. [ ] `README.md` + relecture croisee

### Prochaines actions (cote tchemin), par rentabilite

1. [x] **Campagne de controle MBPP** — faite le 2026-10-01 (`run9`, `run10`,
       `run11`, voir P2.6) : 17/20 Groq, 7/10 OpenRouter. A relancer apres les
       corrections de prompt restantes (P2.4)
2. [x] **Rapatrier `origin/ndi-tull`** — merge le 2026-10-01 (`70207ab`).
       Reste a **caler les signatures avec ndi-tull** (§ V.5) : c'est sa
       partie, a lui transmettre avec le tableau de la revue
3. [x] **Commiter la session du 2026-09-02** (`97091ce` → `3fb1d4f`)
4. [x] **Piege de l'exemple MBPP corrige et mesure** — l'ablation est faite
       (`run6`/`run7` contre `run9`/`run10`, voir P2.6)
4 bis. [~] **Strategie fournisseurs pour SWE — devenue la priorite** : Groq
       gratuit est **exclu** (413 au-dela de 8 000 tokens, verifie le
       2026-10-01), OpenRouter tient 50 req/jour sur **une seule** cle. Sans
       fournisseur gratuit a gros contexte, ni les 2/3 SWE de l'examen ni
       `BENCHMARK_REPORT.md` ne sont atteignables, quoi que fasse ndi-tull.
       **Releve fait** (P2.3, « Fournisseurs pour SWE ») : NVIDIA Build en
       tete, Mistral en second. **Cles posees et fournisseurs branches le
       2026-10-02 : 5 modeles** (2 NVIDIA, 3 Mistral), **Mistral valide
       par l'equipe pedagogique le 2026-10-02**. **Le 2026-10-03, NVIDIA
       retire `nemotron-3-super` : 4 modeles, il en faut un 5e** pour le
       rapport (« at least 5 models »). A sonder : les nouveaux modeles du
       catalogue NVIDIA, d'autres modeles Mistral
4 ter. [x] **Echeance par appel propre a SWE** — fait le 2026-10-02
       (`11cae12`). La constante globale `LLM_TIMEOUT_SECONDS = 30` est
       supprimee ; `Bench` porte `llm_timeout`, a cote des autres limites du
       bench : **SWE 60 s**, MBPP 30 s (inchange). La boucle prend
       `self.bench.llm_timeout`, toujours dans `min(…, temps restant -
       marge)`. **Pourquoi 60 s** : NVIDIA a repondu en 44,4 s sur 56k tokens
       (une fois sur trois) et la sonde est montee a 48 s, coupes a 30 s ;
       5 tentatives a 60 s coutent au plus 300 s, un tiers des 900 s, avant
       que le repli prenne le relais. **Effet de bord** : le client compare le
       `Retry-After` d'un 429 a cette echeance ; en SWE, un 429 a 45 s devient
       une attente de 45 s puis un nouvel essai, au lieu d'une erreur
       permanente (verifie : MBPP → `Permanent`, SWE → `Transient` 45 s).
       **Verifie** : 3 tests ajoutes (`tests/test_loop.py`), celui de SWE
       echoue si l'on remet 30 s en dur ; 453 tests verts, `ruff` propre. Pas
       de run SWE reel (outils non branches)
   - [ ] Revoir la valeur apres les premiers vrais runs SWE : la latence
         au-dela de 56k tokens n'est pas mesuree
4 quater. [x] **`Makefile` : un defaut par benchmark** — fait le
       2026-10-02 (`e0a7737`). `URL` / `MODEL` (OpenRouter
       `nemotron-3-ultra-550b-a55b:free`, inutilisable) remplaces par
       `MBPP_MODEL` / `MBPP_URL` = **`ministral-14b-2512`** sur Mistral
       (15/20, le plus rapide, 0 retry ; Groq le temps que Mistral soit
       valide) et `SWE_MODEL` / `SWE_URL` = **`nemotron-3-super`** sur NVIDIA
       (Groq exclu pour SWE, 413). Les cibles prennent
       `$(or $(MODEL),$(MBPP_MODEL))` : `MODEL=` / `URL=` en ligne de commande
       restent prioritaires ; `make help` affiche les defauts. Verifie :
       `make -n` sur les deux cibles et une surcharge, `make mbpp` reel
       (MBPP 80, PASSED / VALID, sous Groq avant le passage a Mistral).
       **Le 2026-10-03, defaut SWE passe a `codestral-2508`** (Mistral,
       `560a18f`), `nemotron-3-super` etant retire par NVIDIA
4 quinquies. [~] **Campagne MBPP des 5 modeles** — faite (`run15` a
       `run24`), deux defauts de la boucle corriges (`c21b0ce`) et
       `codestral` rejoue (`run25`/`run26`, 17/20). **Exemple MBPP passe en
       multiligne et mesure** le 2026-10-03 (ablation E, `run27` a `run34`).
       **Rejeu fait le 2026-10-03** (`run35` a `run40`) : les deux
       `ministral` a 13/20, `nemotron-3-super` retire. Reste a **decider** du
       modele MBPP par defaut (`codestral-2508` 17/20 contre `ministral-14b`
       13/20 sur l'agent actuel, P2.6)
4 sexies. [~] **`BENCHMARK_REPORT.md`** — partie MBPP ecrite et backing
       versionne (`0faae67`), ablation E ajoutee le 2026-10-03. Reste la partie SWE, des que les outils sont
       appelables : 5 modeles × 3 taches (`sympy__sympy-14711`,
       `sympy__sympy-13480`, `pydata__xarray-4629`), les deux metriques
       propres a SWE, et de preference une ablation SWE. **Chaque nouvelle
       campagne va directement dans `benchmarks/`**, pas dans `cache/`
4 septies. [~] **Repli entre fournisseurs** — fait le 2026-10-02
       (`19e17be`, P2.3, « Repli de provider »). Reste a **decider** des
       erreurs qui declenchent le repli, de l'ordre des listes, et du repli
       en milieu de tache (avertissement `Multiple model_names` de la
       moulinette). Le 410 de `nemotron-3-super` (2026-10-03) a declenche
       le repli des le 1er essai, comme voulu
4 octies. [~] **Limite de tokens par minute de Mistral** — verifiee avant
       l'envoi (P2.3, `36e071b`). Reste a decider s'il faut aussi la limite
       par requete, Groq, ou un plafond mensuel compte par nous
4 nonies. [~] **Modeles payants** — seuls les modeles declares sont acceptes
       (`c7727cc`, P2.5 bis) ; relecture du sujet faite (P2.3, « Ce que dit
       le sujet du payant »). Restent : le test `:free` pour OpenRouter, et
       **demander a l'equipe pedagogique comment les scripts d'examen
       choisissent `--model-name`**
4 decies. [~] **Sandbox manual dans le prompt** — cote `Prompt`, fait le
       2026-10-03, doublons retires (P2.4). Reste a **convenir avec
       ndi-tull** de ce que le sandbox exposera pour que les CLI recuperent
       le manuel, puis a remplacer `manual=None` dans les deux CLI
4 undecies. [~] **Reponses Groq sans `content`** — reprise depuis
       `reasoning` et comptage des tokens rejetes faits le 2026-10-03 (P2.3).
       Restent : **decider** de la sequence d'arret pour `gpt-oss` (vraie
       cause, 4 cas sur 6), puis mesurer l'ensemble sur une campagne Groq de
       20 taches (les totaux de tokens Groq publies sont sous-estimes)
5. [ ] **Brancher `run_tests` MBPP des que ndi-tull l'aura ecrit** (P1.5). Ce qui
       restera cote P2 :
   - passer le manuel a `Prompt(manual=)` au lieu de `None` (le cote `Prompt`
     est pret depuis le 2026-10-03, 4 decies)
   - decrire `run_tests` dans le prompt MBPP et **remplacer ou composer avec** la
     consigne actuelle ("use the assert to VALIDATE your code") : aujourd'hui le
     modele valide par `assert` et fait 8/10, il ne sait pas que l'outil existe
   - rejouer les 10 taches a jeu egal → **etude d'ablation** (assert seul vs
     `run_tests`), meme modele, memes taches
   - surveiller le cout : MBPP plafonne a 6000 tokens d'entree **cumules**, chaque
     description d'outil est rejouee a chaque tour. D'ou la prudence sur le *"any
     additional tools"* — l'invitation du sujet n'est pas gratuite
   - **ne pas rendre le prompt dependant de `run_tests`** : le sujet teste avec un
     serveur MCP inconnu ou l'outil n'existe pas. Les `assert` doivent rester un
     repli utilisable, pas un vestige a supprimer
   - les descriptions ne sont **pas a rediger a la main** : elles viennent des
     schemas du serveur via le manuel de P1.4. Ce que P2 controle, c'est la mise
     en forme et les consignes autour (quand appeler, dans quel ordre, avant
     `final_answer`)

### Le banc d'essai `tests/`

**493 tests** (2026-10-03), gitignore, hors rendu — c'est un outil de travail,
pas un livrable. Les tests parametres sur les fournisseurs du JSON couvrent
chaque nouveau fournisseur sans modification : brancher Mistral en a ajoute 7.

`tests/test_agent_cli.py` (75 tests) comble le trou par lequel le `TypeError` de
`get_task_from_file` est passe dans **les deux** CLI a la fois, 220 tests au vert.
Il construit les deux agents sur **chaque** tache de `cache/`, verifie le cablage
obtenu, les sept echecs nommes, la forme d'appel de `get_task_from_file`, et
`run()` avec une fausse boucle. **Aucun reseau, aucune cle valide requise** :
construire un agent ne fait pas d'appel, seul `run()` en ferait.

Deux details qui le rendent robuste : les taches de `cache/` sont triees par
**validation Pydantic** et non par nom (`cache/` contient aussi des
`solution.json`, qui portent eux aussi un `task_id`), et une tache minimale ecrite
dans `tmp_path` est **toujours** ajoutee au jeu de parametres — le garde-fou
survit a un `make clean-all`. Une fixture remplace `constants.MODELS_CONFIG_FILE`
(chemin relatif) par un absolu et pose les cles factices de **chaque**
`api_key_env_var` du JSON : ajouter un fournisseur le fait couvrir sans toucher
aux tests.

**Pouvoir de detection verifie par deux mutants** (plugins pytest hors depot,
aucun fichier de production touche) : `get_task_from_file` rendant le model au
lieu du dict → **57 echecs** ; signature a un seul argument → **64 echecs**. Sans
ce fichier, les deux passaient inapercus.

---

## Points de synchro

- Format `sandbox_input` / `sandbox_output` : c'est l'interface entre les deux
  moities du projet.
- Le **sandbox manual** est produit par P1 et consomme par P2 : **le format rendu
  est l'interface**, P2 insere dans `Prompt(manual=)`, il ne compose pas.
  **Tranche le 2026-10-03** : un texte deja mis en forme (`render_manual`).
  Reste a convenir de la facon dont l'agent le recupere du sandbox.
- **Aucune consigne du prompt ne doit supposer qu'un outil precis existe** : le
  sujet teste avec un serveur MCP inconnu. D'ou l'`assert` garde comme repli MBPP.
- **`run_tests` MBPP** : exige par le § V.3 mais non specifie. P1 choisit la
  signature, P2 la decrit et mesure l'effet. A caler ensemble, sinon le prompt
  decrira un outil qui n'a pas cette forme. **Recouvrement depuis le
  2026-10-01** : la boucle verifie deja le `final_answer` contre `test_list`
  (P2.1). L'outil sert le modele *avant* de soumettre, la verification
  protege *a la soumission* — decider ensemble si les deux coexistent.
- MBPP end-to-end **avant** de toucher a Docker.
- Ne pas optimiser (tokens, choix de modele) avant que l'approche soit prouvee.
