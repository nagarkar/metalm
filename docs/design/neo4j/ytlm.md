# Neo4j assessment: ytlm

Status: assessment for the adoption session, 2026-11-04. Read-only analysis of
`/Users/nagarkar/workspace/repos/ytlm` (code, docstrings, design docs, the `status` board);
no transcript text was read. Use-case numbers refer to [usecases.md](usecases.md).

## (a) What ytlm does and where its data and decisions live

ytlm fetches captions for YouTube (and Vimeo, file) videos or transcribes their audio,
cleans the transcript in steps (protected vocabulary, spell fix, an AI cleanup), keeps the
result searchable (SQLite FTS5), exports SRTs and an Obsidian vault, and maintains one
standing Google Doc per corpus through authorlm. Scale today: 331 videos, 39 corpora, about
248,000 indexed segments, 313 videos with claims.

- **Records.** One shared SQLite file whose schema corpuslm owns (ytlm reaches it only
  through `corpuslm.store.Store`): `sources`, `corpora`, `corpus_members`, `source_people`,
  `source_topics`, `segments` + FTS, `artifacts` (one row per pipeline node per video, with
  the hashes of its inputs and its provenance), `runs`, `fetch_attempts`, `change_log`,
  and the knowledge tables `claims`, `concepts`, `claim_concepts`, `moments`, `monologues`.
- **Files.** Bulky artifacts under the workspace on the external volume: raw captions,
  `transcript.json`, `digest.json`, the vault, the corpus document's work orders and its
  footnote registry (`_orders/tabs.json`: `<video id>@<seconds>` to footnote tag), the reply
  cache (`llm-cache/<sha256>.json`), and JSONL ledgers (`usage.jsonl`, `trace.jsonl`).
- **Model-driven steps and their decisions.** AI cleanup (edits, ambiguities, speaker
  bindings), the arbiter (Jev, a typed decision model, picks among an ambiguity's options),
  the digest and claim pass (claims tied to segments, topics, people), the document router
  (claims to tabs) and writer (revisions). Owner rulings land as append-only verdict rows
  (`review_verdicts`, `speaker_verdicts`) and a workspace-wide correction memory
  (`corrections`, keyed by normalized span). The Google Doc is authorlm's store.
- **Control flow.** Already an explicit, tested, declarative graph in code:
  `src/ytlm/graph.py` (nodes, a propagation table of change kind to update kind) evaluated
  by `runner.py`. No model chooses a route anywhere in the pipeline.

Two facts shape everything below. First, the graph-shaped data (claims, concepts, people,
moments) is corpuslm's, not ytlm's; ytlm produces rows and reads boards. Second, ytlm is
already built the way the talk recommends: routing in code, a typed decision model at the
one judgement gate, runs and provenance stored beside the data.

## (b) Use cases that plausibly apply

### Knowledge layer and GraphRAG over claims (use cases 5, 11)

- **Shape.** `(Corpus)-[:HAS_MEMBER]->(Source)`, `(Source)-[:PUBLISHED_BY]->(Channel)`,
  `(Source)-[:FEATURES {role}]->(Person)`, `(Source)-[:ABOUT]->(Topic)`,
  `(Source)-[:ASSERTS]->(Claim {kind, speaker, start_seconds})`,
  `(Claim)-[:USES]->(Concept)`, and from ytlm's document registry
  `(Claim)-[:CITED_AS {tag}]->(Tab)-[:OF]->(Manuscript)`. Segments stay in SQLite; a claim
  carries its `yt:<id>@<s>` locus as a property.
- **What it improves.** The cross-video jobs the requirements list but nothing builds yet:
  position drift (one person, one concept, claims ordered by `published_at`), "how would X
  talk about Y", the asked-before ledger, gap finder (concepts strong in a corpus with no
  cited claim in the manuscript), claims versus written work. These run three to five hops:
  person to sources to claims to concepts to other people's claims to manuscript tabs. Also
  browsing: Neo4j Browser or Bloom over 39 corpora is something the owner has no equivalent
  of today.
- **Replaces or sits beside.** Sits beside SQLite as a derived projection, rebuilt from
  `Store` reads plus `tabs.json`. Replaces nothing: FTS5 stays the search index, the
  artifact rows stay the truth.
- **Skeptical notes.** At this size every one of those questions is a four-table SQL join
  that runs in milliseconds; corpuslm already computes concept co-occurrence on demand
  (`Store.concept_edges`). The edges that would make a graph earn its keep do not exist:
  people are free-text names per source (no person identity across videos), and there are no
  claim-to-claim edges (restates, qualifies, contradicts). The owner has ruled that concept
  relations are computed, never inferred or stored; a graph of inferred claim relations
  would reopen that ruling. Without those, this is the relational schema redrawn.
- **Rating.** Medium value, medium effort, and the work is corpuslm's (the schema owner,
  which also holds the Bee sources). ytlm's share is small: a read of `tabs.json` for the
  citation edges. Rated for ytlm alone: low value, small effort.

### Context graph of cleanup decisions (use cases 2, 12)

- **Shape.** `(Ambiguity {key, span})-[:IN]->(Source)`,
  `(ModelPick)-[:PROPOSES]->(Ambiguity)`, `(ArbiterPick {probability})-[:PROPOSES]->(Ambiguity)`,
  `(Verdict {origin})-[:RULES]->(Ambiguity)`, `(Correction)-[:LEARNED_FROM]->(Verdict)`,
  `(Correction)-[:AUTO_RESOLVED]->(Ambiguity)`.
- **What it improves.** Precedent lookup ("has the owner ruled on this span before") and
  audit ("which corrections rest on an arbiter pick the owner later reversed").
- **Replaces or sits beside.** Would sit beside `review_verdicts`, `corrections` and
  `model_suggestions`.
- **Skeptical notes.** Precedent lookup is already built and is one indexed lookup by
  normalized span; arbiter picks are kept out of the correction memory by rule, so the
  chain is two hops at most. Agreement between Jev and the owner is a GROUP BY. No
  multi-hop question here that I could name.
- **Rating.** Low value, medium effort.

### Run storage and lineage (use case 15)

- **Shape.** `(Run)-[:BUILT]->(Artifact {node, sha256, state})-[:DERIVED_FROM]->(Artifact)`,
  `(Artifact)-[:USED]->(LlmCall {model, prompt_id, cost})`, `(Artifact)-[:OF]->(Source)`,
  extended by the citation edges above to `(Tab)`.
- **What it improves.** One lineage question has real appeal: "which footnotes in which
  corpus document rest on a transcript that was unreviewed, or cleaned with prompt version
  N, or patched by an arbiter pick". That crosses artifact rows, the reply cache, claims and
  `tabs.json`, which today live in a table, a directory of JSON files and a registry file.
- **Replaces or sits beside.** Beside `artifacts`, `runs`, `usage.jsonl`, `llm-cache`.
- **Skeptical notes.** The pipeline is a fixed chain of about twenty nodes, so lineage depth
  is bounded and known; no recursive traversal is needed. Each artifact row already records
  its input hashes and whether it was built from a reviewed transcript. The appeal comes
  from the data being spread over three stores, and the cheaper cure for that is one SQL
  view or a board verb (`ytlm lineage <tab>`), not a second database. "Which branches are
  ever taken" is answered by counting `artifacts` by node and state, which `status` does.
- **Rating.** Low value, medium effort.

### Person identity across sources (use case 9, entity resolution)

- **Shape.** `(Person)-[:KNOWN_AS]->(Name)`, `(Source)-[:FEATURES {role}]->(Person)`,
  `(Corpus {person})-[:ABOUT]->(Person)`, joined to peoplelm's person records.
- **What it improves.** A real gap: `source_people.name`, speaker verdicts, channel titles
  and `corpora.person` are unconnected strings, so "every video where this person speaks,
  across corpora" depends on spelling. Caption mis-hearings make that worse.
- **Skeptical notes.** The fix is an identity (a person id with aliases), which is a table
  and a ruling about who owns it (corpuslm or peoplelm), not a graph engine. It is, though,
  the precondition for the knowledge layer above being worth anything.
- **Rating.** Medium value as a data-model fix, small to medium effort; Neo4j adds nothing
  to it.

## (c) Use cases that do not apply

- **1. Execution graphs.** Already done in code: `graph.py` is a declarative typed
  dependency graph pinned by table-driven tests; storing it in a database would loosen it.
- **3, 7. Procedural graphs, compiling a written skill.** The ytlm skill is house rules for
  one CLI; the procedure it would compile to is the runner, which already exists.
- **4. Portable graph artefacts.** No agent framework to be locked into; the surface is one
  CLI and one `run_cli` MCP tool.
- **6. Agent memory.** ytlm has no conversational agent, and its house rule keeps content
  out of the chat window; its only memory is the correction table.
- **8, 13. Distilling skills from traces.** No free-form agent runs to distil; the one
  chat-road step (the document writer) answers a self-contained work order.
- **10. Configuration graphs.** The nearest thing is the propagation table (about fifty
  rows), which lives in code with tests on purpose.
- **14. Typed decision models behind a CLI.** Already in place: the arbiter asks Jev a
  Choice question, combines probabilities, and applies or leaves the item for the owner.
- **16. Cost reduction by moving routing out of the model.** Already the design: no model
  routes, the digest runs on the cheap tier, spend caps stop a run before the call.

## (d) Ranked recommendation

1. **Nothing in ytlm yet.** No ytlm workflow is blocked or slow for want of a graph, the
   data is small, and the multi-hop questions that exist belong to corpuslm's knowledge
   tables. Adding a JVM server to a tool whose design has no resident daemon and whose
   workspace sits on an external volume is cost with no ytlm-side payoff.
2. **If the knowledge layer is tried, try it in corpuslm, as a throwaway first.** A
   one-off export of sources, people, claims, concepts and corpus membership into Neo4j
   Community, then three questions asked by hand in Browser: position drift for one person
   and one concept, concepts shared between two people's corpora, and corpus concepts with
   no cited claim in a manuscript. If plain SQL over the same tables answers them as
   readily, stop there. ytlm's contribution would be the citation edges from `tabs.json`.
3. **Independently of Neo4j: give people an identity.** It is the gap this assessment
   surfaced, and it is a table, not a graph.

## (e) Open questions for the owner

- Would you accept stored, model-inferred claim-to-claim edges (restates, qualifies,
  contradicts)? The concepts ruling says relations are computed, never inferred or stored.
  Without such edges the knowledge graph has little the tables lack; with them it reopens
  that ruling and adds a review burden.
- Who owns person identity: corpuslm (a `people` table beside `source_people`) or peoplelm?
- Is browsing (Bloom or Browser over corpora, claims and concepts) a goal in its own
  right? If so the experiment in (d)2 is worth an afternoon regardless of query needs.
- A graph holding claim text is content. Is it acceptable only as an owner-facing page on
  the tailnet, with any agent-facing surface returning boards (ids, counts, loci) as ytlm's
  verbs do?
- Should the "which footnotes rest on unreviewed or arbiter-patched transcripts" question
  be answered at all? If yes, a `ytlm` board verb over the existing rows is the cheaper road
  and can be filed as an issue.
- Corpus document lineage crosses into authorlm (tabs, revisions, rulings). Does the
  authorlm assessment want claim-to-tab edges from ytlm, and in what form?
