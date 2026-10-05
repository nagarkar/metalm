# metalm

@guidelines/index.md

Source of truth for engineering rules across the owner's `*lm` repos. Changes here reach every repo on `git pull`, so keep guidelines short and edit them deliberately.

## Repo notes

- Rules marked `(owner)` are the owner's; the rest are agent-drafted (guidelines/index.md). How guidelines are written, and their line caps: `guidelines/design.md#writing-metalm-guidelines`; `tools/check-caps.sh` checks the caps.
- Test `metalm-gendocs`: `.venv/bin/pytest` (create with `python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"`). Try the hook in another repo: `pre-commit try-repo <metalm> metalm-gendocs --all-files` (sees committed files only).
- Test the installer with a throwaway config dir: `CLAUDE_CONFIG_DIR=$(mktemp -d) ./install.sh`.

## Agent skills

- Issue tracker: GitHub issues on this private repo. See `skills/metalm-setup/templates/issue-tracker.md`.
