# Neo4j assessment: marketlm

Status: draft, 2026-11-04. Read-only assessment of `/Users/nagarkar/workspace/repos/marketlm` (branch `metalm-setup`) against [usecases.md](usecases.md) and the [adoption plan](../neo4j%20adoption%20plan.md).

Recommendation in one line: **nothing yet.** marketlm holds rules, not data; the one graph worth having (evidence under decisions) belongs to the product repos' `record/` directories, none of which exist today.

## (a) What the repo does, and where its data and agent decisions live

marketlm is a rules repo. It holds 16 guideline files (`guidelines/`, 1,074 lines, all `Status: DRAFT`), 7 lessons for people (`lessons/`, untracked on this branch), one repo skill, `install.sh` (symlinks into `~/.claude`), and `tools/check-caps.sh`. The Python package is a docstring only: `src/marketlm/__init__.py` says "No runtime code yet: a module appears here only when an analysis needs state or an integration". There is no CLI, no store, no LLM call, no scheduled job, no run log. The agent in the picture is Claude Code in whatever product repo imports `guidelines/index.md`, and its decisions are drafts shown to the owner in chat.

The data model marketlm *prescribes* lives elsewhere, by its own ruling (`guidelines/record.md`): "marketlm keeps the rules and none of the records". Each product repo is to keep a git-tracked `record/` (positioning, ICP, pricing, channels, proof, rulings as YAML; metric definitions as SQL; append-only ledgers for ideas, test cards, kill criteria, launches); people, accounts and contact events live in Attio Free (an `(owner)` ruling); billing in Stripe; nightly exports land in one DuckDB or Postgres warehouse that all analyses read. As of today none of this is built: no sibling repo under `/Users/nagarkar/workspace/repos` has a `record/` directory, and no repo's `CLAUDE.md` imports marketlm. The record generator and the `ledger-test` check are both marked "proposed, does not exist yet".

So there are two things to assess: the rules corpus itself (small, static, text), and the prescribed record model (designed, relational plus files, zero rows).

## (b) Use cases that plausibly apply

### Evidence graph under decisions (use cases 2, 5, 11: context graph, knowledge layer, GraphRAG over records plus documents)

This is the only shape here with real multi-hop questions.

- Nodes: `Decision` (one per record file entry or ruling: positioning, ICP, price, channel plan), `Assumption`, `Evidence` (with `provenance` tag, `rung` on the strength ladder, `verification` outcome, `retrieved_at`), `Source` (URL, edition), `TestCard`, `Quote`, `Person` (CRM id only), `ConsentEvent`, `Surface` (pricing page, README, onboarding copy), `KillCriterion`.
- Edges: `(Decision)-[:RESTS_ON]->(Evidence)`, `(Evidence)-[:FROM]->(Source)`, `(Evidence)-[:PRODUCED_BY]->(TestCard)`, `(Quote)-[:SAID_BY]->(Person)`, `(Quote)-[:CONSENTED_BY]->(ConsentEvent)`, `(Surface)-[:COPIES]->(Decision)`, `(Surface)-[:SHOWS]->(Quote)`, `(TestCard)-[:TESTS]->(Assumption)`, `(Decision)-[:ASSUMES]->(Assumption)`, `(KillCriterion)-[:GUARDS]->(Decision)`.
- Questions it answers that files answer badly:
  - A fact is refuted or passes 90 days: which decisions rest on it, and which published surfaces copy those decisions? (3 hops; the "refuted figure is corrected everywhere" and 90-day re-fetch rules both need this.)
  - A person withdraws consent or asks for erasure: every quote, every surface showing it, every decision whose highest rung was that person's statement. (3 to 4 hops across CRM, `record/proof.yaml` and surfaces.)
  - Which decisions rest on no evidence above the stated-intent rung, or on evidence from one person only?
  - Which assumptions under a live bet have no test card?
- Replaces or sits beside: sits beside `record/` as a derived view, rebuilt from the YAML and ledgers (matches adoption-plan rule 5). It would replace nothing; it overlaps the proposed `ledger-test` and the proposed surface drift diff, both of which can be written as plain Python over the files.
- Honest rating: **medium value, medium effort, and premature.** Value depends on volume: at the profile's scale (a solo founder, a handful of decisions, tens of evidence rows per product) a script walking YAML ids answers every question above in milliseconds. A graph wins only when evidence rows reach the hundreds across two or more products and the "what rests on this" question is asked weekly. Zero rows exist today. Home would be the product repo (or a shared generator in `src/marketlm/`), never marketlm's own data.

### Contact and referral graph over people (use cases 2, 6, 9: context graph, memory, entity resolution)

- Nodes: `Person`, `Account`, `ContactEvent` (kind: send, reply, stop, interview, consent, refund…), `Identity` (mailbox, handle), `Channel`, `Community`. Edges: `(ContactEvent)-[:WITH]->(Person)`, `-[:VIA]->(Identity)`, `(Person)-[:INTRODUCED]->(Person)`, `(Person)-[:MEMBER_OF]->(Community)`, `(Person)-[:HEARD_VIA]->(Channel)`.
- Improves: introduction chains for "the first ten", and one view of a person across products.
- Replaces or sits beside: duplicates Attio (owner-ruled system of record) and the warehouse. The contact budget, suppression and attribution reads are single-table filters and counts. Dedupe is ruled deterministic (normalized email, domain), so there is no fuzzy resolution for a graph to help with. The one multi-hop edge, `INTRODUCED`, is a self-referencing column in Attio at this scale. Personal data in a second store also widens the erasure surface the guideline works to keep narrow ("applied in one run to the CRM, the warehouse and every sending list").
- Honest rating: **low value, medium effort.** If peoplelm (the people service) gets a graph for its own reasons, marketlm's contact events could attach there by CRM id; marketlm should not start it.

### Guidelines as a citation graph (use cases 3, 7: procedural graph, compiled skill)

- Nodes: `Rule`, `Guideline`, `Section`, `Origin` (framework, study, practitioner), `Lesson`, `Check` (existing or proposed), `RecordFile`. Edges: `(Rule)-[:CITES]->(Section)`, `-[:FROM]->(Origin)`, `-[:TAUGHT_BY]->(Lesson)`, `-[:ENFORCED_BY]->(Check)`, `-[:WRITES]->(RecordFile)`.
- Improves: "which rules have no check", "which rules rest on one origin", "which anchors are dead", "what else cites the rule I am changing".
- Replaces or sits beside: sits beside `check-caps.sh` and `metalm-gendocs`. Every one of these questions is a one-hop lookup over about 1,100 lines of markdown; a 50-line link checker covers them, and the result belongs in `docs/generated/`.
- Compiling the rules into a typed step graph (use case 7) fits a few procedures only: the outbound gate (show recipients, copy, identity, cost; wait for the owner's word; send byte-identical), the test-card sequence (hypothesis and thresholds before data; read-out leads with disconfirming counts), the kill-criterion review. These are linear with one human gate each. The index already rules "per-platform caps are code, never prompts"; the cheap form of that is a script per gate, which needs no graph store.
- Honest rating: **low value, small effort.** A linter, not a database.

### Jurisdiction and platform rule configuration (use case 10)

- Nodes: `Jurisdiction` (EU, UK, Canada, US), `Platform` (Reddit, X, YouTube, Play), `Action` (send, post, reply, tax), `Rule`, with `APPLIES_IN` and `GOVERNS` edges.
- Improves: "what applies to this send, to this person, on this platform".
- Replaces or sits beside: the guidelines' "EU/UK:" and "mobile:" gate lines. The matrix is roughly 4 jurisdictions by 6 platforms by under 10 actions, sparse and hand-maintained; a YAML table with a lookup function is clearer and diffable.
- Honest rating: **low value, small effort.** Uber's case is thousands of rules across microservices; this is a page.

## (c) Use cases that do not apply

- 1 Execution graphs: marketlm has no agent runtime; Claude Code is the harness.
- 4 Portable graph artefacts: the rules already are portable (markdown symlinked into `~/.claude`, imported by one line).
- 6 Agent memory graph: marketlm rules that a decision "never" lives in agent memory or a chat summary; memory here is `record/` by design.
- 8 Distilling skills from traces: no traces exist; rules are drafted from research and ratified by the owner, not learned from runs.
- 12 Persisting and comparing reasoning traces: no runs to compare.
- 13 Compiling successful runs into a skill: same; no run history.
- 14 Deterministic skill execution via CLI: no CLI and no procedure with enough branching; see the gates note in (b).
- 15 Run storage for observability: no pipeline, job or run exists in this repo.
- 16 Cost and latency reduction: no LLM spend originates in marketlm.

## (d) Ranked recommendation

1. **Nothing in marketlm yet.** No store, no rows, no runs. Adding Neo4j here would be a database with an empty schema.
2. **When the first product repo has a real `record/`**, build the proposed `ledger-test` and the surface drift diff as plain Python over the files first. Give every decision, evidence row, quote and test card a stable id and an explicit `rests_on: [ids]` field from day one (the guideline already demands stable ids); that makes the evidence graph derivable later at near-zero cost, in Neo4j or anything else.
3. **Revisit the evidence graph** when one of these is true: evidence rows pass a few hundred across two products; the owner asks "what rests on this" and the script answer is slow or wrong; or another repo's graph (peoplelm, metalm) already holds `Person` nodes that quotes and consent can attach to. At that point it is a derived, rebuildable view loaded from `record/`, about a week of work.

marketlm is a poor first candidate for learning whether graphs pay off. The repos with existing corpora, runs and stores will teach more.

## (e) Open questions for the owner

1. Which product repo adopts marketlm first and gets a `record/`? Until one does, every graph shape above is hypothetical.
2. Should the `rests_on` id field go into the record schema now (a small guideline edit to `record.md`), so the evidence graph stays a cheap later option?
3. Does peoplelm own the person graph if one is built? If so, do marketlm's contact events stay in Attio only, or mirror there by CRM id?
4. Personal data: is a second store holding person nodes acceptable given the one-run erasure rule, or must any graph hold CRM ids only?
5. The research reports the guidelines cite as origins (`mine-…`, `verify2-…`, `synth-…`) are not in this repo. If they sit in a corpus elsewhere, is retrieval over them a corpuslm question rather than a marketlm one?
