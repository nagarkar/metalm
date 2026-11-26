"""Pending brakes recover across mainline changes and ambiguous commit success."""

import tomllib

import pytest

from improve_fixtures import World, git
from metalm_ops.improve import brake, process, store
from test_ops_improve_brake import NOW, row, trigger


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def publish_other_brake(world):
    """An intervening successful brake and an unrelated owner edit land on main."""
    text = (
        '[[braked]]\nrepo = "blm"\nsince = "2026-11-26T13:10:00+00:00"\nreason = "stalled"\n'
        'summary = "Owner annotated five failures"\nruns = ["other-run"]\nprs = []\n'
    )
    (world.metalm / "improve/braked.toml").write_text(text)
    (world.metalm / "owner-note.txt").write_text("Keep this unrelated owner edit.\n")
    git(world.metalm, "add", ".")
    git(world.metalm, "commit", "-m", "Another brake and owner note")
    git(world.metalm, "push", "origin", "main")
    return tomllib.loads(text)["braked"][0]


@pytest.mark.parametrize("failed_step", ["push", "merge"])
def test_retry_reconciles_intervening_main_and_pins_updated_head(world, monkeypatch, failed_step):
    candidate = trigger([row(1), row(2), row(3)])
    original = world.command
    failed = False

    def command(arguments, **kwargs):
        nonlocal failed
        is_step = (arguments[0] == "git" and arguments[1] == "push") if failed_step == "push" else list(arguments)[1:3] == ["pr", "merge"]
        if is_step and not failed:
            failed = True
            return world.completed(arguments, 1, error=f"transient {failed_step} failure")
        return original(arguments, **kwargs)

    monkeypatch.setattr(process, "RUNNER", command)
    first = brake.apply(world.config, "alm", candidate, "first", NOW)
    assert not first["ok"]
    branch = "auto-improve/brake-alm-20261126"
    old_head = git(world.metalm, "rev-parse", branch).strip()
    if failed_step == "merge":
        world.history = [
            {
                "number": 88,
                "title": "[auto-improve] Brake alm: rejected",
                "url": first["pr_url"],
                "state": "OPEN",
                "headRefName": branch,
                "headRefOid": old_head,
            }
        ]
    other_entry = publish_other_brake(world)
    main_before = git(world.metalm_origin, "rev-parse", "main").strip()
    second = brake.apply(world.config, "alm", candidate, "second", NOW)
    assert second["ok"], second
    entries = brake.read(world.config)
    assert {entry["repo"] for entry in entries} == {"alm", "blm"}
    assert next(entry for entry in entries if entry["repo"] == "blm") == other_entry
    assert git(world.metalm_origin, "show", "main:owner-note.txt") == "Keep this unrelated owner edit.\n"
    new_head = git(world.metalm_origin, "rev-parse", branch).strip()
    assert new_head != old_head
    assert git(world.metalm_origin, "merge-base", new_head, old_head).strip() == old_head
    assert git(world.metalm_origin, "merge-base", new_head, main_before).strip() == main_before
    merge = world.commands("gh", "pr", "merge")[-1]
    assert merge[merge.index("--match-head-commit") + 1] == new_head
    assert len(world.commands("gh", "pr", "create")) == 1
    assert len(world.commands("superlm-notify")) == 1
    assert store.read_steps(world.config, "alm")[-1]["outcome"] == "ok"
    assert any(event["step"] == "commit" and event["details"].get("head") == new_head for event in store.read_steps(world.config, "alm"))


def test_retry_recovers_commit_that_succeeded_before_transport_failure(world, monkeypatch):
    original = world.command
    interrupted = False

    def command(arguments, **kwargs):
        nonlocal interrupted
        result = original(arguments, **kwargs)
        if list(arguments)[:2] == ["git", "commit"] and not interrupted:
            interrupted = True
            raise OSError("response lost after successful commit")
        return result

    monkeypatch.setattr(process, "RUNNER", command)
    candidate = trigger([row(1), row(2), row(3)])
    first = brake.apply(world.config, "alm", candidate, "first", NOW)
    assert not first["ok"] and "response lost" in first["reason"]
    branch = "auto-improve/brake-alm-20261126"
    committed_head = git(world.metalm, "rev-parse", branch).strip()
    assert not any(event["step"] == "commit" and event["outcome"] == "ok" for event in store.read_steps(world.config, "alm"))
    second = brake.apply(world.config, "alm", candidate, "second", NOW)
    assert second["ok"], second
    assert git(world.metalm_origin, "rev-parse", branch).strip() == committed_head
    assert len(world.commands("git", "commit")) == 1
    assert len(world.commands("gh", "pr", "create")) == 1
    assert len(world.commands("superlm-notify")) == 1
    assert any(event["step"] == "commit" and event["details"].get("head") == committed_head for event in store.read_steps(world.config, "alm"))
