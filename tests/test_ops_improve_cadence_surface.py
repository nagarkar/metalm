"""Configuration and public surfaces for slots and the visible brake (#88)."""

import json
import plistlib

import pytest

from metalm_ops import cli, config, schedule
from test_ops_improve_surface import configuration


def test_cadence_defaults_and_custom_slots(tmp_path):
    settings = configuration(tmp_path, {}).improve
    assert settings.slots == ("09:10", "13:10", "17:10", "21:10")
    assert settings.max_lateness_min == 60 and settings.lines_per_run == 400
    assert settings.decay == (1, 1, 0.75, 0.5, 0.5, 0.25, 0.25)
    cfg = configuration(tmp_path, {"slots": ["00:00", "23:59"], "decay": [0] * 7, "lines_per_run": 1, "max_lateness_min": 0})
    assert cfg.improve.slots == ("00:00", "23:59")
    assert cfg.improve.decay == (0,) * 7
    rendered = plistlib.loads(schedule.render(cfg, "improve").encode())
    assert rendered["StartCalendarInterval"] == [{"Hour": 0, "Minute": 0}, {"Hour": 23, "Minute": 59}]


@pytest.mark.parametrize(
    "key,value",
    [
        ("slots", []),
        ("slots", ["09:10"] * 9),
        ("slots", ["9:10"]),
        ("slots", ["24:00"]),
        ("slots", ["09:60"]),
        ("slots", ["13:10", "09:10"]),
        ("slots", ["09:10", "09:10"]),
        ("slots", [True]),
        ("slots", "09:10"),
        ("decay", [1] * 6),
        ("decay", [1] * 8),
        ("decay", [True] * 7),
        ("decay", [float("nan")] * 7),
        ("decay", [float("inf")] * 7),
        ("decay", [-0.1] * 7),
        ("decay", [1.1] * 7),
        ("decay", ["1"] * 7),
        ("lines_per_run", 0),
        ("lines_per_run", True),
        ("lines_per_run", 1.5),
        ("max_lateness_min", -1),
        ("max_lateness_min", True),
        ("max_lateness_min", 1.5),
    ],
)
def test_cadence_config_rejects_invalid_values(tmp_path, key, value):
    with pytest.raises(config.ConfigError, match=key):
        configuration(tmp_path, {key: value})


def test_status_scoped_json_and_unbrake_parser(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "load", lambda path: configuration(tmp_path, {}))
    seen = []
    monkeypatch.setattr(cli.improve, "status", lambda cfg, repo=None: seen.append(repo) or {"opted_in": False})
    assert cli.main(["improve", "status", "--repo", "absent", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"opted_in": False}
    assert seen == ["absent"]
    parsed = cli.build_parser().parse_args(["improve", "unbrake", "--repo", "alm", "--why", "resume it", "--dry-run"])
    assert parsed.repo == "alm" and parsed.why == "resume it" and parsed.dry_run
    assert cli.main(["improve", "unbrake", "--repo", "alm"]) == 1


def test_doctor_reports_slot_mismatch_and_malformed_brake(tmp_path, monkeypatch):
    from metalm_ops import doctor, status
    from metalm_ops.improve import agents, brake
    from metalm_ops.improve.run import LABELS

    cfg = configuration(tmp_path, {"slots": ["12:00"]})
    installed = tmp_path / "improve.plist"
    installed.write_bytes(plistlib.dumps({"StartCalendarInterval": [{"Hour": 9, "Minute": 10}]}))
    monkeypatch.setattr(schedule, "installed_path", lambda *args: installed)
    executable = tmp_path / "agent"
    executable.write_text("stub")
    monkeypatch.setattr(agents, "codex_binary", lambda settings: str(executable))
    monkeypatch.setattr(agents, "claude_binary", lambda settings: str(executable))
    calls = []

    def runner(args, cwd=None):
        calls.append(args)
        assert "pmset" not in args[0]
        if args[1:3] == ["label", "list"]:
            return 0, json.dumps([{"name": name} for name, _, _ in LABELS if name != "auto-improve-brake"])
        return 0, "Logged in"

    def invalid(*args, **kwargs):
        assert kwargs == {"fetch": False}
        raise ValueError("bad brake schema")

    monkeypatch.setattr(status, "RUNNER", runner)
    monkeypatch.setattr(brake, "read", invalid)
    checks = {row.name: row for row in doctor.improve_checks(cfg)}
    assert not checks["improve plist matches slots"].ok
    assert "schedule print improve" in checks["improve plist matches slots"].fix
    assert not checks["improve braked.toml"].ok
    assert "bad brake schema" in checks["improve braked.toml"].detail
    assert not checks["improve metalm labels"].ok
    assert "auto-improve-brake" in checks["improve metalm labels"].detail
    installed.write_text(schedule.render(cfg, "improve"))
    monkeypatch.setattr(brake, "read", lambda *args, **kwargs: {})
    checks = {row.name: row for row in doctor.improve_checks(cfg)}
    assert checks["improve plist matches slots"].ok and checks["improve braked.toml"].ok


def test_cli_unbrake_dispatches_owner_words(tmp_path, monkeypatch, capsys):
    from metalm_ops.improve import brake

    monkeypatch.setattr(cli, "load", lambda path: configuration(tmp_path, {}))
    calls = []
    monkeypatch.setattr(brake, "unbrake", lambda cfg, **kwargs: calls.append(kwargs) or {"ok": True, "next": "review PR", "title": "Unbrake alm"})
    assert cli.main(["improve", "unbrake", "--repo", "alm", "--why", "I approve resuming", "--dry-run", "--json"]) == 0
    assert calls == [{"repo": "alm", "why": "I approve resuming", "dry_run": True}]
    assert json.loads(capsys.readouterr().out)["title"] == "Unbrake alm"
