# Repos that import metalm

One row per repo. `metalm-setup` updates this file through a PR on metalm every time it sets up, adopts or checks a repo, whether the attempt passed or not (skills/metalm-setup/SKILL.md, phase 8). The audit mode reads it to find repos checked before the guidelines last changed.

Status: `compliant` (all checks pass), `adopted` (opted in, with exceptions listed in the repo), `attempted` (a run ended with open failures), `unchecked` (imports metalm; no run recorded here).

| repo | GitHub | status | checked against metalm commit | date | repo PR | open failures or exceptions |
|---|---|---|---|---|---|---|
| authorllm | nagarkar/authorllm | adopted | unrecorded | unrecorded | | `docs/design/exceptions.md` |
| beelm | nagarkar/beelm | unchecked | | | | |
| computerlm | nagarkar/computerlm | compliant | 50cf31a94fb5ff626343f432ae94c2b299d07dce | 2026-10-21 | [nagarkar/computerlm#1](https://github.com/nagarkar/computerlm/pull/1) | setup PR open; brand row in this PR (on top of #42); no exceptions |
| corpuslm | nagarkar/corpuslm | compliant | unrecorded | 2026-10-04 | | none documented |
| gamelm | nagarkar/gamelm | unchecked | | | | |
| llmlm | nagarkar/llmlm | unchecked | | | | imports metalm via its CLAUDE.md; lists no exceptions; no metalm-setup run recorded (nagarkar/metalm#47) |
| publishinglm | nagarkar/publishinglm | attempted | ab00579c7358a7cce9e69df9a87a6a2face5ba08 | 2026-10-21 | [nagarkar/publishinglm#2](https://github.com/nagarkar/publishinglm/pull/2) | setup PR open: pre-commit hook file awaits the owner's first approval; launch agent and tailscale serve await the owner; brand in nagarkar/metalm#43; phase-3 choices taken as defaults, sent to the owner |
| mailerlm | nagarkar/mailerlm | attempted | 58a5033cda569496ae50b0c3a3f3c59ae77b7d09 | 2026-10-10 | [nagarkar/mailerlm#4](https://github.com/nagarkar/mailerlm/pull/4) | setup PR open: pre-commit hook file awaits owner approval; no CUJ tests yet (nagarkar/mailerlm#2) |
| supplylm | nagarkar/supplylm | adopted | f434bf50988e20e361624820740cc8f723f98b7e | 2026-10-16 | [nagarkar/supplylm#44](https://github.com/nagarkar/supplylm/pull/44) (merged) | structure checks pass; content checklists open in nagarkar/supplylm#37–#42; exception in CLAUDE.md: Alembic migrations |
| marketlm | nagarkar/marketlm | unchecked | | | | |
| metalm | nagarkar/metalm | adopted | a09d46afdb3fa3b317e723c1965c0cfafdea9103 | 2026-10-23 | [nagarkar/metalm#52](https://github.com/nagarkar/metalm/pull/52) (merged), [nagarkar/metalm#56](https://github.com/nagarkar/metalm/pull/56) | all checks pass once #56 merges; exception: notifier bundle ID (`(owner)` rule in tools/notifier/build.sh) |
| peoplelm | nagarkar/peoplelm | compliant | 833ce974a2a96a231e41082aef174bdba403e310 | 2026-10-25 | [nagarkar/peoplelm#1](https://github.com/nagarkar/peoplelm/pull/1), [#10](https://github.com/nagarkar/peoplelm/pull/10), [#11](https://github.com/nagarkar/peoplelm/pull/11) | all structure and content checks pass; one exception: undoing a merge deletes rather than writing forward (`(owner)` rule in src/peoplelm/store.py) |
| tradelm | nagarkar/tradelm | unchecked | | | | |
| ytlm | nagarkar/ytlm | adopted | unrecorded | 2026-10-03 | | three grandfathered, listed in `docs/design/README.md`; items awaiting the owner in nagarkar/ytlm#58 |
