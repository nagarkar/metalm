"""Owner issue #88: independently derived activity, weekly floor and clock boundaries."""

from datetime import datetime, timedelta, timezone

import pytest

from improve_fixtures import World, git
from metalm_ops.improve import cadence, store

NOW = datetime(2026, 11, 26, 13, 10, tzinfo=timezone(timedelta(hours=-8)))


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_AUTHOR_DATE", "2026-01-01T00:00:00+00:00")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-01-01T00:00:00+00:00")
    return World(tmp_path, monkeypatch)


def complete(world, lens, when, outcome="no-pr"):
    store.initialize(world.config)
    store.record_run(
        world.config,
        {
            "run_id": lens + when.isoformat(),
            "repo": "alm",
            "started": when.isoformat(),
            "finished": when.isoformat(),
            "outcome": outcome,
            "category": lens,
            "lens": lens,
            "title": "fixture",
            "reason": "fixture",
            "codex_calls": 0,
            "model": "fixture",
            "checkout_updated": False,
        },
    )


def test_demand_superposes_seven_day_impulses():
    activity = {(NOW.date() - timedelta(days=k)).isoformat(): 400 for k in range(8)}
    assert cadence.demand(activity, NOW, (1, 1, 0.75, 0.5, 0.5, 0.25, 0.25)) == 1700
    assert cadence.demand({}, NOW, (1, 1, 0.75, 0.5, 0.5, 0.25, 0.25)) == 0


@pytest.mark.parametrize("hour,minute,slot,late", [(13, 10, "13:10", 0), (14, 10, "13:10", 60), (14, 11, "13:10", 61), (8, 10, "21:10", 660)])
def test_latest_slot_includes_previous_calendar_day(world, hour, minute, slot, late):
    assert cadence.slot(world.config.improve, NOW.replace(hour=hour, minute=minute)) == (slot, late)


def test_weekly_floor_and_skips_do_not_hide_overdue_lens(world, monkeypatch):
    world.data["improve"]["repo"][0]["lenses"] = ["readability", "documentation"]
    world.configure()
    monkeypatch.setattr(cadence, "activity", lambda *args, **kwargs: {})
    complete(world, "readability", NOW - timedelta(days=6))
    complete(world, "documentation", NOW - timedelta(days=1), "skipped")
    plan = cadence.plan(world.config, world.config.improve.repos[0], world.config.repos[0], NOW, fetch=False)
    assert plan["D"] == 0 and plan["T"] == 0 and plan["today"] == 0
    assert plan["overdue"] == ["documentation"] and plan["lens"] == "documentation" and plan["due"]
    complete(world, "documentation", NOW)
    plan = cadence.plan(world.config, world.config.improve.repos[0], world.config.repos[0], NOW, fetch=False)
    assert not plan["due"] and plan["today"] == 1 and plan["lens"] == "readability"


@pytest.mark.parametrize("lines,target", [(0, 0), (1, 1), (400, 1), (401, 2), (10000, 4)])
def test_activity_targets_round_up_and_cap_at_slot_count(world, monkeypatch, lines, target):
    monkeypatch.setattr(cadence, "activity", lambda *args, **kwargs: {NOW.date().isoformat(): lines})
    plan = cadence.plan(world.config, world.config.improve.repos[0], world.config.repos[0], NOW, fetch=False)
    assert plan["D"] == lines and plan["T"] == target


def test_activity_excludes_generated_locks_binary_and_self_merge(world, monkeypatch):
    repo = world.repos["alm"]

    def commit(message, date):
        monkeypatch.setenv("GIT_AUTHOR_DATE", date)
        monkeypatch.setenv("GIT_COMMITTER_DATE", date)
        git(repo, "add", ".")
        git(repo, "commit", "-m", message)

    (repo / "counted.txt").write_text("one\ntwo\nthree\n")
    (repo / "docs/generated").mkdir(parents=True)
    (repo / "docs/generated/noise.txt").write_text("noise\n" * 20)
    (repo / "uv.lock").write_text("lock\n" * 30)
    (repo / "package-lock.json").write_text("lock\n" * 40)
    (repo / "binary.bin").write_bytes(b"\x00binary\n")
    commit("Human work", "2026-11-25T23:30:00-08:00")
    (repo / "counted.txt").write_text("one\nfour\n")
    commit("Human edit", "2026-11-26T09:00:00-08:00")
    git(repo, "checkout", "-b", "auto-improve/example")
    (repo / "self.txt").write_text("self\n" * 100)
    commit("Automated change", "2026-11-26T10:00:00-08:00")
    git(repo, "checkout", "main")
    git(repo, "merge", "--no-ff", "auto-improve/example", "-m", "Merge branch auto-improve/example")
    git(repo, "push", "origin", "main")
    result = cadence.activity(world.config.repos[0], NOW, fetch=True)
    assert result["2026-11-25"] == 3
    # Replace two lines by one: two deletions plus one addition.
    assert result["2026-11-26"] == 3


def test_late_slot_records_one_global_skip_without_agents(world):
    from metalm_ops.improve import run

    board = run.run(world.config, now=NOW.replace(hour=14, minute=11))
    assert len(board["rows"]) == 1
    assert board["rows"][0]["outcome"] == "skipped"
    assert board["rows"][0]["reason"] == "slot 13:10 missed by 61 min (Mac asleep)"
    assert len(world.ledger("run")) == 1 and not world.prompts


def test_manual_run_bypasses_lateness_and_cadence(world):
    from metalm_ops.improve import run

    world.data["improve"]["repo"][0]["lenses"] = ["readability"]
    world.configure()
    complete(world, "readability", NOW - timedelta(hours=1))
    board = run.run(world.config, repo="alm", now=NOW.replace(hour=14, minute=11), no_pr=True)
    assert board["rows"][0]["outcome"] == "no-pr" and len(world.prompts) == 1


def test_status_unknown_repo_has_stable_opt_out_without_agents(world):
    from metalm_ops.improve import run

    assert run.status(world.config, repo="not-opted-in", now=NOW) == {"opted_in": False}
    assert not world.prompts


def test_status_scoped_contains_cadence_and_recent_runs(world):
    from metalm_ops.improve import run

    complete(world, "readability", NOW)
    board = run.status(world.config, repo="alm", now=NOW)
    assert board["opted_in"] is True
    assert {"D", "T", "today", "overdue", "brake", "runs"} <= board.keys()
    assert board["today"] == 1 and board["runs"][0]["lens"] == "readability"


def test_impulse_decays_without_activity_feedback():
    activity = {NOW.date().isoformat(): 10000}
    weights = (1, 1, 0.75, 0.5, 0.5, 0.25, 0.25)
    assert [cadence.demand(activity, NOW + timedelta(days=k), weights) for k in range(8)] == [10000, 10000, 7500, 5000, 5000, 2500, 2500, 0]


def test_overdue_repos_precede_heavier_activity_and_caps_record_remaining(tmp_path, monkeypatch):
    from metalm_ops.improve import run

    world = World(tmp_path, monkeypatch, names=("active", "overdue"), max_codex_calls_per_day=1)
    for selected in world.data["improve"]["repo"]:
        selected["lenses"] = ["readability"]
    world.configure()
    store.initialize(world.config)
    store.record_run(
        world.config,
        {
            "run_id": "recent",
            "repo": "active",
            "started": (NOW - timedelta(days=1)).isoformat(),
            "finished": (NOW - timedelta(days=1)).isoformat(),
            "outcome": "no-pr",
            "category": "readability",
            "lens": "readability",
            "title": "prior",
            "reason": "fixture",
            "codex_calls": 0,
            "model": "fixture",
            "checkout_updated": False,
        },
    )
    monkeypatch.setattr(cadence, "activity", lambda repo, *args, **kwargs: {NOW.date().isoformat(): 10000} if repo.name == "active" else {})
    board = run.run(world.config, now=NOW, no_pr=True)
    assert [row["repo"] for row in board["rows"]] == ["overdue", "active"]
    assert board["rows"][0]["outcome"] == "no-pr"
    assert board["rows"][1]["outcome"] == "skipped" and "cap" in board["rows"][1]["reason"]
    assert len(world.prompts) == 1


def test_quiet_repo_rotates_all_eight_applicable_lenses_in_week(world, monkeypatch):
    monkeypatch.setattr(cadence, "activity", lambda *args, **kwargs: {})
    expected = ["readability", "modularity", "documentation", "duplication", "tests", "backend-robustness", "performance", "drift"]
    for step, lens in enumerate(expected):
        when = NOW + timedelta(hours=20 * step)
        plan = cadence.plan(world.config, world.config.improve.repos[0], world.config.repos[0], when, fetch=False)
        assert plan["due"] and plan["lens"] == lens
        complete(world, lens, when)
    plan = cadence.plan(world.config, world.config.improve.repos[0], world.config.repos[0], NOW + timedelta(hours=20 * 7 + 1), fetch=False)
    assert not plan["due"] and not plan["overdue"]


def test_status_reports_activity_failure_without_claiming_success(world, monkeypatch):
    """Issue #88 session-start status must remain stable on an unavailable repository."""
    from metalm_ops.improve import run

    def unavailable(*args, **kwargs):
        raise ValueError("activity unavailable")

    monkeypatch.setattr(cadence, "activity", unavailable)
    board = run.status(world.config, repo="alm", now=NOW)
    assert not board["ok"] and board["D"] is None
    assert board["reason"] == "activity unavailable"


def test_impulse_target_follows_formula_even_when_default_cap_hides_decay(world, monkeypatch):
    """Issue #88's equation wins over its incompatible 'then fewer' example at 400 lines/run."""
    monkeypatch.setattr(cadence, "activity", lambda *args, **kwargs: {NOW.date().isoformat(): 10000})
    targets = [
        cadence.plan(world.config, world.config.improve.repos[0], world.config.repos[0], NOW + timedelta(days=day), fetch=False)["T"] for day in range(8)
    ]
    assert targets == [4, 4, 4, 4, 4, 4, 4, 0]
    world.configure(lines_per_run=2500)
    targets = [
        cadence.plan(world.config, world.config.improve.repos[0], world.config.repos[0], NOW + timedelta(days=day), fetch=False)["T"] for day in range(8)
    ]
    assert targets == [4, 4, 3, 2, 2, 1, 1, 0]
