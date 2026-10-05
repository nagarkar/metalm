# Install Scripts
Scope: any script that installs, links, or configures a tool on the owner's machine (e.g. metalm `install.sh`, a repo's `schedule install` verb).

## Rules
- Idempotent. A second run with nothing changed changes nothing and says so.
- Edit shared files only inside managed marker blocks: `<!-- <tool>:begin -->` … `<!-- <tool>:end -->` (use the file's comment syntax where Markdown comments do not apply). On rerun, replace the block whole. Touch nothing outside it.
- Show the diff of every file it edits.
- Before editing an existing file, write a timestamped backup beside it: `<file>.bak.<YYYYmmdd-HHMMSS>`.
- Support `--dry-run` (print every action and diff, write nothing) and `--uninstall` (remove its blocks and links, leave everything else).
- Resolve its own location at runtime (`"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`). No hardcoded paths to the clone or the home directory.
- User scope only. No `sudo`. Install inside the user's home or the repo, never globally.
- Check prerequisites first (commands on PATH, versions, target directories). A missing required one stops the script, having changed nothing, with a message naming it and how to get it. One needed only by a later tool (e.g. `gh` for a skill) warns.
- Symlink rather than copy, so `git pull` in the clone updates the installed copy. Where a link already exists and points elsewhere, stop and report; do not overwrite.
- Never install anything that runs at login (launch agents) or a hook. Print the snippet or command and let the owner run it. Why: these execute code unattended.
- Never write secrets into any file it manages.
- End by printing what changed: each file edited, link created or removed, backup written, and anything left for the owner to do.

## Layout example (metalm)
- `install.sh` symlinks `~/.claude/metalm` → the clone and each `~/.claude/skills/<skill>` → `metalm/skills/<skill>`.
- It writes one marker-delimited block in `~/.claude/CLAUDE.md`.
- Each repo's `CLAUDE.md` carries `@~/.claude/metalm/guidelines/index.md`; the script does not edit repos.

## Tests
- Run against a temporary `HOME`: first run, second run (no change), `--dry-run` (no writes), `--uninstall` (back to the starting files byte for byte, apart from backups).
