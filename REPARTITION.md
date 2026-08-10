# Agent Smith — Les deux moities du projet

> Document de discussion, pas de spec. Objectif : que chacun choisisse sa partie
> en sachant a quoi ressemblent ses journees, pas juste en lisant une liste de
> taches. Le decoupage de reference reste `TODO.md`.

---

## Personne 1 — Execution & Outils

**La question centrale :** *comment faire tourner du code arbitraire ecrit par un
LLM sans que ca casse ou compromette la machine ?*

### Ce que tu construis concretement

- **Un sandbox Python.** Un process isole ou on `exec()` du code, avec allowlist
  d'imports (hook `importlib`), allowlist de chemins, `resource.RLIMIT_AS` pour la
  RAM, `SIGALRM` pour le timeout, builtins amputes, socket neutralise. Du Python
  bas niveau, presque du systeme.
- **Un serveur + client MCP** avec les deux transports (stdio et HTTP streamable),
  et surtout la **decouverte dynamique** : brancher un serveur MCP inconnu et
  generer automatiquement les wrappers Python + le manuel des outils.
- **Les 9 outils** : `read_file`, `edit_file`, `list_files`, `search_code`,
  `search_function_or_class_definition_in_code`, `find_references`, `run_tests`,
  `get_patch`, `run_command`. Beaucoup de manipulation de texte, de formats de
  sortie precis, de git.
- **L'integration Docker** pour SWE-bench, avec le cleanup des containers.
- **Une CLI/REPL** (`uv run sandbox`).

### Le quotidien

- Tres **testable en isolation** : tu ecris un test, il passe ou pas, sans
  dependre du LLM. Feedback rapide, aucun aleatoire.
- Beaucoup de **debug penible mais deterministe** : « pourquoi mon monkeypatch de
  socket ne tient pas apres un fork », « pourquoi `RLIMIT_AS` tue l'interpreteur
  entier ».
- Du **contournement de securite** : la partie P1.7, c'est litteralement essayer
  de casser son propre sandbox. Si ca t'amuse, c'est le meilleur morceau du projet.
- **Zero cout API**, aucune attente de reponse reseau.

### Le vrai risque

Le sandbox est le coeur note du projet **et** il est bloquant : tant qu'il
n'execute pas de code, P2 ne peut rien tester end-to-end. Le MCP dynamique est le
piege classique — on sous-estime le boulot pour que ca marche avec un serveur
*inconnu*, pas juste le sien.

---

## Personne 2 — Agent & Intelligence

**La question centrale :** *comment faire en sorte qu'un LLM resolve une tache en
10 iterations et 6000 tokens sans partir en vrille ?*

### Ce que tu construis concretement

- **La boucle agentique** Thought -> Code -> Observation, ecrite a la main
  (frameworks interdits) : gestion de l'historique, budget tokens cumule,
  conditions d'arret, aucune exception non geree.
- **Le parsing des sorties LLM** : blocs ` ```python `, XML style Anthropic,
  JSON/Hermes, ReAct — et la conversion de tout ca vers des appels Python. Du
  parsing defensif sur du texte qui n'est jamais tout a fait au format promis.
- **La couche providers** : abstraction, rotation de cles, fallback,
  `stop_sequences`, retry avec backoff, comptabilite des tokens.
- **Les system prompts**, qui determinent en pratique si le projet marche ou non.
- **Les deux CLI** `agent_mbpp` / `agent_swebench` + l'ecriture du `solution.json`.
- **Le `BENCHMARK_REPORT.md`** : >= 5 modeles x >= 3 taches, metriques
  intermediaires, etude d'ablation.

### Le quotidien

- **Non deterministe.** Le meme prompt donne deux resultats differents. Tu passes
  du temps a te demander si ton fix a marche ou si tu as eu de la chance.
- Beaucoup de **lecture de transcripts** : comprendre pourquoi le modele a
  hallucine une observation, pourquoi il a boucle, pourquoi il n'a pas appele
  `final_answer`.
- Du travail **iteratif et empirique** plutot que « je code puis ca marche » : le
  prompt engineering, c'est de l'experimentation.
- **Attente et couts** : chaque test end-to-end prend des dizaines de secondes et
  consomme des tokens. Le benchmark final est long a produire (5 modeles x 3
  taches SWE-bench = des heures de run).

### Le vrai risque

C'est la partie qui **depend de l'autre**. Sans sandbox ni manuel MCP, P2 tourne a
vide (d'ou le « 1 provider en dur + boucle minimale » de l'ordre de travail). Et
le `BENCHMARK_REPORT.md` est en bout de chaine : s'il y a du retard, c'est lui qui
trinque, alors qu'il pese lourd dans la note.

---

## Comparatif

| | **P1 — Execution** | **P2 — Agent** |
|---|---|---|
| Nature | Systemes, securite, protocoles | Experimental, empirique, analyse |
| Feedback | Immediat, deterministe | Lent, bruite |
| Debug | Stack traces, tests unitaires | Lecture de transcripts |
| Livrable visible | Un sandbox qu'on peut casser ou pas | Un rapport chiffre + des runs qui passent |
| Cout | 0 EUR d'API | Tokens, temps d'attente |
| Position | Bloquant en debut de projet | Sous pression en fin de projet |
| Ecriture | Peu (code + tests) | Beaucoup (prompts + rapport) |

---

## Pour trancher

1. Tu preferes *« ca marche ou ca marche pas »* ou *« ca marche 7 fois sur 10,
   pourquoi ? »* -> P1 vs P2.
2. Tu as envie de toucher a Docker, aux process, aux limites systeme ? -> P1.
3. Tu as envie d'ecrire de la prose analytique (prompts + rapport) autant que du
   code ? -> P2. Il y a une vraie composante redaction dans P2 que P1 n'a pas.
4. Tu supportes mieux la pression d'etre bloquant au debut (P1) ou celle d'etre en
   bout de chaine (P2) ?

---

## Deux nuances sur le decoupage actuel

- **P1 est plus charge.** Sandbox + MCP dual-transport + 9 outils + Docker + tests
  securite, c'est plus de volume que la moitie P2. Un reequilibrage possible :
  passer les **9 outils MBPP** cote P2 (ils sont assez independants du sandbox),
  ou l'**integration Docker**.
- **Le choix engage moins qu'il n'y parait.** Le README et la relecture croisee de
  fin de projet ne sont pas decoratifs : la soutenance demande de savoir modifier
  l'agent en 2-5 min sur une tache MBPP. Celui qui prend P2 devra vraiment
  comprendre le sandbox, et inversement. D'ou les 2 sessions de passation prevues
  dans `TODO.md`.
