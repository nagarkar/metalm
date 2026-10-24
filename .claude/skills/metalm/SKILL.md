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

## Merging

- Merge only on the owner's word in chat: nearly every metalm PR changes a guideline, and a merge reaches every repo.
