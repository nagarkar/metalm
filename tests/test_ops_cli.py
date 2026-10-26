"""The metalm-ops surface, doctor's wake rule, the plists and the nightly job script.

Sources: cli.md#tests-that-hold-the-surface, scheduling.md#launchd-job-safeguards
(clean run silent, failures named once, a killed run says so; wake 1-30 min
before the job), and the owner's 03:30 rule in metalm_ops.
"""

from __future__ import annotations

import json
import os
import plistlib
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

from metalm_ops import cli, doctor, schedule, status
from ops_fixtures import make_cfg

ROOT = Path(__file__).resolve().parents[1]


def leaves():
    return [(g, v) for g, v in cli.LEAVES]


@pytest.mark.parametrize("group, verb", leaves())
def test_every_leaf_has_description_and_example(capsys, group, verb):
    assert cli.main(["help", group] + ([verb] if verb else [])) == 0
    out = capsys.readouterr().out
    assert cli.LEAVES[(group, verb)][0] in " ".join(out.split()) and "example: metalm-ops" in out.replace('eval "$(metalm-ops', "example: metalm-ops")


def test_help_lists_every_leaf(capsys):
    cli.main(["help"])
    out = capsys.readouterr().out
    for g, v in leaves():
        assert (f"{g} {v}" if v else g) in out


def test_skill_names_every_leaf():
    skill = (ROOT / ".claude" / "skills" / "metalm" / "SKILL.md").read_text()
    for g, v in leaves():
        assert f"metalm-ops {g}" + (f" {v}" if v else "") in skill


@pytest.mark.parametrize("argv", [["nonsense"], ["backup", "run", "--bogus"], ["help", "nonsense"], ["schedule", "print", "nightly"]])
def test_usage_error_exits_1(argv, capsys):
    assert cli.main(argv) == 1


def test_missing_config_names_fix(tmp_path, capsys):
    assert cli.main(["status", "--config", str(tmp_path / "ops.toml")]) == 1
    assert "Copy ops.example.toml" in capsys.readouterr().err


def write_config(tmp_path) -> Path:
    db = tmp_path / "data" / "store.sqlite"
    from ops_fixtures import make_db

    make_db(db)
    path = tmp_path / "ops.toml"
    path.write_text(
        f'label_prefix = "com.example"\nport = 8700\nstate_dir = "{tmp_path / "state"}"\n[backup]\nlocal_dir = "{tmp_path / "backups"}"\n'
        f'[[database]]\nrepo = "alm"\nname = "store"\npath = "{db}"\n'
    )
    return path


def test_backup_run_json_board(tmp_path, capsys):
    cfg = write_config(tmp_path)
    assert cli.main(["backup", "run", "--json", "--config", str(cfg)]) == 0
    board = json.loads(capsys.readouterr().out)
    assert board["ok"] and board["next"] == "metalm-ops backup offsite"


def test_status_alerts_once_on_red(tmp_path, capsys, monkeypatch):
    cfg = write_config(tmp_path)
    sent = []
    monkeypatch.setattr(cli, "NOTIFY", lambda title, body: sent.append((title, body)))
    monkeypatch.setattr(status, "RUNNER", lambda argv, cwd: (113, "not loaded"))
    assert cli.main(["status", "--alert", "--json", "--config", str(cfg)]) == 0
    board = json.loads(capsys.readouterr().out)
    assert board["level"] == "red" and "next" in board
    assert len(sent) == 1 and "alm: backup store: no copy yet (red until the first one)" in sent[0][1]


def test_status_without_alert_sends_nothing(tmp_path, capsys, monkeypatch):
    cfg = write_config(tmp_path)
    monkeypatch.setattr(cli, "NOTIFY", lambda *a: pytest.fail("alerted"))
    monkeypatch.setattr(status, "RUNNER", lambda argv, cwd: (113, ""))
    assert cli.main(["status", "--config", str(cfg)]) == 0


def test_completion_loads_in_bash_and_offers_subverb(tmp_path):
    script = tmp_path / "c.sh"
    script.write_text(cli.completion_script() + 'COMP_WORDS=(metalm-ops backup o); COMP_CWORD=2; _metalm_ops; echo "${COMPREPLY[@]}"\n')
    out = subprocess.run(["/bin/bash", str(script)], capture_output=True, text=True, check=True).stdout.split()
    assert out == ["offsite"]


@pytest.mark.parametrize(
    "wakes, ok",
    [
        ("  wakeorpoweron at 3:25AM every day", True),
        ("  wakepoweron at 3:00AM every day", True),
        ("  wakeorpoweron at 2:59AM every day", False),
        ("  wakeorpoweron at 3:30AM every day", False),
        ("  wakeorpoweron at 3:25PM every day", False),
        ("", False),
    ],
)
def test_wake_must_fall_1_to_30_minutes_before(wakes, ok):
    assert doctor.wake_covers((3, 30), doctor.wake_times(wakes)) is ok


def test_backup_plist_runs_at_0330_and_holds_no_owner_details(tmp_path):
    cfg = make_cfg(tmp_path)
    text = schedule.render(cfg, "backup", checkout=Path("/repo"))
    plist = plistlib.loads(text.encode())
    assert plist["Label"] == "com.example.metalm.backup"
    assert plist["StartCalendarInterval"] == {"Hour": 3, "Minute": 30}
    assert plist["ProgramArguments"] == ["/bin/bash", "/repo/scripts/nightly-backup.sh"]
    path = tmp_path / "p.plist"
    path.write_text(text)
    assert schedule.start_time(path) == (3, 30)
    for name in ("backup", "serve"):
        template = (ROOT / "src" / "metalm_ops" / "templates" / f"{name}.plist").read_text()
        assert "@LABEL@" in template and "nagarkar" not in template and "/Users/" not in template


def test_serve_plist_keeps_alive(tmp_path):
    plist = plistlib.loads(schedule.render(make_cfg(tmp_path), "serve", checkout=Path("/repo")).encode())
    assert plist["KeepAlive"] is True and plist["ProgramArguments"] == ["/repo/metalm-ops.sh", "serve"]


# The nightly job script, run as a copy in a stand-in checkout whose CLI is a stub.


def stand_in(tmp_path, fail: set[str], sleep_in: str = "") -> tuple[Path, dict]:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "nightly-backup.sh", repo / "scripts" / "nightly-backup.sh")
    cases = "".join(f'  "{v}") exit 3;;\n' for v in fail)
    sleeper = f'  "{sleep_in}") sleep 30;;\n' if sleep_in else ""
    (repo / "metalm-ops.sh").write_text(f'#!/bin/bash\necho "$*" >> "{tmp_path}/calls"\ncase "$*" in\n{cases}{sleeper}esac\nexit 0\n')
    (repo / "metalm-ops.sh").chmod(0o755)
    notify = tmp_path / "notify"
    notify.write_text(f'#!/bin/bash\necho "$*" >> "{tmp_path}/alerts"\n')
    notify.chmod(0o755)
    env = {**os.environ, "HOME": str(tmp_path / "home"), "METALM_NOTIFY_CMD": str(notify), "METALM_CAFFEINATED": "1"}
    return repo, env


def test_nightly_clean_run_is_silent(tmp_path):
    repo, env = stand_in(tmp_path, set())
    subprocess.run(["/bin/bash", str(repo / "scripts" / "nightly-backup.sh")], env=env, check=True)
    assert (tmp_path / "calls").read_text().splitlines() == ["doctor", "backup run", "backup offsite", "status --alert"]
    assert not (tmp_path / "alerts").exists()
    assert len(list((tmp_path / "home" / ".local" / "state" / "metalm" / "ops" / "logs").glob("backup-*.log"))) == 1


def test_nightly_failures_named_once_rest_still_run(tmp_path):
    repo, env = stand_in(tmp_path, {"doctor", "backup offsite"})
    subprocess.run(["/bin/bash", str(repo / "scripts" / "nightly-backup.sh")], env=env, check=True)
    assert len((tmp_path / "calls").read_text().splitlines()) == 4
    alerts = (tmp_path / "alerts").read_text().splitlines()
    assert len(alerts) == 1 and "failed: doctor, off-site." in alerts[0]


def test_nightly_killed_run_says_so(tmp_path):
    repo, env = stand_in(tmp_path, set(), sleep_in="backup offsite")
    proc = subprocess.Popen(["/bin/bash", str(repo / "scripts" / "nightly-backup.sh")], env=env)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and "backup offsite" not in ((tmp_path / "calls").read_text() if (tmp_path / "calls").exists() else ""):
        time.sleep(0.05)
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=40)
    assert "the run itself" in (tmp_path / "alerts").read_text()
