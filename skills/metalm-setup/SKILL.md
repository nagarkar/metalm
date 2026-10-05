---
name: metalm-setup
description: Set up a repo to metalm guidelines, adopt metalm in an existing repo with its deviations grandfathered, check conformance, or make a repo fully compliant — creates the standard layout, moves and revises docs, grills the owner on repo-specific choices, and proves nothing was lost. Use when the user says "set up a repo", "make the repo compliant with guidelines", "adopt metalm", "grandfather this repo", "check conformance with metalm" or "metalm check". Replaces /setup-matt-pocock-skills.
---

# metalm-setup

Brings one repo to the layout and rules in `~/.claude/metalm/guidelines/`. Read `index.md` there first; read the topic guideline before touching its area.

Modes:
- **setup** (default; "set up a repo", "make the repo compliant with guidelines"): phases 1–7, ends in one PR. Removes grandfathered exceptions it resolves.
- **adopt** ("adopt metalm", "grandfather this repo"): opt in now, conform later. Phases 1 and 6, then on a branch: add the import line to `CLAUDE.md` (create it, `AGENTS.md` content merged, `AGENTS.md` symlinked), and record every phase-6 failure as a row under `## Grandfathered exceptions` in `docs/design/exceptions.md`: `| <rule> | <guideline>.md#<section> | <where in repo> | adopted <YYYY-MM-DD> |`. Moves no content. One PR. New work follows metalm.
- **check** ("metalm check", "check conformance with metalm"): phases 1 and 6. Report only; change nothing. A failure listed as a grandfathered exception reports as `excepted`, not `fail`.

## Target layout

```
CLAUDE.md                     the one loaded file: import line + repo notes (template: templates/CLAUDE.md)
AGENTS.md -> CLAUDE.md        symlink, for Cursor/Codex
src/<pkg>/<area>/__init__.py  area doc: package docstring (guidelines/design.md#the-package-docstring)
pyproject.toml                import-linter contracts (module map), `cuj` pytest marker
docs/generated/               index, decisions, glossary, cujs: generated, committed, never hand-edited
docs/design/<topic>.md        only decisions no code owns (other repos, outside services, data at rest)
.pre-commit-config.yaml       templates/pre-commit-config.yaml (owner approves the first one)
.github/workflows/docs.yml    templates/docs-workflow.yml
tests/test_generated_docs.py  fails when regenerating would change docs/generated/
docs/agents/issue-tracker.md  templates/issue-tracker.md (read by /review, /triage, /to-issues)
docs/agents/triage-labels.md  templates/triage-labels.md
.claude/skills/<repo>/SKILL.md teaches agents the repo CLI
.vscode/extensions.json       recommends bierner.markdown-mermaid
```

Not allowed: `CONTEXT.md`, `docs/adr/`, `docs/requirements/`, `backlog.md`, `.scratch/`, numbered decision logs, `docs/agents/domain.md`, a hand-kept area list.

## Phase 1 — Explore (read only)

- `git status` (must be clean), `git remote -v`. No GitHub remote → create a private repo with `gh repo create <name> --private --source . --push` (owner's standing rule).
- Inventory what exists: `CLAUDE.md`, `AGENTS.md`, `README.md`, every `*.md` under `docs/` and other doc folders, `CONTEXT.md`, `docs/adr/`, `.scratch/`, numbered logs (`design-decisions.md`, `D7`-style references in code: `grep -rn "D[0-9]\+" src`), `.claude/skills/`, `tools/`, test layout, languages (`pyproject.toml`, `package.json`, `Cargo.toml`), served pages / launch agents.
- Skip `.venv`, `node_modules`, `.claude/worktrees`, build output.
- Languages `metalm-gendocs` does not read (its "Not covered" list): ask the owner whether to add each to metalm; on yes, file a metalm issue (doc-comment convention, test framework, this repo).

## Phase 2 — Content inventory (before any edit)

- One line per heading, rule, decision, requirement, open question, and legacy decision reference: `- [ ] path:line | ≤15-word gist`.
- Open a GitHub issue "metalm compliance: content inventory" and post it (split across comments if over ~60k chars). The tree stays clean.

## Phase 3 — Grill the owner

Use `/grilling`: one question at a time, each with a recommendation. Settle only what the guidelines leave open:
1. Areas: the packages that are areas, and the import contracts between them.
2. Status of existing content: which rules are the owner's (they become `(owner)`), which are current, aspirational or stale; where two answers to one question conflict, which one survives.
2a. CUJs: the journeys each core path must have, and the e2e test that will carry each `cuj` marker.
3. Anything proposed for dropping (owner must approve each drop).
4. Languages and toolchain rows that apply (guidelines/testing.md table).
5. Core paths (money, deletion, persistence, auth, user data) → blind test-writer and mutation-testing scope.
6. Surfaces: CLI present? repo skill present? MCP justified per guidelines/coding.md?
7. Served app? → row in guidelines/operations.md table, launch agent, sandbox script.
8. Repo-specific rules found in phase 1 that conflict with metalm: keep as an exception (an `(owner)` rule in the package docstring that owns it), or conform.

## Phase 4 — Branch and restructure

- `git switch -c metalm-setup`.
- Move docs into code per guidelines/design.md#moving-a-repo-to-docs-in-code: area docs → package docstrings; module maps → import contracts; owner rulings → `(owner)` rules (only those already the owner's); requirements → `cuj` markers on e2e tests, or a `ready-for-human` issue when no test exists. Each step deletes what it replaces; meaning moves, never vanishes silently.
- `CONTEXT.md` and glossaries → `Terms:` in the owning package docstrings. `docs/adr/`, numbered logs, design docs → `(owner)` rules or code; D-number citations in code → the package name. Backlog files → GitHub issues.
- Hooks and docs: write `.pre-commit-config.yaml` and `.github/workflows/docs.yml` from templates, add the staleness test, ask the owner to approve the hook file (first time only), then `pre-commit install` (a committed `core.hooksPath` hook moves into the config as a local hook; `git config --unset core.hooksPath`). Regenerate `docs/generated/`.
- `AGENTS.md` content → `CLAUDE.md`; then `ln -s CLAUDE.md AGENTS.md`.
- Write `docs/agents/*` and `.vscode/extensions.json` from templates. Delete `docs/agents/domain.md`.
- Create the five triage labels on the GitHub repo before filing any issue (a `ready-for-human` issue fails without them): `for l in needs-triage needs-info ready-for-agent ready-for-human wontfix; do gh label create "$l" --force; done`.
- Old path cited anywhere (code comments, docs, memory) → leave a one-line pointer stub at the old path.
- Fill gaps with DRAFT stubs, never invented content: a missing section gets `TODO(owner): …`.

## Phase 5 — Prove nothing was lost

- Launch a **separate** subagent (did not do phase 4). Give it: the inventory issue, the old tree (`git show main:<path>`), the new tree. It maps every inventory line → `kept <new path:line>` | `merged into <path:line>` | `dropped (reason)`, verifying each by quoting the new text.
- Post the mapping as a comment on the inventory issue.
- Any `dropped` without the owner's approval in chat, or any unmapped line, blocks phase 7. Fix and re-run phase 5.

## Phase 6 — Conformance

### 6a Structure — report each as pass / fail / excepted, with path:
- [ ] `CLAUDE.md` contains `@~/.claude/metalm/guidelines/index.md`; `AGENTS.md` is a symlink to it or absent.
- [ ] No `CONTEXT.md`, `docs/adr/`, `.scratch/`, `docs/agents/domain.md`, numbered decision log (stubs excepted).
- [ ] No `docs/requirements/`, `backlog.md`, Changes sections or dated rulings ("Ruled YYYY-MM-DD") in docs or docstrings.
- [ ] Every area package has a docstring; import contracts exist where the ecosystem supports them and pass.
- [ ] No question has two answers: every `(owner)` rule is unique (`docs/generated/decisions.md` has no two rules on one subject).
- [ ] Every e2e test carries a `cuj` marker; every core path (money, deletion, persistence, access, user data) has a CUJ.
- [ ] `.pre-commit-config.yaml` has `no-commit-to-branch` and `metalm-gendocs`; `pre-commit install` is done in this checkout; `.github/workflows/docs.yml` exists.
- [ ] `docs/generated/` is current (the staleness test passes).
- [ ] Every setting named in docs gives its location.
- [ ] No "refusal"/"refuse"/"refuses" in docs (`grep -rniw 'refus\w*' docs CLAUDE.md`).
- [ ] `docs/agents/issue-tracker.md` says GitHub; `.vscode/extensions.json` lists the Mermaid extension.
- [ ] The GitHub repo has the five triage labels (`gh label list`: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`).
- [ ] Repo skill exists at `.claude/skills/<repo>/SKILL.md`.
- [ ] Test suite runs green (command recorded in `CLAUDE.md`).

### 6b Content — every guideline

- Take the guideline list from the table in `~/.claude/metalm/guidelines/index.md` (so a new guideline is covered automatically). For each guideline, one subagent: reads the guideline and the repo parts it governs (requirements docs, design docs, code, tests, ops scripts), and returns findings `| rule (guideline.md#section) | repo path:line | pass/fail | evidence quote |`. Sample large code bases; say what was sampled.
- Merge into one report grouped by guideline; fails first. In check mode this report is the output; in setup mode each fail is fixed or, with the owner's approval, recorded as an exception with its reason.

## Phase 7 — PR

- Commit in logical steps (move, revise, add). Push branch, open one PR. Body: summary, link to inventory issue and mapping comment, checklist results, list of owner decisions from phase 3. Never push to main.

## Boundaries

- Does not edit Matt Pocock skills or the global `~/.claude/CLAUDE.md` (install.sh owns its block there).
- Does not drop content without the owner's word in chat.
- Does not touch app data, `.env`, secrets, or running servers. A plaintext secret found in a tracked or local config file is reported to the owner, not moved or printed.
