# Neo4j assessment: podlm

Written 2026-11-04 from a read of the repo at `main` (1f6ca42e). Read-only analysis; nothing in podlm was changed. podlm has no `CLAUDE.md` and no `docs/generated/index.md`; this is based on `docs/`, `docs/design/`, `rules.yaml`, the package docstrings under `src/podlm/`, the state schemas, and the episodes root on the Crucial X6.

Use-case numbers refer to [usecases.md](usecases.md).

## (a) What podlm does and where its data and decisions live

podlm is the production pipeline for The Spiritual Hindu podcast: it imports Riverside tracks, transcribes them, lets a Claude session and the author make editorial decisions, renders a draft, packages and uploads to YouTube, then follows the video's analytics, retention and comments. About sixteen episode folders exist. All state is files: per episode, `episode.json` (measured facts and provenance) and some forty schema-validated `work/*.json` documents (`words`, `edits`, `segments`, `shotplan`, `framing`, `media`, `assets`, `takemap`, `script`, `lint`, `packaging`, `youtube`, `youtube_analytics` and others) on the external drive, plus `approvals.json` and per-stage logs; channel-wide, `growth_decisions.json`, `growth_review.md` and `comment_likes.json` at the episodes root; in git, `config.yaml`, `rules.yaml` (the rule registry), `brand/` (licences, playbook), `prompts/` and `episodes/<slug>/research/`. There is no database. Agent decisions live in three places: `edits.json` entries (cuts, shots, waivers, each with an origin of agent or author), the research brief written by subagents and linted by `podlm research check`, and the growth review plus recorded growth decisions. Model calls made by code are few and narrow: packaging candidates, comment reply drafts, and Jev (a typed classifier) for comment labels, all through llmlm with a reply cache and a usage log. The pipeline itself is already an explicit graph in code: `pipeline/graph.py` declares every stage's inputs, outputs and guard, and `work/fingerprints.json` cascades rebuilds. Text and source video belong to other repos (authorlm owns manuscripts and media tags, ytlm owns YouTube sources and transcripts); podlm reaches them through their CLIs.

Two properties of this data matter for the rest of the assessment. Most of it is time-indexed arrays on one episode's clock (words, segments, frame spans, retention curves), which is interval data, a poor fit for a property graph. And nearly every question podlm asks today is scoped to one episode, where a JSON file read is already the cheapest answer.

## (b) Use cases that plausibly apply

### 5 and 11. Knowledge layer across repos (podlm as a contributor)

- **Shape.** `(:Episode {slug})-[:PUBLISHED_AS]->(:YouTubeVideo)`; `(:Episode)-[:READS]->(:ManuscriptFile)` (authorlm); `(:Sentence {id})-[:COVERED_BY]->(:Shot)-[:SHOWS]->(:Asset)`; `(:Asset)-[:EXCERPT_OF {t0, t1}]->(:SourceVideo)` (ytlm); `(:Asset)-[:CREDITED_AS]->(:Credit {licence})`; `(:Episode)-[:FEATURES]->(:Person)` (guest, peoplelm); `(:ResearchBrief)-[:CITES]->(:SourceVideo)`; `(:Comment)-[:ON]->(:YouTubeVideo)`, `(:Comment)-[:BY]->(:Viewer)`; `(:RetentionDrop {pattern, viewers_lost})-[:IN]->(:Episode)`.
- **Questions it answers.** These are the multi-hop ones podlm cannot answer from one episode folder: Which source clips have already been used on screen, in which episodes, under which licence? Which manuscript passages have become video, and how did those videos hold viewers? What has this guest (or anyone else on the same topic) already been asked, on our show and in the ytlm corpus? (The research brief has an "Already asked" section that a subagent assembles by search each time.) Which viewers comment across several videos, and on which topics?
- **Replaces or sits beside.** Sits beside everything. podlm's files stay the source of truth; a `podlm graph export` verb would emit nodes and edges from `assets.json`, `media.json`, `script.json`, `shotplan.json`, `youtube.json`, `youtube_analytics.json` and the research folder, so the graph is rebuilt, never converted (adoption plan, exit rules 4 and 5).
- **Rating.** Medium value, medium effort, and only if ytlm and authorlm are in the graph first. On its own podlm brings about sixteen episodes and a few hundred assets; the value is entirely in the joins to the ytlm corpus and the manuscripts. podlm should follow here, not lead.

### 2 and 8. Context graph of growth decisions and their evidence

- **Shape.** `(:GrowthReview {date})-[:PROPOSED]->(:Option)-[:BECAME]->(:Decision {decided, change, done})`; `(:Decision)-[:ADDRESSES]->(:Pattern {opening|cold_open_seam|card|…})`; `(:RetentionDrop)-[:CLASSIFIED_AS]->(:Pattern)`; `(:Decision)-[:HOLDS_FROM]->(:Episode)` or `-[:APPLIED_TO]->(:Episode)`; `(:PlaybookRule {status: seed|confirmed|contradicted})-[:EVIDENCED_BY]->(:Episode)`; `(:Decision)-[:CARRIED_OUT_BY]->(:EditEntry)`.
- **Question it improves.** "Which decisions changed the number they were aimed at, and which playbook rules does the evidence now confirm or contradict?" This is the one place podlm's own backlog asks for a database: "podlm database for growth reviews and decisions", deferred 2026-10-03, done when a review → option → decision → outcome schema exists and the growth page reads from it.
- **Replaces or sits beside.** Would replace `growth_decisions.json` and the overwritten `growth_review.md` (earlier reviews survive only in the published page's version history, so the review → option link is lost today).
- **Rating.** Low to medium value, medium effort. Honest caveats: there are three recorded decisions and under twenty episodes; the chain is a fixed four-step path, which is four small relational tables or one JSON file with history kept; outcome numbers are deliberately recomputed from `youtube_analytics.json` and never stored, so the graph would hold labels and links, not measurements. The real gap is that reviews and options are not kept at all, and that is fixed by keeping them, in any store. A graph earns its place here only once the decisions link out to things in other repos (the manuscript passage a cold open came from, the ytlm clips a format used).

### 15 and 12. Rule and lint findings across episodes (run storage)

- **Shape.** `(:Rule {id, strength, blocking})-[:PROMPTED_BY]->(:Episode)`; `(:Finding {target_hash})-[:OF]->(:Rule)`, `-[:IN]->(:Episode)`; `(:Waiver {origin, reason})-[:WAIVES]->(:Finding)`; `(:Rule)-[:RULED_AGAIN_ON {date}]->(:Episode)` (the registry's `repeated` list).
- **Question it improves.** "Which rules fire on every draft, which never fire, which are waived most and by whom?" That is the evidence the author needs before turning a rule `blocking: true`.
- **Replaces or sits beside.** Sits beside `rules.yaml` and each episode's `work/lint.json`.
- **Rating.** Low value, small effort. The answer is a group-by over sixteen `lint.json` files; a twenty-line script or a `podlm lint --across` verb gives it today. No multi-hop query in sight.

### 6. Agent memory

- **Shape.** Conversation → extracted entities (episode, guest, rule, ruling) → reasoning steps.
- **Applies to** the Claude sessions that drive podlm, whose memory is the file-based `MEMORY.md` index and the podlm skill, not podlm's code. The recurring pain it would address is real (rulings given twice: `rules.yaml` tracks `repeated` dates), but podlm's answer is already structural: a repeated note becomes a lint check with a fixture.
- **Rating.** Low value for podlm specifically, large effort; a metalm-level question, not a podlm one.

## (c) Use cases that do not apply

- **1. Execution graphs.** Already present as plain data in `pipeline/graph.py` with fingerprint-driven skips; a framework or database adds nothing.
- **3, 7, 13. Procedural graphs and compiled skills.** podlm's procedure is already compiled: stages are CLI verbs, judgment rules are numbered in `rules.yaml` with checks, and the skill file holds only house rules for driving them. Moving that into a graph store would duplicate code that tests already hold to the declarations.
- **4. Portable graph artefacts.** One harness (Claude Code) and one machine; no lock-in to escape.
- **9. Compliance reporting with entity resolution.** The only entity matching is slug to YouTube video (by duration, ±1 s) and guest names; people belong to peoplelm.
- **10. Regionally varying configuration.** `config.yaml` and `wrap.layouts` are small and flat.
- **14. Deterministic skill execution with typed decision models.** Already done without a graph: Jev labels comments with typed outcomes, and routing is in code.
- **16. Cost reduction by moving routing out of the model.** Same: code makes few model calls, each cached and logged through llmlm; spend is visible on the corpuslm usage page.
- **Timeline data in general** (words, segments, framing, retention curves, camera cuts). Interval arrays on one clock, read whole by one stage at a time. Keep out of any graph.
- **Sentence lineage** (`script.json` splits and merges, `descendants`). Graph-shaped, but per episode, tiny and in-process: the adoption plan's "a data structure, not a database" case, and already written.

## (d) Ranked recommendation

1. **Nothing podlm-specific yet.** podlm should not be the pilot. Its data is small, per-episode and time-indexed, and its one database-shaped need (growth decisions) is a four-step chain with three rows.
2. **If the cross-repo knowledge layer goes ahead with ytlm and authorlm, add podlm as a derived contributor**: one read-only `podlm graph export` that emits Episode, YouTubeVideo, Asset, excerpt-of-source-video, sentence-covered-by-shot, Credit, Comment and Decision records for the shared loader. That is where podlm's multi-hop questions live (clip reuse and licences, manuscript passage to video to retention, "already asked" for research briefs). Small once the shared Cypher module and adapter exist.
3. **Independently of Neo4j, stop losing growth reviews and options**: keep each review and its options beside `growth_decisions.json` (append, not overwrite). This closes most of the deferred backlog item in files, and makes a later graph load a rebuild.

## (e) Open questions for the owner

1. Does the "Already asked" section of a research brief take enough subagent time, or miss enough, that a graph of guest → question → video across the ytlm corpus would be worth building for it alone? That is a ytlm question with podlm as the consumer.
2. Do you want to ask "where has this clip or image been used before, and under what licence" across episodes? Today each episode's `assets.json` answers it for that episode only.
3. For the growth database: is the missing piece the queries across decisions, or simply that old reviews and unapproved options are not kept? The second needs no database.
4. Should viewers (comment authors) become people in peoplelm, joined to their comments across videos? Volume is low now; it matters only if comment replies become automatic.
5. If a shared graph exists, is the episodes root on the Crucial X6 acceptable as a source for a nightly export, given it fails loudly when the drive is unmounted?
