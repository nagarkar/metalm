# Requirements

Status: DRAFT — not yet ratified by the owner. Rules marked `(owner)` are the owner's.
Scope: what a repo's requirements are (CUJs generated from code), how to write a CUJ, work items, checking docs against code, and capturing owner input.

## CUJs are generated from the code
- A repo's requirements are the critical user journeys (CUJs) its code supports, generated into `docs/generated/cujs.md` (design.md#generated-docs). The code is primary; no hand-written file says what the system does. (owner)
- A CUJ is declared on the end-to-end test that proves it. Python: `@pytest.mark.cuj("<journey>")`, the marker registered in `pyproject.toml`. Other languages: a tag the metalm extractor reads (TypeScript `// cuj: <journey>` above the test; Swift a `.tags(.cuj)` trait plus the journey as the test's display name). A journey with no test does not appear. (owner)
- Wanted or planned behavior is a GitHub issue whose acceptance criteria are written as CUJs; it becomes a generated CUJ when its test lands.
- `docs/requirements/` does not exist in a repo; this file is the guidance for writing CUJs. (owner)
- Bugs, exploration and one-offs live only in issues. Closed issues are never the truth.

## Writing a CUJ
- One journey per marker, in this shape: "<Actor> <does what> via <surface>, and sees <outcome>." Add the failure the journey promises: "If <failure>, they see <message>."
- Actor is named (the owner, a reviewer on a phone, the nightly job). Surface is its real name (`ytlm corpus add`, `/approvals`, the review page).
- Outcome is what the actor can observe, with numbers and units where they matter ("within 2 s", "at most 20 hits").
- Every core path has a CUJ: money, deletion, persistence, access, user data, time (expiry, schedules).
- The test asserts what the CUJ says, through the surface it names. A CUJ whose test checks something else is a defect.
- Group by area: the generator sorts CUJs under the area of the test's file.

Banned words in a CUJ (replace with a number, a named actor, or a list):
- Vague: adequate, appropriate, sufficient, efficient, reasonable, flexible, easy, effective, normal, timely, some, several, many, about.
- Escape clauses: as appropriate, as applicable, if practical, where possible.
- Open-ended: etc., and so on, including but not limited to.
- A vague word is a defect only when two readings build two behaviors; one pinned down nearby is fine.

## Issues
- Acceptance criteria: CUJ sentences, plus "Done when:" lines a test can check.
- An issue cites the package or `(owner)` rule it changes.
- Feature ideas that span modules or are hard to reverse go through `/grilling` first (design.md#deciding); small, reversible ones go straight to code and a test.
- Defects: index.md (structured report, owner's confirmation, issue first).

## Checking docs against code
Generated docs cannot disagree with the code. What can:
- An `(owner)` rule the code contradicts.
- A hand-written doc (`README.md`, a skill, `docs/design/`) naming a verb, flag, config key, route or page that no longer exists: check every backticked name against the code.
- Every finding quotes both sides: the rule or doc text, and the code (or the nearest code showing the absence).
- Which side is wrong: the `(owner)` rule wins; else the behavior users already rely on; else fix the doc and leave behavior alone. (owner)
- Changing code to match a doc alters behavior and needs an `(owner)` rule or an issue that asks for it; without one, open a draft PR labeled `needs-intent` and ask.
- Leave alone: private helpers, test utilities, generated or vendored paths, work an open issue marks as planned.

## Readability
- Short sentences, plain words, glossary terms (`docs/generated/glossary.md`). One word, one meaning.
- Settings, knobs, thresholds: one table (Knob / Where / Value), every row filled; an empty row is a decision the owner has not been offered.
- Show results with their baseline; add no judgments (flags, warnings) the owner did not ask for.
- No hard-coded "as of" dates in behavior; end at the latest available data.

## Capturing owner input
- Record the owner's brief verbatim (minus dictation slips) in the issue. Paraphrase destroys evidence. Flag every substantive guess.
- A ruling becomes the rule's text in its one place (design.md#where-decisions-live), marked `(owner)`, no date; the same PR deletes every older answer. (owner)
- Grill one question at a time, each with a recommendation; then a YAGNI pass; then example rows before deciding any schema.
- Never default silently on a choice with real consequences: ask one line, saying what each answer means.
- A bare verdict without a reason: ask why once; if declined, record it as given. Never ask during bulk triage. Never re-ask what an `(owner)` rule settles.
- A mid-work general instruction: apply it now, and in the same reply propose it as a standing rule (exact words, target file), approvable with one word. Qualifies: an explicit terminology or structure ruling at once; a wording preference at two independent instances. A ruling that contradicts an `(owner)` rule replaces it; never leave both.
- Rejected options the owner wants kept out: an `(owner)` rule "<X> is out of bounds: <reason>" in the owning package docstring.
- Open questions are `ready-for-human` issues listing the data that bears on them; current behavior stands until answered.
- The owner makes every substantive judgment. Never silently mutate owner-authored content.
- State the problem with measured symptoms and cost before the solution. Proposals open with a scope note: what was asked vs what was found.
