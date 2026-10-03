---
name: metalm-setup
description: Set up a repo to metalm guidelines, adopt metalm in an existing repo with its deviations grandfathered, check conformance, or make a repo fully compliant — creates the standard layout, moves and revises docs, grills the owner on repo-specific choices, and proves nothing was lost. Use when the user says "set up a repo", "make the repo compliant with guidelines", "adopt metalm", "grandfather this repo", "check conformance with metalm" or "metalm check". Replaces /setup-matt-pocock-skills.
---

# metalm-setup

Brings one repo to the layout and rules in `~/.claude/metalm/guidelines/`. Read `index.md` there first; read the topic guideline before touching its area.

Modes:
- **setup** (default; "set up a repo", "make the repo compliant with guidelines"): phases 1–7, ends in one PR. Removes grandfathered exceptions it resolves.
- **adopt** ("adopt metalm", "grandfather this repo"): opt in now, conform later. Phases 1 and 6, then on a branch: add the import line to `CLAUDE.md` (create it, `AGENTS.md` content merged, `AGENTS.md` symlinked), and record every phase-6 failure as a row under `## Grandfathered exceptions` in `docs/design/README.md` (create from template): `| <rule> | <guideline>.md#<section> | <where in repo> | adopted <YYYY-MM-DD> |`. Moves no content. One PR. New work follows metalm.
- **check** ("metalm check", "check conformance with metalm"): phases 1 and 6. Report only; change nothing. A failure listed as a grandfathered exception reports as `excepted`, not `fail`.

## Target layout

```
CLAUDE.md                     the one loaded file: import line + repo notes (template: templates/CLAUDE.md)
AGENTS.md -> CLAUDE.md        symlink, for Cursor/Codex
docs/requirements/README.md   index of areas (templates/requirements-README.md)
docs/requirements/<area>.md   persistent requirements (templates/requirements-area.md)
docs/design/README.md         index + legacy-number table (templates/design-README.md)
docs/design/<area>.md         named design docs (templates/design-area.md)
docs/design/glossary.md       only if the repo has domain terms
docs/design/backlog.md        ratified-but-unbuilt items, each with "done when"
docs/agents/issue-tracker.md  templates/issue-tracker.md (read by /review, /triage, /to-issues)
docs/agents/triage-labels.md  templates/triage-labels.md
.claude/skills/<repo>/SKILL.md teaches agents the repo CLI
.vscode/extensions.json       recommends bierner.markdown-mermaid
```

Not allowed: `CONTEXT.md`, `docs/adr/`, `.scratch/`, numbered decision logs, `docs/agents/domain.md`.

## Phase 1 — Explore (read only)

- `git status` (must be clean), `git remote -v`. No GitHub remote → create a private repo with `gh repo create <name> --private --source . --push` (owner's standing rule).
- Inventory what exists: `CLAUDE.md`, `AGENTS.md`, `README.md`, every `*.md` under `docs/` and other doc folders, `CONTEXT.md`, `docs/adr/`, `.scratch/`, numbered logs (`design-decisions.md`, `D7`-style references in code: `grep -rn "D[0-9]\+" src`), `.claude/skills/`, `tools/`, test layout, languages (`pyproject.toml`, `package.json`, `Cargo.toml`), served pages / launch agents.
- Skip `.venv`, `node_modules`, `.claude/worktrees`, build output.

## Phase 2 — Content inventory (before any edit)

- One line per heading, rule, decision, requirement, open question, and legacy decision reference: `- [ ] path:line | ≤15-word gist`.
- Open a GitHub issue "metalm compliance: content inventory" and post it (split across comments if over ~60k chars). The tree stays clean.

## Phase 3 — Grill the owner

Use `/grilling`: one question at a time, each with a recommendation. Settle only what the guidelines leave open:
1. Areas: the list of `docs/requirements/` and `docs/design/` areas, and each area's ID prefix (`ORD`).
2. Status of existing content: which docs are current truth, which aspirational, which stale.
3. Anything proposed for dropping (owner must approve each drop).
4. Languages and toolchain rows that apply (guidelines/testing.md table).
5. Core paths (money, deletion, persistence, auth, user data) → blind test-writer and mutation-testing scope.
6. Surfaces: CLI present? repo skill present? MCP justified per guidelines/coding.md?
7. Served app? → row in guidelines/operations.md table, launch agent, sandbox script.
8. Repo-specific rules found in phase 1 that conflict with metalm: keep as a documented exception in the repo's design doc, or conform.

## Phase 4 — Branch and restructure

- `git switch -c metalm-setup`.
- Move with `git mv` to keep history. Split a numbered log into named area docs; headings keep "(was D7)"; `docs/design/README.md` gets the number → document table.
- Revise content to the guideline templates (requirements: IDs, MUST/SHOULD, checkable conditions; design: decision / Why / Rules out / Changes; Mermaid diagrams where guidelines/design.md requires one). Revising means reshaping, never deleting meaning.
- `CONTEXT.md` → `docs/design/glossary.md`. `docs/adr/NNNN-*.md` → the matching named area doc.
- `AGENTS.md` content → `CLAUDE.md`; then `ln -s CLAUDE.md AGENTS.md`.
- Write `docs/agents/*` and `.vscode/extensions.json` from templates. Delete `docs/agents/domain.md`.
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
- [ ] `docs/requirements/README.md` and `docs/design/README.md` list every file in their folder.
- [ ] Every requirement has an ID; no ID duplicated.
- [ ] Every design doc has a Status line and a `## Changes` section.
- [ ] Every setting named in docs gives its location.
- [ ] No "refusal"/"refuse"/"refuses" in docs (`grep -rniw 'refus\w*' docs CLAUDE.md`).
- [ ] `docs/agents/issue-tracker.md` says GitHub; `.vscode/extensions.json` lists the Mermaid extension.
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
