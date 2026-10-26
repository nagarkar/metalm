"""metalm_ops: backs up every *lm repo's databases and shows one health page for all of them.

The machine-specific facts (which databases, which ports, which launch agents,
the B2 bucket) live in one gitignored `ops.toml` in the metalm checkout, filled
by hand or by an agent following the metalm skill's "Finding databases"
section. Nothing about the owner's databases, ports or paths enters git;
`ops.example.toml` shows the shape with placeholders.

Decisions:
- Backups go to two places: a nightly local copy on the internal disk and an encrypted restic snapshot in Backblaze B2. (owner)
- The B2 key id, application key and restic password live only in the login keychain (`metalm-b2-key-id`, `metalm-b2-app-key`, `metalm-restic-password`); the restic password has a second copy in the owner's password manager. (owner)
- The backup runs nightly at 03:30; local keeps the last 7 runs; B2 keeps 7 daily, 4 weekly and 12 monthly snapshots; `restic check` reads a 5% subset weekly. (owner)
- Which databases, apps and agents exist is one central gitignored file in metalm (`ops.toml`), never a manifest in each repo, so no tracked file says what databases exist. (owner)
- Health: a backup or B2 snapshot is green under 26 h, amber 26-50 h, red over 50 h or missing; a served app is green when `/health` answers 200 within 3 s, else red; a launch agent is green loaded with last exit 0, amber loaded with a nonzero exit, red not loaded; git and generated-docs rows are amber at worst. Red sends one SuperLM banner from the nightly job. (owner)
- The dashboard is a served app like the others: its loopback and tailnet ports are one row in the served-apps table in the owner's global `~/.claude/CLAUDE.md`, and `port` in ops.toml repeats the loopback one; no port is written in git. (owner)
- Every copy is taken with SQLite's online backup API and passes `PRAGMA integrity_check` before it counts; a copy that fails is deleted and the run is an error. Enforced by: tests/test_ops_backup.py::test_corrupt_copy_fails.
- A database on an unmounted volume is an error naming the volume, never a skip and never a created folder. Enforced by: tests/test_ops_backup.py::test_unmounted_volume_is_error.

Terms:
- **run**: one nightly invocation of `metalm-ops backup run`, written as one row of `runs.jsonl` whatever its outcome.
- **level**: green, amber or red: the state of one check on the dashboard.
"""
