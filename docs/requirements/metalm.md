# metalm requirements

Status: DRAFT — not yet ratified by the owner.

## Purpose

One place that says how every `*lm` repo handles requirements, design, code, tests and operations, plus a skill that brings a repo into line.

## Requirements

- **MLM-1** metalm MUST provide a requirements guideline: where and how to write requirements, when to use GitHub issues vs markdown (transient vs persistent, partial vs full view), storage under `docs/requirements/`, readability rules. → `guidelines/requirements.md`
- **MLM-2** metalm MUST provide a design guideline: documentation practice, diagramming options (flowcharts, state diagrams with nested states, sequence diagrams, system block diagrams), readability, storage under `docs/design/`; plus architecture principles, OOAD patterns, actors/HSMs and database guidance. → `guidelines/design.md`, `guidelines/architecture.md`
- **MLM-3** metalm MUST provide a coding guideline mixing OOAD, design patterns and agentic practice: context optimization, token cost, when to build an MCP server vs a CLI vs a skill, periodic in-session scanning of one-off scripts for reuse. → `guidelines/coding.md`
- **MLM-4** metalm MUST provide a testing guideline protecting autonomous work from hallucination, dead tests, tests that endorse bad behavior and the wrong kind of test, plus standard practice and per-language tools for Python, Node.js and Rust. → `guidelines/testing.md`
- **MLM-5** metalm MUST provide an install-scripts guideline. → `guidelines/install-scripts.md`
- **MLM-6** metalm MUST be the single source of truth: repos reference it and hold no copy or digest. → `docs/design/distribution.md`
- **MLM-7** `install.sh` MUST be idempotent, user-scoped, support `--dry-run` and `--uninstall`, and edit only its marked block in `~/.claude/CLAUDE.md`. → `install.sh`
- **MLM-8** `metalm-setup` MUST run when the owner says "set up a repo" or "make the repo compliant with guidelines". → `skills/metalm-setup/SKILL.md`
- **MLM-9** `metalm-setup` MUST create the standard structure, move existing content into it, revise content to the guidelines, and fill gaps with marked owner TODOs.
- **MLM-10** `metalm-setup` MUST grill the owner (`/grilling`) on repo-specific choices before restructuring.
- **MLM-11** `metalm-setup` MUST prove nothing was lost: an inventory before edits and an independent mapping after; unmapped lines or unapproved drops block the PR.
- **MLM-12** `metalm-setup` MUST replace `setup-matt-pocock-skills` without conflicting with the Matt Pocock process skills.
- **MLM-13** The first cut of MLM-1 – MLM-4 MUST consolidate every rule found in the existing `*lm` repos and the global `~/.claude/CLAUDE.md`, with each rule mapped to its new home in a GitHub issue.
- **MLM-14** Guidelines MUST be terse: bullets and short sentences, within the caps in `docs/design/guideline-authoring.md`.
- **MLM-15** `metalm-setup` MUST support adopting metalm in an existing repo without restructuring, recording each deviation as a dated grandfathered exception; check mode reports those as excepted.
- **MLM-16** Conformance checks MUST cover the content rules of every guideline listed in `guidelines/index.md`, not only structure.

## Boundaries

- Leaves alone: product-specific rules (they stay in each repo's `docs/design/`); Matt Pocock skill files; cloud sessions (see `docs/design/distribution.md`).

## Done when

- `./install.sh` on a fresh `CLAUDE_CONFIG_DIR` links metalm and the skill and writes the block; a second run changes nothing.
- The consolidation issue maps every scanned rule.
- `metalm-setup` has run on one repo and its PR passes the phase-6 checklist.

## Changes

- 2026-10-03 Created from the owner's request and grilling session.
