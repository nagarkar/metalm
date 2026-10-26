"""Fix prompts: the brief the dashboard copies for a red or amber row, to paste into a new Claude Code session.

Each brief names the repo, says what the check saw, points at the metalm rule
that governs the fix, and says what the session must leave to the owner. It
never asks a session to merge, push to main, install a launch agent or switch
a main checkout's branch.
"""

from __future__ import annotations

BACKUPS = "metalm"  # the Backups card's checks are fixed in metalm


def fix_prompt(repo: str, check: str, detail: str) -> str:
    """The brief for one failing check on one card ("Backups" for the backup jobs)."""
    target = BACKUPS if repo == "Backups" else repo
    seen = f"The ops dashboard shows `{check}`: {detail}."
    if check.startswith("backup "):
        what = (
            f"The backup of {target}'s `{check.removeprefix('backup ')}` database is late or missing. Run `metalm-ops doctor`, read the newest log "
            "in ~/.local/state/metalm/ops/logs, and find why the nightly job did not copy it. Fix the cause in metalm or in ops.toml."
        )
        target = BACKUPS
    elif check in {"last local run", "B2 snapshot", "restic check"}:
        what = (
            "Read the newest log in ~/.local/state/metalm/ops/logs and `runs.jsonl`, run `metalm-ops doctor`, and fix the cause. "
            "Never print a keychain value; a restore or `restic forget` needs my word first."
        )
    elif check.startswith("agent "):
        what = (
            f"Launch agent `{check.removeprefix('agent ')}` is unhealthy. Read its log and plist and find why it exits or is not loaded. "
            "Installing or loading an agent is my step: print the command (metalm operations.md#launch-agents)."
        )
    elif check.startswith("app "):
        what = (
            "Its served app does not answer /health. Find why (its launch agent, its log, the port in the served-apps table of ~/.claude/CLAUDE.md). "
            "Restart only with `launchctl kickstart -k`; never start a server with nohup (metalm operations.md)."
        )
    elif check == "main checkout on main":
        what = (
            "Its main checkout is not on main. Find which session or PR owns that branch and check its work is committed and pushed. "
            "Tell me before switching the checkout to main, and never switch it while its server runs on that branch."
        )
    elif check == "unmerged branches":
        what = (
            "List its local branches not merged into main, each with its PR and last commit, and say which look safe to delete. Delete nothing without my word."
        )
    elif check == "open PRs":
        what = "Go through its PRs open more than 7 days and report what each one waits on. Merge nothing."
    elif check == "generated docs":
        what = "Its docs/generated is stale. Run metalm-gendocs in a worktree and open a PR with the result."
    elif check == "metalm row":
        what = "Run the metalm-setup skill's conformance check on it and update its row in metalm's docs/repos.md through a PR."
    else:
        what = "Find why and propose the fix."
    return f"In {target}: {seen} {what} Work in a worktree, never on the main checkout; open a PR and leave merging to me."
