# metalm-setup skill

Status: DRAFT — not yet ratified by the owner.

Requirements: [../requirements/metalm.md](../requirements/metalm.md) (MLM-8 – MLM-12). Procedure: [../../skills/metalm-setup/SKILL.md](../../skills/metalm-setup/SKILL.md).

## Phases

```mermaid
flowchart LR
  E[1 Explore] --> I[2 Inventory issue] --> G[3 Grill owner] --> R[4 Branch + restructure] --> V[5 Independent mapping]
  V -->|unmapped or unapproved drop| R
  V --> C[6 Checklist] --> P[7 One PR]
```

- `check` mode runs 1 and 6 only and changes nothing.
- `adopt` mode (grandfathering) runs 1 and 6, adds the import line, and records every failure as a dated row under `## Grandfathered exceptions` in the repo's `docs/design/README.md`; it moves no content. Check reports those rows as `excepted`.
- Phase 6 covers structure (6a) and content (6b): one subagent per guideline listed in `guidelines/index.md`, so adding a guideline extends every check.

**Why:** inventory before edits makes loss detectable; a separate mapper cannot excuse its own rewrite.

**Rules out:** pushing to main; dropping content without the owner's word; inventories committed to the tree.

## Nothing-lost proof

- Inventory = one line per heading, rule, decision, requirement, open question, legacy decision reference, with `path:line`. Posted to a GitHub issue before any edit.
- After restructuring, a separate subagent maps every line to `kept` / `merged` / `dropped (reason)`, quoting the new text. Unmapped lines and unapproved drops block the PR.
- Old paths cited anywhere get pointer stubs.

## Handoff from Matt Pocock's setup skill

| Area | `setup-matt-pocock-skills` | metalm |
|---|---|---|
| Issue tracker | asks GitHub / GitLab / `.scratch/` / other | fixed: GitHub, private repo |
| Triage labels | writes `docs/agents/triage-labels.md` | same file, defaults |
| Domain docs | `CONTEXT.md` + `docs/adr/` | `docs/design/` named docs, `docs/design/glossary.md` |
| Agent file | edits `CLAUDE.md` or `AGENTS.md` | `CLAUDE.md` always; `AGENTS.md` symlink to it |
| Invocation | user-only (`disable-model-invocation`) | `metalm-setup`, model- or user-invoked |

- `metalm-setup` writes the two `docs/agents/` files itself from templates adapted from Matt's; it does not call his skill.
- `setup-matt-pocock-skills` is deprecated as of 2026-10-03: stays installed (upstream reinstall restores it) but nothing points to it.
- Process skills stay. `guidelines/index.md` maps their `CONTEXT.md` → `docs/design/glossary.md` and ADR → named design doc; `check` mode catches files a skill created anyway.
- A process skill is deprecated only if it keeps fighting the layout after the mapping; evidence = repeated `check` failures.

**Why:** two setup skills writing the same files conflict; the mapping lets the process skills work unedited.

**Rules out:** editing Matt's skills (overwritten on reinstall); keeping `docs/agents/domain.md` (only Matt's setup skill read it).

## Changes

- 2026-10-03 Created.
- 2026-10-03 Added adopt mode and per-guideline content conformance (owner question on grandfathering and architecture.md coverage).
