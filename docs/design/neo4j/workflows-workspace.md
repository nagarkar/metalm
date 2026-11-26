# Workspace: workflows that cross repos

Status: analysis, 2026-11-04. Read-only pass over session history, skills, guidelines and
code. Second-pass companion to [neo4j adoption plan](../neo4j%20adoption%20plan.md)
("Orchestration framing") and to the per-repo files `workflows-<repo>.md` in this folder.
Content is paraphrased; no manuscript or transcript text is quoted.

## Sources and method

- Transcripts: every JSONL under `~/.claude/projects/-Users-nagarkar-workspace-repos*`
  (58 project folders) for the call matrix; five workspace-root sessions and the podlm
  sessions with the most cross-repo calls for the procedures.
- A script pulled, in order, the owner's typed messages, the assistant's Bash command
  lines and Skill/Agent names. Tool output was left out.
- "Calling repo" means the folder the session was opened in. That is not always the repo
  being worked on: mailerlm was built from a workspace-root session, publishinglm partly
  from a ytlm-folder session. Those rows are marked.
- A call is counted only when the CLI name sits in command position (start of a command,
  after `;`, `&&`, `|`, `$(`, or a `bin/` path). Mentions inside `grep`, `cd` or prose are
  not counted. Counts are commands, so one command line with two verbs counts twice.
- Owner-message pattern counts in (c) come from regular expressions over the owner's
  messages. They are indicative, not exact.

Workspace-root sessions examined (the Neo4j session and trivial ones skipped):

| Session start | What it was | Cross-repo shape |
|---|---|---|
| 2026-11-04 | New repo `robolm`, `metalm-setup`, C++ support added to metalm | metalm rule change plus one repo |
| 2026-10-30 | Which databases and skills could run in a cloud session; cost estimate | read-only survey of all repos, by subagents |
| 2026-10-19 | Cloud-session test of authorlm's papers skill; `doc bind` added | owner carried results between a cloud and a local session by paste |
| 2026-10-18 | Brand icons for five repos from the metalm logo, one PR per repo | fan-out by subagents and worktrees |
| 2026-10-10 to 14 | mailerlm built from nothing (grilling, `metalm-setup`, steps 1 to 4) | new repo; keys and patterns copied from siblings |

Finding: workspace-root sessions carry workspace maintenance (X5 below). The content
workflows that cross repos run from inside podlm, ytlm, publishinglm and beelm sessions.

## (a) Cross-repo call matrix

Commands typed by the assistant in a session of the row's repo that invoke the column's
CLI. Self-calls are in the last column for scale.

| Session folder | authorlm | ytlm | corpuslm | podlm | publishinglm | peoplelm | mailerlm | beelm | computerlm | superlm-notify | own CLI |
|---|---|---|---|---|---|---|---|---|---|---|---|
| podlm | **620** | **124** | 5 | – | 0 | 1 | 0 | 0 | 0 | 8 | 671 |
| ytlm | 110 | – | **144** | 15 | 84 (a) | 0 | 5 | 21 | 0 | 1 | 1119 |
| publishinglm | **131** | 1 | 0 | 0 | – | 64 | 7 | 0 | 1 | 0 | 115 |
| authorlm | – | 54 | 8 | 74 | 0 | 0 | 0 | 0 | 0 | 0 | 4602 |
| beelm | 5 | 11 | 13 | 1 | 0 | 0 | 0 | – | 22 | 7 | 144 |
| metalm | 3 | 24 | 0 | 2 | 0 | 0 | 0 | 0 | 1 | 2 | 25 (`metalm-ops`) |
| llmlm | 3 | 10 | 11 | 0 | 1 | 0 | 2 | 2 | 0 | 0 | library, no CLI |
| tradelm | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 548 |
| (workspace root) | 18 | 2 | 1 | 0 | 1 | 1 | 102 (b) | 0 | 0 | 0 | – |

(a) publishinglm built from a ytlm-folder session. (b) mailerlm built from the root.

Top cross-repo verbs (same counting, flags skipped):

| Caller | Callee verb | Count |
|---|---|---|
| podlm | `authorlm doc pull` / `doc push` / `doc diff` | 104 / 100 / 66 |
| podlm | `authorlm media list` | 54 |
| podlm | `authorlm collect` | 37 |
| podlm | `authorlm illus list` / `illus render` / `illus import` / `illus pick` | 26 / 17 / 7 / 6 |
| podlm | `authorlm clip ensure` / `clip` (job, pick) / `clip spec` | 10 / 12 / 5 |
| podlm | `authorlm doc list` / `doc add` / `doc threads` / `audio export` | 21 / 9 / 9 / 9 |
| podlm | `ytlm corpus list` / `run` / `segments` / `search` / `usage` | 11 / 11 / 9 / 6 / 8 |
| ytlm | `authorlm doc list` / `doc push` / `doc pull` | 24 / 16 / 9 |
| ytlm | `corpuslm doctor` / `monologue run` / `review check` / `speakers attribute` | 20 / 12 / 10 / 8 |
| publishinglm | `authorlm doc list` / `filter status` / `filter run` / `filter edits` / `filter record` | 24 / 12 / 12 / 10 / 8 |
| publishinglm | `peoplelm` (setup, doctor, service calls) | 64 |
| beelm | `computerlm jobs` | 11 |
| authorlm | `ytlm excerpt` / `ytlm find`; `podlm preview-filter` | 10 / 5; 5 |
| tradelm, podlm, beelm | `superlm-notify` | 12, 8, 7 |

What the matrix says:

- **authorlm is the hub.** Three repos drive it harder from outside than they drive most of
  their own verbs: podlm (620), publishinglm (131), ytlm (110). Its document sync
  (`doc diff`, `pull`, `push`) is the single most called cross-repo surface: 270 of
  podlm's 620.
- **podlm is the largest consumer**: almost as many calls into authorlm (620) as into
  itself (671).
- **llmlm does not appear as a called verb.** It is a library with no CLI; every repo
  imports it. "Images and video through llmlm" in the owner's example is in practice
  `authorlm illus` and `authorlm clip`, which call models through llmlm.
- **Two kinds of coupling exist.** Library and database: ytlm and beelm import corpuslm
  (62 and 44 import sites), computerlm imports corpuslm and eventlm. Subprocess: podlm
  has 11 code sites that shell out to `authorlm` and 3 to `ytlm`. Everything else in the
  matrix is the assistant typing another repo's verb by hand.

## (b) Cross-repo workflows

Step kinds: **verb** (a CLI call, deterministic or billed), **model** (judgement by the
assistant or a subagent), **owner** (a decision only the owner makes), **gate** (a check
that must pass before the next step). Formality: **coded** (a verb or code does it and
records state), **skill** (prose in a SKILL.md tells the assistant), **chat** (worked out
between the owner and the assistant in the session, written nowhere or added to a skill
afterwards).

### X1. A monologue episode, from brief to YouTube (the owner's example)

Seen across podlm sessions of 2026-10-25 to 11-02 (series planning, the two "religion"
monologues, their prototype and production rounds). Repos: podlm, authorlm, ytlm,
corpuslm (Bee), then YouTube.

| # | Step | Kind | Owner repo | Artifact in → out, how identified | Formality |
|---|---|---|---|---|---|
| 1 | Series charter and the next topic | owner + model | podlm (files outside git) | charter is an authorlm profile `series-<series>` on the show manuscript | skill, written after the chat of 10-25 |
| 2 | Section brief from the book: paragraph summaries, concepts | verb | authorlm | manuscript name (`-m SMSTTD`); summaries keyed by paragraph | chat first (done ad hoc), then an issue asked for a standard verb |
| 3 | Find source moments: videos, Bee conversations | verb + model | ytlm, corpuslm | `ytlm search` hits: video id plus time; corpus name; Bee source id | skill (podlm research section; `corpuslm` moments) |
| 4 | Choose the spine source and the parallels | owner + model | podlm | chosen clips noted in the section brief | chat ("we should have this dialogue every time") |
| 5 | Draft the script, register it as a file of the show manuscript | model + verb | authorlm | `authorlm -m <show> doc add <slug>.md`; Doc tab created | skill |
| 6 | Review round in the Doc: owner edits and comments | owner | authorlm (Google Doc) | Doc tab; comment threads | coded on the authorlm side |
| 7 | Sync round: `doc diff` → `doc threads` → `doc pull` → revise → `doc push` | verb + model | authorlm | file name plus manuscript; content hash per file in authorlm | coded verbs, order held in the assistant's head |
| 8 | Check the script against the manuscript and style (lens, critique, articulation) | verb + model | authorlm | lens run on the file | partly coded; the articulation check began as pasted instructions |
| 9 | Read-aloud: `audio export` or the teleprompter export | verb | authorlm | file → audio page link | coded |
| 10 | Media tags in the script resolved: `collect`, `media list --json` | verb | authorlm | media key (a slug of the tag text) | coded |
| 11 | Pictures: `illus list` → `illus render "<title>"` → pick or pin | verb (billed) + owner | authorlm | illustration title, take number | coded; spend gate above $0.50 |
| 12 | YouTube clips: sentence boundaries, then cut | verb + model | ytlm | `ytlm segments <video_id> --from --to --check`; `ytlm excerpt <id> --start --end`, cached in the ytlm workspace | coded (podlm calls it in code) |
| 13 | Generated video: `clip ensure --dry-run --json` → owner yes → `--generate --confirm --model` → `clip job` → `clip pick` | verb (billed) + owner | authorlm | clip key, job id (key plus timestamp), take number | coded; the approval itself is chat |
| 14 | Owner records the take (Riverside), files land in the episode folder | owner | podlm | episode slug; folder on the external disk | skill checklist |
| 15 | Build: `podlm up <slug>` to the draft gate; `podlm verify` | verb + gate | podlm | slug; per-stage fresh/stale board | coded |
| 16 | Review page on the phone, notes back, rebuild | owner + verb | podlm | gallery artifact link; notes keyed by beat and time | coded page; "what happens to my notes" settled in chat |
| 17 | `podlm approve <slug> draft` | owner gate | podlm | approval fingerprinted on the file | coded |
| 18 | Packaging: titles, hooks, thumbnail brief, description | model + owner | podlm | `podlm review titles|hooks` | coded plus chat |
| 19 | Upload, then the video link back | owner + verb | podlm → YouTube | YouTube URL pasted by the owner | coded; sign-in check added to the skill after a miss |
| 20 | `superlm-notify` when a long step ends | verb | metalm | repo name and message | coded |

Identifiers that cross the boundary: manuscript name, file name inside it, media key,
clip key and job id, illustration title, ytlm video id with start and end, corpus name,
episode slug, YouTube URL. Only the first two are ever checked by the receiving repo; the
join between "episode slug" (podlm) and "file in manuscript" (authorlm) is by convention
of equal names.

### X2. The corpus document chain (ytlm → corpuslm → authorlm)

Detailed in [workflows-ytlm.md](workflows-ytlm.md) (W2). Cross-repo skeleton:

| # | Step | Kind | Owner repo | Artifact, identifier | Formality |
|---|---|---|---|---|---|
| 1 | Add videos, fetch, transcribe, clean | verb (billed) | ytlm | video id; corpus name | coded |
| 2 | Rows land in the shared transcript database | verb | corpuslm (schema owner) | source id, `kind` = youtube or bee | coded (import, not subprocess) |
| 3 | Health and migrations: `corpuslm doctor`, `review check` | gate | corpuslm | schema `user_version` | coded |
| 4 | Speakers, claims, moments | verb (billed) + owner review page | corpuslm | source id, section | coded; `--dry-run` first |
| 5 | Work orders for the corpus document | model + verb | ytlm | corpus ↔ manuscript name | coded after the 10-02 design chat |
| 6 | Write into the manuscript: `authorlm doc list`, `doc push` | verb | authorlm | manuscript = corpus name; tab = file | coded sync; naming settled in chat (a tab once got a hash for a name) |
| 7 | Owner reads the Doc | owner | authorlm | Doc link | chat |

### X3. A spoken directive becomes a job (beelm → corpuslm → eventlm → computerlm → any repo)

Detailed in [workflows-beelm.md](workflows-beelm.md) (W4). This is the one cross-repo
workflow that is already a procedure in code:

| # | Step | Kind | Owner repo | Artifact, identifier | Formality |
|---|---|---|---|---|---|
| 1 | Sync Bee transcripts | verb (launch agent) | beelm | Bee conversation id | coded |
| 2 | Digest: claims, directives | verb (billed, capped) | corpuslm | source id | coded |
| 3 | Publish `transcript.digested` | verb | eventlm | event row; cursor per subscriber | coded |
| 4 | Draft one plan per directive | model | computerlm | job row | coded |
| 5 | Owner approves on the plan page | owner gate | computerlm (port 15443) | job id | coded |
| 6 | Pinned Claude Code session does the work in the target repo | model | target repo | session; `computerlm jobs` | coded start, free-form inside |
| 7 | Notify | verb | metalm (`superlm-notify`) | – | coded |

It has what X1 lacks: an event that starts it, a stored plan, an approval page, a job
record. Inside step 6 it is as informal as everything else.

### X4. Book launch chain (publishinglm → authorlm → peoplelm → mailerlm)

Seen in publishinglm sessions (131 authorlm calls, 64 peoplelm, 7 mailerlm).

| # | Step | Kind | Owner repo | Artifact, identifier | Formality |
|---|---|---|---|---|---|
| 1 | Plan, goals, schedule | owner + verb | publishinglm | `books/<manuscript>/plan.toml`; task ids | coded (`plan schedule`, `plan status`) + skills |
| 2 | Read the manuscript's state | verb | authorlm | `doc list -m`, `export show`, `style show` | coded |
| 3 | Line edit as filter rounds: `filter run` → `filter status` → `filter edits` → `filter record` | verb (billed) + owner | authorlm | filter run id; edit ids | coded |
| 4 | Lead magnet, description, cover brief drafted from the manuscript | model | publishinglm skills | files under `books/<manuscript>/` | skill |
| 5 | Cover and A+ pictures | verb (billed) | authorlm `illus` | illustration title | coded |
| 6 | People: launch team, group members | verb | peoplelm (HTTP service) | person id | coded service |
| 7 | Campaign drafts; the owner presses Send | verb + owner gate | mailerlm | campaign id, list id | coded; skill says publishinglm never drives mailerlm sends |

The join key is the manuscript name used as a folder name in publishinglm and as `-m` in
authorlm.

### X5. A workspace change fanned out to many repos

Seen in three of the five root sessions (brand icons, new repo setup, mailerlm build) and
in the `metalm-setup` skill.

| # | Step | Kind | Owner repo | Artifact, identifier | Formality |
|---|---|---|---|---|---|
| 1 | Owner names the change and the repos | owner | – | chat | chat |
| 2 | Grilling, one question at a time | owner + model | skill `grilling` | – | skill |
| 3 | Change the rule or asset in metalm, PR | model + verb | metalm | branch, PR number | skill (`metalm`, `metalm-setup`) |
| 4 | One subagent or worktree per target repo | model | each repo | branch `app-brand` style, one per repo | chat; subagent reports are free text |
| 5 | Tests and lint per repo | gate | each repo | – | coded (pre-commit, pytest) |
| 6 | Owner says push; one PR per repo; merge | owner gate | GitHub | PR links | chat |
| 7 | Clean worktrees; update the served-apps table | verb | – | – | chat (the owner asked for both) |

### X6. A tool defect found in another repo, mid-workflow

Seen in podlm (authorlm defects during X1, 10-26), and as W6 in the authorlm and ytlm
files. Guideline: "file an issue there and say which contract term it would change"
(`coding.md`, Contracts between repos).

| # | Step | Kind | Formality |
|---|---|---|---|
| 1 | The calling workflow hits a wrong result from another repo's verb | – | – |
| 2 | Decide: work around, file an issue, or fix now | owner | chat every time |
| 3 | Fix in a subagent or a second session in the other repo, with a test from the failing case | model | chat |
| 4 | Merge there (the owner grants merge rights per repo) | owner gate | chat |
| 5 | Return and rerun the step that failed | verb | chat; nothing records where the workflow stood |

## (c) How the procedure knowledge is carried, and where it failed

### Carriers

| Carrier | Size | What it holds for cross-repo work |
|---|---|---|
| Skill prose | podlm 1,883 lines; authorlm 2,476; ytlm 379; publishinglm 11 skills | The only written procedure. podlm's skill names an `authorlm` verb on 13 lines and a `ytlm` verb on 24, against 720 and 131 actual invocations |
| `CLAUDE.md` and metalm guidelines | 11 guideline files | Rules, not procedures: one hand-off between producer and consumer, shared database rules, spend and outbound gates, contracts between repos |
| Memory notes | podlm 35 files, authorlm 47, ytlm 16, beelm 0, workspace root 0 | Per-repo corrections. Nothing at the workspace level, so a cross-repo lesson learned in a podlm session is invisible to an authorlm session |
| The owner's messages | 1,130 in podlm sessions, 558 in ytlm, 2,750 in authorlm | The actual sequencing: what comes next, which Doc, when to stop |
| Code | podlm: 11 subprocess sites to authorlm, 3 to ytlm; eventlm events | The only handoffs that survive without the assistant |
| Stored state | each repo's own SQLite or files; `podlm status` board; computerlm `jobs` | Per repo. No record spans two repos except eventlm's event log |

### Failure modes, with evidence

1. **Verbs rediscovered each session.** Share of cross-repo commands that are `help` or
   `--help`: podlm→authorlm 90 of 720 (12%), podlm→ytlm 24 of 131 (18%), ytlm→authorlm
   32 of 131 (24%), publishinglm→authorlm 27 of 150 (18%). Roughly one call in six is the
   assistant relearning another repo's interface.
2. **No stable call shape.** The manuscript flag in podlm→authorlm commands sits in three
   positions: straight after `authorlm` (195), after the verb group (214), later (167).
   Same verb, three spellings; a spelling that fails costs a retry.
3. **Which document is which.** Two manuscript names carry X1 (562 and 178 uses). The
   owner asked what "the main manuscript Doc with the scripts" was, whether every
   manuscript has two Docs, and where a file was; this is why the global rule now
   requires a Doc link with every manuscript mention. Owner messages matching
   "where is / which doc, file, folder": 24 in podlm sessions, 37 in authorlm, 7 in ytlm.
4. **Steps skipped or reordered.** Owner messages matching "ignored, lost, forgot,
   missing, dropped": 23 in podlm sessions, 49 in authorlm, 6 in ytlm. Concrete cases in
   X1: a Doc comment the owner asked to have handled first was overwritten by a push; a
   review note to cut a clip was not applied; a picture was removed without saying which.
5. **Steps done outside the sanctioned verb.** Paragraph summaries for the series were
   produced ad hoc; the owner asked whether a standard authorlm verb had been used and
   had an issue filed to make it one. Clips were recorded in a second file when the
   section brief was the agreed place.
6. **Spend gate retried instead of asked once.** On 2026-11-01 `authorlm clip ensure
   --generate` was issued eight times in about a minute across four model names before a
   job started; the owner then ruled that naming a model is the approval.
7. **Preconditions found late.** Google sign-in for `authorlm doc` expired mid-round and
   the owner ran the auth by hand; YouTube sign-in was not checked before the owner was
   asked to upload. Both were then written into a skill.
8. **Procedure written after the fact.** Owner messages asking to put something just
   learned into a skill, rule or guideline: 19 in podlm sessions, 26 in authorlm, 4 in
   ytlm. The skill is a log of past corrections more than a plan.
9. **The owner as scheduler.** "What's next", "anything left", "any tasks for me": 7 in
   podlm, 27 in authorlm, 8 in publishinglm (of 219 messages there). In the cloud-test
   session the owner pasted one session's output into another five times; that is a
   handoff with no carrier at all.
10. **Session folder is not the repo.** 84 publishinglm commands ran from a ytlm-folder
    session and 102 mailerlm commands from the root, so memory notes and skills loaded
    were the wrong repo's.

## (d) What a workspace-level procedure runner would need

### Requirements, from the evidence

- **Definitions as data.** One file per procedure, readable in a PR. A procedure owned by
  one repo lives in that repo (`procedures/<name>.yaml`); one that crosses repos lives
  with the runner, or with the repo that starts it and is registered with the runner.
  Versioned by content hash, per the guideline on identity.
- **A step names a verb by repo and verb path, not by shell text.**
  `use: authorlm/doc.pull` with typed arguments. The runner resolves the CLI on PATH,
  always asks for `--json`, and owns the one spelling of each call (ends failure 2).
  A per-repo verb manifest (generated from each CLI's `help --json`, like
  `metalm-gendocs`) lets the runner check a definition before running it (ends failure 1).
- **Preconditions are steps.** `doctor`, sign-in status and mounted-volume checks run
  first, as gates (ends failure 7).
- **Runs and step results are rows.** Run: procedure id and hash, inputs, who started it,
  state. Step result: step id, attempt, argv, exit code, parsed output, artifacts in and
  out as typed references (`authorlm:file/<manuscript>/<name>@<hash>`,
  `ytlm:video/<id>#t=<start>-<end>`, `podlm:episode/<slug>`), model and cost for model
  steps, the decision and its reason for owner steps. That is the standard decision-trace
  shape: the same columns for every repo.
- **Owner gates and spend gates are step kinds.** `owner` pauses the run, notifies with
  `superlm-notify`, shows what will be decided with its links, and resumes on a recorded
  answer. `spend` runs the verb's `--dry-run`, compares with the $0.50 rule and the
  per-run cap, and either proceeds or becomes an owner gate. An approval is keyed on the
  content hash of what was shown, so a cosmetic change does not reopen it and a retry
  does not ask twice (ends failure 6).
- **Resumable.** A run stopped at a gate, a failed step or a tool defect (X6) restarts
  from the stored state, in any session or none.
- **Model steps are small and typed.** Input artifacts, an output schema, a model
  profile; called through llmlm so cost lands in the existing ledger.
- **It publishes events** to eventlm (`procedure.step.done`, `procedure.gate.waiting`) so
  computerlm, the ops dashboard and other repos can subscribe without importing it.

### Where it should live

| Candidate | For | Against |
|---|---|---|
| llmlm | Already the model-call layer, ledger and spend caps | A library with no CLI and no state of its own beyond the ledger; a runner would change what it is |
| computerlm | Already has plan, approval page, `jobs` table, notify | Built around Bee directives; depends on corpuslm and eventlm; its job is one opaque session, not typed steps |
| metalm | Owns the rules; cross-repo by nature | States that it depends on nothing but git; holds guidelines, not runtime |
| codeteamlm | Has a harness, memory, budgets | Purpose is hardening code by PR; a different loop |
| **A new small repo** | Depends on eventlm and llmlm only; every repo can be a step without importing it | One more repo |

Recommendation: **a new small repo** for the runner and the cross-repo definitions.
llmlm stays the model layer underneath it, eventlm the bus beside it, computerlm becomes
a client (an approved directive starts a procedure) and lends its approval-page pattern.
metalm gets one guideline section on procedure files and the verb manifest.

### Three stores compared

| | YAML files + SQLite | Neo4j Community | LangGraph-style runtime |
|---|---|---|---|
| Definitions | Files in git, reviewed in PRs, hashed | Nodes and edges; needs a loader from files anyway, or definitions leave git | Python graph code; steps are in-process functions |
| Runs | Tables: run, step_result, artifact_ref, gate | Run and step nodes linked to artifact nodes | Checkpoints in SQLite or Postgres |
| Calling a CLI verb | Native: the runner is a process that runs processes | Not its job | Each verb needs a wrapper node |
| Owner gates | A row and a page | Not its job | Interrupts exist, built for a chat loop |
| Fits the guidelines | Yes: SQLite, no daemon, WAL, backed up nightly already | Needs an `(owner)` exception: a daemon, no online backup, no access control | New framework dependency; "reuse house patterns before proposing a library" |
| In use here | Every repo | Nothing | Cloned 2026-07 (`langgraph`, `graphiti`, `neo4j-graphrag-python`, `graph-data-science-client`, `semantica`); no `*lm` repo depends on any of them |

**What Neo4j adds over files plus SQLite for this workspace:**

- Open-ended questions across runs and artifacts without writing a join per question:
  "every run that touched this manuscript file, the clips it used, the videos those came
  from, and the owner decisions on them". With artifact references as nodes, that is one
  pattern match.
- Precedent lookup by neighbourhood for a model step: prior decisions on the same
  artifact, the same source or the same step in other procedures.
- A browser view of a run joined to the knowledge layer, if that layer is ever built
  (the first-pass candidate). Procedures-and-runs then shares one graph with it.

**What it does not add:**

- Execution, gating, retries, idempotency or resumption. Those are the runner.
- Any of the savings in (e). Those come from the procedure being explicit.
- Anything at current volume. X1 runs a few times a week; a run has tens of steps. The
  joins above are three or four tables in SQLite and run in milliseconds.
- Safety. One database, no access control, stop-dump-start backups.

Plain answer: build the runner on YAML plus SQLite. Give `artifact_ref` a stable,
repo-qualified form from day one. If the cross-artifact questions start to hurt, export
runs, steps and artifact references to Neo4j as a derived store (the plan's exit rule 5);
nothing in the runner changes.

## (e) Model routing once procedures are explicit

| Step (workflow) | Today | Could be | Evidence needed to trust it |
|---|---|---|---|
| Finding the right verb and flags (all) | Frontier model reads `help` (12 to 24% of cross-repo calls) | No model: the definition names the verb | The manifest check passes; zero `help` calls inside a run |
| Doc sync round: diff, threads, pull, push in order (X1, X2, X4) | Frontier model sequences 270 calls | No model for sequencing; model only for the revision | Replay of stored rounds gives the same call order; no comment lost over N rounds |
| Precondition and health checks (X1, X2, X3) | Model remembers, sometimes | No model | Gate rows exist for every run |
| Media tag resolution, `collect`, `media list` (X1) | Model drives | No model | Output of `--json` equals the stored result on rerun |
| Clip boundaries snapped to sentences (X1 step 12) | Subagent reads segments | Small model or code over `ytlm segments --check` | Owner "cut mid-speech" notes per episode do not rise against the stored baseline |
| Spend decision (X1 steps 11, 13) | Model asks, retries | No model: dry-run cost against the rule | Every billed step has a dry-run row and one approval |
| Picking candidate moments from search hits (X1 step 3, X2 step 4) | Frontier model | Mid-tier model with a typed output, precedent retrieved | Owner keeps the same share of proposed moments over 20 decisions |
| Titles, hooks, description drafts (X1 step 18) | Frontier model | Mid-tier for options, owner chooses | Chosen option comes from the cheaper model's list as often as before |
| Fan-out edits per repo (X5 step 4) | Frontier subagents | Mid-tier subagents on a fully specified change | Tests pass first time at the same rate; PR review comments per repo |
| Writing or revising the script, choosing the spine, critique (X1 steps 4, 5, 7, 8) | Frontier model | Stays frontier | – |
| Diagnosing a tool defect (X6) | Frontier model | Stays frontier | – |

General rule for trust, matching `coding.md` ("Choosing a model"): record per step the
model, cost, and an outcome signal already produced by the workflow (owner accepted,
owner edited, owner reverted, gate passed). Run the cheaper model in shadow on the same
stored inputs, compare on that signal, and switch a step only when the sample is large
enough to show no drop. The stored runs are the sample; without them the question cannot
be answered.

## (f) Pilot: the script-and-media round of a monologue

Formalise the middle of X1 (steps 6 to 13 and the hand-off to step 15): from "the script
is in the manuscript" to "every media tag has a file and podlm can build". Reasons:

- Highest volume: it is most of podlm's 620 authorlm and 124 ytlm calls.
- Most failures in (c) happen here (lost comment, clip retries, sign-in, wrong Doc).
- Every step already has a verb with `--json` or a dry run. Nothing new is built in
  authorlm, ytlm or podlm; the pilot only sequences.
- It embeds authorlm's own first candidate (the Doc review round, W1 in
  [workflows-authorlm.md](workflows-authorlm.md)) as a sub-procedure, so one pilot tests
  a single-repo procedure and a cross-repo one.
- It has both gate kinds: owner review and spend.

Sketch. Verb names are as observed in sessions and the podlm skill; confirm each against
the CLI's `help` when the manifest is generated.

```yaml
procedure: monologue.script-and-media
version: 1
inputs:
  manuscript: {type: authorlm.manuscript}        # e.g. the show manuscript
  file:       {type: authorlm.file}              # <slug>.md inside it
  episode:    {type: podlm.episode}              # slug; equals the file stem
limits: {usd_per_run: 5.00, ask_above_usd: 0.50}

steps:
  - id: pre
    kind: gate
    all:
      - use: authorlm/doc.status      {manuscript: $manuscript}     # Google sign-in valid
      - use: corpuslm/doctor
      - use: podlm/status             {episode: $episode}
    on_fail: {kind: owner, ask: "Fix sign-in or volume, then resume"}

  - id: doc-round                      # sub-procedure, authorlm W1
    kind: loop
    until: owner.says_closed
    steps:
      - {id: diff,    kind: verb,  use: authorlm/doc.diff,    args: {manuscript: $manuscript, file: $file}}
      - {id: threads, kind: verb,  use: authorlm/doc.threads, args: {manuscript: $manuscript, file: $file}}
      - {id: pull,    kind: verb,  use: authorlm/doc.pull,    when: diff.remote_changed}
      - id: revise
        kind: model                    # frontier; typed output
        in:  [pull.file, threads.open]
        out: {edits: list, replies: list, removed: list}   # removals always listed
        rule: comments are answered before any other edit
      - {id: lens,    kind: gate,  use: authorlm/lens.run,    args: {file: $file}}
      - {id: push,    kind: verb,  use: authorlm/doc.push,    needs: [lens]}
      - {id: review,  kind: owner, show: [doc.link, revise.removed], notify: superlm-notify}

  - id: tags
    kind: verb
    use: authorlm/collect              {manuscript: $manuscript}
  - id: media
    kind: verb
    use: authorlm/media.list           {manuscript: $manuscript, file: $file, json: true}
    out: {items: list}                 # each: key, type (picture | youtube | generated), state

  - id: resolve
    kind: foreach
    over: media.items where state != ready
    switch: item.type
    cases:
      picture:
        - {kind: spend, use: authorlm/illus.render, args: {title: $item.title}, dry_run: true}
        - {kind: owner, when: takes > 1, ask: "Pick a take", then: authorlm/illus.pick}
      youtube:
        - {kind: verb,  use: ytlm/segments, args: {video: $item.video, from: $item.start, to: $item.end, check: true}}
        - {kind: model, tier: small, out: {start: time, end: time}, rule: whole sentences}
        - {kind: verb,  use: ytlm/excerpt,  args: {video: $item.video, start: $start, end: $end, json: true}}
      generated:
        - {kind: verb,  use: authorlm/clip.ensure, args: {key: $item.key, dry_run: true, json: true}, out: {model, seconds, usd}}
        - {kind: spend, approve_once_per: [item.key, model], named_model_counts_as_yes: true}
        - {kind: verb,  use: authorlm/clip.ensure, args: {key: $item.key, generate: true, confirm: true, model: $model}}
        - {kind: wait,  use: authorlm/clip.job,    until: done}
        - {kind: owner, ask: "Accept this take?", on_no: {use: authorlm/clip.spec, then: retry}}

  - id: ready
    kind: gate
    use: authorlm/media.list           {manuscript: $manuscript, file: $file, json: true}
    expect: all items ready

  - id: handoff
    kind: verb
    use: podlm/up                      {episode: $episode}          # stops at podlm's own draft gate
  - id: verify
    kind: gate
    use: podlm/verify                  {episode: $episode}
  - id: done
    kind: owner
    show: [podlm.gallery.link, doc.link]
    notify: superlm-notify

record:                                # one row per step attempt
  [run, step, attempt, argv, exit, out_json, artifacts_in, artifacts_out,
   model, usd, decision, reason, shown_hash, started, ended]
```

What the pilot should measure against the sessions above: `help` calls inside a run
(target none), owner messages of the "where, which, why did you" kind per episode,
duplicate billed calls, and the share of steps that ran with no model.

## Follow-ups noticed, not acted on

- No memory notes exist at the workspace root; cross-repo lessons have no home.
- `authorlm` accepts the manuscript flag in several positions; one documented spelling
  would help even without a runner.
- The join "episode slug equals file stem equals media folder" is a convention; neither
  podlm nor authorlm checks it.
- A per-CLI machine-readable verb manifest (`help --json`) does not exist in every repo.
