"""Surface contracts from issue #80 and the owner's resolved conflicts (2026-11-26)."""

from __future__ import annotations

import json
import os
import plistlib
import subprocess
from pathlib import Path
from datetime import UTC, datetime, timedelta

import pytest

from metalm_ops import cli, config, doctor, schedule, status

ROOT = Path(__file__).resolve().parents[1]


def configuration(tmp_path, improve=None):
    data = {
        "label_prefix": "com.example",
        "port": 8700,
        "state_dir": str(tmp_path / "state"),
        "backup": {"local_dir": str(tmp_path / "backups")},
        "repo": [{"name": "alm", "path": str(tmp_path / "alm"), "github": "owner/alm"}],
    }
    if improve is not None:
        data["improve"] = improve
    return config.parse(data)


def test_improve_absent_is_off(tmp_path):
    assert configuration(tmp_path).improve is None


def test_improve_configuration_defaults_and_each_key(tmp_path):
    settings = configuration(tmp_path, {"repo": [{"name": "alm", "test": "{venv}/bin/pytest -q"}]}).improve
    assert settings.enabled is True
    assert settings.model == "gpt-6-astra" and settings.review_model == "claude-opus-5-5"
    assert settings.max_codex_calls_per_day == 20 and settings.max_review_cost_usd_per_day == 2.0
    assert settings.max_files == 5 and settings.max_changed_lines == 150
    values = {
        "enabled": False,
        "codex_bin": "/a/codex",
        "model": "writer",
        "effort": "medium",
        "max_codex_calls_per_day": 7,
        "claude_bin": "/a/claude",
        "review_model": "reader",
        "max_review_cost_usd_per_day": 0.5,
        "propose_timeout_min": 2,
        "review_timeout_min": 3,
        "ci_timeout_min": 4,
        "max_files": 2,
        "max_changed_lines": 12,
    }
    settings = configuration(
        tmp_path, {**values, "repo": [{"name": "alm", "test": "true", "merge": "squash", "exclude": ["assets/**"], "deploy": "true"}]}
    ).improve
    for key, value in values.items():
        assert getattr(settings, key) == value
    assert settings.repos[0].merge == "squash" and settings.repos[0].exclude == ("assets/**",)
    assert settings.repos[0].deploy == "true"


@pytest.mark.parametrize(
    "key",
    ["max_codex_calls_per_day", "propose_timeout_min", "review_timeout_min", "ci_timeout_min", "max_files", "max_changed_lines", "max_review_cost_usd_per_day"],
)
@pytest.mark.parametrize("value", [-1, True, "one"])
def test_improve_rejects_invalid_numbers_by_key(tmp_path, key, value):
    with pytest.raises(config.ConfigError, match=key):
        configuration(tmp_path, {key: value})


@pytest.mark.parametrize(
    "values,key",
    [
        ({"unknown": 1}, "unknown"),
        ({"enabled": "yes"}, "enabled"),
        ({"codex_bin": 1}, "codex_bin"),
        ({"model": 1}, "model"),
        ({"effort": False}, "effort"),
        ({"claude_bin": False}, "claude_bin"),
        ({"review_model": False}, "review_model"),
        ({"repo": {}}, "repo"),
        ({"repo": [{"name": "missing", "test": "true"}]}, "name"),
        ({"repo": [{"name": "alm", "test": "true", "merge": "reset"}]}, "merge"),
        ({"repo": [{"name": "alm", "test": "true", "exclude": [1]}]}, "exclude"),
        ({"repo": [{"name": "alm", "test": "true", "extra": 1}]}, "extra"),
        ({"repo": [{"name": "alm"}]}, "test"),
        ({"max_review_cost_usd_per_day": float("nan")}, "max_review_cost_usd_per_day"),
        ({"max_review_cost_usd_per_day": 10**400}, "max_review_cost_usd_per_day"),
        ({"max_review_cost_usd_per_day": float("inf")}, "max_review_cost_usd_per_day"),
    ],
)
def test_improve_rejects_bad_shape_by_key(tmp_path, values, key):
    with pytest.raises(config.ConfigError, match=key):
        configuration(tmp_path, values)


def test_improve_plist_and_install_command(tmp_path):
    settings = configuration(tmp_path)
    rendered = plistlib.loads(schedule.render(settings, "improve", checkout=tmp_path / "checkout").encode())
    assert rendered["Label"] == "com.example.metalm.improve"
    assert rendered["StartCalendarInterval"] == {"Hour": 1, "Minute": 30}
    assert rendered["StandardOutPath"].endswith("improve.launchd.log")
    assert rendered["ProgramArguments"] == ["/bin/bash", str(tmp_path / "checkout/scripts/nightly-improve.sh")]
    assert "schedule print improve" in schedule.install_command(settings, "improve")


def test_preview_and_rehearsal_are_mutually_exclusive(capsys):
    assert cli.main(["improve", "run", "--dry-run", "--no-pr"]) == 1
    assert "not allowed" in capsys.readouterr().err


def test_new_help_and_completion(capsys):
    for verb in ("run", "status", "labels"):
        assert cli.main(["help", "improve", verb]) == 0
        assert "example: metalm-ops improve" in capsys.readouterr().out
    completion = cli.completion_script()
    assert "improve" in completion and "--no-pr" in completion and "--repo" in completion


def stand_in(tmp_path, failed=(), sleeping=False):
    checkout = tmp_path / "checkout"
    (checkout / "scripts").mkdir(parents=True)
    script = checkout / "scripts/nightly-improve.sh"
    script.write_text((ROOT / "scripts/nightly-improve.sh").read_text())
    cases = "".join(f'"{name}") exit 3;;\n' for name in failed)
    if sleeping:
        cases += '"improve run") kill -TERM "$PPID"; exit 0;;\n'
    launcher = checkout / "metalm-ops.sh"
    launcher.write_text(f'#!/bin/bash\necho "$*" >> "{tmp_path}/calls"\ncase "$*" in\n{cases}esac\n')
    launcher.chmod(0o755)
    notifier = tmp_path / "notify"
    notifier.write_text(f'#!/bin/bash\necho "$*" >> "{tmp_path}/alerts"\n')
    notifier.chmod(0o755)
    environment = {**os.environ, "HOME": str(tmp_path / "home"), "METALM_CAFFEINATED": "1", "METALM_NOTIFY_CMD": str(notifier)}
    return script, environment


def test_improve_nightly_clean_is_silent(tmp_path):
    script, environment = stand_in(tmp_path)
    result = subprocess.run(["/bin/bash", str(script)], env=environment, capture_output=True, text=True)
    assert result.returncode == 0 and not result.stdout and not result.stderr
    assert (tmp_path / "calls").read_text().splitlines() == ["doctor", "improve run"]
    assert not (tmp_path / "alerts").exists()
    assert len(list((tmp_path / "home/.local/state/metalm/ops/logs").glob("improve-*.log"))) == 1


def test_improve_nightly_failures_alert_once_and_continue(tmp_path):
    script, environment = stand_in(tmp_path, ("doctor", "improve run"))
    subprocess.run(["/bin/bash", str(script)], env=environment, check=False)
    assert (tmp_path / "calls").read_text().splitlines() == ["doctor", "improve run"]
    alerts = (tmp_path / "alerts").read_text().splitlines()
    assert len(alerts) == 1 and "nightly improve" in alerts[0] and "doctor, improve" in alerts[0]


def test_improve_nightly_killed_names_run(tmp_path):
    script, environment = stand_in(tmp_path, sleeping=True)
    subprocess.run(["/bin/bash", str(script)], env=environment, check=False, timeout=5)
    assert "the run itself" in (tmp_path / "alerts").read_text()


def test_doctor_improve_dependencies_and_wake(tmp_path, monkeypatch):
    from metalm_ops.improve import agents
    from metalm_ops.improve.run import LABELS

    selected = configuration(tmp_path, {"repo": [{"name": "alm", "test": "true"}]})
    (tmp_path / "alm/.venv").mkdir(parents=True)
    executable = tmp_path / "agent"
    executable.write_text("stub")
    monkeypatch.setattr(agents, "codex_binary", lambda settings: str(executable))
    monkeypatch.setattr(agents, "claude_binary", lambda settings: str(executable))
    monkeypatch.setattr(schedule, "installed_path", lambda settings, job: tmp_path / "missing.plist")

    def runner(arguments, cwd=None):
        if arguments[1:] == ["login", "status"]:
            return 0, "Logged in using ChatGPT"
        if arguments[1:3] == ["auth", "status"]:
            return 0, "logged in"
        if arguments[1:3] == ["label", "list"]:
            return 0, json.dumps([{"name": name} for name, _, _ in LABELS])
        if arguments[0] == "/usr/bin/pmset":
            return 0, "wakeorpoweron at 1:20AM every day"
        raise AssertionError(arguments)

    monkeypatch.setattr(status, "RUNNER", runner)
    findings = doctor.improve_checks(selected)
    assert all(finding.ok for finding in findings)
    assert any(finding.name == "daily wake before improve" and finding.fix.endswith("01:20:00") for finding in findings)
    assert any(finding.name == "improve alm labels" for finding in findings)
    monkeypatch.setattr(status, "RUNNER", lambda arguments, cwd=None: (1, "unavailable"))
    failed = doctor.improve_checks(selected)
    assert any(not finding.ok and finding.fix.endswith(" login") for finding in failed)
    assert any(not finding.ok and finding.fix == "metalm-ops improve labels --repo alm" for finding in failed)
    assert all(not finding.required for finding in doctor.improve_checks(configuration(tmp_path)))


@pytest.mark.parametrize(
    "hours,outcome,loaded,expected",
    [(1, "merged", True, "green"), (1, "rejected", True, "green"), (1, "failed", False, "red"), (37, "merged", True, "red"), (37, "merged", False, "amber")],
)
def test_auto_improve_status_thresholds(tmp_path, monkeypatch, hours, outcome, loaded, expected):
    from metalm_ops.improve import store

    selected = configuration(tmp_path, {"repo": [{"name": "alm", "test": "true"}]})
    now = datetime(2026, 11, 26, 12, tzinfo=UTC)
    monkeypatch.setattr(
        store,
        "read_runs",
        lambda *arguments, **keywords: [{"finished": (now - timedelta(hours=hours)).isoformat(), "outcome": outcome, "reason": "test reason"}],
    )
    assert status.improve_row(selected, "alm", now, loaded=loaded).level == expected
    (selected.state_dir / "improve").mkdir(parents=True)
    (selected.state_dir / "improve/paused-alm").touch()
    assert status.improve_row(selected, "alm", now, loaded=loaded).level == "amber"


def test_auto_improve_status_never_run_is_amber(tmp_path, monkeypatch):
    from metalm_ops.improve import store

    selected = configuration(tmp_path, {"repo": [{"name": "alm", "test": "true"}]})
    monkeypatch.setattr(store, "read_runs", lambda *arguments, **keywords: [])
    assert status.improve_row(selected, "alm", datetime.now(UTC), loaded=True).level == "amber"
    assert not selected.state_dir.exists()


def test_improve_cli_json_routes_preview_and_status(tmp_path, monkeypatch, capsys):
    from metalm_ops.improve import run

    selected = configuration(tmp_path, {"repo": [{"name": "alm", "test": "true"}]})
    monkeypatch.setattr(cli, "load", lambda path: selected)
    seen = []
    monkeypatch.setattr(
        run,
        "run",
        lambda settings, **keywords: seen.append(keywords)
        or {"rows": [], "ok": True, "usage": {"calls": 0, "review_cost_usd": 0}, "next": "metalm-ops improve status"},
    )
    assert cli.main(["improve", "run", "--repo", "alm", "--no-pr", "--json"]) == 0
    assert seen == [{"repo": "alm", "dry_run": False, "no_pr": True}]
    assert json.loads(capsys.readouterr().out)["next"] == "metalm-ops improve status"
    monkeypatch.setattr(
        run,
        "status",
        lambda settings: {
            "repos": [{"name": "alm", "paused": True}],
            "rows": [{"repo": "alm", "outcome": "rejected", "reason": "too broad", "pr_url": "https://example.test/1"}],
            "ok": True,
            "next": "review pause",
        },
    )
    assert cli.main(["improve", "status"]) == 0
    output = capsys.readouterr().out
    assert "alm: paused" in output and "rejected" in output and "https://example.test/1" in output


def test_prompts_inventory_and_json(capsys):
    assert cli.main(["prompts", "--json"]) == 0
    board = json.loads(capsys.readouterr().out)
    assert {row["file"] for row in board["prompts"]} == {"propose_v1.md", "review_senior_v1.md", "review_boundaries_v1.md"}
    assert all(row["version"] == 1 and len(row["sha256"]) == 64 for row in board["prompts"])


def test_schedule_improve_json_board(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "load", lambda path: configuration(tmp_path))
    assert cli.main(["schedule", "print", "improve", "--json"]) == 0
    board = json.loads(capsys.readouterr().out)
    assert plistlib.loads(board["plist"].encode())["Label"] == "com.example.metalm.improve"
    assert "schedule print improve" in board["install"] and board["next"]


def test_nightly_uses_configured_logs_and_retains_thirty_days(tmp_path):
    script, environment = stand_in(tmp_path)
    interpreter = script.parents[1] / ".venv/bin/python"
    interpreter.parent.mkdir(parents=True)
    log_directory = tmp_path / "configured/logs"
    log_directory.mkdir(parents=True)
    interpreter.write_text(f'#!/bin/bash\nprintf "%s\\n" "{log_directory}"\n')
    interpreter.chmod(0o755)
    expired = log_directory / "improve-old.log"
    preserved = log_directory / "backup-old.log"
    for path in (expired, preserved):
        path.write_text("old log")
        os.utime(path, (0, 0))
    subprocess.run(["/bin/bash", str(script)], env=environment, check=True)
    assert not expired.exists() and preserved.exists()
    assert len(list(log_directory.glob("improve-*.log"))) == 1


def test_improve_no_pr_cli_prints_diff_and_usage(tmp_path, monkeypatch, capsys):
    from metalm_ops.improve import run

    monkeypatch.setattr(cli, "load", lambda path: configuration(tmp_path))
    monkeypatch.setattr(
        run,
        "run",
        lambda *arguments, **keywords: {
            "rows": [{"repo": "alm", "outcome": "no-pr", "reason": "gates passed", "diff_stat": "file.py | 2 +-"}],
            "ok": True,
            "usage": {"calls": 1, "codex_calls": 1, "review_cost_usd": 0},
            "next": "metalm-ops improve status",
        },
    )
    assert cli.main(["improve", "run", "--no-pr"]) == 0
    output = capsys.readouterr().out
    assert "file.py | 2 +-" in output and "gates passed" in output and "usage: 1 calls" in output


@pytest.mark.parametrize(
    "row,key",
    [
        ({"name": 1, "test": "true"}, "name"),
        ({"name": "alm", "test": False}, "test"),
        ({"name": "alm", "test": "true", "merge": False}, "merge"),
        ({"name": "alm", "test": "true", "exclude": "src/**"}, "exclude"),
        ({"name": "alm", "test": "true", "deploy": False}, "deploy"),
        ({"name": "../alm", "test": "true"}, "name"),
    ],
)
def test_improve_repo_rejects_wrong_types(tmp_path, row, key):
    with pytest.raises(config.ConfigError, match=key):
        configuration(tmp_path, {"repo": [row]})


def test_improve_rejects_table_instead_of_array_and_duplicate_names(tmp_path):
    with pytest.raises(config.ConfigError, match="improve"):
        configuration(tmp_path, [])
    with pytest.raises(config.ConfigError, match="name"):
        configuration(tmp_path, {"repo": [{"name": "alm", "test": "true"}, {"name": "alm", "test": "true"}]})


def test_status_collect_includes_auto_improve_on_repository_card(tmp_path, monkeypatch):
    selected = configuration(tmp_path, {"repo": [{"name": "alm", "test": "true"}]})
    monkeypatch.setattr(status, "RUNNER", lambda *arguments: (1, "not loaded"))
    monkeypatch.setattr(status, "REPOS_MD", tmp_path / "missing.md")
    board = status.collect(selected)
    checks = board["repos"][0]["checks"]
    assert {"check": "auto-improve", "level": "amber", "detail": "no run yet"} in checks
    assert not selected.state_dir.exists()
