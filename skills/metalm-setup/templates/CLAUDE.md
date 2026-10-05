# <repo>

@~/.claude/metalm/guidelines/index.md

<One paragraph: what this repo is.>

## Commands

- Test: `<command>`
- Lint: `<command>`
- CLI: `<launcher> <verb>`; see `.claude/skills/<repo>/SKILL.md`.
- Docs: `docs/generated/index.md` (areas, `(owner)` decisions, glossary, CUJs); generated, never edited.
- Hooks: `pre-commit install` once per checkout.

## Repo notes

- Exceptions to metalm: each is an `(owner)` rule in the package docstring (or `docs/design/`) that decides it.

## Agent skills

- Issue tracker: GitHub issues on this private repo. See `docs/agents/issue-tracker.md`.
- Triage labels: defaults. See `docs/agents/triage-labels.md`.
