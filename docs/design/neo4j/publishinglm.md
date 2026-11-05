# Neo4j for publishinglm: assessment

Status: draft, 2026-11-04. Read-only assessment of `/Users/nagarkar/workspace/repos/publishinglm`
(branch `codex/synthilogicsystems-website-record`) against the sixteen use cases in
[usecases.md](usecases.md) and the [adoption plan](../neo4j%20adoption%20plan.md).

Short answer: nothing in this repo alone justifies standing up Neo4j today. One thing here is
graph-shaped and worth joining a shared graph if another repo pays for the server: the people
and resources mined from the Facebook groups, joined to launch-team members, podcast hosts and
vendors. Everything else is small, single-book, tree- or DAG-shaped data that TOML and the
existing scheduler already handle.

## (a) What the repo does and where its data and decisions live

publishinglm is the owner's working copy of the selfpublishing.com "Market Your Book" course
plus the per-book launch workspace built from it. Four kinds of data:

- **Course corpus** (in git, `data/course/`, `data/faqs/`): 48 lesson files with their videos,
  158 help-center FAQ articles; transcripts live in the ytlm workspace, the corpus manuscript in
  authorlm. Read-only reference material, served by the lesson site (port 14443).
- **Book workspace** (outside git, `PUBLISHINGLM_WORKSPACE/books/<manuscript>/`): plain TOML and
  markdown, one folder per book keyed by the authorlm manuscript name. `plan.toml` (`[[task]]`
  with `depends_on`, stage, owning skill, hours, status; five milestones), `goals.toml`,
  `schedule.toml` (written only by the deterministic scheduler, `publishinglm.schedule`, 1,054
  lines of standard library: DAG, two hour buckets, forward and backward pass, critical path),
  `hours.toml`, `editing.toml`, `keywords/keywords.toml` with research exports, `podcasts.toml`
  (`[[show]]` rows moving research → referral → pitched → booked → aired), `launch-team.toml`
  (`[[member]]` with `mailerlm_id`), `listing.toml`, `audiobook.toml`, `social/`. Today there is
  **one book** (SMSTTD) with **111 tasks**.
- **Groups store** (outside git, `groups/groups.sqlite`, 3.3 MB, schema version 10 on disk): Facebook
  group posts and threads. 335 messages, 2,678 comments, 482 people, 1,968 message-people rows,
  230 classifications (Jev through corpuslm.judge), 220 extractions and 507 resources (Gemini
  Flash-Lite through llmlm; kinds: person 117, link 111, company 90, tool 83, book 50, program
  40, other 16). Resources are keyed by message and sequence; the same company or tool named in
  ten threads is ten rows with ten spellings.
- **Vendor and services research** (`services/` in the repo, untracked; `contracts/` and
  `books/SMSTTD/vendor/` in the workspace): markdown per provider (offers, marketplace value,
  contracts, email drafts).

Agent decisions live in two places. The model-driven pipeline steps (classify, extract) are
stored relationally with model, payload hash, cost and producer, and are cached by thread hash.
The eleven skills (book-launch-plan, keyword-research, launch-team, podcast-research,
kdp-listing, cover-and-description, lead-magnet, audiobook-launch, social-media,
seven-fundamentals, publishinglm) are prose `SKILL.md` files run by Claude in a chat session with
the owner answering one question at a time; what they decide lands as rows and `notes` fields in
the TOML files, with evidence beside them (keyword exports, `takes_guests_source`, "assumption"
labels). The reasoning itself is in the session transcript and nowhere else. Links out:
authorlm (`toc.toml`, `authorlm status`, Doc link), mailerlm (CLI, `mailerlm_id`, campaigns),
ytlm (transcripts), corpuslm and llmlm (judge, model client, spend ledger). A peoplelm
integration exists only in the worktree `.claude/worktrees/bold-boyd-618347`, not on this branch.

## (b) Use cases that plausibly apply

### 5 + 9. Knowledge layer with entity resolution: people, shows, vendors, resources

- **Shape.** `(:Person)` resolved across sources, with `(:Identity {source, key})` nodes for a
  Facebook id (groups store), a mailerlm contact id, a peoplelm id, a podcast host name, a
  vendor contact. `(:Person)-[:POSTED|COMMENTED_ON|REPLIED_TO]->(:Thread)`,
  `(:Thread)-[:MENTIONS {recommended}]->(:Resource)` where `Resource` is one resolved node per
  company, tool, book, program or person, `(:Thread)-[:ABOUT]->(:Topic)`,
  `(:Person)-[:HOSTS]->(:Show)`, `(:Person)-[:GUEST_ON]->(:Show)`,
  `(:Person)-[:MEMBER_OF {role, reviewed}]->(:LaunchTeam)-[:FOR]->(:Book)`,
  `(:Show)-[:PITCH {stage, dates}]->(:Book)`, `(:Vendor)-[:OFFERS]->(:Service)-[:FOR_STAGE]->(:Stage)`.
- **What it improves.** Real multi-hop questions the tables cannot answer without hand-written
  joins across three stores: "who in the group recommended a podcast I am about to pitch, and
  are they on my list?"; "which people on the launch team have also guested on shows in
  `podcasts.toml`?" (the referral path the podcast skill already asks for by `--person`);
  "which vendors are recommended by people other than their own staff, and warned against by
  whom?"; "which group members ask launch-team or review questions and so are ARC-reader
  prospects?". Resolving the 507 resource rows to perhaps 150 entities is most of the value and
  is needed with or without a graph.
- **Replaces or sits beside.** Sits beside. SQLite and TOML stay the source of truth; the graph
  is a derived projection rebuilt from them (adoption plan rule 5). Entity resolution of people
  arguably belongs in peoplelm, not here; publishinglm would contribute edges, not own the nodes.
- **Rating.** Medium value, medium effort. The value is real only if peoplelm/mailerlm people
  are in the same graph; with publishinglm's data alone it is 482 Facebook names and one launch
  team that does not exist yet (`launch-team.toml` and `podcasts.toml` are not yet written for
  SMSTTD), and three SQL joins would do.

### 11. GraphRAG over course, FAQs, group threads, contracts and the book's plan

- **Shape.** `(:Lesson)-[:IN]->(:Section)`, `(:Lesson)-[:HAS]->(:Chunk)`,
  `(:Video)-[:HAS]->(:TranscriptChunk)`, `(:FAQ)`, `(:Thread)`, `(:ContractClause)`,
  `(:Task)-[:CITES]->(:Lesson)` (skills already cite lesson numbers in every task and rule),
  `(:Skill)-[:IMPLEMENTS]->(:Lesson)`, `(:Resource)-[:NAMED_IN]->(:Lesson|:Thread|:FAQ)`.
- **What it improves.** "What does the course, the help center, the contract and the group each
  say about ARC lead time?" with the evidence path shown; "which lessons have no skill or task
  citing them?" (a coverage check). The second is a genuine graph question and cheap.
- **Replaces or sits beside.** Sits beside ytlm/corpuslm search and the lesson site. The corpus
  is 48 lessons and 158 FAQs: small enough that an agent reads the relevant lesson file whole,
  which the skills do today by lesson number.
- **Rating.** Low value, medium effort. At this size retrieval is not the bottleneck, and the
  lesson-to-skill citations could be checked with grep. Worth revisiting only as a tenant of a
  corpus graph that ytlm or corpuslm builds for their own reasons.

### 2 + 12. Context graph: skill decisions linked to the book entities they concern

- **Shape.** `(:Session)-[:RAN]->(:SkillRun {skill, at})-[:DECIDED]->(:Decision {question,
  answer, basis: lesson|owner|assumption})-[:ABOUT]->(:Task|:Keyword|:Show|:Member|:Goal)`,
  `(:Decision)-[:CITES]->(:Lesson)`, `(:Decision)-[:SUPERSEDES]->(:Decision)`.
- **What it improves.** "Why is this keyword in box 3 and what did we reject?"; "which plan
  figures are still assumptions the course was silent on?"; precedent for book two ("how did
  we size the launch team last time and what happened?"). The last one is the only question a
  graph answers better than a `notes` field, and it needs a second book.
- **Replaces or sits beside.** Would sit beside the TOML `notes`, "assumption" labels and
  evidence files, which already carry the decision and its basis next to the row. Capturing
  traces needs a hook in the Claude Code session, which is metalm's problem, not this repo's.
- **Rating.** Low value now (one book, owner present in every decision), medium to large
  effort. Medium value once there are two or three books.

### 3 + 7 + 14 + 16. Skills as procedural graphs run through a CLI

- **Shape.** `(:Skill)-[:HAS_STEP]->(:Step {kind: ask-owner|script|decision|validation|handoff})
  -[:NEXT {when}]->(:Step)`, `(:Step)-[:WRITES]->(:File)`, `(:Step)-[:CITES]->(:Lesson)`,
  `(:Step)-[:OWNS]->(:TaskTemplate)`.
- **What it improves.** The skills are already numbered procedures with preconditions, a master
  task template and "done when" checks, so they would compile cleanly. But most steps are
  "ask the owner one question": human-in-the-loop interviews, not routing an LLM gets wrong.
  The deterministic parts have already been moved into verbs the plain way (`publishinglm plan
  schedule`, `podcasts search|vet|stage`, the groups pipeline with Jev as the typed decision
  model). That is use case 14 achieved without a graph store.
- **Replaces or sits beside.** Would replace prose `SKILL.md` with a compiled artefact. The
  repo's own contract says the opposite direction is intended: "a skill can write them by hand
  today and a verb can own them tomorrow".
- **Rating.** Low value, large effort. If metalm decides to compile skills fleet-wide,
  book-launch-plan and launch-team are reasonable test subjects; publishinglm should not lead.

### 15. Run storage

- **Shape.** `(:Run {kind, started, outcome, spend})-[:STEP]->(:StepRun)-[:ON]->(:Thread)`.
- **What it improves.** Nothing the `runs`, `search_runs`, `classifications` and `extractions`
  tables do not already answer with `GROUP BY`. Skill runs are not recorded at all, but see the
  context-graph section: the gap is capture, not storage.
- **Rating.** Low value, small effort. A duplicate of relational tables with no multi-hop query.

### Plan and schedule as a graph (not from the talk, but the obvious candidate)

- **Shape.** `(:Task)-[:DEPENDS_ON]->(:Task)`, `(:Task)-[:CHILD_OF]->(:Task)`,
  `(:Task)-[:IN]->(:Stage)`, `(:Task)-[:OWNED_BY]->(:Skill)`, `(:Goal)-[:MEASURED_BY]->(:Task)`.
- **Honest verdict.** It is a DAG of 111 nodes that the scheduler loads into memory, orders,
  packs into hour buckets and writes back byte-identically, with tests. The adoption plan's own
  exception applies: "a single in-process adjacency structure with a few fixed traversals is a
  data structure, not a database". Cypher cannot do the capacity packing; Neo4j would add a
  server dependency to a verb that today runs offline. The one missing link, goal → task, is a
  TOML field.
- **Rating.** Low value, medium effort. Do not do this.

## (c) Use cases that do not apply

- **1. Execution graphs in the harness**: no agent framework here; skills run in Claude Code and
  the pipeline is three plain Python stages.
- **4. Portable graph artefacts**: one harness (Claude Code), no second runtime to port to.
- **6. Agent memory (conversation, entities, traces)**: no long-lived agent; memory is the book
  folder, which is already structured and owner-readable.
- **8. Distilling skills from memory with drift tracking**: skills are hand-written from course
  lessons and versioned in git; there are no stored traces to distil from.
- **10. Configuration graphs for regionally varying rules**: the closest thing (KDP royalty
  thresholds per format and marketplace) is one small table in the kdp-listing skill.
- **13. Compiling successful runs into a YAML skill**: needs many comparable runs; a book launch
  runs once a year.

## (d) Ranked recommendation

1. **Nothing yet, for this repo on its own.** One book, 111 tasks, a 3.3 MB SQLite store and
   48 lessons do not have a query that hurts. The scheduler and the TOML contract are working
   and tested; putting either behind a graph server is cost with no return.
2. **Do the entity resolution of group resources in SQLite first** (a `resource_entities` table
   plus an alias map, or the stage-3 extract prompt asked for a canonical name). This is needed
   regardless, costs little, and makes "which tools and vendors does the group recommend most,
   by distinct people" a one-line query. It is also exactly the data a graph would ingest later.
3. **If the adoption session picks a cross-repo people graph (peoplelm + mailerlm + podlm
   guests) as the first use case, publishinglm joins as a source, second wave.** It contributes
   Facebook identities, thread participation, resource mentions with `recommended`, launch-team
   membership and podcast pitch state through a small export verb
   (`publishinglm graph export` → CSV or JSON rows), with no Neo4j driver in this repo. That
   keeps the adoption plan's isolation rule trivially: the Cypher lives wherever the shared
   graph lives.

## (e) Open questions for the owner

1. Will there be a second and third book through this pipeline, and when? Precedent lookup and
   decision traces only pay with more than one book.
2. Who owns person identity across repos: peoplelm? If so, should the Facebook group people
   (482 today) be pushed into peoplelm at all, given they are strangers scraped from a group and
   not contacts? This is a privacy ruling as much as a modelling one.
3. Is the groups collection ongoing (more groups, months of history), or a one-off study of one
   group? At ten groups and tens of thousands of threads the who-recommends-what network becomes
   interesting; at 335 posts it is a spreadsheet.
4. Is there a question you have actually wanted to ask and could not, of the kind "which people
   connect X and Y"? If none comes to mind for publishing, that supports "nothing yet".
5. The peoplelm integration sits in worktree `bold-boyd-618347` and is not on this branch or
   main as far as this assessment saw. Is it landing? The people-graph recommendation depends on
   it.
6. Should skill-run capture (which skill ran, what it asked, what the owner answered) be solved
   once in metalm for every repo, rather than per repo? publishinglm would be a consumer.
