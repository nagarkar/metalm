# Guideline authoring

Status: DRAFT — not yet ratified by the owner.

## Short, imperative, generic

- Reader is a strong model. Bullets, short imperative sentences, a "Why" clause only where non-obvious.
- Generic rules only. A product-specific rule stays in its repo's `docs/design/`; it appears here only as a one-line example.
- Hard caps (lines): `index.md` 80, `requirements.md` 160, `design.md` 160, `architecture.md` 130, `coding.md` 300, `testing.md` 200, `operations.md` 120, `install-scripts.md` 60. Over the cap → cut or split, never raise silently.

**Why:** long rule files are followed less, and `index.md` is paid for in every session. Cached input is cheap; attention is not.

**Rules out:** essays, motivation sections, duplicated rules across files.

## Token economy order

1. Fewer turns and less wasted work.
2. Fewer output tokens (output costs several times input).
3. Less uncached input.
4. Cached input.

**Why:** in long agent loops context is re-sent every turn, but per token output dominates; waste of whole turns dominates both.

## Ratification

- Every guideline starts `Status: DRAFT` until the owner ratifies it; ratification is a dated `## Changes` line in this file and the status flips.
- A change to a ratified guideline: edit it in place and add a dated line under this file's `## Changes` naming the guideline and the change. Guidelines carry no Changes section of their own, to stay short.

## Vocabulary

- Never "refusal", "refuse", "refuses". Use "will not", "leaves alone", "boundaries", "declines".
- Every setting named gives its location, or "proposed, does not exist yet" with the file it would live in.

## Changes

- 2026-10-03 Created.
- 2026-10-03 Owner database guidelines merged into `architecture.md` (environment, schema), `coding.md` (migrations, database safety) and `index.md` (destructive-SQL rule). Reconciled: DB lives in the workspace, not `./data/`; embedded SQLite keeps in-code additive migrations, server Postgres uses timestamped UP/DOWN files.
- 2026-10-03 Added `coding.md#data-objects` (frozen dataclasses; validate at the edge; Pydantic only at heavy-parsing edges) and a data-objects row in `testing.md#toolchain`, codifying existing repo practice.
