# Neo4j assessment: authorlm

Written 2026-11-04 by a read-only session over `/Users/nagarkar/workspace/repos/authorllm`. Counts are from the live workspace (`~/.authorlm/authorlm.db`, opened read-only) on that date.

## (a) What the repo does and where its data lives

AuthorLM is an editorial collaborator for the owner's philosophy writing: a CLI (`authorlm`) and an MCP server over one SQLite file (`~/.authorlm/authorlm.db`, 507 MB, 13 manuscripts), with the manuscript files on disk as the system of record for text and Google Doc tabs as the review surface. Its stores are: full-text snapshots (`manuscript_versions`, 1,027 rows of JSON, which is most of the 507 MB) and their diffs (`editorial_transitions`, 5,408); the Concept Graph (`concept_nodes`, `concept_edges`); the summary hierarchy (`paragraph_summaries` 2,628, `section_summaries` 399, `essay_summaries` 44), whose paragraph records hold term mentions, relations, back and forward references and paragraph-to-paragraph `depends_on` inside a JSON column; the author's knowledge split into machine guesses and declared law (`editorial_beliefs` 419, `style_laws` 149, with `style_guides` in a parent chain); and the decision record: every machine proposal and the author's verdict on it (`doc_threads` 7,786, `knowledge_proposals` 1,343, `guidance_history` 629, `editorial_reviews` 312, `evidence` 5,420). LLM-driven steps are single calls behind deterministic gates (extraction and its adjudicator, the paragraph, section and essay summary passes, critique, filter, lens, morph, interlocutor, the belief distiller, the triage screen); there is no agent framework. The agent is the chat session (Claude Code) driving CLI verbs, and its per-verb trace is `~/.authorlm/logs/trace.jsonl` plus the usage ledger `usage.jsonl`. Run state lives in rows with cursors (`critique_passes`, `filter_runs`, `writeups`, `triage_runs`).

Two facts set the bar for everything below.

- The Concept Graph is small. SMSTTD, the only manuscript with a real graph, has 290 live nodes and 158 live edges (1,160 nodes and 1,584 edges including retired and rejected rows, which are kept as history). Every consumer (`plan.build_plan`, `guidance.compute_prerequisite_gaps`, `concepts.scoped_concepts`) loads the manuscript's nodes and edges into Python dicts and looks one hop out. The prerequisite check documents itself as under 20 ms. There is no recursive query anywhere in the package.
- Half the graph's edges are not stored as edges at all: "concept X appears in essay Y" is a regex scan over the text at read time (`concept_pattern`, `primary_location`), re-derived on every collect by ruling (2026-09-07). A graph database would have to materialise what the repo deliberately keeps derived.

## (b) Use cases that plausibly apply

### 1. Knowledge layer and GraphRAG over the book's argument (talk use cases 5, 11)

- **Graph shape.** `(:Manuscript)-[:HAS]->(:Essay)-[:HAS]->(:Section)-[:HAS]->(:Paragraph {para_hash, kind, move, gist, claim})`; `(:Essay)-[:NEXT]->(:Essay)` for the toc reading order; `(:Paragraph)-[:DEPENDS_ON]->(:Paragraph)`; `(:Paragraph)-[:MENTIONS {role: introduces|defines|uses|names}]->(:Term)`; `(:Paragraph)-[:REFERS {direction: back|forward}]->(:Term)`; `(:Term)-[:NAMES]->(:Concept)` (the alias list); `(:Concept)-[:DEPENDS_ON|GENERALIZES|REFUTES|…]->(:Concept)` (the fifteen ratified relations). All of it already exists: the first half in the JSON `record` column of `paragraph_summaries`, the second in `concept_nodes` and `concept_edges`.
- **What it improves.** Multi-hop questions nobody can ask today without writing Python: "if this essay moves after that one, which paragraphs downstream now use a term before it is introduced, and through which chain"; "every forward promise that no later paragraph pays"; "the shortest chain of essays a reader needs before chapter N"; "which concepts does the whole argument for X rest on, three levels down". The Reader load (`manifest.compute`) and the essay summary's INTRODUCES / ASSUMES / PROMISES / DEBTS lists answer the one-hop versions now. It would also give a chat session a retrieval road that follows evidence (paragraph, its dependencies, the concept notes) instead of loading whole essays.
- **Replaces or sits beside.** Sits beside SQLite as a derived, rebuildable projection (adoption plan rule 5). Replaces nothing: paragraph identity is a content hash that changes on every edit, so the projection is rebuilt after `summarize rebuild`, never written to directly.
- **Rating.** Medium value, medium effort. Value is medium, not high, because at 2,628 paragraphs and 44 essays the same questions are a 40-line Python function or a recursive CTE over a small table, and because nobody has asked them yet. The honest gain is exploration (Browser, Bloom) and ad-hoc Cypher, not anything the product needs. Effort: an exporter (one module, read-only against SQLite), a server to keep running, and a rebuild hook.

### 2. Context graph: the author's verdicts joined to what they were about (talk use cases 2, 12)

- **Graph shape.** `(:Proposal {producer: critique|filter|lens|morph|extraction|placement, old, new, note})-[:ANCHORED_IN]->(:Paragraph)`, `-[:ABOUT]->(:Concept)`; `(:Verdict {decision, explanation, at})-[:ON]->(:Proposal)`; `(:Verdict)-[:SUPPORTS|CONTRADICTS]->(:Belief)`; `(:Belief)-[:BECAME]->(:Law)-[:IN]->(:Guide)-[:PARENT]->(:Guide)`; `(:Run {filter|pass|lens, model})-[:PRODUCED]->(:Proposal)`; `(:Source {author|critic|system})-[:ORIGINATED]->(…)`.
- **What it improves.** Precedent lookup: "what has the author already decided about edits to this paragraph, this concept, this kind of change, from this producer", fed into the next critique or filter prompt. And audit of a law: from a `style_laws` row back through the belief, the evidence rows and the original threads to the sentences that started it.
- **Replaces or sits beside.** Sits beside the tables. The proposal learning loop (`loop.py`, built 2026-08-20) already does the valuable part with SQL: it screens new proposals against validated beliefs, keeps cut items in folds, and never asks the same thing twice.
- **Rating.** Low to medium value, medium effort. The blocker is not the engine. In a sample of `evidence` rows, `target` is display text (`<file>: «(insertion)»`), not an id, and only 621 of 5,420 evidence rows carry `supports_belief`. A graph loaded from this would have the same missing edges. The first step is relational: give evidence rows structured targets (thread id, `para_hash`, concept id). After that, the precedent query is a two-join SQL statement. A graph adds little until the chains get longer than that.

### 3. Agent memory as one graph (talk use case 6)

- **Graph shape.** NAMS's three layers map onto things AuthorLM already separates on purpose: conversation (`sessions`, `declared_intents`, `editorial_episodes`), long-term entities (Concept Graph, `style_laws`), reasoning traces (`evidence`, `editorial_reviews`).
- **What it improves.** Little. The session-opening briefing and `get_style` already serve the ratified memory to the chat session.
- **Replaces or sits beside.** It would sit beside, and that is the risk: the repo's central invariant is that a machine guess (`editorial_beliefs`) becomes binding (`style_laws`) only when the author accepts it. A general agent-memory service that extracts entities from conversations and serves them back has no such door.
- **Rating.** Low value, medium effort. Not recommended.

### 4. Distilling rules from decision traces with provenance (talk use case 8)

- **Graph shape.** `(:Belief)-[:DISTILLED_FROM]->(:Verdict)`, version nodes per belief revision, `(:Belief)-[:CUT]->(:Proposal)` for the screen's folds.
- **What it improves.** Drift inspection: which beliefs are cutting more over time, which were promoted on thin evidence.
- **Replaces or sits beside.** This is the proposal learning loop, already built, with its two invariants (machine cuts are never author evidence; cuts fold, never vanish). The talk's version is the same idea with a graph store under it.
- **Rating.** Low value (the mechanism exists; 10 validated beliefs, 354 candidates), small effort only if use case 2's projection is already there. Useful as confirmation that the design matches outside practice, not as work to do.

### 5. Run storage for observability (talk use case 15)

- **Graph shape.** `(:Run)-[:STEP]->(:UnitExecution {status})-[:ON]->(:Paragraph)`, `(:Run)-[:USED]->(:Prompt {name, version})`, `(:Run)-[:COST]->(:UsageEntry)`.
- **What it improves.** "Which filter units are always declined", "which lens never produces an accepted finding", "cost per accepted edit by prompt". Today that means joining `filter_runs`, `doc_threads`, `evidence` and `usage.jsonl` by hand.
- **Replaces or sits beside.** Beside. These are aggregate questions over flat rows: group-bys, not traversals.
- **Rating.** Low value for a graph, small effort in SQL. A view or a `usage` report column answers it without a new store.

### 6. Entity resolution across manuscripts (talk use case 9, loosely)

- **Graph shape.** `(:Concept {manuscript})-[:SAME_AS]->(:Concept {manuscript})`; `(:Essay)-[:COMMENTS_ON]->(:Essay)` for the papers and recaps written from SMSTTD chapters; `(:Clip)-[:TAGGED_IN]->(:Essay)` and `(:Clip)-[:USED_IN]->(:Episode)` toward podlm; `(:Transcript)-[:SOURCE_OF]->(:Essay)` toward corpuslm monologues.
- **What it improves.** One concept ("Nothing", "choice") followed across the book, the philosophy papers, the poems and the podcast episodes. Today concepts are keyed by `manuscript_id` and nothing links them across manuscripts; clips reach podlm through JSON verbs.
- **Replaces or sits beside.** Beside, and not inside authorlm: this is the cross-repo knowledge layer, where authorlm is one contributor of nodes. Whichever repo hosts that layer would read authorlm through an export, not the other way round.
- **Rating.** Medium value if the cross-repo layer is built elsewhere, low on its own (only SMSTTD has a graph today; on-becoming has 6 nodes, DON has 26 and no edges). Effort inside authorlm: small (an export verb with stable ids).

### 7. Compiling prose skills into procedure graphs (talk use cases 3, 7, 13, 14)

- **Graph shape.** `(:Skill)-[:STEP]->(:Step {kind: script|decision|gate|escalate})` for `.claude/skills/authorlm/SKILL.md`, `papers`, `papers-philosophy`, the filter Doc-road protocol.
- **What it improves.** The chat session following a multi-verb protocol (apply a filter end to end; the papers stages and gates) the same way every time, on a smaller model.
- **Replaces or sits beside.** Mostly already done the repo's own way: wherever a procedure mattered, it was moved out of prose and into a CLI verb with a stored state machine (`filter_runs.cursor`, `critique_passes.essay_state`, `writeups.plan` and `cursor`) and deterministic gates (`lint`, `hygiene`, `triage_rules`, the output-contract validators with retry). The remaining prose skills are the candidate, and they are shared with other repos.
- **Rating.** Low value here, medium effort. A metalm-level question, not an authorlm one.

## (c) Use cases that do not apply

- **1, execution graphs.** No agent framework; orchestration is CLI verbs called by a chat session.
- **4, portable graph artefacts.** One harness (Claude Code, plus the cloud routine running the same CLI); nothing to port between runtimes.
- **10, configuration graphs.** The nearest thing is "which style law applies to this file": a guide chain two or three deep with file-local overrides, 149 laws, composed by `styles.effective_style` with no model in the loop. Too shallow to gain from a graph.
- **16, cost reduction by moving routing out of the LLM.** Already the house practice (zero-token triage rules, deterministic lint, gates before the adjudicator, a flash model for paragraph records). Nothing left that a graph would move.

## (d) Ranked recommendation

**Nothing yet as a dependency of authorlm.** The repo's graph is a few hundred nodes read one hop at a time, its text-to-concept edges are derived on purpose, and its decision record lacks the ids that would make a context graph worth querying. Adding a JVM server to a single-file SQLite tool with a hermetic test suite, cloud sessions and a nightly file backup costs more than any query above returns today. Community Edition has no online backup, which matters less only because the graph would be derived.

If the owner wants authorlm to be one of the learning cases anyway, in this order:

1. **A read-only exporter of the SMSTTD argument graph (use case 1), outside the package's runtime path.** One script: SQLite in, Neo4j out, full rebuild each time (about 3,000 paragraphs, 400 sections, 44 essays, 290 concepts, a few thousand mention and dependency edges). No verb depends on it, no test needs it. Success test, stated before building: three questions about the book the author actually wants answered that took more than a few lines of SQL or Python. If the test fails, delete the script and nothing else changes. This is also the natural feed for use case 6 if a cross-repo layer is built.
2. **Independently of Neo4j: structured targets on `evidence` rows** (thread id, `para_hash`, concept id instead of display text). This is what use cases 2 and 4 need whichever store they end up in, and it improves the existing learning loop on its own.

Everything else (agent memory, run storage, skill compilation) is either already built in the repo's own terms or belongs to the metalm-level decision.

## (e) Open questions for the owner

1. Are there questions about the book's argument structure (ordering, dependency chains, unpaid promises) you have wanted answered and could not get from the Reader load or the essay summaries? If none come to mind, recommendation 1 has no customer.
2. Should the Concept Graph ever span manuscripts (SMSTTD, the philosophy papers, DON, on-becoming), or is one graph per manuscript the intended shape? Use case 6 depends on the answer, and so does the multi-tenancy design (tenant > workspace > manuscript), which would need per-tenant separation that Community's single database does not give.
3. Is a cross-repo knowledge layer (book chapters, podcast clips and episodes, monologue transcripts, launch plans) wanted? If yes, which repo hosts it; authorlm should export to it, not own it.
4. Would you accept a served dependency (a running Neo4j process) for authorlm at all, given cloud sessions and the daily improvement routine run the CLI where no such server exists? If not, any graph use is local exploration only.
5. Is the precedent lookup in use case 2 ("what did I decide before about this paragraph or this kind of edit") something you want in critique and filter prompts? If yes, the evidence-target work is worth filing as an issue now, with or without a graph.
