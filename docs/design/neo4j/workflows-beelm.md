# beelm: workflows actually run

Second pass of the Neo4j assessment (see `../neo4j adoption plan.md`, "Orchestration framing"). The first pass, `beelm.md`, looked at beelm's data. This one reads the real session history and the skills to list the workflows the owner and Claude actually ran, as candidate procedures.

Method: a script extracted, in order, the owner's typed messages, the assistant's text, Bash command lines and tool names from each session file under `~/.claude/projects/-Users-nagarkar-workspace-repos-beelm/`. Tool outputs were left out. Nothing below quotes a conversation, and no person outside the household is named. Counts are from those digests; where a count is a lower bound it says so.

## (a) Sessions examined

| # | Dates (local) | Topic | Rough length |
|---|---|---|---|
| S1 | 2026-10-21 to 10-24 | "Bee transcript processing pipeline", part 1: what the pipeline does today, a grilling on the directives digest, then building it across four repos (eventlm, corpuslm, beelm, computerlm), the first live run, and a secrets-in-git rollout it uncovered | 43 owner turns, about 400 assistant turns, 4 days, compacted at least twice |
| S2 | 2026-11-02 to 11-03 | The same session, continued: branch cleanup, "process latest", a recall request for the manuscript, then four rounds of digest-failure diagnosis and fixes | 23 owner turns, about 370 assistant turns (its first half repeats S1's tail after a compaction) |
| S3 | 2026-11-02 to 11-03 | "Bee transcript pipeline performance" (two files, one session): the owner asks a second session to audit S2; it finds the root cause S2 missed, then repairs computerlm's sign-in and walks the first planned jobs | 11 owner turns, about 145 assistant turns |
| S4 | 2026-10-27 | Pull one conversation recorded minutes earlier, run the chain on it step by step, then digest the whole backlog and chase the failures | 8 owner turns, about 150 assistant turns |
| S5 | 2026-10-18 | Recall a conversation from "a week or so back", summarise the idea in it, have a subagent review it, publish the result as a Google Doc | 6 owner turns, about 70 assistant turns |

Skimmed for one data point only: 2026-10-08 "Latest Bee import" (a bare `sync`, then metalm setup work). Skipped: "Neo4j assessment: beelm", the two October "Metalm setup" sessions (setup, not a workflow).

## (b) Workflows observed

Step kinds: **verb** (a script or CLI call), **model** (model judgement), **owner** (owner decision), **gate** (a check that passes or stops).

### W1. Process the latest Bee transcripts (the daily chain)

Observed by hand 3 times (10-08 sync only; 10-27 one step per owner message; 11-02 "Process latest bee transcripts") and nightly by launchd since 10-22. The scheduled form is `scripts/sync.sh` → `beelm.sh doctor` → `beelm.sh corpus nightly`.

| # | Step | Kind | Verb or tool | Owner repo | In → out | Formality |
|---|---|---|---|---|---|---|
| 1 | Health check | gate | `beelm.sh doctor` | beelm | — → pass/fail per check | formal |
| 2 | Sync from the device | verb | `beelm.sh sync` (wraps the global `bee` CLI) | beelm | — → conversation files under `~/Bee`, one row in `runs.jsonl`, event `transcript.synced` | formal |
| 3 | Ingest | verb | `beelm.sh corpus ingest` | beelm, writing through **corpuslm**'s store | conversation JSON → `sources` and `segments` rows keyed `bee:<id>` in the shared transcript database | formal |
| 4 | Free cleanup | verb | `beelm.sh corpus basic-cleanup` | beelm, **corpuslm** chain | source → artifact files per source id | formal |
| 5 | Price the AI cleanup | verb | `beelm.sh corpus ai-cleanup --dry-run` | beelm | → sources, model calls, estimated dollars | formal |
| 6 | Spend gate | gate | under $2 run, at or above stop and tell the owner | beelm (rule in the skill and in `corpus nightly`) | estimate → go / stop | formal inside `nightly`; semi-formal (skill prose) when run by hand |
| 7 | AI cleanup, speaker map, subtitles | verb + model inside | `beelm.sh corpus ai-cleanup` (Gemini flash-lite through **llmlm**, prompts in **corpuslm**) | beelm | → cleaned transcript, speaker map, subtitle file, search index; open cards on **corpuslm**'s review page | formal |
| 8 | Price the digest | verb | `beelm.sh corpus digest [--source bee:<id>] --dry-run` | beelm | → sources, calls, dollars | formal |
| 9 | Spend gate | gate | same $2 rule; also the per-run cap `[llm].max_usd_per_run` | beelm | | formal / semi-formal as step 6 |
| 10 | Digest | verb + model inside | `beelm.sh corpus digest` (form by Jev, claims and directives by the Bee claims prompt, summary; all **corpuslm** code) | beelm | → `claims` rows (kind claim or directive), summary, events `transcript.digested` per source and `directive.found` per directive said to Computer | formal |
| 11 | Read the board, decide what failed | model | the assistant reads the counts | — | board → "done" or go to W2 | informal |
| 12 | Land review answers | verb | `beelm.sh review apply --dry-run`, then live | beelm (answers come from **corpuslm**'s review page) | owner's taps → verdict rows, rebuilt maps, event `speaker.landed` | formal verb; when to run it is informal (run once in three passes) |
| 13 | Report | model | one line per verb | — | | semi-formal (skill rule) |

### W2. Digest failure triage and recovery

Observed twice, both long: 10-27 (three passes over the backlog) and 11-02/03 (four rounds in S2, then the audit in S3). Entirely worked out in conversation.

| # | Step | Kind | Verb or tool | Owner repo | In → out | Formality |
|---|---|---|---|---|---|---|
| 1 | Notice failures | gate | `sources failed` on the digest board | beelm | | formal (the count); since beelm#53 the board also names failure types and skipped sections |
| 2 | Find which sources and which calls | verb | ad-hoc Python over `~/Bee/beelm/logs/usage.jsonl`, the per-run logs under `logs/runs/`, later `calls.jsonl` | beelm logs, written by **llmlm** | → list of source ids and call tags | informal (a new one-off script each time; at least 12 such scripts across S2 and S4) |
| 3 | See the real error | verb | 10-27: a temporary re-raise patched into `digest.py`, run on one source, reverted (done 3 times); 11-02: a scratch `repro.py` | beelm | → exception type | informal, and a different method each time |
| 4 | Classify the failure | model | content filter / reply cut off at the token limit / Jev HTTP 400 / a cached bad reply | — | → failure type | informal; four types seen |
| 5 | Decide the fix and where it lives | model, then owner | owner words: "Diagnose them", "Fix it here", "Fix the two remaining failures", "Recover them", "Yes, inspect one" | **llmlm**, **corpuslm**, beelm | | informal |
| 6 | Fix test-first and merge | verb + model | branch, failing test, fix, `pytest`, `ruff`, `pyright`, `metalm-gendocs`, `gh pr create`, `gh pr merge` in dependency order (llmlm → corpuslm → beelm) | each repo | → PRs (beelm 51, 53, 54; corpuslm 93, 94, 95; llmlm 18) | semi-formal (the skill's merge authorization; metalm's rules) |
| 7 | Rerun what failed | verb | `corpus digest`, later `corpus digest --retry-skipped` | beelm | → recovered sections, remaining skips | formal verb; nothing schedules it |
| 8 | Compare estimate with actual | model | read the board and the usage log | | | informal |

### W3. Recall from Bee for work in another repo

Observed 3 times: S5 (a past conversation → summary → expert subagent review → Google Doc), S4 (a call from minutes earlier → file link and summary), S2 (every mention of two concepts across all transcripts → the definitions given → the places in the [SMSTTD](https://docs.google.com/document/d/1VDLq5605h6f9yykyMCtWnsCOP9lnMIsTdVl6IrgF2ls/edit) manuscript that discuss them → four drafted insertions).

| # | Step | Kind | Verb or tool | Owner repo | In → out | Formality |
|---|---|---|---|---|---|---|
| 1 | Owner describes what to find | owner | a description, sometimes with a wrong or misheard name | — | | informal |
| 2 | Make sure it is in the store | verb | `beelm.sh sync` (S4 only: the conversation had just ended) | beelm | | formal |
| 3 | Locate the conversation or the passages | verb + model | three different paths in three runs: `ls`/`grep` over Bee's own markdown export; `beelm.sh search` per keyword; a Python regex over every `transcript.json` under the workspace | beelm | → source ids, segment references | informal |
| 4 | Read around each hit | model | file reads | | → what was said, with rough attribution | informal |
| 5 | Synthesise | model | summary, list of definitions, a pick | | → text in chat | informal |
| 6 | Locate the target in the other repo | verb + model | `authorlm doc list -m <manuscript>`, `grep` over the manuscript's chapter files and `toc.toml` | **authorlm** | → file and line for each insertion | informal |
| 7 | Second opinion | model | a subagent with a reviewer brief (S5) | | | informal |
| 8 | Deliver | owner then verb | S5: publish a Google Doc (Drive connector), then tidy a duplicate; S2: "Draft them" → drafts in chat only, because two target chapters were checked out to Google Docs | Google Drive; **authorlm** owns the checkout state | → Doc, or drafts with file:line targets | informal |

### W4. A spoken directive becomes a job (beelm → eventlm → computerlm → a session in any repo)

Designed in S1, first seen running in S3 (2026-11-02).

| # | Step | Kind | Verb or tool | Owner repo | In → out | Formality |
|---|---|---|---|---|---|---|
| 1 | Directive extracted | model | inside `corpus digest`: the wake word "Computer" makes a directive for computerlm, any other imperative is a note to self; a Jev gate checks each candidate | beelm calling **corpuslm** | → `claims` rows of kind directive, with addressee | formal |
| 2 | Events published | verb | `eventlm` publish from `beelm.digest`: `transcript.digested` (ids and counts) and `directive.found` (claim id); sources recorded before `[digest].directives_since` publish no `directive.found` | beelm → **eventlm** | → rows in the common events file | formal |
| 3 | Watcher makes a job | verb | `computerlm watch` under launchd, every 30 minutes | **computerlm** | one `transcript.digested` with directives → one job (`cj-…`), status `found` | formal |
| 4 | Plan drafted | model | `computerlm plan` (headless `claude -p`, capped per draft and per day); the prompt carries the whole cleaned transcript | **computerlm** | → plan, status `planned` | formal |
| 5 | Owner told | verb | mail through Resend | **computerlm** (mailerlm's key) | | formal, but was failing with HTTP 403 on 11-02 |
| 6 | Owner edits, approves or declines | owner | approval page (tailnet port 15443) | **computerlm** | → status `approved` or declined | formal |
| 7 | Job started in a session | verb + model | the "Computer" desktop scheduled task reads `computerlm approved`, starts a child session named "Computer Task: …" in the target repo, pins it | **computerlm**, then whichever repo the plan names (authorlm, ytlm, beelm, …) | → a pinned session | formal on paper; not yet seen running end to end in these sessions |
| 8 | Job closed | owner | the owner says so in the session, or archives it; `computerlm close` mails once | **computerlm** | → `done` | semi-formal (a child-session skill) |
| x | Stop a job that cannot be planned | owner then verb | `computerlm fail <job> --result …` | **computerlm** | → `failed` | formal verb, used once |

How `directive.found` reaches computerlm: it does not. beelm publishes it, but the watcher subscribes to `transcript.digested` only (the owner ruled one job per transcript, not one per directive) and then reads the directives from the transcript database. `directive.found` has no consumer today.

### Also observed, not specific to beelm

Design-to-build (S1): `/grilling` (20 questions) → issues filed (beelm#43, corpuslm#86) → child sessions per repo plus subagents → PRs merged under each repo's authorization → first live run. And repo hygiene (S2): list branches and worktrees, delete what is fully merged, extend `.gitignore`. Both are general development procedures better captured once in metalm than per repo.

## (c) Friction, with evidence

| Friction | Evidence | Count |
|---|---|---|
| The owner drove the chain one verb at a time | S4: four consecutive owner messages, each naming the next verb; two of them restate the $2 standing authorization that the skill already records | 4 messages, 2 restatements |
| "What's left here?" / "What's next here?" | S1 twice, S3 twice. The session had no stored notion of where the run stood | 4 |
| The chain's dry run cannot price what it has not synced | `corpus nightly --dry-run` printed $0.00 on 10-22 and again on 11-02; both times the assistant discovered it afresh and fell back to running the steps by hand | 2 |
| The root cause was missed while symptoms were treated | S2 ran four rounds (token limit, skip the section, clip the field, short-quote retry). S3 then checked every cut-off reply in the run logs: all 35 stopped inside the same unbounded quoted field. S4 had already met an oversized instance of that field six days earlier; nothing carried the finding forward | 4 rounds; 1 finding lost between sessions |
| A different diagnostic path each time | See W2 steps 2 and 3: a re-raise patch applied and reverted 3 times in S4, a repro script in S2, log parsing rewritten per question | 3 patches, 12+ one-off scripts |
| A different locate path each time | W3 step 3: three runs, three methods. In S4 the assistant read the raw export with `ls` and `grep` and did not use the search verb | 3 of 3 differ |
| Source id format guessed wrong | S4: `--source` tried with the bare id twice before `bee:<id>` | 1 (3 attempts) |
| Estimates not matching the bill | S2: failed calls were absent from the spend log, so a run reported at about one cent may have cost near a dollar; the retry was estimated at $0.03 and cost $0.16 | 2 |
| The first unattended run would have failed | S1, found only because the owner asked "what's left": a conversation with no end time crashed ingest; the venv lacked a newly split-out dependency; the model keys were missing from `.env` | 3 causes |
| Silent failure downstream | computerlm's planner was turned away at sign-in from 10-23 to 11-02 (a token saved across three lines). 3,185 failed planner runs, no alert. The owner learned of it from the S3 audit | about 10 days |
| Wrong advice the owner had to correct | S3: told to create a new token; the owner objected that it lasts a year; the stored value was merely split. S1: "Why are the steps for computerlm mine?" | 2 |
| Terms the owner had to ask about | "What claims are we talking about?", "What cache replies?", whether claims live in files and tables at once (three turns in the grilling) | 3 topics |
| A rule attributed to the owner that the owner never made | S1: the secrecy rule had been written by the assistant and tagged as an owner rule; the owner asked who made it and threw it out | 1 |
| Jobs raised from ordinary talk | S3: of 15 jobs, the assistant flagged several as conversation, not requests; the owner declined at least 2; one was blocked by the planner model's safety filter and retried, billed each time, until marked failed by hand | 15 jobs: 14 planned, 1 failed, 2+ declined |
| Steps the owner must remember | sync before pricing; `review apply` after tapping answers on the review page (and that it must be beelm's verb, not corpuslm's); `--retry-skipped` (nightly never retries); raising the per-run cap for a backlog; loading launch agents; restarting the review server onto new code | 6 |
| Skill and help drift | `--retry-skipped` is in neither skill; `beelm help` says search hits are references only while the skill says they carry the line; the owner's two skill edits have sat uncommitted since before 10-22 and are reported as "still uncommitted" in at least 6 assistant messages | 3 |
| Tests wrote into live state | S1: 11 of the first 16 rows in the common events file came from test runs | 1 |
| Very long sessions | S1+S2 is one session spanning 13 days and at least four compactions; S3 judged that its drift, not its token use, was the cost | — |

## (d) Model fit per step

The model calls inside the verbs are already on cheap tiers: Gemini flash-lite for cleanup, claims and summary, Jev for form and the directive gate. The expensive part is the orchestrating session, which ran on a frontier model throughout (the owner set Opus on 10-22) for work that was mostly running verbs and reading boards.

| Step | Fit | Reasoning |
|---|---|---|
| W1 steps 1–10, 12 | No model | Fixed order, typed boards with `--json`, numeric gates. `corpus nightly` already runs most of it with no model at all. |
| W1 step 11, 13 (read the board, report) | No model, or the cheapest tier for wording | "Any failures? which type? how many skipped?" is a field lookup on the board. |
| W2 step 2 (which sources, which calls) | No model | A fixed query over `calls.jsonl` and `usage.jsonl`; it was rewritten by hand each time only because no verb exists. |
| W2 step 3 (surface the error) | No model | Should be a flag on the verb, not a patch. |
| W2 step 4 (classify) | Cheap model or rules | Four known types, each with a signature in the logs (finish reason, HTTP status, cache hit). Unknown signature → escalate. |
| W2 step 5 (root cause, choice of fix across three repos) | Frontier | This is where S2 went round in circles and S3 succeeded, and S3's edge was method (look at all 35 failures before theorising), which a procedure can require as a step. |
| W2 step 6 (TDD fix, PRs in dependency order) | Mid to frontier for the edit; no model for the checks and merge order | The checks and the merge rule are mechanical. |
| W3 step 3 (locate) | Cheap model driving `search`, with a rule to widen when the name is misheard | Narrow: query in, source ids out. |
| W3 steps 4–5 (read, weigh definitions, choose) | Frontier | Judgement over noisy, mis-attributed speech, and the output goes into a manuscript. |
| W3 step 6 (find the place in the manuscript) | Mid for candidates, frontier for the pick | `grep` finds candidates; where a definition belongs is an editorial call. |
| W3 step 7 (expert review) | Frontier | It is asked for precisely as a stronger second reader. |
| W4 step 1 (is this a directive?) | Cheap model plus Jev, but the gate needs tightening | The false positives suggest the cheap extraction is too generous; the fix is a better gate question, not a bigger model. |
| W4 step 4 (plan) | Mid tier | Small tasks by design; a frontier model only for plans that span repos. |
| W4 steps 3, 5, 7x | No model | Event to row, mail, status change. |

## (e) Decisions and traces

Standing decisions, reusable as precedent, and where they are recorded today:

| Decision (date) | Recorded in |
|---|---|
| A paid run priced under $2 needs no word from the owner (10-21) | beelm skill; enforced in `corpus nightly`; cited in issue beelm#43 |
| The agent merges its own PR when hooks and tests pass, except owner-rule, spend or live-migration changes (10-08) | beelm skill, "Merging" |
| Transcript text may be read and shown; the earlier secrecy rule is gone (10-21) | beelm skill and package docstring |
| "Computer, …" is a directive for computerlm; any other imperative is a note to self; anything addressed to a person folds into self (10-21) | issue beelm#43; the Bee claims prompt in corpuslm |
| Four conversation forms, decided by Jev (10-21) | issue beelm#43; `config.toml` |
| One job per transcript; one gate (the plan); no size special-casing; an unapproved plan waits with no reminders; a job closes only on the owner's word (10-21/22) | issue beelm#43; computerlm's package docstring |
| Backlog directives are shown but never mailed (10-22) | `[digest].directives_since` in `config.toml` |
| A shared events database any tool may publish to and subscribe from (10-21) | the eventlm repo |
| No `.env*` file in git, ever; keys template renamed (10-24) | metalm guidelines, a pre-commit hook, the conformance check |

Per-run decisions, and whether anything keeps them:

| Decision | Kept? |
|---|---|
| Raise the per-run cap to $1 for one backlog run (`--set llm.max_usd_per_run=1.00`) | Only in the session transcript and that run's log line |
| "Fix it here", "merge both", "recover them", "inspect one", "a full rebuild is fine if the dry run is under $2" | Session transcript only (PR bodies carry the what, not the owner's go-ahead) |
| Which definition was picked, and that the drafts were not inserted because the chapters were checked out | Session transcript only |
| Mark one job failed so it stops retrying | Yes: the job row's result text says it was on the owner's word |
| Approve, edit or decline a plan | Yes: computerlm's jobs store (status and plan) |
| Speaker and ambiguity answers | Yes: corpuslm verdict tables; beelm deletes the answer once landed |
| Dry-run estimate, gate outcome, actual spend for a run | Partly: spend in `usage.jsonl` and `calls.jsonl`, the nightly banner in the notifier; the estimate and the gate decision are not stored together with the run |

What exists as trace: `runs.jsonl` (one row per sync), per-run logs, `usage.jsonl` and `calls.jsonl` (per model call), the eventlm events, corpuslm's `artifacts` build ledger and `change_log`, computerlm's jobs. No record ties one pass of the chain together (steps, gate values, failures by type, who authorised what), and no record holds an owner decision made in chat in a form a later run could look up.

## (f) The workflow to formalise first

**W1, the daily chain, with W2's triage as its exception path.** It runs every day, every step is already a verb with a JSON board, and nearly all the friction in (c) sits at its edges: pricing before sync, gates restated in chat, failures that drop the owner into an open-ended session, and a hand-off whose consumer failed silently for ten days. It also needs no frontier model on its normal path, so it is the clearest saving.

What a procedure definition would need that does not exist yet:

1. **A run record.** One id per pass of the chain, with a row per step: verb, arguments, start and end, exit code, the board as JSON. Today the pieces are spread over `runs.jsonl`, a log file and the usage logs.
2. **Gates as data.** For each paid step: the estimate, the threshold, the cap in force, the outcome, and the authorization relied on (a link to the ruling). Estimate and actual stored side by side.
3. **A chain dry run that can price.** Either sync is allowed before pricing (it is free and idempotent), or the procedure prices after step 4; the current `nightly --dry-run` answers $0.00 by construction.
4. **A typed failure outcome and an evidence query.** A verb (or a `--json` field) that returns, per failed source or skipped section, the failure type and a pointer to the logged call, so W2 steps 2–4 stop being hand-written scripts. Plus a "show the error" flag in place of patching the code.
5. **A triage step with a rule.** Known type → the fixed remedy (retry with `--retry-skipped`, skip and record, wait). Unknown type, or the same type on more than a set share of sources → escalate. The escalation step must require "look at every failure of this type" before any fix is proposed; that single rule separates S3 from S2.
6. **An escalation payload.** What the owner or a frontier session receives: the run id, counts by type, the evidence pointers, spend so far. Today it is a banner with a log path.
7. **A retry policy.** Nothing reruns skipped sections; the nightly job leaves them.
8. **A source selector type.** `bee:<id>`, validated before the call.
9. **A check on the consumer.** The chain ends by publishing `transcript.digested`; the procedure should confirm that computerlm's cursor moved and its last plan step did not fail, or say so. Decide also whether `directive.found` is kept, since nothing reads it.
10. **A precedent store.** Per-run owner decisions (cap raised for a backlog, a job marked failed, a rebuild allowed) written where the next run can find them, in one shape across repos.
11. **Step-level model assignment.** The normal path declared model-free; classification on a cheap tier; only the escalation branch on a frontier model.

Where Bee transcripts feed other repos:

- **computerlm, and through it any repo**: by design (W4). The planner prompt carries the whole transcript, so copies of Bee conversations also land in computerlm's own Claude session logs (about 900 MB on 11-03).
- **authorlm**: by hand (W3). Bee passages were mined for definitions and placed against manuscript chapters; the hand-off stopped at drafts in chat because authorlm's checkout state blocked the insert. A procedure would need authorlm's "is this chapter checked out" as a gate and an insert verb as the last step.
- **Google Docs**: by hand (W3, S5), through the Drive connector.
- **publishinglm**: a book-marketing call was pulled and summarised in S4; nothing carried it into publishinglm.
- **podlm**: no pull from Bee was seen in these sessions. If a monologue workflow draws on Bee material, the evidence will be in podlm's sessions, and it would be another instance of W3 with podlm as the target.
- **corpuslm** (review page, search, the shared database) and **llmlm** (model calls, spend logs) are libraries under every W1 step, and every W2 fix landed in them as well as in beelm.
