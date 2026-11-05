# Neo4j adoption plan

Status: decided in a grilling session with the owner, 2026-11-04. Living document.

## Decision

The question began as "adopt Neo4j?" and ended as "formalise our workflows".

- **Build flowlm**, a new small repo: a runner for procedures written as YAML files,
  with runs, steps, gates and verdicts stored in SQLite. See "Decisions from the
  grilling" for the nine rulings and "Second pass" for the evidence.
- **Neo4j is deferred, not dropped.** No repo's data needs a graph today, and a graph
  database does not orchestrate. It returns only on evidence (decision 10), as a
  derived view of flowlm's runs and artifact references.
- **No homegrown graph engine**, and no generic agent-memory service.

The sections from here to "Per-repo assessments" are the original Neo4j evaluation.
They stand as the reference for the day a trigger fires.

## Why Neo4j Community first

- Cheapest way to find out whether a graph model pays off for our problems.
- Cypher is now the ISO GQL standard (Cypher 25 since Neo4j 2025.06). Modelling
  and query knowledge transfers to Memgraph, FalkorDB, Apache AGE, Kuzu and others.
- Best-in-class planner, tooling (Browser, Bloom), docs, Graph Data Science
  library, vector index (VECTOR type since 2025.10), and LLM-framework integrations.
- Single node, one database is far from a ceiling for most of our workloads.

## Community Edition limits (GPLv3)

One database, no clustering, no RBAC, no online backup, no GDS enterprise
features, no sharding. Everything multi-node or multi-tenant is Enterprise
(closed, paid) or Aura (managed).

## Why not a homegrown engine later

The gated features (consensus-based clustering, online backup, sharding, RBAC,
a planner that stays fast at scale) are years of database-team work. A homegrown
store would be the least-tested component carrying the most important data.
The one exception: if the "enterprise" need is a single in-process adjacency
structure with a few fixed traversals, that is a data structure, not a
database, and is fine to write.

## Keeping the exit open

1. All Cypher lives in one module, not scattered through application code.
2. Plain Cypher over APOC and Neo4j-only procedures wherever it does the job.
3. Bolt driver behind a thin adapter of our own so the connection layer can swap.
4. An export path exercised regularly (nightly dump to CSV or Parquet); data is
   never only inside the store.
5. Graph as a derived or secondary store where possible; source of truth stays
   in Postgres or files, so migration is a rebuild, not a conversion.

## Exit options when Community is outgrown

| Option | License | Fit |
|---|---|---|
| Memgraph | BSL 1.1 (not OSI) | Near drop-in: Cypher, Bolt. In-memory. HA paid. |
| FalkorDB | SSPL (not OSI) | Cypher on Redis; many small graphs, GraphRAG. |
| Apache AGE | Apache 2.0 | openCypher in Postgres; fully open; slower on deep traversals. |
| Kuzu | MIT | Embedded analytical engine; upstream archived Oct 2025, forks only. |
| JanusGraph / NebulaGraph / Dgraph | Apache 2.0 | Distributed scale; Gremlin, nGQL or DQL, not Cypher. |
| Neo4j Enterprise or Aura | Commercial | Pay when the ceiling is actually hit. |

Decide only when the ceiling is reached. Any of these is cheaper and safer than
a rewrite.

## Use cases from the Neo4j talk

Source: [Make Your AI Agents Predictable With Graph Engineering](https://www.youtube.com/watch?v=g_NgCLTibiM)
(Zachary Blumenfeld, Neo4j), in the ytlm corpus. Sixteen use cases are summarised in
[neo4j/usecases.md](neo4j/usecases.md). The ones most likely to matter for our repos:

- Context graphs: agent decision traces linked to the domain entities they concern
  (precedent lookup, audit).
- Agent memory as one graph: conversation, extracted entities, reasoning traces.
- Procedural graphs: skills compiled from prose into typed step graphs, run
  deterministically through a CLI, with provenance back to the traces that justified them.
- Knowledge layer: one graph joining documents and structured records from several
  systems of record, so GraphRAG can follow evidence across them.
- Run storage: every skill run persisted as run and step nodes for observability.
- Cost: routing moved out of the LLM into scripts and small typed models.

## Per-repo assessments

One session per repo assessed fit against the use cases; each wrote `neo4j/<repo>.md`.
Evaluated 2026-11-04. **All nine recommend "nothing yet" for the repo on its own.**

| Repo | Verdict | If a shared graph exists | Better done without Neo4j |
|---|---|---|---|
| [authorlm](neo4j/authorlm.md) | Nothing as a dependency | Read-only export of the argument graph (paragraphs, sections, essays, concepts) | Structured targets on `evidence` rows |
| [podlm](neo4j/podlm.md) | Not the pilot | Derived contributor: episodes, clips, assets, credits, comments | Keep growth reviews and options (append, not overwrite) |
| [beelm](neo4j/beelm.md) | Nothing; producer with no schema | Its rows arrive through corpuslm | Resolve people and topics in corpuslm first |
| [ytlm](neo4j/ytlm.md) | Nothing | Citation edges; try the layer in corpuslm as a throwaway | Give people an identity (a table) |
| [metalm](neo4j/metalm.md) | Nothing for its own data | Rule provenance graph as a derived second tenant | Check verb for `metalm-setup` phase 6a |
| [corpuslm](neo4j/corpuslm.md) | Nothing; never mirror the system of record | Feeder: `corpuslm graph export` (corpus, source, claim, concept, person) | Record arbiter picks; calibration board |
| [tradelm](neo4j/tradelm.md) | Nothing; already the talk's design in SQLite | Feed a ticker/company graph, second | Link signals to selection rows; hedge rating history |
| [marketlm](neo4j/marketlm.md) | Nothing; no data yet | Evidence graph later | `rests_on` ids in the record schema |
| [publishinglm](neo4j/publishinglm.md) | Nothing on its own | Source for a cross-repo people graph, second wave | Entity resolution of group resources in SQLite |

### What the assessments agree on

- No single repo has a multi-hop query that hurts today. Data is small and star-shaped.
- The only place Neo4j could pay is **across** repos. Two candidate first use cases:
  1. **Knowledge layer**: sources, people, claims and concepts from corpuslm (ytlm and
     beelm rows), joined to authorlm's argument graph and podlm's episodes. Suggested
     first step: a throwaway export and three hand-asked questions in Browser.
  2. **People graph**: one person identity across peoplelm, mailerlm, podlm guests,
     publishinglm group members, corpuslm speakers.
- The talk's most transferable lesson (routing and checks out of the model, decisions
  recorded with calibration) is cheaper in SQLite and scripts than in a graph.
- Every feeder should be a read-only export verb with no Neo4j driver in the repo; the
  Cypher module and adapter live in one place.

### Prerequisites surfaced (metalm's to settle if a store is adopted)

- An `(owner)` exception to "no background daemons / no database until a query needs a
  join" in `guidelines/architecture.md`, carrying this plan's five exit rules.
- Backup: Community has no online backup. Either stop-dump-start nightly, or treat the
  graph as derived and back up the export only.
- One database in Community means all repos share a graph: a named schema owner and
  per-repo label prefixes are needed.
- Privacy: no access control in Community. Bee claim text, trade holdings and scraped
  Facebook identities each need a ruling on whether they may enter the graph.
- The concepts ruling ("no relation is ever inferred or stored") limits the knowledge
  layer to co-occurrence edges unless reopened.
- Person identity has no owner yet (peoplelm or corpuslm).

## Orchestration framing (owner, 2026-11-04)

The first pass read repos only, not session history. The owner's real interest is
orchestration: workflows in beelm, ytlm, authorlm and podlm, some spanning the
workspace, live informally in skills, code and back-and-forth sessions. Example: podlm
takes a script, reviews it against an authorlm manuscript, pulls ytlm videos or Bee
transcripts, merges them into the monologue, then gets images and video through
authorlm or llmlm verbs.

Working answers, to be tested by a second pass that mines recent sessions:

- **Neo4j does not orchestrate.** It stores. The gain comes from writing each workflow
  down as a procedure graph (typed steps that call existing verbs, gates, decision
  points) and running it through one runner. Neo4j is a candidate store for the
  procedures and their runs, joined to the artifacts they touch across repos.
- **Cost.** Cheaper models become safe when routing and checks are scripts, each
  model step is small and typed, precedent is retrieved for it, and stored runs show
  per step whether the cheaper model held quality. The store supplies precedent and
  evidence; the saving comes from the compiled procedure.
- **authorlm decision traces.** The implementation already matches the talk's design.
  Its gap is relational: evidence rows target display text, not ids, and few link to a
  belief. A shared trace schema across repos is the standardising move; whether it
  sits in Neo4j or SQLite is secondary.

This changes the candidate first use case from a knowledge layer to **cross-repo
procedures and runs**.

## Second pass: workflows mined from session history (2026-11-04)

Five sessions read recent session transcripts and skills and wrote down the workflows
actually run: [podlm](neo4j/workflows-podlm.md), [authorlm](neo4j/workflows-authorlm.md),
[ytlm](neo4j/workflows-ytlm.md), [beelm](neo4j/workflows-beelm.md),
[workspace-wide](neo4j/workflows-workspace.md).

### Findings

- **authorlm is the hub.** podlm sessions made 620 calls into authorlm against 671 into
  podlm itself; publishinglm 131; ytlm 110. Document sync (`doc diff`, `pull`, `push`)
  is the most-called cross-repo surface.
- **Six cross-repo workflows** were found: the monologue episode from brief to YouTube
  (the owner's example, 20 steps over podlm, authorlm, ytlm, corpuslm), the corpus
  document chain, spoken directive to job (already a coded procedure through eventlm
  and computerlm), the book launch chain, workspace fan-out changes, and a tool defect
  found mid-workflow.
- **The procedure lives in the owner's messages and skill prose.** Evidence: 12 to 24
  percent of cross-repo commands are `help` lookups; the same verb is spelled three
  ways; steps skipped or reordered; a spend gate retried eight times in a minute;
  preconditions found late; skills written after the fact as a log of corrections; the
  owner acting as scheduler ("what's next").
- **Every session named the same missing pieces**: a run record, typed verb results
  (`--json`, named exit states), gates as data (owner, spend, precondition), one
  decision record shape, a resumable wait for human hand-offs, and a model assigned per
  step.
- **authorlm's trace design generalises** to one envelope: run, step, proposal, verdict,
  evidence, belief, law, with the rule that nothing a model inferred binds until a
  named person accepts it. Nine gaps were listed, chiefly untyped evidence targets, no
  uniform run id, chat verdicts not captured, and no model or prompt recorded on a
  proposal.
- **Cheaper models**: most steps need no model at all once the procedure is explicit
  (sequencing, verb lookup, checks, spend decisions). Narrow judgement steps suit a
  mid-tier model. Writing, critique and defect diagnosis stay on a frontier model.
  Trust comes from stored runs: shadow the cheaper model on stored inputs and compare
  on the outcome signal the workflow already produces.

### Where Neo4j lands

All five say the same: **the runner and its records belong in YAML files plus SQLite**,
which fits the guidelines (no daemon, backed up nightly). Neo4j adds nothing to
execution, gating, resumption or cost. It adds open-ended questions across runs and
artifacts, and precedent lookup by neighbourhood, neither of which hurts at current
volume. It stays a later **derived projection** of runs, steps and artifact references,
which requires only that artifact references be stable and repo-qualified from day one.

### Proposed shape (pending the grilling)

- A new small repo holds the runner and cross-repo procedure definitions; llmlm stays
  the model layer, eventlm the bus, computerlm becomes a client.
- A step names a verb as `repo/verb.path` with typed arguments, checked against a
  per-repo verb manifest generated from each CLI's help.
- Step kinds: verb, model, owner gate, spend gate, precondition gate, wait.
- One trace envelope for every repo, modelled on authorlm's.
- Pilot candidates: the script-and-media round of a monologue (cross-repo, highest
  volume, embeds authorlm's form round), authorlm's form round alone, ytlm's "import
  the latest videos", beelm's daily chain.

## Decisions from the grilling (2026-11-04)

1. **Runner on YAML plus SQLite; Neo4j deferred to a derived view.** Accepted by the
   owner. Artifact references are stable and repo-qualified from day one so a later
   export is a rebuild.
2. **Procedures are living documents, updated through `harvest-tools`.** The owner's
   requirement: procedures evolve daily, so the recorded procedure must be updated as
   part of the harvest. Design: a third harvest pass, "procedures", beside the tools
   and skills passes. It reads the session since the checkpoint and the run records,
   finds where the session departed from the recorded procedure (a step done by hand,
   a step reordered or skipped, an owner correction at a gate, a new step, a verb used
   that the procedure does not name), and writes the change as a diff to the procedure
   file. A session that ran no recorded procedure but repeated a sequence of verbs
   yields a proposed new procedure. **Split by risk (owner):** a change that only
   records what happened and cannot alter spend or outcomes (a corrected verb
   spelling, a new precondition check, an added `--json` flag, a note on a step)
   applies automatically and is listed in the harvest summary. A change to what the
   next run does or costs (a step added, removed or reordered, a gate or spend
   threshold, a tier, a new procedure) waits for the owner's approval as a diff.
   Every change is a git commit to the procedure file.
3. **Model tiers are declared in the procedure.** Each model step carries a tier code
   name (`neophyte`, `medium`, `expert`). The mapping from tier to a concrete model is
   an llmlm profile, in one place, so a model release changes one line and no
   procedure. Runs record tier, model, cost and the outcome signal per step; a report
   over stored runs proposes moving a step down (or up) a tier, and the harvest pass
   carries that proposal. Neo4j plays no part: this is a field in the file and columns
   in the run table. Consequence: tiers are enforceable only where the runner makes
   the model call or starts the subagent, so the runner must drive the procedure and
   the interactive frontier session becomes its client, not its executor.
4. **authorlm's trace implementation is not the model to copy.** The owner rates it
   the weakest part of authorlm: unreliable and too much human work. The shared trace
   envelope keeps its good rule (nothing a model inferred binds until a named person
   accepts it) and drops its cost: verdicts are recorded by the runner at owner gates
   as a by-product of work the owner is already doing, never as a separate review
   queue. authorlm migrates to the shared envelope after the pilot proves it.

5. **The runner lives in a new small repo** (owner). It depends only on llmlm (model
   calls) and eventlm (events). A procedure owned by one repo stays in that repo under
   `procedures/` and is registered with the runner; a cross-repo procedure lives with
   the runner. computerlm becomes a client: an approved directive starts a procedure,
   and its approval-page pattern is reused for owner gates. The repo and its command
   are named **flowlm** (owner).

6. **Pilot sequence (owner): all of them, and more after.**
   1. ytlm "import the latest videos": proves the runner (run record, spend gate, job
      wait, retries, typed exits).
   2. authorlm form round: proves owner gates on a Doc and the trace envelope.
   3. Monologue script-and-media round (podlm, authorlm, ytlm): the real target; embeds
      the form round; proves cross-repo steps and artifact references.
   4. beelm daily chain: proves unattended runs and failure triage.
   5. Then the remaining workflows found: the rest of the monologue episode, the corpus
      document chain, the book launch chain, workspace fan-out changes, and others as
      the harvest pass surfaces them.

7. **Two model step kinds, each with a tier (owner).** `model`: a typed call through
   llmlm with an output schema, no tools, any provider, billed per token through the
   existing ledger and caps; for narrow judgement. `agent`: a headless Claude Code
   agent with a brief, a tier mapped to a Claude model and a limited tool set; for open
   work that needs tools or several turns. Authoring rule: use `model` wherever the
   output can be given a schema, `agent` only otherwise. Savings come from moving steps
   out of `agent` into `model` or into no model.

8. **Gates: one record, a page and a verb (owner).** Gate kinds: owner decision, spend
   above threshold, wait for a human hand-off. A tailnet page (the computerlm approval
   pattern, phone first) lists waiting gates across runs with links and cost and takes
   the choice and the owner's reason; `superlm-notify` alerts when a gate opens. A CLI
   verb answers the same gate so a chat answer lands in the same record. An approval is
   keyed to the content hash of what was shown: a cosmetic change does not reopen it, a
   real change does, a retry never asks twice. The gate answer is the verdict in the
   trace.

9. **Recorded procedures run through the runner, with one escape (owner).** A metalm
   rule: when a recorded procedure covers the ask, the session starts a run and reports
   its state; it does not type the procedure's verbs itself. Each repo's skill shrinks
   to a pointer to the procedure plus the constraints that bind any caller. Escape: on
   the owner's explicit word, or when the runner stops at a step it cannot handle, the
   session continues by hand and records that as a departure on the run with the
   commands it ran; the harvest pass turns departures into proposed procedure changes.

10. **Neo4j returns only on evidence (owner).** Two triggers: (a) a question across
    runs and artifacts is asked more than once and needs a hand-written SQL query each
    time; (b) a `model` step on a cheaper tier keeps failing its quality comparison
    because plain lookup missed precedent on neighbouring artifacts. First move when
    either fires: a throwaway export of runs, steps, verdicts and artifact references
    to a local Neo4j Community instance, real questions asked by hand, kept only if it
    clearly beats SQL. flowlm keeps artifact references stable and repo-qualified and
    gains one export verb at that point. The prerequisites in "Per-repo assessments"
    then apply (daemon exception, derived-store backup, privacy rulings).

## flowlm in brief

- **Procedure file**: inputs with types, limits (spend per run, ask-above threshold),
  ordered steps. A step names a verb as `repo/verb.path` with typed arguments, checked
  against a per-repo verb manifest generated from each CLI's help.
- **Step kinds**: `verb`, `model` (typed llmlm call), `agent` (headless Claude Code),
  `gate` (precondition), `owner` (decision), `spend`, `wait` (human hand-off). `model`
  and `agent` carry a tier: `neophyte`, `medium`, `expert`, mapped to models in llmlm.
- **Records**: run, step result (argv, exit, parsed output, artifact references in and
  out, tier, model, cost), gate, verdict (choice and the owner's words), departure.
  Artifact references look like `authorlm:file/<manuscript>/<name>@<hash>`,
  `ytlm:video/<id>#t=<start>-<end>`, `podlm:episode/<slug>`.
- **Surfaces**: a CLI, a tailnet gate page, events on eventlm, `superlm-notify`.
- **Learning**: the `harvest-tools` procedures pass (split by risk), and a tier report
  over stored runs that proposes moving a step down or up.
- **A skeleton for the first cross-repo procedure** is sketched in
  [neo4j/workflows-workspace.md](neo4j/workflows-workspace.md), section (f).

## Next steps

- [ ] Create the flowlm repo with `metalm-setup`; port to be assigned for the gate page
      and added to the served-apps table.
- [ ] metalm: guideline section for procedure files, the verb manifest, tiers, and the
      run-through-the-runner rule (decision 9).
- [ ] llmlm: tier profiles (`neophyte`, `medium`, `expert`).
- [ ] harvest-tools: the procedures pass.
- [ ] Pilot 1, ytlm import: the stored filing proposal verb, board fields as
      contracts, spend threshold in config (see [workflows-ytlm.md](neo4j/workflows-ytlm.md) (f)).
- [ ] Pilot 2, authorlm form round (see [workflows-authorlm.md](neo4j/workflows-authorlm.md) (f)).
- [ ] Pilot 3, monologue script-and-media round (see [workflows-podlm.md](neo4j/workflows-podlm.md) (f)).
- [ ] Pilot 4, beelm daily chain (see [workflows-beelm.md](neo4j/workflows-beelm.md) (f)).
- [ ] File the non-graph improvements each first-pass assessment named, as issues in
      their repos.

## Open questions

- Where the shared trace envelope's belief and law tables live, and when authorlm
  migrates to it.
- Whether person identity is owned by peoplelm (raised by four assessments;
  independent of flowlm).
- The gate page's port.
