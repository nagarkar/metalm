# metalm

@~/.claude/metalm/guidelines/index.md

Source of truth for engineering rules across the owner's `*lm` repos: the guidelines, the `metalm-setup` skill, the `metalm-gendocs` pre-commit hook, the SuperLM notifier and the app icons (`brand/`). Every repo that imports `guidelines/index.md` reads it on its next `git pull`, so guidelines stay short and change deliberately. Depends on nothing but `git`, `gh` and the Xcode command line tools.

## Commands

- Install: `python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/pre-commit install`; for the owner's machine: `./install.sh` (`--dry-run`, `--uninstall`).
- Test: `.venv/bin/pytest`
- Lint: `.venv/bin/ruff check . && .venv/bin/ruff format --check . && tools/check-caps.sh`
- CLI: `metalm-gendocs`, `install.sh`, `tools/check-caps.sh`, `superlm-notify`, `tools/notifier/make_brand.py`; see `.claude/skills/metalm/SKILL.md`.

## Exceptions to metalm

- The notifier keeps its bundle ID `com.nagarkar.superlm.notifier` (user-specific details stay out of git, operations.md#served-apps): `(owner)` rule in `tools/notifier/build.sh`.

## Agent skills

- Issue tracker: GitHub issues on `nagarkar/metalm`. See `docs/agents/issue-tracker.md`.
- Triage labels: defaults. See `docs/agents/triage-labels.md`.
