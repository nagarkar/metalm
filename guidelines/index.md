# metalm index

Rules ending `(owner)`, and every rule in a section or file that opens with `(owner)`, are the owner's; the rest are agent-drafted and may change.
Scope: every repo whose `CLAUDE.md` imports this file. These rules beat skill defaults. A repo's documented exception (an `(owner)` rule in its code or `docs/design/`) beats these.

## Read before acting

| When you are about to… | Read `~/.claude/metalm/guidelines/` |
|---|---|
| write a CUJ or its test, file a work item, or record an owner ruling | `requirements.md` |
| record a design decision, write a package docstring, generated docs, or a diagram | `design.md` |
| design or review structure: principles, patterns, concurrency, state machines, database choice and schema | `architecture.md` |
| write SQL, a migration, or query a database | `coding.md#storage-and-migrations` |
| plan a non-additive migration or a refactor spanning several PRs or repos | `coding.md#major-migrations-and-multi-step-refactors` |
| share a database between repos, or point a repo at another repo's database | `coding.md#sharing-one-database-between-repos` |
| put `.env` outside the checkout, share one between repos, or read a new environment variable | `coding.md#where-env-lives` |
| write code, a CLI, skill, MCP server, or an LLM call | `coding.md` |
| write or change tests, or claim something works | `testing.md` |
| move code between repos, or decide where a test belongs | `testing.md#where-tests-live` |
| touch a served page, server, launch agent, Tailscale | `operations.md` |
| check, diagnose or screenshot a served page (including "the owner cannot see it") | `operations.md#browser-checks` and `operations.md#served-apps` |
| design or change a page's layout or navigation, or hand over a UI feature | `ui.md` |
| create or change a scheduled job (launchd, local scheduled task, cloud routine) or unattended work | `scheduling.md`: go down the checklist for its type |
| write an install script | `install-scripts.md` |

## Repo layout

- `CLAUDE.md` is the one loaded file; `AGENTS.md` is a symlink to it. It follows the `metalm-setup` template and nothing else: the import line, what the repo is, its commands, its exceptions to metalm (each pointing to its `(owner)` rule), and agent-skill pointers. It never restates a metalm rule; repo knowledge lives in the code, the skill or the generated docs. (owner)
- The code is the design and the requirements (owner): area docs are package docstrings; decisions that span modules are inline rules marked `(owner)`, one answer per question, no dates or history (git keeps it); CUJs are markers on e2e tests. All of it is generated into `docs/generated/` (committed; never hand-edited). `docs/design/` only for decisions no code owns. Details: `design.md`, `requirements.md`.
- Work items are GitHub issues (`gh`). Issues are transient deltas; the code is the truth.
- Never create `CONTEXT.md`, `docs/adr/`, `docs/requirements/`, `.scratch/`, `backlog.md`, or a numbered decision log.
- Skills that say `CONTEXT.md` mean `docs/generated/glossary.md` (write terms in the owning package docstring). Skills that say ADR mean an `(owner)` rule in the owning package docstring. "Publish to the issue tracker" = create a GitHub issue; "fetch the ticket" = `gh issue view <n> --comments`.
- "Set up a repo" / "make the repo compliant with guidelines" → `metalm-setup` skill.

## Session

- Start: read `docs/generated/index.md` and the area's package docstring, and run the repo's `doctor`/status verb; do not redo design or scaffolding. One session per working directory.
- Token order: fewest turns > fewest output tokens > least uncached input > cached input. Terse replies; `Edit`, not full rewrites; never echo files; subagents for wide searches.
- End: run `/harvest-tools`; also whenever the same ad-hoc script runs a second time.

## Git and work items

- Branch for every change; never commit to `main` (the pre-commit hook `no-commit-to-branch` enforces it). Push `main`, force-push, or merge only on the owner's word in chat, or under the standing authorization in the repo's skill (`## Merging`, written by `metalm-setup`; it names its exceptions and the point at which the owner must revisit it: a second contributor, user or shared service); record one-off authorizations with date and issue number. (owner)
- One PR per change. Automation (CI, bots) opens PRs; it never merges, approves, or closes them, except a commit or PR that changes only `docs/generated/`, which agents may merge. (owner)
- Commit after each completed step. Subject: one sentence of behavior change + `(#<issue>)`; `Closes #N` where it finishes.
- `git status` before assuming a change landed. Never commit over the owner's uncommitted work.
- Defects: structured report (evidence file:line, given/observed/expected, owner verdict verbatim), filed only on the owner's confirmation; issue first (records commit + data version), fix second. Mention a filed defect once; keep the defect queue out of domain briefings.
- `gh`: bodies via heredoc; `gh issue view N --comments`; `gh issue list --json … --jq`; `--add-label`/`--remove-label`; close with `--comment`. Issues and PRs share numbers: resolve `#N` with `gh pr view`, fall back to `gh issue view`. PRs are not a request or triage surface.
- Triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. `ready-for-agent` = doable without the owner; `ready-for-human` = ask, do not guess. An open question for the owner becomes a `ready-for-human` issue. Work issues in milestone order.

## Asking and approvals

- Ask one question at a time, with your recommendation. Ask only for blocking or product-judgment calls.
- A multi-step instruction is one instruction: carry it end to end. Offer follow-ups; do not run them unasked.
- Never approve a gate, answer a review item, tag a release, or send anything to a vendor on the owner's behalf. Never present an automated pick as the owner's.
- Ask before any spend on a paid service, stating the cost. Nothing public without approval in chat. Show dry-run output before `--yes`. Never run an irreversible "accept all" (e.g. `resolve --all`) unless asked, and then only for what was named.
- When a rule blocks you, say so; do not work around it. Flag contradictions with an `(owner)` rule; never override silently.
- Leave system settings to the owner.

## Owner data

- Never mutate owner data or owner-authored content silently. Propose wording; apply only when told. Mechanical operations are fine.
- Check every place state lives before assuming where it is.
- Destructive SQL (`DROP`, `TRUNCATE`, `DROP COLUMN`, `DELETE`/`UPDATE` without a targeted `WHERE`): print it and wait for the owner's confirmation. Query with read-only access. More: `coding.md#database-safety`.

## Writing for the owner

- Every setting, flag, pin or config value named comes with its location: file path (line for code), or "proposed, does not exist yet" + the file it would live in; also its default, and whether the file is global or per-unit. (owner)
- Terse. Lead with the action; report outcomes, not effort. Plain words, not pipeline jargon. No pasted JSON or old/new text in chat. Summaries 3–5 bullets; no long walkthroughs unless asked. Report in prose per unit (staged, written, left out, skipped). After tool output, state the next action it implies; do not stop at status.
- Mark owner rulings `(owner)` where they are written down; no date.
- Every review ask carries a phone-ready page link.
- Surface warnings, conflicts and open questions unprompted.

## Memory

- Memory notes carry **Why:**, **How to apply:**, `[[links]]`; `MEMORY.md` is a one-line index.
- Decisions and rules belong in the code (package docstrings) or metalm, not memory; move them and delete the note. Correct or delete superseded notes.
- Before recording a lesson, check it is not already done (`git log`, code).
