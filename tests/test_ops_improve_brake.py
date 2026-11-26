"""Owner issue #88: blind-written persistence, rejection brake and deletion contract."""

from datetime import datetime, timezone
import tomllib

import pytest

from improve_fixtures import World, git
from metalm_ops.improve import brake, store

NOW = datetime(2026, 11, 26, 13, 10, tzinfo=timezone.utc)


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def row(number, outcome="rejected", reason="verifier refuted: wrong", pr=True):
    return {
        "run_id": f"r{number}",
        "repo": "alm",
        "outcome": outcome,
        "reason": reason,
        "pr_url": f"https://github.com/example/alm/pull/{number}" if pr else "",
        "started": f"2026-11-{20+number:02d}T13:10:00+00:00",
        "finished": f"2026-11-{20+number:02d}T13:11:00+00:00",
    }


def trigger(rows):
    """Public ledger order is newest first; fixtures tell the story chronologically."""
    return brake.trigger(list(reversed(rows)))


def test_three_judge_rejections_trigger_but_merge_resets():
    assert trigger([row(1), row(2)]) is None
    candidate = trigger([row(1), row(2), row(3)])
    assert candidate["reason"] == "rejected" and set(candidate["runs"]) == {"r1", "r2", "r3"}
    assert trigger([row(1), row(2), row(3, "merged"), row(4)]) is None


def test_ci_failure_is_not_a_judge_rejection():
    assert trigger([row(1), row(2), row(3, reason="CI failed")]) is None


def test_stalled_ignores_caps_but_counts_five_no_pr_failures():
    failures = [row(i, "gate-failed", "evidence quote not found", False) for i in range(1, 6)]
    assert trigger(failures[:4]) is None
    cap = row(6, "skipped", "daily Codex call cap reached", False)
    candidate = trigger([*failures[:2], cap, *failures[2:]])
    assert candidate["reason"] == "stalled" and set(candidate["runs"]) == {"r1", "r2", "r3", "r4", "r5"}
    assert trigger([*failures[:4], row(6, "merged")]) is None


def test_brake_persists_to_main_merges_pinned_and_alerts_once(world):
    store.initialize(world.config)
    candidate = trigger([row(1), row(2), row(3)])
    result = brake.apply(world.config, world.config.repos[0], candidate, "slot-run", NOW)
    assert result["ok"]
    entries = tomllib.loads(git(world.metalm_origin, "show", "main:improve/braked.toml"))["braked"]
    assert len(entries) == 1 and entries[0]["repo"] == "alm" and entries[0]["reason"] == "rejected"
    assert set(entries[0]["runs"]) == {"r1", "r2", "r3"}
    branch = "auto-improve/brake-alm-20261126"
    head = git(world.metalm_origin, "rev-parse", f"refs/heads/{branch}").strip()
    merge = world.commands("gh", "pr", "merge")[0]
    assert merge[merge.index("--match-head-commit") + 1] == head
    create = world.commands("gh", "pr", "create")[0]
    assert "[auto-improve] Brake alm: rejected" in create
    assert "auto-improve-brake" in " ".join(create)
    assert world.commands("superlm-notify") and world.metalm in world.pulled
    assert brake.read(world.config, fetch=True)[0]["repo"] == "alm"


def test_unbrake_opens_removal_pr_and_preserves_main_until_owner_merge(world):
    entry = '[[braked]]\nrepo = "alm"\nsince = "2026-11-25T13:10:00+00:00"\nreason = "stalled"\nsummary = "five failures"\nruns = ["r1"]\nprs = []\n'
    (world.metalm / "improve/braked.toml").write_text(entry)
    git(world.metalm, "add", ".")
    git(world.metalm, "commit", "-m", "Existing brake")
    git(world.metalm, "push", "origin", "main")
    original = git(world.metalm_origin, "rev-parse", "main")
    brake.unbrake(world.config, world.config.repos[0], "I checked the failures; resume it.")
    assert not world.commands("gh", "pr", "merge")
    assert git(world.metalm_origin, "rev-parse", "main") == original
    proposed = tomllib.loads(git(world.metalm_origin, "show", f"{world.last_branch}:improve/braked.toml"))
    assert not proposed.get("braked")
    assert "I checked the failures; resume it." in world.bodies[-1]
    assert "auto-improve-brake" in " ".join(world.commands("gh", "pr", "create")[0])


def test_failed_merge_retries_existing_pr_without_creating_duplicate(world, monkeypatch):
    from metalm_ops.improve import process

    store.initialize(world.config)
    candidate = trigger([row(1), row(2), row(3)])
    original = world.command
    failed = False

    def command(arguments, **kwargs):
        nonlocal failed
        if list(arguments)[1:3] == ["pr", "merge"] and not failed:
            failed = True
            return world.completed(arguments, 1, error="fixture merge unavailable")
        return original(arguments, **kwargs)

    monkeypatch.setattr(process, "RUNNER", command)
    first = brake.apply(world.config, world.config.repos[0], candidate, "slot-one", NOW)
    assert not first["ok"] and not brake.read(world.config)
    branch = "auto-improve/brake-alm-20261126"
    world.history = [
        {
            "number": 88,
            "title": "[auto-improve] Brake alm: rejected",
            "url": "https://github.com/nagarkar/metalm/pull/88",
            "state": "OPEN",
            "headRefName": branch,
            "headRefOid": git(world.metalm_origin, "rev-parse", branch).strip(),
        }
    ]
    second = brake.apply(world.config, world.config.repos[0], candidate, "slot-two", NOW)
    assert second["ok"] and brake.read(world.config)[0]["repo"] == "alm"
    assert len(world.commands("gh", "pr", "create")) == 1
    assert len(world.commands("superlm-notify")) == 1


def test_unbrake_dry_run_does_not_change_remote_or_open_pr(world):
    from test_ops_improve import publish_brake

    publish_brake(world)
    before = git(world.metalm_origin, "show-ref")
    board = brake.unbrake(world.config, "alm", "Resume after investigating.", dry_run=True)
    assert "Resume after investigating." in str(board)
    assert git(world.metalm_origin, "show-ref") == before
    assert not world.commands("gh", "pr", "create") and not world.commands("gh", "pr", "merge")


def test_failed_alert_retries_once_without_duplicate_pr_or_merge(world, monkeypatch):
    from metalm_ops.improve import process

    store.initialize(world.config)
    candidate = trigger([row(1), row(2), row(3)])
    original = world.command
    attempts = []

    def command(arguments, **kwargs):
        if str(arguments[0]).endswith("superlm-notify"):
            attempts.append(list(arguments))
            if len(attempts) == 1:
                return world.completed(arguments, 1, error="notification offline")
        return original(arguments, **kwargs)

    monkeypatch.setattr(process, "RUNNER", command)
    assert not brake.apply(world.config, "alm", candidate, "first", NOW)["ok"]
    assert brake.read(world.config)[0]["repo"] == "alm"
    assert brake.apply(world.config, "alm", candidate, "second", NOW)["ok"]
    assert brake.apply(world.config, "alm", candidate, "third", NOW)["ok"]
    assert len(attempts) == 2
    assert len(world.commands("gh", "pr", "create")) == 1
    assert len(world.commands("gh", "pr", "merge")) == 1


def test_partial_worktree_creation_failure_leaves_no_registered_worktree(world, monkeypatch):
    from metalm_ops.improve import process

    store.initialize(world.config)
    original = world.command
    before = git(world.metalm, "worktree", "list", "--porcelain")

    def command(arguments, **kwargs):
        result = original(arguments, **kwargs)
        if "worktree" in arguments and "add" in arguments:
            return world.completed(arguments, 1, error="worktree registered before failure")
        return result

    monkeypatch.setattr(process, "RUNNER", command)
    result = brake.apply(world.config, "alm", trigger([row(1), row(2), row(3)]), "failed-worktree", NOW)
    assert not result["ok"]
    assert git(world.metalm, "worktree", "list", "--porcelain") == before
    assert not world.commands("gh", "pr", "create")


def test_no_pr_mode_does_not_publish_pending_brake(world):
    from metalm_ops.improve import run

    store.initialize(world.config)
    for number in range(1, 4):
        previous = row(number)
        store.record_run(
            world.config,
            {
                **previous,
                "category": "readability",
                "lens": "readability",
                "title": "Rejected fixture",
                "codex_calls": 0,
                "model": "fixture",
                "checkout_updated": False,
            },
        )
    run.run(world.config, repo="alm", no_pr=True, now=NOW)
    assert not world.commands("gh", "pr", "create")
    assert not world.commands("gh", "pr", "merge")
    assert not world.commands("superlm-notify")
    assert not brake.read(world.config)


def test_five_activity_fetch_failures_publish_stalled_brake(world):
    from metalm_ops.improve import run

    world.crash_fetch.add("alm")
    for _ in range(5):
        run.run(world.config, now=NOW)
    entries = brake.read(world.config)
    assert entries and entries[0]["repo"] == "alm" and entries[0]["reason"] == "stalled"
    assert len(entries[0]["runs"]) == 5
    assert not world.prompts


def test_pending_brake_retries_while_target_fetch_still_fails(world):
    from metalm_ops.improve import run

    store.initialize(world.config)
    for number in range(1, 6):
        store.record_run(
            world.config,
            {
                **row(number, "failed", "fixture fetch crashed", False),
                "category": "readability",
                "lens": "readability",
                "title": "",
                "codex_calls": 0,
                "model": "fixture",
                "checkout_updated": False,
            },
        )
    world.crash_fetch.add("alm")
    run.run(world.config, now=NOW)
    assert brake.read(world.config)[0]["reason"] == "stalled"
    assert not world.prompts


def test_owner_removal_acknowledges_completed_brake_history(world):
    store.initialize(world.config)
    candidate = trigger([row(1), row(2), row(3)])
    assert brake.apply(world.config, "alm", candidate, "first", NOW)["ok"]
    (world.metalm / "improve/braked.toml").write_text("braked = []\n")
    git(world.metalm, "add", ".")
    git(world.metalm, "commit", "-m", "Owner authorized resume")
    git(world.metalm, "push", "origin", "main")
    result = brake.apply(world.config, "alm", candidate, "next-slot", NOW)
    assert result["ok"] and result["entry"] is None
    assert not brake.read(world.config)
    assert len(world.commands("gh", "pr", "create")) == 1
    assert len(world.commands("superlm-notify")) == 1


@pytest.mark.parametrize("state", ["dirty", "off-main"])
def test_brake_does_not_pull_dirty_or_off_main_checkout(world, state):
    store.initialize(world.config)
    original = git(world.metalm, "rev-parse", "HEAD")
    if state == "dirty":
        (world.metalm / "owner-work.txt").write_text("uncommitted work\n")
    else:
        git(world.metalm, "checkout", "-b", "owner-work")
    assert brake.apply(world.config, "alm", trigger([row(1), row(2), row(3)]), "first", NOW)["ok"]
    assert git(world.metalm, "rev-parse", "HEAD") == original
    assert world.metalm not in world.pulled
    assert brake.read(world.config)[0]["repo"] == "alm"


@pytest.mark.parametrize(
    "replacement", ['repo = "../alm"', 'since = "yesterday"', 'reason = "unknown"', 'summary = ["wrong shape"]', 'runs = "r1"', 'prs = ["wrong shape"]']
)
def test_invalid_tracked_brake_fields_are_rejected(world, replacement):
    from metalm_ops.improve.run import ImproveError

    fields = {"repo": '"alm"', "since": '"2026-11-25T13:10:00+00:00"', "reason": '"stalled"', "summary": '"five failures"', "runs": '["r1"]', "prs": "[]"}
    key, value = replacement.split(" = ", 1)
    fields[key] = value
    (world.metalm / "improve/braked.toml").write_text("[[braked]]\n" + "\n".join(f"{name} = {literal}" for name, literal in fields.items()) + "\n")
    git(world.metalm, "add", ".")
    git(world.metalm, "commit", "-m", "Malformed fixture")
    git(world.metalm, "push", "origin", "main")
    with pytest.raises(ImproveError, match="improve/braked.toml"):
        brake.read(world.config)
