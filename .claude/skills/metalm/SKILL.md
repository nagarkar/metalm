---
name: metalm
description: House rules for working in the metalm repo itself, the source of the owner's engineering guidelines. Use when editing a guideline, the metalm-setup skill, the metalm-gendocs hook, install.sh, the SuperLM notifier or brand icons.
---

# metalm

A change here reaches every repo that imports `guidelines/index.md` on its next `git pull`. How guidelines are written, and their line caps: `guidelines/design.md#writing-metalm-guidelines`.

## Tools

- `metalm-gendocs [--dry-run]`: regenerates `docs/generated/`; the pre-commit hook other repos pin. Try it in another repo: `pre-commit try-repo <metalm checkout> metalm-gendocs --all-files` (sees committed files only).
- `./install.sh [--dry-run|--uninstall]`: links metalm and its skills into `~/.claude`, writes the managed block in `~/.claude/CLAUDE.md`, builds the notifier. Tested against a throwaway home in `tests/test_install.py`; by hand: `CLAUDE_CONFIG_DIR=$(mktemp -d) ./install.sh`.
- `tools/check-caps.sh`: fails when a guideline is over its cap (the "Hard caps" line in `guidelines/design.md`). A pre-commit hook.
- `superlm-notify --repo <repo> [--title T] --body <message>`: one macOS banner under the SuperLM name.
- `tools/notifier/make_brand.py --app <repo>`: an app's icons and wordmarks into `brand/<repo>/` (needs the `brand` extra: Pillow).
- `docs/repos.md`: which repos import metalm and how each last checked out; `metalm-setup` phase 8 writes it.

## Ops: backups, auto-improve and the dashboard

`metalm-ops` (package `metalm_ops`) backs up every listed database and serves one health page for all repos. What it watches is `ops.toml` in the main checkout (read as `~/.claude/metalm/ops.toml`), gitignored; `ops.example.toml` shows the shape. The dashboard's ports are in the served-apps table in `~/.claude/CLAUDE.md`.

- `metalm-ops backup run [--dry-run]`: verified SQLite copy of every database into the local backup folder; keeps the last 7 runs.
- `metalm-ops backup offsite [--dry-run] [--check]`: restic to B2 (keys from the keychain), retention 7 daily / 4 weekly / 12 monthly, a 5% `restic check` weekly.
- `metalm-ops backup init`: creates the restic repository in the bucket, once.
- `metalm-ops status [--alert]`: every check per repo; writes `status.json`; `--alert` sends one SuperLM banner when any check is red.
- `metalm-ops serve [--port N]`: the dashboard; its launch agent runs it.
- `metalm-ops deploy [--dry-run]`: after a metalm-ops PR merges, pulls main into the main checkout (only a clean checkout on `main`), restarts the dashboard through its agent, waits for /health and collects once.
- `metalm-ops discover`: read-only list of SQLite files in the places below, `NEW` where ops.toml does not list one yet.
- `metalm-ops doctor`: setup steps no code installs, each with its fix; the nightly job runs it first.
- `metalm-ops schedule print backup|serve|improve`: the launch agent plist to install; stderr prints the install command for the owner.
- `metalm-ops improve run [--repo NAME] [--lens NAME] [--dry-run | --no-pr]`: one Codex proposal, an independent Claude verifier trying to disprove its claim, and two independent Claude reviews per opted-in repo; Python merges only after the verifier confirms, both reviewers approve and CI is green. `--dry-run` previews skips, caps and usage without models or writes; `--no-pr` runs the proposer and gates, then discards without a commit or PR. Review calls can incur cost.
- `metalm-ops improve status [--repo NAME] [--json]`: demand `D`, activity target `T`, runs `today`, overdue lenses, brake entry and the last ten runs with PR links and reasons. At session start use `--repo NAME --json`; a repo not opted in returns `{"opted_in": false}`. Report a brake immediately, or seven days without a PR, following `guidelines/auto-improve.md`.
- `metalm-ops improve labels [--repo NAME] [--dry-run]`: creates or updates the six system labels (including `auto-improve-brake`) in metalm and opted-in repos before the first live run.
- `metalm-ops prompts [--json]`: lists the versioned proposer and reviewer prompts, schemas and hashes.
- `scripts/improve-slot.sh`: the slot job (doctor, improve run); one failure-only banner, logs retained 30 days. It holds an already-awake Mac awake while running, never schedules a wake.

Lenses rotate by oldest completed run, never-run first: readability, documentation, duplication, tests, backend-robustness, frontend-robustness, ui, performance and drift. Frontend lenses require tracked frontend files; optional `[[improve.repo]] lenses` limits them. `--lens NAME` forces an applicable lens and requires `--repo`. Performance requires before/after measurements; evidence quotes are checked against the base commit. This replaces codeteamlm, which is retired after this merges (the owner handles archiving and target migration).

Slots default to 09:10, 13:10, 17:10 and 21:10; configure 1–8 increasing `HH:MM` times in `[improve] slots`. A slot more than `max_lateness_min` (default 60) late is skipped. Demand sums eligible changed lines over seven days with `decay = [1, 1, .75, .5, .5, .25, .25]`; `lines_per_run = 400` sets the activity target, capped at the number of slots. Overdue applicable lenses get a weekly floor; oldest lenses run first. `--repo` ignores cadence for a manual run. `--dry-run` shows demand, target, today, overdue, due reason and lens. Doctor checks installed times against config; after changing slots, reinstall the printed plist.

Targets (nagarkar/metalm#97): before Codex is called, `metalm_ops.improve.signals` measures the repo at origin/main with no model: churn (files changed in 14 days), size (files > 400 lines, functions > 60), complexity, security and missing docstrings (metalm's own ruff, `--isolated`), coupling (import fan-in/out and cycles from `ast`), duplication (12+ matching normalised lines), untested modules (no test imports them), slow tests (junit timings from the last green gate run). The lens picks its best finding: measured findings in recently changed files first; a finding with a PR in 30 days or a proposer skip in 14 is not retried. No finding: the run skips without a Codex call. Codex answers in a single request (`propose_v5`, `mode: oneshot`, read-only sandbox, no tools): it gets the finding and windows of the target files (the finding, any other copy, up to 2 tests) and returns exact search/replace `edits`, which Python applies, formats with the repo's ruff, then gates; about 30K tokens per proposal, against ~380K when Codex explored. The repo's `.env` is linked into the worktree only after the proposal, so the model never sees it. A proposal whose edits do not compile or break the tests gets one repair round: the worktree is reset and Codex sees its edits and the error once more. Generated docs are refreshed with the repo's `metalm-gendocs` before the tests. Reviewers (`review_*_v3`) also get the changed code around each hunk. After the gates, the finding is re-measured: it must be gone or smaller (`finding not improved` otherwise). Design signals (feed the `modularity` lens, which may change up to 6 files / 300 lines): complexity, oversized files and functions, import coupling and cycles, classes with > 20 methods or > 300 lines, long parameter lists (PLR0913), and encapsulation breaks (another module's `_private` names, module state changed through `global`). Reuse: exact copies and renamed copies (names and literals ignored). Performance: DB/network/subprocess/sleep calls inside loops, ruff PERF101/102/203, and slow tests (`improve signals --timings` runs each suite once to record per-test times; every green gate run refreshes them). Each run measures first, then picks the lens: an overdue lens (weekly floor) whose best finding is worth most (`signals.WEIGHT` × distance over threshold, ×1.5 in recently changed files); overdue lenses with nothing measured are recorded done without a Codex call. Failed runs never count as a lens done. `metalm-ops improve signals [--repo X] [--json] [--timings]` prints the board; `improve status` shows each run's finding and proposer tokens. Per-repo `[[improve.repo]] thresholds = {size_lines = 600}` overrides `signals.THRESHOLDS`.

Outcomes: a proposer that searched and found nothing is `skipped` ("proposer found nothing: …") and counts its lens as done; a proposer that could not run or returned an invalid proposal is `failed` and counts toward the stall brake. When Codex reports its subscription usage limit, the run records `failed` with a `system: Codex usage limit` reason, writes the reset time to `<state_dir>/improve/codex-limit-until`, and every later run skips with `system: Codex usage limit until <time>` until then; `system:` rows never count toward a brake. `improve status --json` shows `codex_limit_until`. Delete the file to retry sooner.

Pause all runs: create `<state_dir>/improve/PAUSE`, or set `[improve] enabled = false` in the global `~/.claude/metalm/ops.toml` (default true when the table exists; absent means off).
A repo brakes after three judge-rejected PRs or five qualifying runs without a PR. The system records `improve/braked.toml` through a visible PR in metalm, merges it and alerts. On the owner’s word, `metalm-ops improve unbrake --repo NAME --why "<owner’s words>" [--dry-run]` opens the removal PR; it never merges it. Diagnose the rejected PRs or failed runs before resuming.
Run artifacts are in `<state_dir>/improve/runs/<run_id>/<repo>/`; the run and call ledger is `<state_dir>/improve/runs.sqlite`. Global `state_dir` defaults to `~/.local/state/metalm/ops` in `~/.claude/metalm/ops.toml`.

- `metalm-ops help [verb]`, `metalm-ops completion`.
- `scripts/nightly-backup.sh`: the 03:30 job (doctor, backup run, backup offsite, status --alert); silent when clean.

Restore a database: stop its app's server (ask the owner to unload its agent), copy `<local_dir>/<stamp>/<repo>/<name>.sqlite` over the file, or for an older one `restic restore latest --target /tmp/restore` (or a snapshot id from `restic snapshots`) with the keychain values exported in your own terminal, then restart the agent.

### Finding databases

`ops.toml` is filled by hand or by an agent asked to look; `metalm-ops discover` searches the places below and marks what is missing. Check each repo in `docs/repos.md`, and list every live SQLite file as one `[[database]]` row:
- The repo's `.env` keys ending in `_WORKSPACE`, `_DB` or `_DIR`: read only those keys, never print other values. A `_DB` key names the file; a `_WORKSPACE` key names a folder to search.
- The repo's own skill and `doctor` verb first: they name the workspace and its store.
- `~/.<repo>/` and `~/.<cli>/`: the CLI's name can differ from the repo's (authorllm's CLI is `authorlm`, so `~/.authorlm/authorlm.db`), and folders in the home folder named after the app.
- `<the external drive>/<repo>/` (the drive the `.env` pointers name).
- `config.toml` keys that name a path.
Search with `find <folder> -maxdepth 4 \( -name '*.sqlite' -o -name '*.db' -o -name '*.sqlite3' \)`. Skip `backups/` folders, files named for a migration (`*-before-*`, `*backup*`), 0-byte files and other apps' stores (Photos). A database several repos share is listed once, under its schema owner (the transcript store under corpuslm). State that is not a local SQLite file (an Artifact database on claude.ai, media folders, downloadable caches such as a WordNet `wn.db`) is outside `backup run`; name it to the owner instead of listing it. Show the owner the rows before writing them.

## Merging

- Merge only on the owner's word in chat: nearly every metalm PR changes a guideline, and a merge reaches every repo.
