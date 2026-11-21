# Workflows actually run: authorlm

Written 2026-11-04 by a read-only session over `/Users/nagarkar/workspace/repos/authorllm`. Second pass after `authorlm.md` (the data assessment). Source: digests of session transcripts (owner turns, command lines, tool and subagent names, assistant text; tool outputs left out), the repo's skills (`.claude/skills/authorlm/SKILL.md`, 2,476 lines; `papers`, `papers-philosophy`), the CLI's verb list, and the live workspace's table columns (opened read-only). Counts of commands are lower bounds: the digest keeps only the first line of each shell command.

## (a) Sessions examined

Five main sessions, two more skimmed for corroboration. All on the SMSTTD manuscript unless noted.

| session | dates | topic | rough length |
|---|---|---|---|
| `0960051c` "Nature of intelligence essay" | Nov 1 to 2 | A new essay written end to end through the beat loop, then source check, summaries, push, referee round | 146 owner turns, about 440 tool calls, 100 subagents, 2 context compactions |
| `2719461c` "Forms in discernment.md" | Oct 30 to Nov 2 | Accepting referee forms on two essays; drafting and staging new passages; five Doc-road failures diagnosed and fixed along the way; concept-note corrections; research fan-out for a planned essay | 97 owner turns, about 510 tool calls, 10 subagents, 5 compactions |
| `2947ae0e` "SMSTTD reviews: recaps, essay referees" | Oct 29 to 30 | Fifteen referee rounds fanned out as side sessions; margin comments processed; forms resolved on six files; chapter introductions drafted as A/B options | 77 owner turns, about 330 tool calls, 15 side sessions, 8 subagents, 4 compactions |
| `c4c19fc1` "Narration guideline for essays" | Oct 30 to 31 | A read-aloud procedure defined, corrected three times, then used on three essays | 49 owner turns (about 20 are "Next"), 84 tool calls |
| `4b7195f3` "Authorlm web UI outage" | Nov 3 to 4 | Audiobook page down; launch agent added; a new chapter file promoted into the table of contents and read in the page | 17 owner turns, about 150 tool calls |
| `f29202f6` "Explain and footnote forms in kindness.md" (skimmed) | Oct 31 to Nov 1 | Comments, directives and forms on one essay; a dropped margin reply filed as a defect | 12 owner turns, 112 tool calls |
| `c6b88a73` "Branches and main situation" (skimmed) | Oct 29 to Nov 4 | PR and branch triage; engineering, not editorial | 51 owner turns, 271 tool calls |

Skipped: "Neo4j assessment", bug-fix worktrees, the Haiku narration side session, older sessions (video clips, DON planning, audiobook editing).

## (b) Workflows observed

Step kinds: **V** verb or script call, **M** model judgement, **O** owner decision, **G** gate or check. Formality: **F** formal (a verb with stored state), **S** semi-formal (skill prose), **I** informal (worked out in conversation). Owner is authorlm unless a repo is named.

### W1. The form round: stage, review in the Doc, resolve, sync

The most frequent workflow by far. Across three sessions: at least 14 `revise stage`, 24 `revise resolve`, 22 `doc push`, 47 `doc pull`, 43 `doc diff`. Every other workflow ends in it.

| # | step | kind | verb or tool | in → out | formality |
|---|---|---|---|---|---|
| 1 | Find the file, its tab and what is pending on it | V | `authorlm _manuscripts`, `doc list -m`, `doc threads <file>`, and in practice raw `sqlite3` on `doc_threads` | manuscript, file → tab link, thread ids, origins | S (the lookup by origin has no verb; done by SQL 54 times in three sessions) |
| 2 | Pre-flight: are Doc and file level | G | `doc diff <file>` | → clean / ahead / conflict | F |
| 3 | Pull the owner's Doc edits and margin comments | V | `doc pull <file>` | Doc tab → file, `doc_threads` rows (`author_comment`), a merged draft on conflict | F |
| 4 | Decide what each comment needs (answer, edit, question) | M | chat session, with `get_style`, `get_concepts`, section summaries | comment + context → a proposed edit or reply | S |
| 5 | Write the proposed edits as a JSON list | M | chat session; payload `[{old, new, note, anchor_paragraph}]` | → revisions file | S (payload shape is in `revise --help`; the paragraph numbering rule was read from source three times) |
| 6 | Stage them as red/green forms in the tab | V | `revise stage <file> --origin <name>`; `doc propose` for a reply beside a comment; `footnote`/`explain`/`suggestion` verbs for directives | revisions → `doc_threads` rows in state `written`, forms in the Doc | F |
| 7 | Owner reads the tab; leaves, rewords, empties a form, or replies in the margin | O | Google Docs | → edited tab | F as a state machine (docs/margin-threads-design.md), but the trigger back to the session is a chat message ("I've resolved the forms", "Ruled, land them") |
| 8 | Read the tab back and land verdicts | V | `revise resolve <file> --origin <name>` (or `filter resolve`, `critique resolve`, `lens resolve`, `footnote resolve`, `doc decide <comment id> --accept/--decline --reason`) | tab → file, thread states `applied`/`declined`, a new manuscript version, evidence rows | F |
| 9 | Push the clean file; confirm level | V, G | `doc push <file>`, then `doc diff` | file → tab; expect "unchanged" | F |
| 10 | Snapshot | V | `collect` (MCP `collect_revision`) | → `manuscript_versions`, `editorial_transitions` | F |
| 11 | Report: counts, version id, Doc link | M | chat | | S |

Recovery branches seen (all I): rebuild the tab from the local file (`doc push --rebuild`, owner's word needed because a rebuild orphans margin comments); hand-settle a merge conflict; strip broken markers by script; withdraw a staged form (no verb; an internal function was called directly); close a stale thread (`doc resolve-comments <id>`).

Cross-repo: Google Docs and Drive APIs only. No call into another LM repo.

### W2. A new essay through the beat loop

Seen once in full (`0960051c`), 17 beats over about 22 hours of wall clock.

| # | step | kind | verb or tool | in → out | formality |
|---|---|---|---|---|---|
| 1 | Owner states the thesis and where the essay sits | O | chat | → brief | I |
| 2 | Assemble the machinery | V | `get_style(file)`, `get_concepts(name/query)`, read `papers/house-rules.md`, neighbouring essays | → effective style law, ratified concept notes | S ("Drafting on request") |
| 3 | Propose a beat plan; owner approves | M, O | chat | → plan | S |
| 4 | Open the writeup | V | `write start <file> --new --after <essay> --style <guide>`, `declare_intent`, `write plan` | → `writeups` row (plan, cursor), `declared_intents` row | F |
| 5 | Refresh summaries so the drafter has the book's state | V | `summarize rebuild` (llmlm model call inside) | → paragraph, section, essay summaries | F |
| 6 | Draft the beat | M | `write draft` builds the payload; a drafter subagent writes the text (23 draft, 17 redraft subagents) | payload → beat text | F payload, S hand-off |
| 7 | Lint and critic gate | G, M | `write critique` (31 calls; deterministic lint, then a critic subagent, 46 critic runs and 4 rechecks) | beat → findings; redraft until clean or `--no-critic <reason>` | F gate, S loop |
| 8 | Put the beat before the owner | V | `write propose` (13) | → proposal shown in chat | F |
| 9 | Owner verdict, usually with line-level corrections | O | chat: "Accept", "Accept with fixes", or a rewrite | → verdict + reasons | I for the corrections |
| 10 | Record | V | `write accept` (7) / `write reject --reason "<owner's words>"` (4) | → file appended, cursor advanced, evidence | F |
| 11 | A correction that should bind later beats | O, V | `add_style_law` (2 added mid-essay) | → `style_laws` row | F, but only when the owner says "fix this permanently" |
| 12 | Close | V | `write learn`, `write complete` | → learnings on the writeup | F |
| 13 | Source check of every citation | M | one subagent with web search; owner: "apply all seven" | essay → correction list | I |
| 14 | Summaries, push | V | `summarize rebuild <file>`, `doc push` | | F |
| 15 | Hand to W3 | O | "Run the referee pass" | | S |

Cross-repo: llmlm (the model-call layer under `summarize`). A defect in the beat instructions found mid-essay became a PR in authorllm; nothing else left the repo.

### W3. The persona referee round

Seen in `2947ae0e` (15 essays at once), `0960051c` (one essay, six referees), and as the source of every `referees-r1` origin resolved in W1.

| # | step | kind | verb or tool | in → out | formality |
|---|---|---|---|---|---|
| 1 | Choose the referees per essay | M, O | proposal file in `_drafts/`; owner adds and removes names; or "identify them from the footnotes" | essay → named thinkers | S (`papers-philosophy`) |
| 2 | Pre-flight: no unresolved forms on the tab | G | `doc pull`, `doc threads` | → go / stop | S (one of 15 rounds stopped here: 19 older forms already on the tab) |
| 3 | Write one shared brief (rulings, house rules, sources by rank) | M | file in scratchpad | → brief | S |
| 4 | One referee per subagent, or one side session per essay | M | Agent tool ×6, or `start_session` ×15 | essay + brief → objections tagged answer / survive, fidelity findings, proposed repairs | S |
| 5 | Verify citations on the web | M | WebSearch inside the referee | → checked references | S |
| 6 | Adjudicate across referees; keep or drop each repair | M | chat session | → repair list | S |
| 7 | Stage repairs as forms, origin `referees-rN` | V | W1 step 6 | | F |
| 8 | Owner rules in the Doc | O | W1 step 7 | | F |
| 9 | Resolve, push, next round until the gate | V, O | W1 steps 8 to 10; gate passed in chat | | F for the forms, S for the gate |
| 10 | Close-out: a standing rule becomes a proposed style law; a reason stays in the thread note; open questions go to the owner | M, O | `add_style_law` on acceptance | | S |

Cross-repo: none. Web search is the only outside call. `interlocutor` and `critique` are the formal relatives (stored payloads, imports, passes with cursors); the referee round itself has no stored run.

### W4. Narration (read-aloud review)

| # | step | kind | verb or tool | formality |
|---|---|---|---|---|
| 1 | "Narrate X" | O | chat | S (skill section, written in this session) |
| 2 | Get the text as if every pending form were accepted, with no tags, captions or directives | V | no verb: the session read the Doc through the Drive connector and stripped it by hand | I |
| 3 | Print a few paragraphs | V | chat | S |
| 4 | "Next" | O | chat (about 20 times) | S |
| 5 | A remark on what was just read becomes an edit | O, M | enters W1 | I |

Run on three essays, plus one attempt to hand it to a Haiku side session (started twice, then abandoned for the main session).

### W5. Concept note follows the chapter

Small, but it recurs and the owner is sharp about it ("the graph being wrong all the time").

| # | step | kind | verb or tool | formality |
|---|---|---|---|---|
| 1 | Owner corrects a definition in conversation | O | chat | I |
| 2 | Read the current note | V | `get_concepts(name=…)` / `concept show` | F |
| 3 | Rewrite the note in the owner's words | M | chat | I |
| 4 | Store it | V | `concept edit <name> --notes …` (the same concept rewritten three times in one evening) | F |
| 5 | Find text that contradicts the new note | M, V | grep over chapter files, summaries | I |
| 6 | Stage the text repairs | V | W1 | F |

### W6. Tool defect found mid-edit

Seen 4 times in the editorial sessions (wrong declines on resolve; a dropped margin reply; a lost paragraph after a broken insertion; beat budget counting footnotes).

Steps: notice (M) → `file_improvement` in the workspace database plus `gh issue create` without private data (V; the pairing was ruled on Oct 31 and moved into metalm on Nov 1) → fix in a worktree subagent or branch with a failing test first (M) → `python3 tests/run_all.py` (G) → PR, checks, merge (V, O: owner's word or standing authority) → `git pull` on main, `pkill -f authorlm-mcp` (V) → resume the edit. Cross-repo: metalm guidelines govern; one fix changed metalm itself (its own PR).

### W7. Audiobook page read-through (thin evidence)

One session: page down → restart `audio serve` → launch agent template and install script (PR) → promote a file into `toc.toml` → open the page in the browser pane and check it → owner edits the card text in the page, pushes to the Doc from the page. Cross-repo: launchd and Tailscale on this Mac; ElevenLabs behind `audio`; podlm reads clips through `clip … --json` (in the skill, not exercised in these sessions).

## (c) Friction, with evidence

1. **The Doc road broke mid-round, repeatedly.** In `2719461c` a single "accept the forms" turned into: push blocked after resolve; a shell error that left the damaged Doc text in the local file; a pull conflict from a form that had lost its closing marker; an approval that garbled a paragraph; a push held by a stale thread; a push held by a pending-form check. Six incidents in one day, later reduced to five reproducible failures and seven fixes (PRs 323, 325, 326, 332). In `2947ae0e` a tab-nesting bug needed the owner to repair the Doc by hand. The owner asked "did it push?" or "is the Doc updated?" at least 4 times across sessions.
2. **The session re-learns the verbs every time.** `--help` was run at least 42 times, source files were read to learn a verb's behaviour at least 90 times, and `sqlite3` was used against the live database at least 54 times, mostly to answer "which forms are pending on this tab, under which origin". The first owner turn of `2719461c` ("accept the forms") took 12 commands before the resolve started.
3. **Different path than last time.** Forms were landed by `revise resolve --origin` in one session and by running `filter resolve`, `critique resolve`, `footnote resolve`, `explain resolve`, `suggestion resolve` in a row in another. Narration text came from the local file on the first try and from the Drive connector on the second. A staged form was withdrawn by calling an internal function. The fan-out for referees was side sessions once and subagents the next time.
4. **Owner corrections that were process, not prose.**
   - Narration: three corrections in ten minutes (captions leaking in; pending forms not shown as accepted; skill not reloaded).
   - Beat loop: "when I provide [a rewrite], you should be passing it back to the critic" (not in the skill; added to a PR). Footnotes counted against the beat budget (PR).
   - Margin reply that was not a bare verdict was dropped: "My verdict is in the response to the comment. Why didn't you process it?"
   - Long-lived local branch running the live tool: the owner had to restate trunk practice that metalm already held.
   - An id from `file_improvement` shown with no link; the owner asked what it was.
5. **Prose corrections that recur.** In the beat loop the owner sent line-level corrections on about 14 of 17 beats, and the same kinds came back: opening sentences too dense, unfamiliar idioms, metaphors that do not land, technical vocabulary. Only two became style laws, and only when the owner said "fix this permanently". The loop's own learning step (`write learn`) ran once, at the end.
6. **Drafter and critic churn.** 100 subagents for 17 beats: 40 drafts and redrafts, 50 critic runs. Beat 5 alone took 5 drafts and 6 critic runs. The critic passed text the owner then rejected for plainness, so the gate is not measuring what the owner measures.
7. **Steps the owner had to remember and say.** Pull before proposing; "rebuild" summaries; "push"; "resolve the forms" after reviewing; re-read the skill after compaction ("Reread the authorlm skill so we can proceed"); merge the PR and restart the server. Context compaction happened 14 times across the five sessions, and each time the procedure state (which origin is staged where, which round) survived only in the summary text.
8. **Slowness changed behaviour.** A resolve took minutes; a push took 133 s before the fix and 47 s after. The session filled the wait with side investigations, which is where several of the wandering turns came from.
9. **Concept graph drift.** One concept's note was rewritten three times in one evening as the owner refined it in conversation; the chapters that contradicted it were found by grep.

## (d) Model fit per step

| step | fit | reasoning |
|---|---|---|
| W1 1 to 3, 6, 8 to 10 (locate, diff, pull, stage, resolve, push, collect) | no model | Pure verb calls with typed results. A runner needs only the exit state (clean, ahead, conflict, blocked) to pick the next step. Today a frontier model spends most of its turns here. |
| W1 recovery branches | no model for detection, frontier for repair until the failure table is closed | Each of the five failures has a recognisable signature in verb output. The repair is mechanical once named (rebuild, close thread, strip marker). Until every signature has a tested branch, escalate to the owner instead of improvising. |
| W1 4 sort and scope comments | small model | Classify each comment (verdict, question, edit request, new idea) and choose how much context it needs (paragraph, section, essay). Narrow, checkable, and the pull already prints the comments. |
| W1 4 to 5 drafting the answer or edit | frontier | Has to hold the style law, the concept notes and the owner's argument at once; an error here costs an owner correction. |
| W1 11 report | no model | Template over the resolve counts, version id and tab link. |
| W2 payload assembly, lint, accept, reject, append | no model | Already verbs. |
| W2 drafter | frontier | The owner corrected most beats even from a frontier drafter. |
| W2 critic | mid-size for the checklist, frontier for argument | Lint is deterministic. Budget, banned constructions, term fidelity against concept notes are checklist work. Whether the paragraph argues what the plan says needs the stronger model. Split the critic and most of the 50 runs get cheaper. |
| W2 source check | mid-size with search | Per citation: does the source exist, does it say this. Independent items, verifiable. |
| W3 referee selection | mid-size, owner confirms | Names fall out of the footnotes and the essay summary. |
| W3 referee personas | frontier | Arguing from a thinker's documented position against a novel metaphysic is the hardest reading task in the repo. |
| W3 adjudication | frontier | Decides what reaches the owner. |
| W3 pre-flight, staging, rounds | no model | W1. |
| W4 narration | no model | Render the settled text, page it, wait for "next". The one attempt to hand it to Haiku stalled on tooling, not on ability; a `doc`-level "settled text" verb would make it a script. |
| W5 note rewrite | mid-size | The owner dictates the definition; the model's job is to store it in the owner's words. Finding contradicting passages is retrieval over summaries: small model or none once paragraph records carry term mentions. |
| W6 defect filing | small model | Fill a repro template from the failing command and its output; strip private text. The fix itself is frontier. |

## (e) Decision traces: the existing design as a schema

What authorlm has, stated so another repo could adopt it. Table names are authorlm's.

- **Run**: one row per pass with a cursor and a pinned input version. `writeups` (plan, cursor, learnings, source version), `filter_runs` (unit count, cursor, registry, result version), `critique_passes` (cursor, per-essay state, pinned versions), `triage_runs` (profile snapshot, requested ids, manuscript version). The verb timeline is `~/.authorlm/logs/trace.jsonl`; model spend is `usage.jsonl`.
- **Step**: not a row. A step is the cursor position inside a run plus the unit it points at (a beat, a filter unit, an essay). Verb calls are trace lines.
- **Proposal**: anything the machine puts before the author. `doc_threads` for text (origin type and id, file, anchor quote, proposed old and new, note, state, scope); `knowledge_proposals` for graph changes (kind, target, payload, content hash, source, state); `guidance_history` for suggestions (batch, kind, suggestion, explanation, state).
- **Verdict**: the author's decision, with their words. For text it is the thread's state transition (`written` → `applied` / `declined` / `withdrawn` / `stale` / `cleaned`) read back from the Doc; for suggestions an `editorial_reviews` row (decision, explanation). The explanation is kept verbatim: the skill treats it as the most valuable evidence.
- **Evidence**: one row per observed signal (`evidence_type`, `signal`, `target`, `weight`, `supports_belief`, `episode_id`, `source_id`). Types seen: author review, external edit, filter edit, concept and edge triage, critique triage, extraction adjudication, episode analysis.
- **Belief**: `editorial_beliefs`, a machine guess (statement, status candidate / validated / retired, confidence, supporting and contradicting lists, outstanding questions). Never authored directly; retractable.
- **Law**: `style_laws`, declared by the author (guide, file, aspect, statement, status, overrides), composed per file through a guide chain with no model in the loop.
- **The door**: a belief becomes a law only by `convert_belief_to_law` on the author's acceptance. Two further invariants from the learning loop: a machine cut is never counted as author evidence, and a cut item is folded, never deleted, so the author can open the fold.
- **Source rank**: every row carries a source (author, critic, system). A critic's input is never law until triaged.

### Gaps

1. **Evidence targets are display text.** `target` holds a string such as a file name and a quoted fragment, not a thread id, paragraph hash or concept id. Precedent lookup ("what did the author decide about this paragraph before") cannot be a join.
2. **Most evidence supports no belief.** Only the episode-analysis rows and about half the accepted author reviews carry `supports_belief`. The largest classes (resolved external edits, concept triage, critique triage, filter edits) carry none.
3. **No uniform run or step id.** Four run tables with different shapes; `revise` rounds, referee rounds, narration and the comment pass have no run row at all. An origin name (`referees-r1`, `ending-r1`) is the only handle, typed by hand, and it was the thing looked up by SQL most often.
4. **Verdict has two shapes.** A thread state for text, a review row for suggestions, a `write accept/reject` for beats. "Accepted with rewording" exists only for forms.
5. **Chat verdicts are not captured.** The owner's line-level corrections in the beat loop (about 14 of 17 beats) reached the store only as 4 `write reject --reason` rows and 2 style laws. The rest live in the transcript.
6. **Thread to version link is implicit.** A resolve prints the new version id; the thread row does not hold it. Paragraph identity is a content hash that changes on edit, so an old verdict cannot be re-attached to the paragraph's successor.
7. **No model or prompt on the proposal.** `usage.jsonl` knows what a call cost; the proposal does not say which model and prompt version produced it, so "accept rate by model" (the question the cheaper-model goal needs) cannot be asked.
8. **Subagent work is invisible.** Drafter, critic and referee runs happen in the chat harness; only their final text reaches a verb.
9. **Belief validation is slow.** 10 validated against 354 candidates; 138 active laws, nearly all declared directly. The door works; the feed into it is thin (gaps 1, 2, 5).

### What a workspace-wide standard would need from it

- One envelope for every repo: `run(id, procedure, version, subject, started, status)`, `step(run, index, kind, verb, input refs, output refs, model, prompt version, cost, status)`, `proposal(id, step, target ref, old, new, note)`, `verdict(proposal, decision ∈ accept / accept-modified / decline / defer, final text, reason verbatim, by, at)`, `evidence(verdict or observation, typed target ref, supports)`, `belief`, `law`.
- Typed target refs: `{kind, id}` with a stable id (thread id, concept id, a paragraph lineage id that survives edits, clip id, episode id).
- The door as a rule of the standard, not of one repo: nothing a model inferred may bind until a named person accepts it, and the acceptance is itself a verdict row.
- Source rank and the two loop invariants (machine cuts are not human evidence; cuts fold).
- A place for chat verdicts: the runner, not the model, records what the owner said at an owner-decision step.
- The store can stay SQLite per repo with the same columns; a graph projection, if wanted, reads these tables.

### What a generic agent-memory service would lose

- The door. Such services extract facts from conversation and serve them back; an unratified guess would steer the next draft. authorlm's whole design exists to prevent that.
- Belief versus law as two tables with different rights (confidence and retraction on one side, binding and file-scoped composition on the other).
- Composition without a model: the effective guide for a file is computed, not retrieved by similarity.
- Verdicts tied to exact old and new text in a specific tab, with the reworded final text kept.
- Folds: what the screen cut stays inspectable.
- Source rank: a critic's or a referee's claim would sit beside the author's.
- Hermetic tests and cloud sessions: the CLI runs where no memory server exists.

## (f) Formalise first: W1, the form round

Why this one: it is the tail of every editorial workflow (W2, W3, W5 and the directive, filter, lens and critique passes all end in it); it ran more often than everything else combined; nine of its eleven steps need no model; it is where the six incidents, the "did it push?" questions and most of the `--help`, source-reading and SQL lookups happened; and its owner step already has a real state machine in `doc_threads`. A runner here turns "accept the forms in X" from a dozen exploratory commands into one procedure with a frontier model called only for the drafting step.

What a procedure definition for it needs that does not exist yet:

1. **A status verb with typed output**: for one file, the tab link, sync state (level, file ahead, Doc ahead, conflict), and pending forms grouped by origin type and origin id with counts and thread ids. This replaces the SQL lookups and lets "which resolve verb" be a table lookup on origin type.
2. **One resolve entry point** that dispatches to `revise`, `filter`, `critique`, `lens`, `morph`, `footnote`, `explain`, `suggestion` by origin, so the path cannot differ between sessions.
3. **Machine-readable results (`--json`) and distinct exit states** on `doc diff`, `doc pull`, `doc push`, `revise stage`, `revise resolve`: counts of accepted, modified, declined; the new version id; and a named blocker (pending form, stale thread, unbalanced marker, conflict) instead of prose.
4. **A closed failure table**: each named blocker mapped to a tested branch (close thread, rebuild with the owner's word, strip marker, hand merge) or to escalation. The five reproduced failures and the live-recorded Doc fakes are the starting set.
5. **A round id.** One row per stage-to-resolve round (file, origin, staged thread ids, base version, result version, state), replacing the hand-typed origin name and surviving context compaction.
6. **A withdraw verb** for staged forms, and a "settled text" verb (the file as if pending forms were accepted, tags stripped), which W4 also needs.
7. **An owner-decision step the runner can wait on**: today the signal is a chat sentence. Either a "done reviewing" marker the pull can read from the tab, or a runner prompt with the three answers (land them, not yet, discard).
8. **Reply text in a margin thread treated as a verdict with words**, not dropped when it is more than a bare accept or decline.
9. **Verdict and evidence rows written with typed targets** (thread id, paragraph ref, round id, model and prompt of the proposing step) at resolve time. This closes gaps 1, 3, 6 and 7 for all new data without touching old rows.
10. **A speed budget**: the round is interactive; a resolve that takes minutes invites the side work seen in (c) 8. Per-verb timing is already in `trace.jsonl`; the procedure should state the expected time per step and flag overruns.

Not needed for this: Neo4j. The round, step and verdict rows are flat and belong beside `doc_threads`.
