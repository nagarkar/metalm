# Auto-improve verification

## Propose and merge one justified improvement

Offline fixtures create local repositories and bare origins under pytest's temporary directory. Scripted Codex, Claude and GitHub responses drive the real worktree lifecycle, gates, commits, run ledger and checkout update. The suite checks clean and dirty checkouts, interruption cleanup, caps, labels, PR attribution and independent reviewer inputs.

## Choose a lens and verify its claim

Versioned lens missions rotate by oldest completed run. Tests cover never-run ties, old category rows, skipped runs, configured subsets and tracked frontend applicability. Quotes must match exact base-commit line ranges, allowing only whitespace normalization inside lines; malformed, misplaced, edited, Unicode-separated and empty-file evidence is rejected. Performance requires a before/after measurement; the tests lens cannot edit production code.

A confirmed Claude verifier proceeds to both reviewers; refuted, uncertain or malformed answers close without further model calls. Invalid counter-quotes downgrade a refutation. The verifier receives full base files and no safety reasoning. All three calls share the review cost cap. Merge behavior follows lens metadata.

| Journey | Coverage |
|---|---|
| Preview without models or writes; rehearse without PR | automated |
| Valid claim through verifier/reviewers to merge | automated |
| Bad quote, measurement, verifier or review prevents merge | automated |
| Status, strict config, completion and doctor | automated |
| Real provider quality or live target deployment | intentionally untested; no real run authorized |

2026-11-26: baseline 383 tests; lens/verifier suite 438 tests. Run `LC_ALL=C LANG=C PYTHONPATH=$PWD/src .venv/bin/pytest -q`, plus Ruff and `tools/check-caps.sh`. Every external process is stubbed or confined to local test repositories. No model spend is required. The owner installs schedules and configures target repositories after merge.
