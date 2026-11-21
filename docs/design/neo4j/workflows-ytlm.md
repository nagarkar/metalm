# ytlm: workflows actually run

Second pass of the Neo4j adoption work (see [neo4j adoption plan.md](/Users/nagarkar/workspace/repos/metalm/docs/design/neo4j%20adoption%20plan.md), "Orchestration framing"). The first pass, [ytlm.md](/Users/nagarkar/workspace/repos/metalm/docs/design/neo4j/ytlm.md), looked at data only. This one reads session history and the ytlm skill to find the procedures the owner and Claude really run, where they go wrong, and which is worth formalising first.

Method: a script reduced each session transcript to the owner's typed messages, the assistant's command lines, tool and subagent names, and assistant prose. Tool outputs were left out, so no transcript content was read. Everything below is paraphrase. Counts are from those digests and are exact where a number is given without "about".

## (a) Sessions examined

Timestamps in the logs are UTC; dates here are the local day, give or take one.

| Session title | Dates | Topic | Rough length |
|---|---|---|---|
| YTLM Imports | 2026-11-04 | Import seven new videos, file them, add a `corpus remove` verb mid-run, repair five transcripts the run damaged, start a Dharma document update | 7 typed owner turns, 14 subagents, about 5.5 hours wall clock |
| Financial Reset corpus and manuscript | 2026-11-03 to 11-04 | New corpus of 21 videos, its corpus document from nothing to nine tabs in the Doc, with Claude subagents standing in for Gemini | about 6 typed owner turns, 43 subagents, 18 throwaway scripts |
| YTLM | 2026-10-21 to 10-22 | Import with a new DIY corpus; documents for Investment and DIY through two rounds; design and build of "the chain runs to the owner's door" (ytlm#132); a monologue in the SpiritualHindu manuscript | 32 typed owner turns, 32 subagents |
| Import latest playlist videos | 2026-10-08 to 10-16 | Five imports, the bulk review of Bee cleanup questions, the spend rule, the feed rules, first corpus documents (Physics, Dharma), the monologue framework | about 139 typed owner turns, 57 subagents; the longest by far, and half of it is building ytlm, corpuslm and beelm rather than using them |
| ytlm cleanup | 2026-10-22 to 11-03 | Branch and PR hygiene, then a long authorlm manuscript discussion with two single-video pulls handed to subagents | 31 typed owner turns; little ytlm procedure, kept because it shows a ytlm session drifting into authorlm work |

Also read: the ytlm skill ([SKILL.md](/Users/nagarkar/.claude/skills/ytlm/SKILL.md), 379 lines), the repo [CLAUDE.md](/Users/nagarkar/workspace/repos/ytlm/CLAUDE.md), and `ytlm help` (51 verbs).

## (b) Workflows

Step kinds: **verb** (a CLI call), **judgement** (a model decides), **owner** (owner decision), **gate** (a check that can stop the run), **spend gate**. Formality: **formal** (a verb with stored state), **semi-formal** (the skill's prose tells the assistant what to do), **informal** (worked out in conversation).

### W1. Import the latest videos

Run eight times across the five sessions (10-08, 10-11 twice, 10-16 twice, 10-21, 11-03 as a filtered variant, 11-04). The most frequent workflow.

| # | Step | Kind | Verb or tool | Owner repo | In → out | Formality |
|---|---|---|---|---|---|---|
| 1 | List tracked feeds | verb | `ytlm feed list` | ytlm | → feed rows | formal |
| 2 | Scan for new videos | verb | `ytlm feed scan` | ytlm | feeds → new video ids and titles; scan time stored | formal |
| 3 | Stop if nothing new | gate | read the board | ytlm | | semi-formal |
| 4 | Add the new ones to the catalog | verb | `ytlm video add ID...` | ytlm (rows in corpuslm's database) | ids → catalog rows, status added | formal |
| 5 | Price the run | spend gate | `ytlm pending`, `ytlm run --now --dry-run --video ...` | ytlm | → billable count, `estimate_usd` | verb formal; the 50-cent rule is skill prose |
| 6 | Ask the owner when above 50 cents | owner | chat | | estimate → yes or no | semi-formal |
| 7 | Build | verb | `ytlm run --now --video ...` (fetch, cleanup passes, AI cleanup on Gemini, Jev arbiter, index, notes) | ytlm, with corpuslm's cleanup chain and llmlm | ids → transcripts, SRTs, notes, open review items; a run log and a usage ledger row | formal |
| 8 | Retry what failed | gate + judgement | read `errors`, wait, rerun step 7 on the failed ids | ytlm | | informal: no rule says how many tries or how long to wait |
| 9 | Rescan so the feed is stamped | verb | `ytlm feed scan URL` | ytlm | | semi-formal (one sentence in the skill) |
| 10 | Report estimate and actual cost | verb | `ytlm usage` before and after | ytlm | | semi-formal |
| 11 | Propose a corpus per video | judgement | `ytlm corpus list`, then a table in chat: best corpus, alternate, confidence | ytlm | titles + corpus list → proposal | semi-formal; the proposal is stored nowhere |
| 12 | Owner confirms or overrides | owner | chat | | → final filing | informal record: chat only |
| 13 | File | verb | `ytlm corpus add NAME ID...` | ytlm | → membership rows | formal |
| 14 | Refresh notes for the filed videos | verb | `ytlm run --now --video ...` (free when cleanup is built) | ytlm | → corpus notes | informal; the skill does not mention it and the 11-04 run got it wrong |
| 15 | Offer the document update for each filed corpus that has one | owner | chat, Doc link from `authorlm doc list` | ytlm, authorlm | | semi-formal |
| 16 | Tell the owner about new review questions, with the page link | gate | `corpuslm review check` | corpuslm | | semi-formal (W3) |

### W2. The corpus document chain

Run for Physics and Dharma (10-12 to 10-13), Investment and DIY (10-21, two full rounds each), Financial Reset (11-03 to 11-04) and a Dharma update (11-04). The most expensive workflow in tokens and in owner attention.

| # | Step | Kind | Verb or tool | Owner repo | In → out | Formality |
|---|---|---|---|---|---|---|
| 1 | What is outstanding | verb | `ytlm document status "<corpus>"` | ytlm | → board with `next`, `orders_to_write`, `results_to_propose`, tabs awaiting the owner | formal; this board is already a small state machine |
| 2 | Price the create | spend gate | `ytlm document create --dry-run` | ytlm | → digest count, estimate | formal + skill prose |
| 3 | Create | verb | `ytlm document create` (registers the manuscript, one Gemini digest per video, writes a guidance order) | ytlm; the Doc is created through corpuslm's document store by authorlm | → Google Doc id, `guidance.order.json` | formal |
| 4 | Write each order | judgement | one fresh subagent per `*.order.json`, in parallel, each writing `*.result.json` | ytlm (orders), Claude subagents | order → revisions | semi-formal; the fan-out is skill prose, the order file is formal |
| 5 | Stage results in the Doc | verb | `ytlm document propose` | ytlm → corpuslm → authorlm → Google Docs | results → revisions shown in green | formal |
| 6 | Owner reads the Doc | owner | Google Doc: leave, edit, delete, comment | authorlm's Doc | → rulings in the Doc | formal (the Doc is the record) |
| 7 | Land the rulings | verb, on the owner's word only | `ytlm document resolve "<corpus>" <tab>` or `--all` | ytlm → authorlm | → settled text; plans the next round itself | formal |
| 8 | Check the tab really cleared | gate | `tab_cleared` on the board; `ytlm document withdraw` for tabs under `tabs_not_cleared` | ytlm | | semi-formal |
| 9 | Plan new videos into tabs | spend gate + verb | `ytlm workorders update --dry-run`, then for real (Gemini digest and router) | ytlm | claims → one order per tab | formal |
| 10 | Repeat 4, 5, 6, 7 until the board says nothing to do | loop | `status` after every `resolve` | ytlm | | semi-formal (the 2026-10-21 "owner's door" rule) |
| 11 | Bring settled text home | verb | `ytlm document pull` | ytlm → authorlm | Doc → local files | formal |

Variant seen on 11-03: the owner said to leave Gemini out. Steps 3, 7 and 9 each call Gemini inside the verb, so the assistant rebuilt them by hand: Claude subagents wrote digests, a Haiku subagent routed 1,831 claims to nine tabs, a script landed the Guidance rulings without the verb's planning half, and nine verifier subagents checked each tab against per-video summaries. That variant is wholly informal and lives in 18 scripts in a scratchpad that no longer matters to anyone.

### W3. The cleanup review loop

Seen in full once (10-10, mostly Bee items, bulk), and as an ask with no apply on 11-03.

| # | Step | Kind | Verb or tool | Owner repo | Formality |
|---|---|---|---|---|---|
| 1 | Run leaves open questions | verb | `ytlm run` board lists corpora under `review` | ytlm | formal |
| 2 | Jev answers the confident ones | judgement (small model) | arbiter stage inside `run`, `min_probability` 0.8 | ytlm, TypeSafe | formal |
| 3 | Check the review server is up and current | gate | `corpuslm review check --config <review.toml>` | corpuslm | semi-formal |
| 4 | Owner restarts it if stale | owner | `launchctl kickstart ...` | owner's Mac | semi-formal |
| 5 | Ask, with the page link and counts | owner | chat + review page on port 12443 | corpuslm | semi-formal (a hard rule in the skill) |
| 6 | Optional: fill older cards with the model's suggestion | verb, date chosen by owner | `corpuslm review accept-suggestions --before DATE --dry-run`, then for real | corpuslm | formal |
| 7 | Owner answers on the page | owner | review page | corpuslm | formal (answers table) |
| 8 | Land answers | verb | `ytlm review apply "<corpus>" --page-answers` | ytlm → corpuslm | formal: verdict rows and correction memory |
| 9 | Rebuild the reviewed videos, checking it costs nothing | spend gate + verb | `ytlm usage`, `ytlm run --now --video ...`, `ytlm usage` | ytlm | semi-formal |

### W4. A monologue from a corpus

Seen 10-14 to 10-16 and 10-21 to 10-22. Started from a ytlm session but nearly every step belongs to corpuslm, and the result lands in an authorlm manuscript; podlm takes it from there.

| # | Step | Kind | Verb or tool | Owner repo | Formality |
|---|---|---|---|---|---|
| 1 | Get the source video in | verb | `ytlm corpus add`, `ytlm run --now --video` | ytlm | formal |
| 2 | Create the monologue with title, series and brief | verb | `corpuslm monologue new ... --brief` | corpuslm | formal, but no verb changes a brief later: on 10-21 it was written through the store by a script |
| 3 | Build claims for the corpus | spend gate + verb | `corpuslm claims build --corpus ... --dry-run`, then for real | corpuslm | formal |
| 4 | Propose moments | verb (model) | `corpuslm moments propose --corpus ...` | corpuslm | formal |
| 5 | Owner approves moments | owner | moments page | corpuslm | formal |
| 6 | Attach approved moments | verb | `corpuslm monologue attach NAME --moment ID` | corpuslm | formal |
| 7 | Run the recipe | spend gate + verb (frontier writer) | `corpuslm monologue run NAME` | corpuslm → authorlm Doc tab | formal |
| 8 | Push the series About tab | verb | `authorlm doc push` | authorlm | informal: needed after a failed push inside step 7 |

The order of steps 3 to 7 was discovered by running step 7 and reading why it stopped, twice.

### W5. Pull one video and have a subagent analyse it

Seen 10-11 (summaries of physics videos into a folder), 10-16 (two analyses that fed the owner's manuscript), 11-03 (two pulls during an authorlm discussion). Steps: `ytlm video add` or `corpus add`, price, `ytlm run --now --video`, then a subagent reads the transcript on disk and writes an essay or summary to a file; the owner then discusses the result. Wholly informal after the run: the output folder, the file shape and whether the result goes into a manuscript are decided each time. It matters because it is how ytlm content reaches authorlm without passing through the chat.

### W6. Fix forward in the middle of a run

Not a content workflow, but it interrupts every other one: a missing verb or a wrong behaviour is found, and the assistant opens an issue, branches, writes the change with a test, opens a PR, merges on the standing authorization, returns to `main` and resumes. Seen at least nine times in the five sessions (private-video skips, the ignore status, dry-run flags on five verbs, feed rules, ytlm#132, ytlm#135, `corpus remove`, two fixes on 11-04). Steps are semi-formal (metalm guidelines plus the skill's Merging section). The resume is informal: nothing records where the interrupted run stood.

## (c) Friction, with evidence

**The owner corrected the assistant on the import flow five times before it settled.** On 10-08 it proposed new corpora where one existed. On 10-11 it asked which corpus instead of proposing a table, and the rule was then added to the skill. Later that day it tracked seven playlists found on the owner's channel, which the owner had never named; they were untracked and the "only playlists the owner asked for" rule was written. Private videos were asked about until a rule made them silent. On 11-04 it filed before the owner's corpus instruction arrived, leaving two videos in two corpora, with no verb to take them out.

**Transient model failures are handled by hand every time.** Gemini rate limits or bad-request replies hit AI cleanup in three of the five sessions: 4 of 7 videos on 11-04 (three rounds of retries), 7 of 21 on 11-03 plus every digest, and one rebuild that took three tries. The assistant waits with hand-written sleeps (2, 5 and 15 occurrences in three sessions) and decides each time whether one more try is within the spend rule. The run log cuts the provider's error text short, so the cause was never established; the owner asked on 11-04 why this keeps happening.

**Google Docs write limits broke staging twice.** On 10-21 the assistant paced `propose` calls with 70-second sleeps and four tabs ended up conflicted, needing withdraw and re-stage on the owner's instruction. On 11-04 a 254-revision staging lost 13 paragraphs and 280 footnotes; a repair loop then made 60 writes that did nothing because a tab with open revisions takes no new ones (a rule that is in the skill).

**A side effect nobody priced.** On 11-04 a corpus-wide note refresh, whose dry run showed nothing billable, reverted AI cleanup on five older transcripts. Repair cost about 29 cents and two code fixes.

**The house rule on content was broken once.** On 11-03 a broad search of a run log printed short transcript fragments into the chat; the assistant reported it itself.

**The assistant reads source code to learn how to drive the tool.** Commands that grep or print lines of `src/` during operational work: 13 on 11-03, 33 on 10-21, 4 on 11-04. Throwaway scripts written inline: 18 on 11-03 and 18 on 10-21. Verb shapes were guessed wrong at least four times (`--wait` on `run`, several ids after one `--video`, a renamed verb, authorlm argument order), and shell quoting failed twice on 11-04.

**The path changed between runs of the same workflow.** The pipeline was started three different ways (nohup to a temp file, a background Bash task, a detached job). Document writing used Gemini digests on 10-21 and Claude subagents on 11-03. One writer subagent on 11-04 split its order among six further subagents on its own and said the sections were simply joined.

**Subagent fan-out is under-briefed.** On 11-03 nine writers shared a temp file name and overwrote each other; a check was written afterwards. A tab's file name exceeded Google's 50-character limit and stopped the first staging.

**Things the owner had to remember or chase.** The owner asked "anything left?" or "what is running?" six times (10-10, 10-12, 10-13 twice, 10-26 twice). On 10-21 the owner said plainly that the next step must happen without having to come back for it, which produced the "owner's door" rule. Dry-run prompts were tiring enough that the 50-cent rule replaced them (10-13), and PR-then-merge asks were tiring enough that the standing merge authorization replaced them (10-08). Keys for corpuslm verbs were borrowed from another repo's `.env` twice.

**Progress chatter.** With parallel subagents the assistant writes one message per finished agent: 21, 9, 9 and 11 such messages in the two November sessions. Each is a frontier-model turn that says only a count.

## (d) Model fit per step

**No model needed** (a runner calls the verb and reads `--json`): W1 steps 1 to 5, 7, 9, 10, 13, 14; W2 steps 1, 2, 3, 5, 8, 9, 11; W3 steps 3, 6, 8, 9; W4 steps 3, 6. The decision "estimate above 50 cents → ask" is a comparison. "Retry failed ids up to N times with a wait" is a loop with a rule for which errors are transient. Counting finished subagents is a counter. Today a frontier model does all of these and is where the quoting slips and wrong flags come from.

**A small or cheap model is enough:**
- W1 step 11, the corpus proposal: titles against a list of about twenty corpus names with subjects. A cheap model, or Jev-style scoring with a probability, with the owner seeing only the low-confidence rows.
- W2 routing claims to tabs: Haiku did 1,831 claims into nine tabs with none missed or repeated (11-03).
- W2 digests (claims per video): Gemini Flash Lite does this in the verb today; Claude subagents did ten of them on 11-03 with no reported loss.
- W3 step 2: already Jev.
- Checking that a result cites only claims from its own order: no model, a script did it.

**A mid-tier model:** W2 step 4, writing a tab from an order (the order file carries the whole prompt, so the writer needs no session context), and the per-tab verification against summaries. W5's analysis when it is a plain summary.

**Frontier model:** W4 step 7, the monologue script (the cheap tier wrote a poor first script, per the note in corpuslm's settings). W5 when the analysis is philosophical and feeds the manuscript. Diagnosing a new failure (the reverted transcripts, the tab that would not clear). W6, writing the code fix. Talking with the owner about what they want.

The pattern: in W1 and W3 the frontier model is needed only when something new breaks. In W2 it is needed for none of the fixed steps.

## (e) Decisions and traces

| Decision the owner made | Reusable as precedent? | Where it is recorded today |
|---|---|---|
| Cleanup answers (which word, which speaker) | Yes, and already reused | Verdict rows and correction memory in corpuslm's database; Jev sees memory rules as precedent |
| "Use the model's top suggestion for everything before a date" | Yes | `corpuslm review accept-suggestions --before` takes the date; the date itself was said in chat |
| Which corpus a video belongs in, including overrides ("these fall under Dharma", "use a new AI Engineering corpus") | Yes: the next proposal should cite them | Membership rows only. The proposal, its confidence and the fact of an override are in chat and lost |
| New corpus allowed or not | Yes | Skill prose ("never create a new corpus unasked") |
| Spend approvals and the 50-cent line | The line yes; each approval no | Skill prose, dated; actual spend in the usage ledger; the approval itself only in chat |
| Skip, ignore, private | Yes | Formal: skip rows with reasons, ignore status |
| Which feeds exist | Yes | Formal: feed rows |
| Document rulings per revision | Yes, as style precedent for the next writer | The Doc and authorlm's settled text; margin comments feed the next update; Guidance tab is the standing instruction |
| "Leave Gemini out for this corpus" | Possibly, per corpus | Chat only; not in `config.toml` |
| Moments approved or declined; the monologue brief | Yes | corpuslm tables |
| Standing rules (owner's door, additions-only documents, merge authorization, link rules) | Yes | Skill prose with dates, `ytlm.api` docstrings, metalm guidelines |
| Which path was taken when a step failed (retry, withdraw, re-stage) | Yes: this is the decision trace the plan asks for | Nowhere. Run logs and the usage ledger record calls, not choices |

So ytlm has good records of content decisions (verdicts, memory, Doc rulings) and almost none of procedural ones. A standard trace would add, per run: the step, its inputs by id, the gate value and outcome, who decided (rule, model with probability, or owner), and the precedent consulted.

## (f) What to formalise first

**W1, import the latest videos, ending with the filing decision and the offer of W2.**

Why this one: it runs most often (eight times here), 13 of its 16 steps need no model, it has exactly one spend gate and one owner decision, and nearly all its friction is of the kind a runner removes: step order (file only after the owner confirms), bounded retries on transient failures, the rescan, the free refresh scoped to the filed videos, cost before and after. It is also the entry to W2 and W3, so its run record gives those something to hang from. W2 is the larger prize but depends on things W1 would prove first (detached jobs, retry policy, parallel order writers with their own files), and its `document status` board already does part of the job.

What a procedure definition for W1 needs that does not exist yet:

1. **A run record.** One id that ties the scan, the adds, the pipeline job and its retries, the proposal and the filing together. Today these are separate ledger lines and a chat transcript.
2. **A transient-failure rule.** Which errors are retried, how many times, with what wait, and inside what total spend. This needs the run board to give a full error class per video; today the log cuts the provider's message short.
3. **A stored filing proposal.** A verb such as `ytlm corpus propose ID...` that writes the table (video, best corpus, alternate, confidence, the earlier filings it leaned on) to the database, and a way for the owner to rule on it (the review page is the natural place, since the owner works from a phone). The ruling is then precedent for the next proposal. Without this the one judgement in the workflow has no trace.
4. **The spend gate as data.** The 50-cent line and "several billed verbs in one request count together" live in skill prose; they belong in `config.toml` beside `max_usd_per_run`, with the approval recorded on the run.
5. **A wait-for-job step.** `run` already returns a job id through MCP and `job status` reads it; the runner needs to wait on it instead of a model polling or sleeping.
6. **A scoped, safe note refresh.** After filing, rebuild notes for the filed videos only, with a guarantee it cannot touch cleanup. The 11-04 fixes moved toward this; the procedure should call a verb that can only do that.
7. **Typed exits.** "Nothing new", "waiting for spend approval", "waiting for filing ruling", "failed after retries: needs a person" as named end states, the last one alerting through `superlm-notify`.
8. **Board contracts.** The runner reads `--json`; each board field a gate depends on (`new`, `estimate_usd`, `errors`, `needs_ai_cleanup`) needs to be a stated contract with a test.

How much skill prose goes away: the "Import the latest videos" entry, the corpus-proposal sentence under `corpus add`, the rescan and private-video sentences, and most of "Before any spend" become procedure definition and config: about 45 to 50 of the skill's 379 lines, roughly an eighth. If W2 and W3 follow, "The corpus document" (about 75 lines) and "Review" (about 50 lines) shrink to the owner-facing rules, which brings the total to around 150 lines, or two fifths of the skill. What stays as prose: the verb glossary, "never in the window", and the "on the owner's word only" boundaries, which are constraints on any caller and not steps.

One caution from the evidence: the variants matter. Two of the eight imports were not the plain flow (a title-filtered import into a new named corpus, and "process the one I just added, then analyse it"). The procedure should take a scope (all tracked feeds, one feed, a title filter, explicit ids) and an optional target corpus as inputs, or those runs fall back to conversation.
