# Neo4j assessment: corpuslm

Written 2026-11-04 from a read of corpuslm's code, schema document and design docs (no transcript
content was read). Use-case numbers refer to [usecases.md](usecases.md).

## (a) What the repo does and where its data and decisions live

corpuslm is the Python library that owns the shared transcript database (one SQLite file, schema
version 18, about 315 sources and 920,000 rows in October, most of them transcript segments) used
by ytlm (YouTube, Vimeo, files), beelm (Bee conversations) and text imports of manuscripts. One
module, `corpuslm.store.Store`, holds every read and write; a test fails when any other module
writes SQL. On top of the catalog (`sources`, `corpora`, `corpus_members`, `feeds`) it runs a
build chain per source (normalize, protected vocabulary, spell fix, AI cleanup, speaker map,
subtitles, search index) whose every step is an `artifacts` row keyed by the hashes of its inputs,
and a second layer of derived knowledge: `claims` (about 30,000, each tied to its segments),
`concepts` with `claim_concepts` tags, `moments`, `bodies_of_work`, and `monologues` with
`monologue_runs`. LLM-driven steps are AI cleanup, the claim, concept, moment and line-speaker
passes, the monologue recipe, and Jev (TypeSafe's typed decision model) as arbiter of cleanup
ambiguities, judge of a conversation's form and gate on directives. Decisions live in three
places: the owner's rulings in seven append-only verdict tables with `vw_current_*` views and a
content hash of what was judged; the model's picks in derived tables (`model_suggestions` with
per-candidate probabilities, `line_speakers` with confidence); and the arbiter's picks inside each
source's AI cleanup artifact file (an `origin` string such as `arbiter <model> 0.93`), not in a
table. Model spend is in llmlm's ledger files, read by the usage dashboard; pipeline runs are one
coarse row each in `runs`.

The short version of what follows: corpuslm already implements most of the talk's ideas
relationally (decision traces linked to domain rows, a typed decision model at the routing point,
content-hash caching so nothing is billed twice, deterministic procedure in code). The one thing
it holds that is graph-shaped is the claims-and-concepts layer, and that only pays off when it is
joined to other repos' data.

## (b) Use cases that plausibly apply

### 5 and 11. Knowledge layer and GraphRAG over claims and concepts

- Shape: `(:Corpus)-[:HAS_MEMBER]->(:Source {kind})`, `(:Source)-[:CLAIMS]->(:Claim {kind, section})`,
  `(:Claim)-[:USES]->(:Concept)`, `(:Moment)-[:IN]->(:Source)`, `(:Moment)-[:DRAWS_ON]->(:Claim)`,
  `(:Monologue)-[:USES]->(:Moment)`, `(:Monologue)-[:DRAWS_ON]->(:Body)`,
  `(:Body)-[:IS]->(:Source|:Corpus)`, `(:Person)-[:SPEAKS_IN {role}]->(:Source)`. Segments stay in
  SQLite; a claim carries segment positions as a property, so the graph holds references, never
  transcript text.
- What it improves: questions that cross source kinds and repos. "Which Bee conversations, YouTube
  talks and manuscript sections bear on the concepts this monologue uses, and which of those have
  no approved moment yet"; "what path connects concept A to concept B through shared claims";
  concept communities and centrality (Graph Data Science) to propose monologue themes. Inside
  corpuslm alone, the first of these is three or four fixed joins and SQLite answers it today;
  `Store.concept_edges` already computes co-occurrence with the claims as evidence. The
  variable-length and whole-graph questions are the ones SQL does badly.
- The cross-repo part is where the value is: authorlm keeps a concept graph per manuscript (the
  monologue series shares one), peoplelm keeps people, podlm keeps episodes. corpuslm's concepts
  and `source_people` names are strings with no link to any of them.
- Replaces or sits beside: sits beside. SQLite stays the system of record; the graph is a derived
  projection rebuilt from `Store` reads, exactly the adoption plan's rule 5. Nothing is replaced.
- Caution: two docstrings record deliberate decisions that a graph must not quietly reverse: "No
  row ever links one claim to another" and "No relation is ever inferred or stored" between
  concepts. Co-occurrence edges computed at projection time respect both; typed relations
  extracted by a model (the usual GraphRAG entity-relation pass) would not, and need the owner's
  ruling.
- Caution: at this size (tens of thousands of claims, a few thousand concepts at most) the concept
  co-occurrence graph fits in memory. By the adoption plan's own exception, community detection
  over it is a networkx call, not a database. Neo4j earns its place here only through the
  cross-repo join.
- Rating: medium value if a cross-repo knowledge layer is built, low value for corpuslm alone;
  small effort for corpuslm's share (one read-only export verb through `Store`, references only).

### 9. Entity resolution of people

- Shape: `(:Person)` resolved from `source_people.name`, `speaker_verdicts.name`,
  `line_speakers.name` (household names and their misspellings from settings) and peoplelm's
  records; `(:Person)-[:SPEAKS_IN]->(:Source)`, `(:Person)-[:KNOWN_AS]->(:Alias)`.
- What it improves: "every source where this person speaks, across YouTube guests and Bee
  conversations", which today is a string match on names spelled per source.
- Replaces or sits beside: beside. The resolution itself (deciding two spellings are one person)
  is the work, and it is peoplelm's to own; once a person id exists, a foreign key answers the
  question as well as an edge does.
- Rating: medium value, medium effort, and the effort is not graph work. A graph is a reasonable
  place to hold the result if the knowledge layer above exists; it is not a reason to build one.

### 2 and 12. Context graph of decision traces

- Shape: `(:Ambiguity {key, span_norm})-[:IN]->(:Source)`, `(:Suggestion {probability})-[:FOR]->(:Ambiguity)`,
  `(:ArbiterPick {probability})-[:FOR]->(:Ambiguity)`, `(:Verdict)-[:RULES_ON]->(:Ambiguity)`,
  `(:Correction)-[:ORIGINATED_FROM]->(:Verdict)`, `(:Verdict)-[:SUPERSEDES]->(:Verdict)`.
- What it improves: precedent lookup and audit. Both exist: the correction memory is precedent
  keyed by normalized span, verdicts are append-only with `previous_subject_sha256` lineage, and
  every verdict row carries its source. Every hop is a single foreign key or a key match; the
  longest chain (suggestion, arbiter pick, verdict, correction) has fixed depth.
- The real gap is not shape: the arbiter's picks live only in artifact files, so "how often did
  Jev agree with the owner, by probability band" cannot be asked of the database. A small
  `arbiter_picks` table (or columns on `model_suggestions`) closes it. The talk's calibration
  point (use case 14) is then one SQL join of `model_suggestions`, arbiter picks and
  `vw_current_review_verdicts`.
- Rating: low value as a graph, small effort for the relational fix. This is the textbook case of
  a graph duplicating tables with no multi-hop query.

### 15. Run storage for observability

- Shape: `(:Run)-[:BUILT]->(:Artifact {node, state})-[:OF]->(:Source)`,
  `(:Artifact)-[:INPUT]->(:Artifact)`, `(:ModelCall {stage, cost})-[:IN]->(:Run)`.
- What it improves: "which steps fail", "what did this run cost per stage", "what is stale
  because of what". The first two are GROUP BY queries over `artifacts`, `runs`, `monologue_runs`
  and the ledger, and the usage dashboard already shows spend by tool, stage and day. Staleness is
  the one traversal, and it walks a fixed chain of about eight steps per source that
  `corpuslm.chain` already resolves from input hashes.
- Rating: low value, medium effort (the ledger is files, `runs` is coarse; a graph would first
  need per-step run rows that do not exist). If finer run records are wanted, add them to SQLite.

### 14 and 16. Typed decision models, routing out of the LLM

Already built, without a graph: Jev answers typed `choice` and `noul` questions at the three
routing points, its probability is combined with the cleanup model's by Bayes' rule against a
threshold, anything under it escalates to the owner on the review page, replies are cached by
payload, and the chain around the model calls is deterministic code. The talk's lesson here is
applied; the remaining piece is the calibration check above. Rating as a Neo4j use case: none.

## (c) Use cases that do not apply

- 1 Execution graphs: the chain is a fixed linear builder sequence in code; there is no agent
  routing to constrain.
- 3, 4 Procedural graphs, portable artefacts: the procedure is Python with tests that enforce its
  decisions; one runtime, no second harness to port to.
- 6 Agent memory: corpuslm holds no conversations with an agent; Bee conversations are source
  material, not agent memory.
- 7, 8, 13 Skill compilation and distillation: the repo's skill is a short page of house rules
  for a CLI; there are no free-form agent traces to compile from.
- 10 Configuration graphs: per-kind differences are two injected objects (`SourceKind`,
  `ReviewKind`) and one settings file.

## (d) Ranked recommendation

1. Nothing in corpuslm on its own account. Its data is a star around `sources` with fixed-depth
   joins, its decision traces are already linked, append-only and hashed, and its largest table
   (segments, full-text indexed) is the worst possible fit for a graph. Do not move or mirror the
   system of record.
2. If the adoption session chooses a cross-repo knowledge layer (use case 5) as the first use
   case, corpuslm should be one of its feeders: a read-only `corpuslm graph export` verb that
   reads through `Store` and writes nodes and edges for Corpus, Source, Claim, Concept, Moment,
   Monologue, Body and Person as CSV, references only. The Cypher and the driver adapter live in
   the shared module the plan describes, not here, so corpuslm takes no Neo4j dependency. This is
   the only place I see multi-hop questions corpuslm cannot already answer.
3. Independent of Neo4j, and worth more than either: record the arbiter's picks in a table and
   add a calibration board (model and Jev probability against the owner's verdict). It is the
   talk's most transferable point for this repo and needs no new engine.

## (e) Open questions for the owner

- Privacy: claims and directives restate private Bee conversations. Community Edition has no
  access control and one database. Is claim text allowed in a graph store on the Mac, or do Bee
  sources contribute ids, kinds and concept tags only?
- Does the "no relation is ever inferred or stored" rule for concepts still stand? If yes, the
  graph holds co-occurrence edges only and model-extracted relations are out of bounds.
- Is corpuslm's concept lexicon meant to meet authorlm's per-manuscript concept graph? If they
  stay separate by design, the cross-repo case for corpuslm weakens to people and sources.
- Who owns person identity: peoplelm? corpuslm would then store a person id beside the names it
  has, graph or no graph.
- Is there a question about themes across the whole corpus (communities of concepts, bridges
  between bodies of work) that the owner actually wants asked? If so, try it first with networkx
  over `Store.concept_edges`; if that answers it, Neo4j is not needed for it.
- The database sits on an external drive (Crucial X6). A derived graph must tolerate the drive
  being absent and be rebuilt whole; is a nightly rebuild acceptable, or must it follow each run?
