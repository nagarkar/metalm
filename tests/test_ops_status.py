"""Status levels and checks, with fake commands and fetches.

Source: the owner's health thresholds in metalm_ops (26 h / 50 h, /health 200
in 3 s, agent loaded with exit 0, git and docs amber at worst).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from metalm_ops import backup, status
from ops_fixtures import make_cfg

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "hours, level",
    [(None, "red"), (0, "green"), (25.99, "green"), (26, "amber"), (50, "amber"), (50.01, "red")],
)
def test_age_level_boundaries(hours, level):
    assert status.age_level(None if hours is None else timedelta(hours=hours)) == level


AGENT_OK = '{\n\t"LastExitStatus" = 0;\n\t"PID" = 123;\n\t"Label" = "x";\n};'
AGENT_BAD = '{\n\t"LastExitStatus" = -15;\n\t"Label" = "x";\n};'


@pytest.mark.parametrize(
    "reply, level, detail",
    [
        ((0, AGENT_OK), "green", "loaded, running (pid 123)"),
        ((0, AGENT_BAD), "amber", "loaded, not running, last exit -15"),
        ((113, "Could not find"), "red", "not loaded"),
    ],
)
def test_agent_levels(monkeypatch, reply, level, detail):
    monkeypatch.setattr(status, "RUNNER", lambda argv, cwd: reply)
    assert status.agent("com.example.a.serve") == status.Check("agent com.example.a.serve", level, detail)


@pytest.mark.parametrize(
    "code, level, detail", [(200, "green", "port 8700: 200"), (500, "red", "port 8700: HTTP 500"), (0, "red", "port 8700: no answer in 3 s")]
)
def test_health_levels(monkeypatch, code, level, detail):
    monkeypatch.setattr(status, "FETCH", lambda url: code)
    assert status.health(8700) == status.Check("app :8700 /health", level, detail)


def test_health_against_real_socket_times_out_fast():
    import socket
    import time

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)  # accepts, never answers
    start = time.monotonic()
    row = status.health(sock.getsockname()[1])
    sock.close()
    assert row.level == "red" and time.monotonic() - start < 5


def test_conformance_parses_repos_md():
    md = "| repo | GitHub | status |\n|---|---|---|\n| alm | o/alm | compliant |\n| blm | o/blm | attempted |\n"
    assert status.conformance(md) == {"alm": "compliant", "blm": "attempted"}


def fake_world(prs_created: str = "2026-10-25T00:00:00Z", branches: str = "", gendocs: tuple = (0, ""), checkout: str = "main"):
    def run(argv, cwd):
        if argv[0] == "/bin/launchctl":
            return 0, AGENT_OK
        if argv[:3] == ["git", "branch", "--show-current"]:
            return 0, checkout + "\n"
        if argv[0] == "git":
            return 0, branches
        if argv[:2] == ["gh", "pr"]:
            return 0, json.dumps([{"number": 1, "createdAt": prs_created}])
        if argv[:2] == ["gh", "issue"]:
            return 0, json.dumps([{"number": 1}, {"number": 2}])
        if argv[0].endswith("metalm-gendocs"):
            return gendocs
        raise AssertionError(argv)

    return run


def test_collect_all_green(tmp_path, monkeypatch):
    repo_dir = tmp_path / "alm"
    (repo_dir / "docs" / "generated").mkdir(parents=True)
    cfg = make_cfg(tmp_path, repos=[{"name": "alm", "path": str(repo_dir), "github": "o/alm", "ports": [8700], "agents": ["com.example.alm.serve"]}])
    monkeypatch.setattr(status, "RUNNER", fake_world())
    monkeypatch.setattr(status, "FETCH", lambda url: 200)
    monkeypatch.setattr(status, "REPOS_MD", tmp_path / "repos.md")
    (tmp_path / "repos.md").write_text("| alm | o/alm | compliant |\n")
    backup.run(cfg, now=NOW - timedelta(hours=2))
    backup.record(cfg, {"kind": "offsite", "ts": (NOW - timedelta(hours=2)).isoformat(), "ok": True})
    got = status.collect(cfg, now=NOW)
    checks = {c["check"]: (c["level"], c["detail"]) for c in got["repos"][0]["checks"]}
    assert checks == {
        "backup store": ("green", "2 h ago"),
        "app :8700 /health": ("green", "port 8700: 200"),
        "agent com.example.alm.serve": ("green", "loaded, running (pid 123)"),
        "main checkout on main": ("green", "main"),
        "unmerged branches": ("green", "0"),
        "open PRs": ("green", "1 open, 0 over 7 days"),
        "open issues": ("green", "2"),
        "generated docs": ("green", "current"),
        "metalm row": ("green", "compliant"),
    }
    assert got["level"] == "green" and status.reds(got) == []


def test_collect_amber_and_red(tmp_path, monkeypatch):
    repo_dir = tmp_path / "alm"
    (repo_dir / "docs" / "generated").mkdir(parents=True)
    cfg = make_cfg(tmp_path, repos=[{"name": "alm", "path": str(repo_dir), "github": "o/alm", "ports": [8700]}])
    monkeypatch.setattr(
        status, "RUNNER", fake_world(prs_created="2026-10-01T00:00:00Z", branches="old-work\n", gendocs=(1, "stale: docs/generated/index.md\n"))
    )
    monkeypatch.setattr(status, "FETCH", lambda url: 0)
    monkeypatch.setattr(status, "REPOS_MD", tmp_path / "missing.md")
    got = status.collect(cfg, now=NOW)  # never backed up, never sent off-site
    checks = {c["check"]: c["level"] for c in got["repos"][0]["checks"]}
    assert checks == {
        "main checkout on main": "green",
        "backup store": "red",
        "app :8700 /health": "red",
        "unmerged branches": "amber",
        "open PRs": "amber",
        "open issues": "green",
        "generated docs": "amber",
        "metalm row": "amber",
    }
    jobs = {c["check"]: c["level"] for c in got["jobs"]}
    assert jobs["B2 snapshot"] == "red"
    assert got["level"] == "red"
    assert "alm: app :8700 /health (port 8700: no answer in 3 s)" in status.reds(got)


def test_failed_local_run_is_red_with_reason(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path, databases=[{"repo": "alm", "name": "x", "path": str(tmp_path / "gone.sqlite")}])
    monkeypatch.setattr(status, "RUNNER", fake_world())
    backup.run(cfg, now=NOW)
    got = status.collect(cfg, now=NOW)
    row = next(c for c in got["jobs"] if c["check"] == "last local run")
    assert row["level"] == "red" and "alm/x: no database at" in row["detail"]


def test_database_only_repo_gets_a_card(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path)
    monkeypatch.setattr(status, "RUNNER", fake_world())
    got = status.collect(cfg, now=NOW)
    assert [r["name"] for r in got["repos"]] == ["alm"]


@pytest.mark.parametrize(
    "branch, level, detail",
    [
        ("main", "green", "main"),
        ("ai-writing-patterns", "red", "on ai-writing-patterns: commit or push it, then git switch main"),
        ("", "red", "on a detached HEAD: commit or push it, then git switch main"),
    ],
)
def test_main_checkout_must_be_on_main(tmp_path, monkeypatch, branch, level, detail):
    """Source: coding.md owner rule of 2026-10-25 (a session left metalm's main checkout on its branch)."""
    monkeypatch.setattr(status, "RUNNER", fake_world(checkout=branch))
    from metalm_ops.config import Repo

    assert status.checkout_row(Repo("alm", tmp_path)) == status.Check("main checkout on main", level, detail)
