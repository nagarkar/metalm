"""Fix prompts copied from the dashboard.

Source: the owner's request of 2026-10-25; the boundaries come from
operations.md (launch agents are the owner's, no nohup), coding.md (main
checkout stays on main, work in worktrees) and the metalm skill (merge only on
the owner's word).
"""

from __future__ import annotations

import pytest

from metalm_ops.prompts import fix_prompt

CASES = [
    ("gamelm", "app :8778 /health", "port 8778: no answer in 3 s", "In gamelm:", "never start a server with nohup"),
    ("peoplelm", "agent com.example.peoplelm.serve", "loaded, not running, last exit -15", "In peoplelm:", "Installing or loading an agent is my step"),
    ("ytlm", "main checkout on main", "on music-identify: commit or push it, then git switch main", "In ytlm:", "Tell me before switching"),
    ("alm", "unmerged branches", "3", "In alm:", "Delete nothing without my word"),
    ("alm", "open PRs", "4 open, 2 over 7 days", "In alm:", "Merge nothing"),
    ("alm", "generated docs", "stale: docs/generated/index.md", "In alm:", "metalm-gendocs"),
    ("alm", "metalm row", "unchecked", "In alm:", "metalm-setup"),
    ("peoplelm", "backup people", "never", "In metalm:", "ops.toml"),
    ("Backups", "B2 snapshot", "51 h ago", "In metalm:", "Never print a keychain value"),
]


@pytest.mark.parametrize("repo, check, detail, starts, rule", CASES)
def test_prompt_names_repo_finding_and_boundary(repo, check, detail, starts, rule):
    text = fix_prompt(repo, check, detail)
    assert text.startswith(starts)
    assert f"`{check}`: {detail}." in text
    assert rule in text
    assert text.endswith("Work in a worktree, never on the main checkout; open a PR and leave merging to me.")
