# Workflows observed in podlm sessions

Written 2026-11-04. Read-only analysis of podlm's recent Claude Code sessions, its skill (`.claude/skills/podlm/SKILL.md`, 1,883 lines) and its CLI (`podlm --help`, the `authorlm`/`ytlm` calls in `src/podlm/`). Second pass after [podlm.md](podlm.md); the framing is "Orchestration framing" in the adoption plan. podlm has no `CLAUDE.md`; the skill is the only prose procedure.

Method: a script reduced each transcript to owner turns, assistant text, Bash command lines and tool names (tool outputs left out). Three of the digests were read by subagents and two by this session. Limits: assistant text and commands were truncated in the digests; the second half of session 2 below was read as a condensed outline; counts are of what the digests show and are lower bounds.

## (a) Sessions examined

| # | Dates (UTC stamps) | Topic | Length |
|---|---|---|---|
| 1 | 2026-11-03 to 11-05 | Repo hygiene and conventions: branch and worktree cleanup, PRs #71/#69/#65, replacing `--yes` flags across seven repos, then designing and building comment likes and the comment-replies page | 37 turn headers (about 20 owner-typed), 109 commands, 8 subagents |
| 2 | 2026-10-25 to 10-30 | "Monologue for read again": series charter from the book, clip research, script in the authorlm manuscript, prototype video, recorded production draft, for Read Again and Bind Again | 196 headers (about 115 owner-typed), 796 commands, 33 subagents, 3 context compactions |
| 3 | 2026-10-28 to 10-30 | "Monologue for bind again": second monologue started from a Riverside take, false-start cuts, shot plan re-cue, review rounds | 31 headers (about 14 owner-typed), 222 commands |
| 4 | 2026-11-01 to 11-02 | "Podcast script types and podlm process" (one session, continued): scripted-editing design and build, both monologues re-produced, a retake, both published to YouTube, PR #70, tool harvest | 119 headers (about 54 owner-typed), 602 commands, 115 Artifact publishes |
| 5 | 2026-10-01 to 10-03 | "Episode 8 processing": a guest episode from Riverside import to public on YouTube, with the YouTube publish step designed and built on the way | 77 headers (52 owner-typed), 435 commands |

Skipped: the Neo4j assessment, scheduled check-ins and one-turn sessions. Session 5's production verbs (cutaways, `transcript-fix`, edited-master) were retired on 2026-10-16; its publish half is still current.

## (b) Workflows as procedures

Step kinds: **V** verb or script call, **M** model judgement, **O** owner decision, **G** gate or check. Formality: **F** formal (a verb with stored state), **S** semi-formal (skill prose), **I** informal (worked out in the session, ad-hoc python/ffmpeg).

### W1. Monologue: book to script to video (the owner's example)

Seen in sessions 2, 3 and 4. It crosses podlm, authorlm, ytlm, corpuslm's database and (once, through a subagent) Bee transcripts.

| # | Step | Kind | Verb or tool | Owner repo | In → out | Form |
|---|---|---|---|---|---|---|
| 1 | Read the series charter and audience | V | `authorlm -m <show> profile show series-<series>` | authorlm | profile → text in context | F (profile), S (the duty to read it) |
| 2 | Paragraph and section summaries of the book | V+M | `split.py` in the series folder, then parallel subagents filling rows | podlm workspace (to move to authorlm, authorllm#264) | manuscript files → `paragraphs/<file>.json` (id, hash, summary, concepts) | I |
| 3 | Section brief: what the book says on a topic, aspects, clips, coverage | M | ad-hoc python over the summaries, then writing | podlm workspace | summaries → `briefs/<topic>.md` | S |
| 4 | Find candidate clips | V+M | `ytlm find`, `ytlm search`; once a raw sqlite query on the shared transcript database; Bee search inside one evidence subagent | ytlm, corpuslm, beelm | topic → video ids, spans | F verbs, I selection |
| 5 | Add and transcribe new sources | V+G | `ytlm video add`, `ytlm run --dry-run` (cost shown, small threshold), `ytlm run` | ytlm | URL → transcript in the corpus | F |
| 6 | Pin each clip's exact span and quote | M (narrow) | `ytlm segments <id> --from --to`, `ytlm quote`; a cheaper subagent rounds to whole sentences | ytlm | span → `quote:`/`moment:` on the tag | S |
| 7 | Owner's reading of each clip | O | chat | — | recorded in the section brief | S |
| 8 | Choose the spine source | M then O | three to five candidates proposed, owner picks | — | choice lives in the brief | S |
| 9 | Episode brief for review | M+V | Artifact page | podlm | briefs → page | S |
| 10 | Draft the script as a manuscript chapter with media tags | M | file write, `authorlm -m <show> doc add`, `doc push` | authorlm | brief → `<slug>.md`, Google Doc tab | F verbs, S writing rules |
| 11 | Check the script against the book and the spoken-style rules | G+M | `check_monologue.py --spoken-json` over `authorlm audio export`; the book check itself is reading the summaries and exact lines | podlm `articulation/`, authorlm | script → `review.md`, `log.jsonl` | S (style), I (book check) |
| 12 | Owner edits in the Doc; round trip | O+V | `authorlm doc diff`, `doc pull`, `doc threads`, `doc merge`, `doc push` | authorlm | Doc ⇄ `.md` | F verbs, fragile |
| 13 | Prototype narration | V | `podlm import <slug> --prototype -m <show> --file` (calls authorlm `doc pull`, `audio export`, `audio preview --rebuild`, `audio stitch --preview`) | podlm calling authorlm | text → `say` narration, `episode.json` hashes | F |
| 14 | Bind media tags | V | `podlm media read <slug> -m <show> --file` (reads `authorlm media --json list`) | podlm calling authorlm | tags → `work/media.json`, board | F |
| 15 | Illustrations | V+O | `authorlm illus list/render/pick/pin` | authorlm (image model) | tag → image; cost reported after | F |
| 16 | Generated clips | V+G+O | `authorlm clip ensure --dry-run --json`, `clip ensure`, `clip pick --take`, `clip spec` | authorlm (video model) | spec → takes, picked take | F |
| 17 | Free-licence stills | M+V | subagent with a scratch search script, Wikimedia Commons | — | query → image, licence record | I |
| 18 | Trim clips, build reels | V+M | `podlm media trim --key --in --out`, `media look`, `media collage --no-auphonic`, `media insert` (downloads via `ytlm --json excerpt`) | podlm calling ytlm | tag → excerpt, trim, reel | F verbs, M for in/out points |
| 19 | Hand-written shot plan | M | edit `work/edits.json` `shots`, `podlm shots --check` | podlm | script + images → shot plan | S, heavy judgement |
| 20 | Build and self-check the draft | V+G | `podlm up`, `podlm media timeline`, `podlm verify`, `podlm lint`; ad-hoc ffmpeg frame grabs | podlm | → `review/draft.mp4`, `review/timeline.md` | F plus I |
| 21 | Teleprompter and recording | V+O | `authorlm export teleprompter --upload`; owner records in Riverside | authorlm, owner | script → Drive doc → take in Downloads | F verb, I hand-off |
| 22 | Swap in the recording | V+M | `podlm import --production --narration`, `words`, `takemap`, `edits`, `edit-inspect`; false starts cut by subagent pass | podlm | take → `words.json`, `takemap`, `edits.json` | F verbs, M cuts |
| 23 | Re-cue after text or take changes | V+M | `podlm relocate` (lists displaced items), hand-written decisions file, apply | podlm | `relocate.json` → decisions → `edits.json` | F since 2026-11-01; before that ad-hoc python |
| 24 | Review rounds | O+M+V | W2 below | podlm | — | S |
| 25 | Publish | — | W3 below | podlm | — | F |

Not observed as a discrete step: a check of the finished script against the manuscript with a recorded result. The book enters through the summaries and briefs (steps 2 and 3) and through the author's Doc edits; nothing states "script claim X is supported by passage Y". Bee transcripts were consulted once, inside a subagent, with no verb called from the main thread; llmlm was never called from a session (podlm code calls it for packaging and comment labels).

### W2. Draft review round

Sessions 3, 4, 5; about eight rounds in session 4 alone.

1. **V** Build the review page: `podlm gallery edits <slug>` or `podlm review events|storyboard|draft` (podlm, F).
2. **V** Put it in front of the owner: Artifact publish, one video per call; later the tailnet file browser (I; the route changed mid-session after uploads failed).
3. **O** Owner notes arrive three ways: the page's data store, a wake comment, or pasted text in chat (I).
4. **M** Map each note to a change: an `edits.json` or `media.json` patch, a `media trim`, a manuscript tag change with `authorlm doc pull/push`, or a code fix (I, frontier for free text).
5. **V+G** Rebuild (`podlm up` or the stage chain, `draft --no-auphonic`), `verify`, `lint`, frame grabs (F plus I).
6. **V** Republish and notify with `superlm-notify` (S).
7. **O** Sign-off: `podlm approve <slug> draft` on the owner's word (F, fingerprinted in `approvals.json`).

### W3. Publish to YouTube

Sessions 4 and 5. The most formal workflow; the skill lists it and every step has a verb.

1. **V** `podlm up` past the draft gate: publish files, `package` (model call through llmlm), `thumbkit`, `kit`. Auphonic is a spend gate (**G+O**, `--confirm-spend`).
2. **O+M** Titles and hooks: `podlm review titles`; thumbnail plate made by the owner, then `podlm thumbnail plate --text --layout`.
3. **V** `podlm youtube-meta` → `work/youtube.json`.
4. **G** `podlm youtube-login --check`; **O** owner signs in if needed.
5. **O** Owner uploads the file as Private in Studio and gives the video id (manual by design).
6. **V** `podlm upload --video <url>` dry run; `podlm gallery youtube-before`; Artifact.
7. **O** Owner says send. **V** live upload, read-back compare (**G**: any difference is a bug), `gallery youtube-after`.
8. **O** Owner says make it public. **V** `podlm upload --make-public` with the pinned comment.
9. **V** `podlm growth checkin-plan`, scheduled check-ins, `podlm facebook`.

### W4. Guest episode production (legacy shape, current analogue is the edit workflow)

Session 5. Stem sanity check (I, later an import guard) → owner picks workflow and spend → `podlm import` → `podlm up` to a gate → model checks proposed cards against the transcript and the web (M) → gallery, owner approves → `up` to the draft gate → `verify` → owner watches → fixes → `approve` → `kit`. A re-export from Riverside happened three times and each time ran an unwritten sub-procedure: validate the new files, set old ones aside by hand, re-import, re-apply spelling fixes, re-time approved cards by anchor phrase.

### W5. Design, build, merge (changing the pipeline itself)

Sessions 1, 4, 5; it interleaves with production in every session. `/grilling` or a subagent debate → `docs/design/<name>.md` as an Artifact → owner ratifies → issues → TDD per slice, sometimes one subagent per worktree → pre-commit → PR → merge → `/harvest-tools`. Cross-repo in session 1: one PR per repo for a flag rename, with a merge-order dependency between authorlm and podlm found only after the first PRs were open. Semi-formal (global skills), and outside what a production runner needs.

### W6. Audience follow-up

Session 1 and the scheduled check-ins: `podlm analytics`, `podlm growth`, `podlm comment-likes`, `podlm comment-replies` (labels by Jev through llmlm, drafts held on a served page, Accept posts). Formal, with stored state; built on 2026-11-04 and not yet run enough to show friction.

## (c) Friction, with evidence

Counts are occurrences visible in the digests.

**Text keeps moving under work built on it (W1).** The shot plan was re-cued at least 5 times in session 2 and again in sessions 3 and 4 because the script or the take changed. The retake in session 4 displaced 69 placed items; 50 were moved and 19 removed by a hand-written decisions file, and the owner then had to ask which removals were real. `relocate` now exists, but the judging step has no recorded rationale per item.

**Stale or wrong output reached the owner.** Freshness skips that needed a forced rebuild: about 5 in session 2. The owner was shown an old or mislabelled draft 4 times in session 4. In session 5 an import silently kept old stems and reused an old Auphonic run (two wasted imports, one wasted paid production).

**The Doc round trip is fragile.** Lines joined on push about 4 times before a fix; a rebuild of a Doc tab orphaned an owner comment after the owner had said to address it first; a conflict needed the owner to say which side stands (session 3). `authorlm doc pull/diff/push` is the most-called cross-repo verb group: about 90 calls across the monologue sessions.

**Where things live was re-decided in conversation.** The series charter's location was corrected 5 times in two days (skill, workspace file, authorlm profile). In session 5 the owner looked for a design doc in the wrong repo.

**Review delivery changed route mid-run.** Artifact video uploads failed at least 5 times in session 4; the fallback (the tailnet file browser) lost the wake button, so notes came by paste. Three intake routes for notes exist and none is the one a run expects.

**Owner reminders of rulings already given.** At least 8 in sessions 2 to 5: do not ask again before AI generation, check YouTube sign-in first, links at the end, name what was removed, the thumbnail is already in the publish folder (twice), use standard authorlm verbs, stop over-designing (twice).

**Editorial rules stated as corrections after a draft.** Session 3 has four owner messages of numbered defects: shots cut too quickly, audio cut mid-sentence, a picture arriving before its concept is introduced, a clip that does not carry its own context. Each became skill prose or a rule in `rules.yaml` afterwards. The last one (transcribe the narration before, the clip, and the narration after, and check continuity) is a procedure step that did not exist.

**The model took a different path than last time.** Thumbnail edits bypassed any verb and called an image API from a scratch script (session 4, 6 rounds, 2 sharp corrections). A raw database query stood in for a ytlm verb once. A PDF was exported when the teleprompter was meant. Paragraph summaries were produced by subagents outside authorlm's usage ledger. In session 5 the stem check ran on the first import and was skipped on the second.

**Ad-hoc glue is large.** Inline python: 64 runs in session 2, 33 in session 3, 24 in session 4, 20 in session 5. ffmpeg/ffprobe: 38, 19, 13, 35. `/harvest-tools` found 94 candidate scripts after session 4. Each is a step with no name.

**Tool repair interrupts production.** About 12 subagent PRs across authorlm and podlm during session 2; the pre-commit hook failed or ran slowly in sessions 2, 4 and 5; sign-in took 4 attempts in session 5.

**Steps the owner had to remember:** upload Private in Studio and hand over the id; run `authorlm doc auth`; say whether an inserted reel needs a name tag; confirm Auphonic spend; record and drop the take in Downloads; tell the session which earlier session to learn from (session 3 opened with exactly that instruction).

## (d) Model fit per step

**No model (a runner calls the verb and checks the exit and the stored state).** W1 steps 1, 5, 13, 14, 20, 21's export; W2 steps 1, 5, 6; all of W3 except titles, thumbnail text and the three owner words; W6 fetches. Also the glue that is ad-hoc today but deterministic: stem identity and overlap checks, aspect probing, frame grabs at known times, cue checking against `words.json`, re-timing by anchor phrase, cost dry-runs, sign-in checks, Doc diff before pull. These fail today mainly through sequencing (skipped, or run against stale inputs), which is the runner's job.

**Cheaper model, narrow input and typed output.** Pinning a clip span to whole sentences from a timed transcript (already delegated to a smaller model in session 2); paragraph summaries (1,219 rows, hash-keyed, done once); confirming what a speaker says in a span; ASR spelling variants; turning a structured review note (event id plus a preset) into an `edits.json` patch; lint triage; false-start candidates from a take map, if a check verifies every cut against the audio (session 3 showed word times running early, so the check is required); Facebook post and description drafts; comment labels (already Jev).

**Frontier model.** Section and episode brief synthesis; spine proposals; drafting the script in the author's spoken voice; the shot plan (the skill itself calls it judgement work, never seeded alone); relocation decisions after a retake; continuity of narration, clip, narration; choosing pictures and scenes; free-text review notes; diagnosing wrong output; design work (W5). These are also the steps where a decision trace is worth the most, because the owner corrected them most.

The split suggests the shape of a procedure: frontier steps are few and sit between long mechanical stretches, so a runner that owns the stretches would leave the frontier model with a small, well-fed context per step instead of a five-day session with three compactions.

## (e) Decisions and traces

**Recorded today, in five places with no common shape.**

- `approvals.json` and `work/fingerprints.json`: the draft gate, fingerprinted. The only decision record that is machine-checked.
- `work/edits.json`: each entry has an origin (agent or author) and author locks; it holds what was decided, seldom why.
- `rules.yaml` and config: rules R1 to R16, clip length bounds, wrap defaults, spend thresholds.
- Skill prose with a date and "owner" or "ruled": several dozen rulings (hand-written shot plan, prototype work is never thrown away, every clip ready before the draft, trim and sound duties, publish steps).
- Memory files and authorlm profiles: working preferences, series charter, audience, coverage. Section briefs hold the owner's reading of each clip.
- Design docs and commit messages: some card and layout rulings from session 5 live only there.

**Decided in a session and not clearly recorded anywhere.** Split a monologue at 8 to 10 minutes; stills stay at least 4 seconds; historical figures need no cast character; short clips were a one-episode choice; name every removal after a retake; on a re-export, treat it as a fresh run but keep approved cards; the owner's own thumbnail outranks generated options; AI disclosure answer for a generic generated clip; slow tests only for shared changes.

**Reusable as precedent, if recorded per instance.**

- Clip in or out: which clip, which span, for which point, accepted or dropped, and the owner's reason. Today only the surviving clips are in the brief; rejected ones and reasons are lost, so the next search re-proposes them.
- Spine choice: the candidates, what each covered, which won.
- Review note → change: the note, the edit it became, whether the owner accepted the result. This is the largest stream (dozens per episode) and the best training set for the cheaper-model step in (d).
- Relocation: item, moved or removed, why.
- Spend approvals: what was quoted, what was approved, actual cost. Auphonic and generation costs are reported in chat and in logs, not against the decision.
- Doc conflicts: which side stood.
- Publish read-back differences and how each was settled.

Nothing ties a decision to the run it was made in. A run is a chat session; its id appears in no state file, and one session spans several episodes and several workflows (session 2 carried W1 for two episodes plus W5 across two repos).

## (f) What to formalise first

**W1's middle: script chapter to prototype draft** (steps 10 to 20, with W2 as its loop). Reasons: it is the owner's example; it ran four times in ten days (Read Again and Bind Again, each twice); it has the most cross-repo calls (authorlm about 300, ytlm about 50 in the sessions examined); its friction is mostly sequencing and staleness, which a runner fixes; and most of its steps already have verbs with JSON output, so the procedure is mainly an ordering with gates. W3 is already close to formal and gains little. Steps 1 to 9 (research and briefs) are still changing shape and should follow once the summaries move into authorlm.

What a procedure definition would need that does not exist yet:

1. **A run record.** An id per run of a procedure on a slug, with each step's verb, arguments, input and output hashes, exit state, cost and who decided. podlm's fingerprints cover its own stages; nothing covers the authorlm and ytlm steps or the hand-offs between them.
2. **Step contracts across repos.** Each verb the procedure calls needs a stated JSON result and exit meaning. Known gaps from the sessions: `authorlm doc pull` conflict as a typed outcome; `authorlm illus` and `clip ensure` cost before and after in one shape; `ytlm run --dry-run` cost as data; `podlm media read` reporting which tags are not ready.
3. **A text-freeze gate with a version.** The manuscript chapter's hash is recorded at prototype import; the procedure needs a named state ("script frozen at hash H") so the shot plan, trims and reels are built against a known text and a change is an explicit re-entry at `relocate`, not a discovery.
4. **A readiness gate before the draft.** Every clip has its quote and trim, every illustration is rendered or deliberately a placeholder, every inserted reel has its name-tag answer. `verify` checks some of this after the build; the gate belongs before it.
5. **The continuity check as a step.** Narration before, clip, narration after, transcribed and judged, with a typed result per clip. Stated by the owner on 2026-10-30; exists only as prose.
6. **A manuscript-support check as a step**, if the owner wants the "review against the manuscript" in the example to be real: script claims and quoted lines matched to paragraph ids from the summaries, with unmatched ones listed. Depends on authorllm#264.
7. **One review-note intake.** A single typed note shape (target event or span, kind, text) and one route, with the page, the wake comment and pasted notes all normalised into it; and the resulting change linked back to the note.
8. **A decision record shape** shared by the owner-decision steps: question, options shown, choice, reason, run id, artifact ids. The same shape would serve the spend gates, clip choices, relocation and Doc conflicts listed in (e).
9. **Named verbs for the recurring glue**, starting with what `/harvest-tools` already found: frame grabs for self-check, cue check against words, aspect probe, free-licence image search with a licence record, thumbnail edits through a verb instead of a direct API call.
10. **Model assignment per step**, declared in the procedure, so span pinning, summaries and note-to-patch run on a cheaper model by default and the shot plan, relocation and continuity steps run on a frontier model with only that step's inputs.
11. **Human hand-off steps as first-class waits**: owner records the take, owner edits the Doc, owner uploads in Studio. Each needs a stated artifact that ends the wait (a file in a folder, a Doc revision, a video id) so the runner can resume without a new conversation.
