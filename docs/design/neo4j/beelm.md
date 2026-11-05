# Neo4j assessment: beelm

Written 2026-11-04 from the code and docstrings of `/Users/nagarkar/workspace/repos/beelm` (no transcript content was read). Use-case numbers refer to [usecases.md](usecases.md).

## (a) What beelm does and where its data and decisions live

beelm keeps the owner's Bee wearable conversations synced onto this Mac and turns them into a searchable, digested corpus. It is a thin tool: about 4,400 lines that wrap the official Bee CLI (`beelm.bee`) and call the `corpuslm` library for almost everything else. Its data lives in four places, none of which beelm owns the schema of:

- **Files**: the Bee CLI's store under `~/Bee/transcripts`, one conversation JSON per id under `~/Bee/beelm/conversations/<day>/<id>.json`, built artifacts under `~/Bee/beelm/transcripts/<source id>/` (model cleanup, speaker map, transcript, subtitles), a sync run log `runs.jsonl`, and payload logs per invocation.
- **The shared transcript database** (SQLite, schema owned by corpuslm, shared with ytlm): a `sources` row of kind `bee` per conversation, raw `segments`, `cleaned_segments` with FTS5, `artifacts` rows (node name plus input hashes, which is how freshness is decided), `claims` (including claims of kind `directive` with `addressee` and `heard`), `directive_verdicts`, `review_answers` and verdict rows, corpus membership.
- **The events database** (eventlm, SQLite): `transcript.digested` and `directive.found`, ids and counts only, consumed by computerlm.
- **config.toml**: the household list, the directive cutoff date, model and spend settings.

The LLM-driven steps are all fixed pipelines, not free agents: AI cleanup (one model step, then a speaker map with a household guard), the digest (form classification decided by Jev, a claim pass with one model read per section, a Jev gate on directives, a summary pass yielding topics, people and perspective). Each step is a typed, cached, hash-keyed artifact. The owner's decisions (speaker names, cleanup ambiguities, confirm or decline on a directive) are append-only verdict rows keyed by content hash. There is no agent that chooses its own path, so there are no reasoning traces to store: the "decisions" are either the owner's verdicts or typed model replies already persisted with provenance.

The consequence for this assessment: **beelm has almost no graph-shaped data of its own.** Whatever graph value exists in Bee conversations sits in corpuslm's tables (claims, concepts, moments, directives) and in what computerlm does with a directive. beelm would at most be a producer of rows for a graph that another repo owns.

## (b) Use cases that plausibly apply

### 6 / 5. Personal memory graph over conversations (agent memory, knowledge layer)

This is the one place where a graph does something the relational store cannot do cheaply.

- **Shape**: `(:Conversation {id, day, form})` from `sources` of kind `bee`; `(:Person)` from speaker maps (owner and household, each named only by the owner's rule) and from the digest summary's people list; `(:Topic)` from the summary's topics; `(:Claim {kind})` from `claims`; `(:Directive)` as a claim subtype; `(:Concept)` once corpuslm's concept pass runs over Bee sources. Edges: `(Person)-[:SPOKE_IN]->(Conversation)`, `(Conversation)-[:MENTIONS]->(Person)`, `(Conversation)-[:ABOUT]->(Topic)`, `(Claim)-[:FROM {segments}]->(Conversation)`, `(Claim)-[:USES]->(Concept)`, `(Directive)-[:RULED {confirm|decline}]->...`, `(Conversation)-[:NEXT]->(Conversation)` by time.
- **Questions it improves**: "what have I said about X across the last three months, and with whom", "which topics come up whenever person Y is in the room", "what did I commit to in conversations that also touched project Z", "what was I talking about in the days before I gave directive D". These are two- to four-hop joins across people, topics, claims and time. Today `search` answers only "which lines match these words".
- **Replaces or sits beside**: sits beside. Strictly a derived store, rebuilt from the transcript database; FTS5 search, claims and verdicts stay where they are.
- **The honest catch**: the nodes that make this multi-hop do not exist yet in resolved form. The summary's topics and people are free-text strings per conversation with no identity across conversations; "Topic" in one digest and the same topic worded differently in another are two strings. Without entity resolution (a canonical person and topic registry with owner verdicts, in the style corpuslm already uses for concepts), the graph is a star of disconnected leaves around each conversation and every query is one hop, which SQLite does fine. The work is the resolution pass, not the database; that pass belongs in corpuslm (it has `concepts` and the verdict machinery) and its output would be just as queryable in SQL for the first several questions. corpuslm already computes concept co-occurrence edges on demand in SQL and records "no relation is ever inferred or stored" as a decision.
- **Rating**: medium value (potentially high if the owner really asks cross-conversation questions about people and commitments), large effort, almost all of it outside beelm and before Neo4j. Privacy note: this graph would be the most sensitive store the owner has, a queryable map of household members, topics and commitments. Community Edition has no access control, so it would have to stay bound to localhost and off the tailnet.

### 2. Context graph: directives joined to what was done about them

- **Shape**: `(:Directive {subject_sha256, addressee, heard})-[:FOUND_IN]->(:Conversation)`, `(:Directive)-[:RULED]->(:Verdict)`, `(:Directive)-[:TRIGGERED]->(:Plan)-[:HAS_STEP]->(:Step)-[:TOUCHED]->(:Repo|:File|:Message)` on the computerlm side.
- **Question it improves**: "I said 'Computer, do X' on the 28th: was it confirmed, what plan came of it, what did it change, and has a similar directive come up before and how was it handled". That is a real precedent and audit chain crossing three stores (transcript database, events database, computerlm's plan store).
- **Replaces or sits beside**: sits beside. beelm's part is two edges it already publishes as events; the chain's interesting half (plans, steps, outcomes) is computerlm's.
- **Rating**: medium value, small effort **for beelm** (emit what it already emits), and the cost and the decision belong to the computerlm assessment. In beelm alone this is a three-table join keyed by subject hash, not a graph.

### 15 / 12. Run storage and artifact lineage

- **Shape**: `(:Run {verb, status, usd})-[:BUILT]->(:Artifact {node, inputs_sha})-[:OF]->(:Source)`, `(:Artifact)-[:DEPENDS_ON]->(:Artifact)` following corpuslm's `graph.CORE_NODES`.
- **Question it improves**: "why was this transcript rebuilt", "which artifacts go stale if I change the cleanup prompt", "which digest sections were skipped and why".
- **Replaces or sits beside**: would duplicate the `artifacts` table, `runs.jsonl`, the payload logs and corpuslm's usage dashboard.
- **Rating**: low value, medium effort. The dependency graph is a fixed tuple of about a dozen node kinds held in code; staleness is already answered by input hashes; the lineage depth is constant and small. This is exactly the "relational table with no multi-hop queries" case. If the owner wants one run store across all repos, that is a metalm decision (see metalm's assessment), and beelm would feed it, not own it.

### 11. GraphRAG over Bee conversations plus other sources

- **Shape**: chunk nodes for cleaned segments with vector embeddings, linked to the entity nodes of the memory graph above, and to ytlm sources, authorlm manuscripts and podlm episodes through shared `Concept` and `Person` nodes.
- **Question it improves**: "find where I talked through the idea that later became chapter 4", "what did I say aloud about the thing this YouTube source claims".
- **Replaces or sits beside**: sits beside FTS5. Depends entirely on the memory graph's entity resolution and on a cross-repo knowledge layer existing.
- **Rating**: medium value in a cross-repo setting, low for beelm alone; large effort. Not a first step.

## (c) Use cases that do not apply

- **1. Execution graphs**: beelm's pipelines are fixed verb sequences in Python; nothing routes dynamically.
- **3, 7, 13. Procedural graphs / compiling skills**: beelm's two skills are short house rules for driving a CLI; the procedure is already deterministic code behind `./beelm.sh`, so there is nothing for a compiler to make deterministic.
- **4. Portable graph artefacts**: no orchestration logic is locked in an agent framework here.
- **8. Distilling skills from traces**: there are no agent traces; model steps are single typed calls with cached replies.
- **9. Compliance reports with entity resolution**: no regulated reporting. The entity-resolution half is relevant only as the precondition named under the memory graph.
- **10. Configuration graphs**: beelm's configuration is one small TOML file with no regional or hierarchical variation.
- **14. Deterministic skill execution with typed decision models**: already how beelm works (Jev gates with thresholds, JSON-schema replies), without a graph.
- **16. Moving routing out of the LLM**: no routing is in the LLM today; spend is capped per run and dominated by the cleanup and claim reads, which a graph does not shorten.

## (d) Ranked recommendation

**Nothing yet, in beelm.** beelm is a producer with no schema of its own and no multi-hop question it can answer from its own data. Adding a Neo4j dependency here would duplicate corpuslm's tables.

What is worth doing, in order, and where:

1. **In corpuslm, before any graph**: decide whether Bee conversations get resolved people and topics (a canonical registry with owner verdicts, as concepts have). Run corpuslm's concept pass over the Bee corpus and see whether the co-occurrence queries the owner wants are already answerable in SQL. If two or three real cross-conversation questions turn out to be awkward or slow there, that is the evidence for the memory graph (use case 6), built as a derived projection from the transcript database with beelm contributing only its `bee` rows.
2. **In computerlm's assessment**: the directive-to-outcome chain (use case 2) is the most concrete context graph touching Bee data. If computerlm adopts a graph for plans and steps, beelm's `directive.found` events are already the right feed; beelm needs no change beyond possibly carrying the source id and subject hash, which it does.

If Neo4j is adopted elsewhere first, beelm's cost to join later is small because everything is already keyed by stable ids and content hashes.

## (e) Open questions for the owner

1. What cross-conversation questions do you actually want to ask of Bee data that `search` cannot answer today? Three concrete examples would settle whether the memory graph is worth the entity-resolution work.
2. Should people outside the household ever become named, resolved entities? The 2026-10-14 rule names a speaker only within the household; a person graph of everyone mentioned is a different privacy posture.
3. Are topics and people from the digest summary meant to be stable identities across conversations, or per-conversation descriptions? Today they are the latter.
4. Is a derived graph containing household conversation structure acceptable on this Mac given Community Edition has no access control and no online backup? (Localhost only, excluded from the tailnet, rebuilt from the transcript database and never backed up on its own, would be the conservative answer.)
5. Should Bee sources join the same concept lexicon as ytlm and authorlm sources, so that spoken ideas link to published ones? That is what would make the cross-repo knowledge layer (use cases 5 and 11) pay off, and it is a corpuslm decision.
6. Does computerlm keep an outcome record per directive today? If not, the context graph has no second half regardless of the database.
