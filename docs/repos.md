# Repos that import metalm

One row per repo. `metalm-setup` updates this file through a PR on metalm every time it sets up, adopts or checks a repo, whether the attempt passed or not (skills/metalm-setup/SKILL.md, phase 8). The audit mode reads it to find repos checked before the guidelines last changed.

Status: `compliant` (all checks pass), `adopted` (opted in, with exceptions listed in the repo), `attempted` (a run ended with open failures), `unchecked` (imports metalm; no run recorded here).

| repo | GitHub | status | checked against metalm commit | date | repo PR | open failures or exceptions |
|---|---|---|---|---|---|---|
| authorllm | nagarkar/authorllm | adopted | unrecorded | unrecorded | | `docs/design/exceptions.md` |
| beelm | nagarkar/beelm | attempted | 58a5033 | 2026-10-09 | | fails: stale test plan, corpus/review/cleanup lack CUJs, env switches and config validation, no served-app row/serve agent/doctor checks, schedule install not idempotent, docstring status lines; history holds personal paths |
| corpuslm | nagarkar/corpuslm | compliant | unrecorded | 2026-10-04 | | none documented |
| gamelm | nagarkar/gamelm | unchecked | | | | |
| marketlm | nagarkar/marketlm | unchecked | | | | |
| tradelm | nagarkar/tradelm | unchecked | | | | |
| ytlm | nagarkar/ytlm | adopted | unrecorded | 2026-10-03 | | three grandfathered, listed in `docs/design/README.md`; items awaiting the owner in nagarkar/ytlm#58 |
