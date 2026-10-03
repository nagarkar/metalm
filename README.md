# metalm

Engineering rules for the `*lm` repos, plus the skill that brings a repo into line.

| Path | What |
|---|---|
| `guidelines/index.md` | Always-loaded rules; every repo imports it |
| `guidelines/requirements.md` | Where and how to write requirements; issues vs markdown |
| `guidelines/design.md` | How to document and ratify a design; diagrams (Mermaid) |
| `guidelines/architecture.md` | What a good design looks like: principles, OOAD patterns, actors/HSMs, databases |
| `guidelines/coding.md` | Code shape, config vs state, agentic practice, token economy, CLI/skill/MCP |
| `guidelines/testing.md` | Testing for autonomous agents; per-language toolchain |
| `guidelines/operations.md` | Served apps, launch agents, Tailscale, sandboxes |
| `guidelines/install-scripts.md` | How install scripts behave |
| `examples/` | Tested reference code cited by guidelines |
| `skills/metalm-setup/` | "Set up a repo" / "make the repo compliant with guidelines" |
| `docs/` | metalm's own requirements and design |

## Install

```bash
./install.sh --dry-run
./install.sh
```

It symlinks `~/.claude/metalm` and `~/.claude/skills/metalm-setup` to this clone and writes a marked block in `~/.claude/CLAUDE.md`. Update with `git pull`. Remove with `./install.sh --uninstall`.

A repo opts in by adding this line to its `CLAUDE.md` (`metalm-setup` does it):

```
@~/.claude/metalm/guidelines/index.md
```
