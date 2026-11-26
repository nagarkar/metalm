"""`deploy` and `discover`, folded in from this session's hand-written runs (harvest 2026-10-25).

Sources: coding.md (a main checkout stays on main), operations.md (restart only
through `launchctl kickstart -k`), and the metalm skill's "Finding databases"
(the CLI's own name, `.env` path keys only, skip backups and caches).
Incident 2026-10-25: authorllm's store, ~/.authorlm/authorlm.db, was missed
because the search used the repo's name.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from metalm_ops import deploy, status
from ops_fixtures import make_cfg, make_db


def world(branch="main", dirty="", pull=(0, "Fast-forward")):
    calls = []

    def run(argv, cwd):
        calls.append(argv)
        if argv[:3] == ["git", "branch", "--show-current"]:
            return 0, branch + "\n"
        if argv[:2] == ["git", "status"]:
            return 0, dirty
        if argv[:2] == ["git", "pull"]:
            return pull
        if argv[:2] == ["git", "log"]:
            return 0, "abc123 Merge pull request #1\n"
        return 0, ""

    return run, calls


def test_deploy_pulls_restarts_waits_and_collects(tmp_path, monkeypatch):
    run, calls = world()
    posted = []
    monkeypatch.setattr(deploy, "RUNNER", run)
    monkeypatch.setattr(deploy, "POST", lambda url: posted.append(url) or 303)
    monkeypatch.setattr(status, "FETCH", lambda url: 200)
    steps = deploy.deploy(make_cfg(tmp_path), checkout=tmp_path)
    assert steps == ["main at abc123 Merge pull request #1", "restarted com.example.metalm.ops.serve", "/health ok", "collected"]
    assert ["git", "pull", "--ff-only", "origin", "main"] in calls
    assert any(a[:3] == ["launchctl", "kickstart", "-k"] and a[3].endswith("/com.example.metalm.ops.serve") for a in calls)
    assert posted == ["http://127.0.0.1:8700/refresh"]


@pytest.mark.parametrize(
    "branch, dirty, message",
    [
        ("ai-writing-patterns", "", "is on ai-writing-patterns, not main"),
        ("", "", "is on a detached HEAD"),
        ("main", " M guidelines/index.md\n", "uncommitted changes"),
    ],
)
def test_deploy_declines_a_checkout_off_main_or_dirty(tmp_path, monkeypatch, branch, dirty, message):
    run, calls = world(branch=branch, dirty=dirty)
    monkeypatch.setattr(deploy, "RUNNER", run)
    with pytest.raises(deploy.DeployError, match=message):
        deploy.deploy(make_cfg(tmp_path), checkout=tmp_path)
    assert not any(a[:2] == ["git", "pull"] or a[0] == "launchctl" for a in calls)


def test_deploy_dry_run_changes_nothing(tmp_path, monkeypatch):
    run, calls = world()
    monkeypatch.setattr(deploy, "RUNNER", run)
    steps = deploy.deploy(make_cfg(tmp_path), checkout=tmp_path, dry_run=True)
    assert steps[0] == "would: git pull --ff-only origin main" and len(steps) == 4
    assert not any(a[:2] == ["git", "pull"] or a[0] == "launchctl" for a in calls)


def test_deploy_names_a_server_that_never_answers(tmp_path, monkeypatch):
    run, _ = world()
    monkeypatch.setattr(deploy, "RUNNER", run)
    monkeypatch.setattr(deploy, "HEALTH_WAIT", 0.2)
    monkeypatch.setattr(status, "FETCH", lambda url: 0)
    with pytest.raises(deploy.DeployError, match="did not answer"):
        deploy.deploy(make_cfg(tmp_path), checkout=tmp_path)


def repo_with(tmp_path: Path, name: str, cli: str, env: str = "") -> Path:
    repo = tmp_path / "repos" / name
    repo.mkdir(parents=True)
    (repo / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n[project.scripts]\n{cli} = "{cli}.cli:main"\n')
    (repo / ".env").write_text(env)
    return repo


def test_discover_finds_the_store_under_the_cli_name(tmp_path):
    home, volumes = tmp_path / "home", tmp_path / "Volumes"
    repo = repo_with(tmp_path, "authorllm", "authorlm", env="SECRET_API_KEY=sk-not-read\n")
    store = make_db(home / ".authorlm" / "authorlm.db")
    make_db(home / ".authorlm" / "backups" / "authorlm-20261018.db")  # a backup folder is skipped
    make_db(home / ".authorlm" / "authorlm-before-series.db")  # a pre-migration copy is skipped
    (home / ".authorlm" / "empty.db").write_bytes(b"")  # 0-byte files are skipped
    cfg = make_cfg(tmp_path, repos=[{"name": "authorllm", "path": str(repo)}])
    found = deploy.discover(cfg, home=home, volumes=volumes)
    assert [(f.repo, f.path, f.listed) for f in found] == [("authorllm", store, False)]


def test_discover_follows_env_path_keys_and_drives_and_marks_listed(tmp_path):
    home, volumes = tmp_path / "home", tmp_path / "Volumes"
    shared = make_db(volumes / "X" / "corpuslm" / "transcript.sqlite")
    events = make_db(tmp_path / "elsewhere" / "events.sqlite")
    repo = repo_with(tmp_path, "ytlm", "ytlm", env=f'YTLM_DB={shared}\nEVENTS_DB="{events}"\nGEMINI_API_KEY=x\n')
    cache = make_db(volumes / "X" / "ytlm" / "cache" / "wn.db")  # a cache folder is skipped
    cfg = make_cfg(tmp_path, databases=[{"repo": "corpuslm", "name": "transcript", "path": str(shared)}], repos=[{"name": "ytlm", "path": str(repo)}])
    found = {f.path: f.listed for f in deploy.discover(cfg, home=home, volumes=volumes)}
    assert found == {shared: True, events: False}
    assert cache not in found


def test_cli_name_from_a_sub_project(tmp_path):
    """authorllm's CLI is declared in authorlm/pyproject.toml, not at the repo root."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "authorllm"\n')
    (tmp_path / "authorlm").mkdir()
    (tmp_path / "authorlm" / "pyproject.toml").write_text('[project]\nname = "authorlm"\n[project.scripts]\nauthorlm = "authorlm.cli:main"\n')
    assert deploy.cli_names(tmp_path) == ["authorlm"]


def test_env_paths_reads_only_path_keys(tmp_path):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-123\nPEOPLELM_WORKSPACE=/data/peoplelm\nLOG_DIR='~/logs'\n")
    assert deploy.env_paths(tmp_path) == [Path("/data/peoplelm"), Path("~/logs").expanduser()]
