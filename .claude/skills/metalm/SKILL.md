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

## Ops: backups and the dashboard

`metalm-ops` (package `metalm_ops`) backs up every listed database and serves one health page for all repos. What it watches is `ops.toml` in the main checkout (read as `~/.claude/metalm/ops.toml`), gitignored; `ops.example.toml` shows the shape. The dashboard's ports are in the served-apps table in `~/.claude/CLAUDE.md`.

- `metalm-ops backup run [--dry-run]`: verified SQLite copy of every database into the local backup folder; keeps the last 7 runs.
- `metalm-ops backup offsite [--dry-run] [--check]`: restic to B2 (keys from the keychain), retention 7 daily / 4 weekly / 12 monthly, a 5% `restic check` weekly.
- `metalm-ops backup init`: creates the restic repository in the bucket, once.
- `metalm-ops status [--alert]`: every check per repo; writes `status.json`; `--alert` sends one SuperLM banner when any check is red.
- `metalm-ops serve [--port N]`: the dashboard; its launch agent runs it.
- `metalm-ops doctor`: setup steps no code installs, each with its fix; the nightly job runs it first.
- `metalm-ops schedule print backup|serve`: the launch agent plist to install; stderr prints the install command for the owner.
- `metalm-ops help [verb]`, `metalm-ops completion`.
- `scripts/nightly-backup.sh`: the 03:30 job (doctor, backup run, backup offsite, status --alert); silent when clean.

Restore a database: stop its app's server (ask the owner to unload its agent), copy `<local_dir>/<stamp>/<repo>/<name>.sqlite` over the file, or for an older one `restic restore latest --target /tmp/restore` (or a snapshot id from `restic snapshots`) with the keychain values exported in your own terminal, then restart the agent.

### Finding databases

`ops.toml` is filled by hand or by an agent asked to look. Check each repo in `docs/repos.md`, and list every live SQLite file as one `[[database]]` row:
- The repo's `.env` keys ending in `_WORKSPACE`, `_DB` or `_DIR`: read only those keys, never print other values. A `_DB` key names the file; a `_WORKSPACE` key names a folder to search.
- `~/.<repo>/` (e.g. `~/.<app>/<app>.sqlite`), and folders in the home folder named after the app.
- `<the external drive>/<repo>/` (the drive the `.env` pointers name).
- `config.toml` keys that name a path.
Search with `find <folder> -maxdepth 4 \( -name '*.sqlite' -o -name '*.db' -o -name '*.sqlite3' \)`. Skip `backups/` folders, files named for a migration (`*-before-*`, `*backup*`), 0-byte files and other apps' stores (Photos). A database several repos share is listed once, under its schema owner (the transcript store under corpuslm). Show the owner the rows before writing them.

## Merging

- Merge only on the owner's word in chat: nearly every metalm PR changes a guideline, and a merge reaches every repo.
