# Agent Smith — TODO & repartition du travail

| | Qui | Domaine |
|---|---|---|
| **Personne 1** | ndi-tull | Execution & Outils (sandbox, MCP, tools, Docker) |
| **Personne 2** | tchemin | Agent & Intelligence (boucle, LLM, prompts, bench) |

> Le projet n'est **pas** "faire generer du code par un LLM". C'est construire un
> **runtime securise et instrumente** pour un agent de code. MBPP / SWE-bench sont
> le banc d'essai, pas l'objet. Voir [RESUME.md](RESUME.md).

---

## Etat actuel — 2026-09-02

**Cote P2 (tchemin) : tout ce qui pouvait etre fait sans MCP l'est.** Boucle,
extraction, couche LLM, provider, prompts MBPP et SWE, les deux CLI, la config
modeles. **295 tests verts, dette ruff a 0.**

**Cote P1 (ndi-tull) : demarre.** L'executeur et cinq modules de securite
existent, le sandbox execute du code et remonte `final_answer` — c'est ce qui a
debloque la boucle. Restent le CLI/REPL, le manual, **et tout MCP**.

> **Le chemin critique est cote P1.** Sans `mcp_tools/`, sans client MCP et sans
> Docker, ni SWE-bench ni le rapport de benchmark ne peuvent avancer. Le prompt
> SWE n'a jamais tourne contre un vrai depot.

**Deux dettes qui bloquent la mesure :**

1. **`origin/ndi-tull` (`eedbf20`) n'est pas mergee** dans `thomas` — a
   rapatrier avant toute nouvelle mesure, sinon les deux moities divergent.
2. **Le modele declare en premier dans `configs/models.json` est inutilisable.**
   `nvidia/nemotron-3-ultra-550b-a55b:free` met 27 a 40 s par reponse, contre
   30 s d'echeance par appel : le run pilote de `run5` a fini a 0 iteration.
   Releve des deux fournisseurs refait le 2026-09-02, voir P2.3 — **Groq est un
   ordre de grandeur plus rapide** (0,1-4,7 s) et deja declare dans le JSON.

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

**2026-09-02** (dans l'arbre de travail, **non commite**) : `ModelConfig`
supprime, `is_reasoning` retire partout, consigne d'`assert` rendue dependante du
bench. Detail en P2.5 bis et P2.1.

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
| `core/` : `models.py`, `config_models.py`, `errors.py`, `constants.py`, `api_key.py`, `agent_cli_helper.py` | `sandbox/cli.py`, `manual.py`, `security/limits.py` |
| `core/agent/` : `loop.py`, `prompt.py`, `extraction.py` | tout `sandbox/mcp_client/` |
| `core/llm/` : `client.py`, `provider.py` | tout `mcp_tools/` + les 2 `mcp_tools_*.py` racine |
| `agent_mbpp/`, `agent_swebench/` (sauf `docker.py`) | `agent_swebench/docker.py` |
| `sandbox/executor.py`, `configs/models.json` | `sandbox_template.json` |
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
sandbox/       . cli.py  + executor.py  . manual.py
  security/    + imports.py  + filesystem.py  + builtins.py  + network.py
               + ast_guard.py  . limits.py
  mcp_client/  . client.py  . transports.py
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

**MCP** — serveur : `from mcp.server.fastmcp import FastMCP`. Client (les **deux**
transports sont obligatoires) : `ClientSession`, `StdioServerParameters`,
`mcp.client.stdio.stdio_client`, `mcp.client.streamable_http.streamablehttp_client`.
C'est `list_tools()` qui alimente la generation du manuel. *(verifier les
signatures selon la version installee)*

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
- [ ] Generation dynamique du **sandbox manual** depuis les schemas du serveur

```
prompt (manuel)      <- decouverte <- serveur MCP
namespace du sandbox -> wrapper    -> client MCP -> serveur -> outil
```

Trois maillons sur cinq sont vides : `sandbox/mcp_client/`, `mcp_tools/`, et la
generation du manuel. Le namespace d'`executor.py:32` ne contient toujours que
`final_answer`.

- [ ] Le manuel contient le **contrat** (nom, description, types), **jamais le
      code** : l'implementation peut changer sous le modele
- [ ] Une liste d'outils **ecrite en dur** passerait nos 3 taches et
      **echouerait a l'evaluation** (*"The system will be tested with an unknown
      MCP server"*). La decouverte n'est pas un confort, c'est la condition de la
      note
- [ ] Le wrapper est une entree du dict `ns` d'`executor.py` : **aucune magie**,
      donc un `def run_tests():` ecrit par le modele **ecrase le wrapper**. Vu
      pour de vrai dans un ancien exemple, ou le modele redefinissait
      `get_patch()` et fabriquait son propre diff (cf. P1.7)

**Interface avec P2 :** le manuel est le livrable que consomme `Prompt(tools=)`.
Tant qu'il n'existe pas, les deux CLI passent `tools=None` et le prompt affiche
litteralement "None". **Le format rendu est l'interface** — liste de chaines ? de
dicts ? deja mise en forme ? P2 insere, il ne compose pas.

### P1.5 — Les 9 outils obligatoires

*Testes independamment de la boucle.*

- [ ] **FS** : `read_file(filepath, start_line, end_line)` (format `cat -n` :
      `"<line>: <content>"`), `edit_file(filepath, old_str, new_str)`
      (remplacement exact), `list_files(directory, pattern)`
- [ ] **Recherche** (format commun `/abs/path.py:<line> <content>`) :
      `search_code`, `search_function_or_class_definition_in_code`,
      `find_references`
- [ ] **Execution** : `run_tests()` (lance l'`eval_script`), `get_patch()` (git
      diff unifie), `run_command(command, workdir)`
- [~] `mcp_tools_mbpp.py` et `mcp_tools_swebench.py` a la **racine** (crees, vides)

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
- [ ] **Les `retries` d'un tour qui sort par une garde ne sont comptes nulle
      part** : un rendu peut afficher `total_requests: 9` avec `steps: []`, sans
      dire ce qui a echoue

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
JSON, pas une branche `if`. Deux declares : `openrouter`, `groq`.

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
conserve **en plus** : il coupe les serveurs muets, l'echeance borne les lents.

**Recul entre deux tentatives (2026-08-22).** Trois pieces : `Provider.get_retry_after()`
lit `X-RateLimit-Reset` — un **instant** epoch en millisecondes, pas une duree —
et le convertit (format et echelle de chaque en-tete declares dans le JSON) ;
`APIKey` porte un `next_retry_time` ; `get_next_api_key()` refuse toute clef dont
le delai depasse le budget de la tache, la condamne, et recommence. Le piege
etait dans l'ordre des tests : tant que le delai n'etait verifie que sur le
candidat **immediat**, une clef atteinte en sautant une morte passait sans
controle — avec 4 clefs, deux n'etaient jamais examinees.

#### Repli de provider — ce que dit le sujet (releve du 2026-09-02)

§ V.6.1 : *"Ensure your implementation supports multiple API keys per provider
**and consider implementing provider fallback**."* Le contraste des verbes est
tout le message :

| Mecanisme | Formulation | Statut |
|---|---|---|
| Plusieurs cles par provider | *"multi-token management is **mandatory**"*, *"token rotation **must** be implemented"* | obligatoire — **fait** |
| Repli de provider | *"**consider** implementing"* | suggere — a defendre |

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

- [~] **Repli entre providers non implemente** : la configuration est
      multi-provider mais le choix est fige au demarrage par `--provider-url`.
      Deux pieges a traiter le jour ou on le branche — le budget de tokens est
      **cumulatif par tache**, un repli au step 20 herite des tokens deja
      consommes et ne les reinitialise pas ; et il change de modele, donc de
      tokenizer et de verbosite (un repli vers un modele de raisonnement peut
      faire exploser la limite de sortie a lui seul)
- [ ] **Le fournisseur est retrouve par egalite stricte d'URL**
      (`find_provider_by_url`) : un `/` final de trop dans `--provider-url` et
      rien ne matche. Normaliser, ou chercher par nom

#### Modeles gratuits — releve du 2026-09-02 (les deux fournisseurs)

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
vaut 30 s, donc un modele a 27 s comme `nemotron-3-ultra` est hors-jeu en
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
| Cles dans `.env` | 2 | **1** |

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
- [ ] **Rien de tout ca n'est mesure.** Le prompt SWE a ete verifie par lecture
      et par `ast`, jamais par une execution reelle — il faut `mcp_tools/`.
      `cache/swebench_task.json` (`sympy__sympy-14711`) attend comme banc d'essai
- [~] **Injection du sandbox manual** : le slot existe (`Prompt(tools=)`) mais les
      **deux** CLI passent `tools=None`, le prompt affiche litteralement "None".
      Cote SWE c'est plus grave : le prompt decrit une methode entierement fondee
      sur 9 outils dont il ne donne jamais la liste. Attend P1.4
- [~] **Exemple MBPP** : coquilles corrigees (`Obvservation`, virgule du second
      `assert` passee apres le saut de ligne, cloture ``` ``` ``` recollee,
      indentation du corps). **Le piege principal tient toujours** : le
      `final_answer("def smallest_abs(a):` reste coupe par un vrai retour a la
      ligne, donc le modele lit une chaine non terminee et copie une forme qui ne
      compile pas. Il faut une chaine sur une ligne, un `\n` litteral, ou des
      triples quotes. **Et l'effet n'est pas mesure** — l'ablation a jeu egal
      reste a faire

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
      execution** : `get_patch()` est un outil MCP de P1.5, il n'existe pas encore

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

#### `ModelConfig` supprime (2026-09-02) — fin d'un chantier de trois semaines

Le champ `reasoning: bool` cote `models` a vecu trois etats et c'est le troisieme
qui est le bon :

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

**Ce qu'on defend :** une abstraction a un seul champ jamais lu ne portait rien,
et sa suppression supprime avec elle la classe de bug qui venait de mordre.

- [ ] **Le typage a perdu en precision** : `model_config: dict` cote helper et
      cote `LLMClient`, plus rien ne valide ce qui sort du JSON pour un modele.
      Prix assume tant que le dict est vide — **le jour ou une cle y revient, la
      validation doit revenir avec**, sinon une faute de frappe deviendra un
      `KeyError` en pleine tache au lieu d'une erreur au demarrage. Et choisir
      `extra=` explicitement a ce moment-la : `extra="forbid"` attrape la
      coquille, `extra="ignore"` (le defaut) la laisse passer sans bruit — c'est
      exactement ce qui a produit la regression de l'etape 2
- [ ] **Le repli sur modele inconnu est silencieux** : aucun avertissement n'est
      affiche quand `--model-name` est absent du JSON. Assumer, ou logger. A
      savoir dire : absent de `models.json` **n'est pas** invalide chez le
      fournisseur — ce fichier est notre base de connaissances, pas le catalogue
      d'OpenRouter. Le nom part dans la requete quel que soit le contenu du JSON,
      et un nom faux revient en 400/404, donc en `Permanent` (pas de rotation de
      cles : elles seraient toutes brulees pour rien)
- [ ] Regle de precedence CLI > fichier : sans objet tant qu'aucun reglage n'est
      expose en double. A rouvrir des qu'un l'est

### P2.6 — `BENCHMARK_REPORT.md` *(vide)*

**≥ 5 modeles × ≥ 3 taches SWE-bench communes.**

- [ ] Setup (modeles/providers, taches + justification)
- [ ] Tableau modele × tache : pass/fail, iterations, tokens in/out, temps mur
- [ ] Fiabilite provider : temps de reponse moyen, retries, disponibilite
- [ ] ≥ 2 metriques intermediaires : etape du 1er acces au fichier du patch final
      (exploration) / etape ou les echecs de tests baissent (progres partiel) /
      iterations entre "tests au vert" et `final_answer` (discipline, 0 ideal)
- [ ] **Etude d'ablation** avant/apres un changement, memes taches, meme modele
- [ ] Conclusions justifiees par les donnees + les `solution.json` de backing
      **presents dans le repo**

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
| `run7` | **Groq `gpt-oss-120b`**, 10 taches neuves | **9/10** | 18 | **53 s** |

**19/20 sur deux jeux de taches independants** (seeds 1..10 et 11..20, aucun
recouvrement) : le meilleur resultat du projet, et le seul sans aucun faux
positif. Rapports complets dans `cache/run5..7/RAPPORT.md`.

Le basculement vers Groq explique l'essentiel : `run5` et `run6` portent sur
**les memes 10 taches** avec le meme agent, 4/10 contre 10/10. Les quatre
echecs `run5` par plafond de sortie crevé passent tous en un seul tour chez
Groq. Matiere directe pour le `BENCHMARK_REPORT.md`.

Le seul echec restant (`run7`, MBPP 462) est un **echec de quota, pas de
raisonnement** : l'enonce porte un `test_list` de ~1000 tokens, la tache
consomme 2961 tokens d'un coup, le seau Groq (8000/min) tombe a 2438 et les
cinq tentatives suivantes partent en 429. Les deux gardes ont joue leur role —
le plafond a coupe la rafale, les metriques restent valides sur les 10.

Barre du sujet : 4/5 (80 %). Sur les campagnes OpenRouter, 84 % ; sur Groq,
**95 % (19/20)**.

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
> suffisant au recit, pas a une verification. **Prochaine campagne : sortir les
> `solution.json` de `cache/` et les versionner**, le sujet exige les fichiers de
> backing dans le repo.

- [ ] Rejouer 59 et 413 en quota epuise pour verifier le nombre de requetes
      emises : le correctif est teste unitairement, pas en campagne
- [ ] Etendre a plus de taches — 10 ne separent pas deux modeles a 87 %

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

1. [ ] **Campagne de controle MBPP** — le chantier le plus rentable et il ne
       depend de personne. Prealable : **refaire le releve des modeles gratuits**
2. [ ] **Rapatrier `origin/ndi-tull`** (`eedbf20`) avant toute mesure
3. [ ] **Commiter la session du 2026-09-02** (`ModelConfig` supprime, consigne
       d'`assert` par bench) : 5 fichiers modifies, 295 tests verts, ruff a 0
4. [ ] **Corriger le piege de l'exemple MBPP** (chaine coupee par un vrai retour
       a la ligne, cf. P2.4) — et **mesurer** l'effet : c'est une ablation toute
       trouvee pour le rapport
5. [ ] **Brancher `run_tests` MBPP des que ndi-tull l'aura ecrit** (P1.5). Ce qui
       restera cote P2 :
   - passer la liste des outils a `Prompt` au lieu de `tools=None`
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

**295 tests**, gitignore, hors rendu — c'est un outil de travail, pas un livrable.

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
  est l'interface**, P2 insere dans `Prompt(tools=)`, il ne compose pas.
- **Aucune consigne du prompt ne doit supposer qu'un outil precis existe** : le
  sujet teste avec un serveur MCP inconnu. D'ou l'`assert` garde comme repli MBPP.
- **`run_tests` MBPP** : exige par le § V.3 mais non specifie. P1 choisit la
  signature, P2 la decrit et mesure l'effet. A caler ensemble, sinon le prompt
  decrira un outil qui n'a pas cette forme.
- MBPP end-to-end **avant** de toucher a Docker.
- Ne pas optimiser (tokens, choix de modele) avant que l'approche soit prouvee.
