# Requirements

Status: DRAFT — not yet ratified by the owner.
Scope: where requirements live, how to write and check them, how to trace them to design and code, how to capture owner input.

## Where requirements live

| Kind | Home | View | Lifetime |
|---|---|---|---|
| What the system must do (lasting behavior) | `docs/requirements/<area>.md` | full, current | persistent; edited in place |
| Why it is built that way | `docs/design/<area>.md` (see `design.md`) | full, current | persistent |
| One change, bug, exploration, one-off | GitHub issue | partial delta | transient; closed when done |

- One requirements file per area, mirroring `docs/design/`. Index: `docs/requirements/README.md`.
- Requirements say WHAT; design docs say WHY and HOW. A requirement cites the design decision that realizes it.
- Issues cite the requirement IDs they change or satisfy. Closed issues are never the truth.
- A PR that changes lasting behavior updates the requirement file in the same PR.
- Bugs, exploration and one-offs live only in issues; they never enter `docs/requirements/`.
- Feature ideas go through grilling → design doc → requirement. Only a defect with a verifiable repro goes straight to an issue.
- Doc-light repo: propose one derived requirements file; each behavior a numbered requirement citing the file it comes from, marked "derived from <file>; owner to confirm". One document per PR.

From the global "Repository Layout for Design and Work Items" rule (Ruled 2026-10-02):
- Decisions live in named design documents under `docs/design/`, listed in `docs/design/README.md`. No numbered decision log, no `docs/adr/`, no `CONTEXT.md`.
- A design is ratified as a design document (drafted as DRAFT in `docs/design/<name>.md`) before work items are cut. Then write the PRD and issues.
- Work items are GitHub issues via `gh`, on a private repository. No `.scratch/`, no issue files in the tree. A repo without a remote gets a private GitHub repo first. `docs/agents/issue-tracker.md` says GitHub.
- Code quality review: built-in `/code-review`. The Matt Pocock `review` skill is used only for its spec axis (does the diff do what the issue asked).

## File template

```markdown
# <Area> requirements
Owner: <name> · Updated: <YYYY-MM-DD> · Status: DRAFT | ratified
Nothing here is built unless the status table says so.

## Purpose
<2–4 lines: who uses this, the loop they live, what must hold; budget context (volume, acceptable $/month).>

## Requirements
- **ORD-1** The system MUST <behavior> within <number unit> when <condition>. (Design: `docs/design/orders.md#approval`)
- **ORD-2** ...
- ~~**ORD-3** ...~~ Retired 2026-10-03: <reason>.

## Boundaries (what this area leaves alone)
- <Out of scope item> — <reason>. Do not resurrect without new evidence.

## Status against these requirements
| ID | Built? | Where |
|---|---|---|

## Open questions
- <Question> — data that bears on it; current default stands until answered.

## Done when
- <Concrete, checkable acceptance test.>

## Changes
- 2026-10-03: <what changed, why, owner quote if a ruling>.
```

- Edit in place. Every change adds a dated line under `## Changes`.
- Every setting named gives its location (file path), or "proposed, does not exist yet" plus the file it would live in.

## IDs

- Format `<AREA>-<n>` (e.g. `ORD-3`). Area code is short, uppercase, unique per repo.
- Never reuse an ID. Retire by striking through with date and reason; keep the line.
- One ID defines one thing. Duplicate IDs and `TBD`s are always defects; report them.

## Normative language

- RFC 2119/8174: only capitalized MUST / MUST NOT / SHOULD / SHOULD NOT / MAY carry force.
- Core behavior (user data, money, access, time) uses MUST. Never state a core behavior as SHOULD/MAY while code treats it as mandatory.
- One requirement per bullet. No "and" joining two obligations.

## Quality checklist

Each requirement (ISO/IEC/IEEE 29148): necessary, appropriate, unambiguous, complete, singular, feasible, verifiable, correct, conforming.
- Complete = carries every condition needed to check it: number, unit, time window, actor, error case.

The set: complete, consistent, feasible, comprehensible, validatable.
- Contradiction and omission are invisible line by line. Read the whole file before declaring it sound.

Banned words (replace with a number, a named actor, or a list):
- Vague: adequate, appropriate, sufficient, efficient, reasonable, flexible, easy, effective, normal, timely, some, several, many, about.
- Escape clauses: as appropriate, as applicable, if practical, where possible, as little as possible.
- Open-ended: etc., and so on, including but not limited to.
- Weak options: can, optionally, be able to; `tbd`.
- Word lists are hints (~6 in 10 hits are real). A vague word is a defect only when two readings build two behaviors; one pinned down nearby is fine.

Defect priority (fix the first that applies; a precise edit to one requirement beats rewriting the doc):
1. Two requirements that cannot both hold (quote both).
2. A behavior on user data, money, access or time (deleting, charging, locking, expiring, sharing) no requirement covers.
3. Ambiguity on a core path that changes what gets built.
4. Missing condition (number, unit, actor, error case).
5. Duplicate ID or TBD (esp. a TBD the code already depends on).
6. Core behavior stated only as SHOULD/MAY.

Leave alone: wording, grammar, formatting, heading style; items marked aspirational/planned/non-goal; needs you cannot show with a quote; code disagreeing with a clear requirement (that is traceability, below).

Before shipping, ask "would this help someone build and test it?"; list what it does and does not resolve.

## Traceability

- Forward: every requirement is implemented. Backward: every behavior in code traces to a requirement (nothing unnecessary built). Check both.
- Classify each relation: convergence (agree), divergence (code has it, docs do not), absence (docs have it, code does not).
- Prefer exact doc-reference checks (backticked names, commands, routes, config keys exist in code) over text-similarity matching. Ignore planned features, external tools' commands, same-meaning naming, generic words.
- Every finding quotes BOTH sides: doc text and code, or the nearest code showing absence.
- A disagreement does not say which side is wrong. Decide in order:
  1. Confirmed owner ruling / ratified requirement.
  2. The more recent deliberate decision (dated `## Changes` line, ratified doc).
  3. Behavior users already rely on.
  4. Still unclear: fix the doc; leave behavior alone.
- Changing code to match a doc alters behavior; it needs a governing requirement or ruling. Without one, open a draft PR labeled `needs-intent` and ask.
- Any change to observable behavior (return values, errors, stored data, messages, timing) names the requirement ID that justifies it.
- Priority: documented behavior the code does differently and hurts a relying user (a "safe" flag that writes, an unenforced limit); unimplemented requirement; destructive or externally visible entry point (CLI verb, route, script, config key) no doc mentions; doc naming a command/flag/key that no longer exists; data stored somewhere other than documented; a design decision the code contradicts; a requirement the design omits.
- Leave alone: private helpers, test utilities, generated/vendored paths, work marked planned, behavior a confirmed intent/ruling marks deliberate (no review lens flags it).
- A small, sure fix to the wrong side beats rewriting either side.

## Readability

- Short sentences. One requirement per bullet. Plain words; glossary terms from `docs/design/glossary.md`. One word, one meaning: retire a word with two meanings and record renames in the glossary. Use glossary terms in code, issues and test names too; a missing term is invented language or a gap. Do not over-formalize a pattern that already works.
- Settings, knobs, thresholds: one table (Knob / Where / Value). Every row filled; an empty row is a decision the owner has not been offered.
- Show results and their baseline; do not add judgments (flags, warnings) the owner did not ask for.
- No hard-coded "as of" dates in behavior; end at the latest available data.

## Capturing owner input

- Record the owner's brief and rulings verbatim (minus dictation artifacts). Paraphrase destroys evidence.
- Clean obvious transcription slips silently; flag every substantive guess.
- Rulings carry "(Ruled <YYYY-MM-DD>)" and the owner's exact quote where wording matters. Owner-requested changes say "Why: asked for by the owner" plus the triggering question.
- Grill one question at a time, each with a recommendation. Then a YAGNI pass. Then concrete example rows before ratifying any schema.
- Never default silently on a choice with real consequences: ask one line, explain what each answer means.
- Bare verdict without a reason: ask why once. If declined, record as-is. Never ask during bulk triage. Never re-ask what a ruling settled.
- A mid-work general instruction: apply now, and in the same reply propose it as a standing rule (exact words, scope, target file), approvable with one word. Qualifies: an explicit terminology/structure ruling at once; a wording preference at two independent instances. Never ratify silently. A contradicting ruling becomes an amendment question (retire + re-add), never left to drift.
- Record rejected options and out-of-scope requests under Boundaries with reasons and date: "do not resurrect without new evidence".
- Open questions list the data that bears on them; current defaults stand until answered.
- Proposals not yet agreed live in a DRAFT doc ("Not ratified; nothing here is built") ending with "Questions to settle before ratifying".
- Owner makes every substantive judgment. Never silently mutate owner-authored content.
- First round covers common cases without decisions that block later ones; start with the case blocking real work.
- State the problem with measured symptoms and cost before the solution. Proposals open with a scope note: what was asked vs what was found.
