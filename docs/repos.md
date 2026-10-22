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
| marketlm | nagarkar/marketlm | unchecked | | | | |
| tradelm | nagarkar/tradelm | unchecked | | | | |
| ytlm | nagarkar/ytlm | adopted | unrecorded | 2026-10-03 | | three grandfathered, listed in `docs/design/README.md`; items awaiting the owner in nagarkar/ytlm#58 |
