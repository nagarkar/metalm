# Neo4j for metalm: assessment

Status: draft, 2026-11-04. Input to the adoption decision in [../neo4j adoption plan.md](../neo4j%20adoption%20plan.md); use-case numbers refer to [usecases.md](usecases.md).

Short answer: nothing in metalm's own data needs a graph database yet. metalm's real part in an adoption is the supporting work (a database-choice rule, backup and health for the Neo4j store, where the shared adapter lives). One graph, rule provenance across repos, is a fair second tenant once a store exists for another repo's sake.

## (a) What metalm is and where its data and decisions live

metalm is the source of truth for engineering rules across about fourteen `*lm` repos. Its data is almost all text in git: eleven guideline files (about 1,100 lines, roughly 90 lines carrying an `(owner)` rule), the `metalm-setup` skill (eight phases, four modes, 131 lines), the conformance registry `docs/repos.md` (one row per repo: status, metalm commit checked against, date, PR, open failures), and `docs/generated/` (areas, decisions, glossary, CUJs, produced by `metalm-gendocs` from docstrings and test markers). The machine-specific data is one gitignored `ops.toml` (26 `[[repo]]` and `[[database]]` entries: paths, ports, launch agents), the nightly backup folders plus `runs.jsonl`, and the dashboard's `status.json`. There is no database of metalm's own; `metalm-ops` copies other repos' SQLite files and never opens them. Agent decisions live in three places: `(owner)` rules in package docstrings and guidelines (one answer per question, no dates, history left to git), GitHub issues and PRs (inventory issues, phase-5 mappings, conformance PRs), and session transcripts, which nothing reads back. LLM-driven steps are the `metalm-setup` phases (inventory, grilling, restructure, a separate mapper subagent, one subagent per guideline for content checks) and the fix prompts the dashboard copies for a new session. None of these runs is recorded step by step.

## (b) Use cases that plausibly apply

### Rule provenance and impact graph (use cases 2, 8, 10)

- Shape: `(:Rule {file, anchor, text, owner})`, `(:Guideline)`, `(:Repo)`, `(:Exception)`, `(:CheckItem)` (a phase-6a line), `(:Test)`, `(:Citation {path, line})`, `(:Commit)`, `(:Issue)`. Edges: `(Rule)-[:IN]->(Guideline)`, `(Rule)-[:CITES]->(Rule)` (39 anchor citations inside metalm), `(Citation)-[:CITES]->(Rule)` and `(Citation)-[:IN]->(Repo)` (58 citations of metalm anchors in sibling repos' code, skills and design docs), `(Exception)-[:OVERRIDES]->(Rule)`, `(Repo)-[:HAS]->(Exception)`, `(CheckItem)-[:ENFORCES]->(Rule)`, `(Test)-[:ENFORCES]->(Rule)` (the `Enforced by:` lines), `(Commit)-[:CHANGED]->(Rule)`, `(Repo)-[:CHECKED_AT]->(Commit)`.
- Question it improves: "I am about to change `coding.md#where-env-lives`: which repos cite it, which hold an exception to it, which checks and tests enforce it, and which repos were last checked before it changed?" Also the Uber-style lookup: "which rules apply in supplylm, net of its exceptions?" These are real three- and four-hop joins across repos, and today an agent answers them by grep in each repo plus reading `docs/repos.md`.
- Replaces or sits beside: sits beside git as a derived store, rebuilt from the checkouts by one script. It replaces nothing; `docs/repos.md` and the audit mode stay.
- Honest limits: about 150 rules, 14 repos and 100 citations. Grep answers each hop in seconds and audit mode already does the "checked before the last guideline change" comparison with one `git log`. At this size the graph is a data structure (the plan's own exception), and a dict built by a script would serve. Rules have no stable identity: anchors name sections, not rules, so `CHANGED` and `ENFORCES` edges need either rule ids or text matching, and the owner's layout rule keeps numbered decision logs out.
- Rating: medium value, medium effort (mostly the extractor and rule identity, not the database). Low value as a reason to stand up Neo4j; reasonable as a second tenant of a store that exists anyway.

### metalm-setup as a compiled procedure (use cases 3, 7, 14)

- Shape: `(:Skill {name:'metalm-setup'})-[:HAS_STEP]->(:Step {kind})` with kinds script (the `git grep`, `gh label list`, staleness test and symlink checks of phase 6a), agent (inventory, restructure), subagent fan-out (6b, one per guideline), owner gate (hook-file approval, each drop, merge authorization), router (mode: setup, adopt, audit, check); `(:Step)-[:NEXT {when}]->(:Step)`.
- What it improves: phase 6a is nineteen checks, of which about fourteen are deterministic commands that a model re-reads and re-runs from prose each time. Results vary by run (the registry shows `unrecorded` commits and differently worded failures). Putting those in a script gives the same answer every run and lets a small model do check mode.
- Replaces or sits beside: the win is a `check` verb in code that the skill calls, which is exactly what `coding.md` already asks for (behavior in one typed API, skill as a thin surface). That needs no graph database. Storing the step graph in Neo4j adds a second copy of a procedure whose truth is the skill file in git, for a skill that has run perhaps fifteen times in total.
- Rating: high value for the script, small to medium effort, zero Neo4j. Low value, medium effort for the graph-stored form.

### Conformance run storage (use cases 12, 15)

- Shape: `(:Run {mode, date})-[:OF]->(:Repo)`, `(:Run)-[:READ]->(:Commit)`, `(:Run)-[:HAS]->(:CheckResult {status: pass|fail|excepted, path})-[:FOR]->(:CheckItem)`.
- What it improves: "which checks fail in most repos", "which check has never failed" (a candidate to drop), "what newly failed in ytlm since its last run". Today only the summary cell in `docs/repos.md` survives a run.
- Replaces or sits beside: three tables, one join deep. A `runs.jsonl` like the backup's, or a small SQLite file, answers all of it; no path queries. Only worth doing after the check verb above exists to emit structured results.
- Rating: low to medium value, small effort as JSONL; no case for a graph on its own. It becomes useful input to the rule graph (`CheckResult` joins `Rule` to `Repo`).

### Ops topology as a knowledge layer (use case 5)

- Shape: `(:Repo)-[:SERVES]->(:App {port})`, `(:App)-[:RUN_BY]->(:Agent)`, `(:Repo)-[:OWNS|READS]->(:Database)-[:ON]->(:Volume)`, `(:Repo)-[:CALLS]->(:App)` (mailerlm and publishinglm call peoplelm; ytlm and beelm read corpuslm's transcript file).
- What it improves: blast-radius questions on the dashboard: "the external volume is unmounted, which apps and backups are affected", "peoplelm is red, what depends on it".
- Replaces or sits beside: `ops.toml` holds the nodes already but no consumer edges (a database has one `repo`). Adding a `consumers` list there gives the same answers over about forty nodes with a ten-line traversal, and keeps the (owner) rule that one central gitignored file says what exists.
- Rating: low value for a graph, small effort for the `ops.toml` field.

### Decision traces behind owner rules (use cases 2, 6)

- Shape: `(:Session)-[:ASKED]->(:Question)-[:ANSWERED_BY]->(:Decision)-[:BECAME]->(:Rule)`, with `(:Decision)-[:SUPERSEDES]->(:Decision)`.
- What it improves: "why is this rule here, and what did it replace" without reading git blame.
- Conflict: `guidelines/index.md` and `design.md` say one answer per question, no dates or history, no numbered decision log, decisions out of memory and into code. A trace graph is that log in another form. It would need the owner's word, and git history plus the PR already answers the question for the few times it is asked.
- Rating: low value, medium effort, and it contradicts a standing (owner) rule.

## (c) Use cases that do not apply

- 1 Execution graphs: Claude Code is the harness; metalm runs no orchestrator of its own.
- 4 Portable artefacts: skills are already files in git, symlinked into every session; there is no second runtime to port to.
- 9 Entity resolution for audit reports: the only alias problem is a repo name spelled two ways (authorlm, authorllm), which a column fixes.
- 11 GraphRAG: the whole guideline set is about 1,100 lines and the index table already routes an agent to the right file; it fits in context.
- 13 Compiling skills from successful runs: no run traces are stored, and the skill is owner-ruled prose, not behavior to be mined.
- 16 Cost reduction: setup and audit run a few times a month; the saving is real per run and negligible in total.

## (d) Recommendation, ranked

1. Do the supporting work only if another repo's assessment justifies a store. That work is metalm's and is not optional once Neo4j holds anything:
   - A graph row in the database-choice section of `guidelines/architecture.md`. Today it reads "No database until a query needs a join" and "No Docker containers or background … daemons unless the owner asks", so a Neo4j daemon needs an explicit (owner) rule, and the plan's five exit rules belong there.
   - Backup. `src/metalm_ops/backup.py` copies SQLite only, through the online backup API. Community Edition has no online backup: `neo4j-admin database dump` needs the database stopped. The nightly job would either stop, dump and start at 03:30, or back up the plan's nightly CSV/Parquet export instead, which is simpler and fits "graph as a derived store". `ops.toml`'s strict loader needs a database kind for it, and the dashboard a health row and a served-apps row.
   - A home for the one Cypher module and driver adapter. Community has one database, so every repo shares one graph; by `coding.md#sharing-one-database-between-repos` that needs a named schema owner and label prefixes per repo. metalm should state the rule, not hold the code (it depends on nothing but `git`, `gh` and the Xcode tools).
2. Independently of Neo4j, turn the deterministic part of `metalm-setup` phase 6a into a check verb that writes one structured result per check per run. This is the talk's main lesson (routing and checks out of the model) at its cheapest, and it produces the data the other metalm ideas would need.
3. If and when a store exists, load the rule provenance graph as a derived second tenant, rebuilt from git on demand. It is the only metalm data with honest multi-hop questions, it risks nothing (delete and rebuild), and it is a cheap test of whether Cypher beats grep for the owner in practice.

For metalm's own data, taken alone: nothing yet.

## (e) Open questions for the owner

- Does a Neo4j daemon (launch agent or Docker) get an (owner) exception to the no-background-daemons rule, and is it stated in metalm or per repo?
- Is the nightly export the backup of record for the graph (graph always derived, so losing it means a rebuild), or must the store itself be dumped, with a nightly stop?
- Which repo owns the shared graph's schema and the adapter: the first adopter, corpuslm (already a schema owner), or a new repo?
- Should rules get stable ids (for example an anchor per rule) so tools can cite and track a single rule? That changes how guidelines are written and helps the provenance graph and plain grep alike.
- Is a check verb for phase 6a wanted now, regardless of the Neo4j decision?
- Is recording why a rule changed (a decision trace) wanted at all, given the standing rule of one answer per question with history left to git?
