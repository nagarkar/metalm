"""Off-site backups through restic, with a fake runner (no network, no keychain).

Sources: the owner's rules in metalm_ops (B2 retention 7/4/12, weekly 5%
check, secrets only from the keychain) and coding.md#security-and-secrets
(secrets never printed or logged).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from metalm_ops import backup, offsite
from ops_fixtures import make_cfg

SECRET = "s3cr3t-value"


@pytest.fixture
def calls(monkeypatch):
    seen = []

    def fake(argv, env):
        seen.append((argv, env))
        if argv[0] == "/usr/bin/security":
            return 0, SECRET + "\n"
        return 0, "snapshot 1a2b saved\n"

    monkeypatch.setattr(offsite, "RUNNER", fake)
    monkeypatch.setattr(offsite, "restic_path", lambda: "/opt/homebrew/bin/restic")
    return seen


def restic_calls(calls):
    return [(argv[1:], env) for argv, env in calls if argv[0].endswith("restic")]


def test_backup_forget_and_first_check(tmp_path, calls):
    cfg = make_cfg(tmp_path)
    backup.run(cfg, now=datetime(2026, 10, 26, 10, 30, tzinfo=UTC))
    rows = offsite.run(cfg, now=datetime(2026, 10, 26, 10, 31, tzinfo=UTC))
    got = restic_calls(calls)
    assert [r["kind"] for r in rows] == ["offsite", "forget", "check"]
    assert got[0][0] == ["backup", "--tag", "metalm", "--host", "metalm", str(cfg.backup.local_dir / "20261026T103000Z")]
    assert got[1][0] == ["forget", "--tag", "metalm", "--group-by", "host,tags", "--keep-daily", "7", "--keep-weekly", "4", "--keep-monthly", "12", "--prune"]
    assert got[2][0] == ["check", "--read-data-subset=5%"]
    env = got[0][1]
    assert env["RESTIC_REPOSITORY"] == "b2:example-bucket:metalm"
    assert env["RESTIC_PASSWORD"] == SECRET and env["B2_ACCOUNT_ID"] == SECRET and env["B2_ACCOUNT_KEY"] == SECRET


def test_check_runs_weekly_only(tmp_path, calls):
    cfg = make_cfg(tmp_path)
    t0 = datetime(2026, 10, 1, 10, 30, tzinfo=UTC)
    kinds = []
    for day in range(8):
        backup.run(cfg, now=t0 + timedelta(days=day))
        kinds.append([r["kind"] for r in offsite.run(cfg, now=t0 + timedelta(days=day, minutes=1))])
    assert [("check" in k) for k in kinds] == [True, False, False, False, False, False, False, True]


def test_failed_upload_leaves_retention_alone(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path)
    backup.run(cfg)
    monkeypatch.setattr(offsite, "restic_path", lambda: "/opt/homebrew/bin/restic")
    monkeypatch.setattr(offsite, "RUNNER", lambda argv, env: (0, SECRET) if argv[0] == "/usr/bin/security" else (1, "Fatal: unable to open repository"))
    rows = offsite.run(cfg)
    assert [(r["kind"], r["ok"]) for r in rows] == [("offsite", False)]


def test_secret_never_recorded(tmp_path, calls):
    cfg = make_cfg(tmp_path)
    backup.run(cfg)
    offsite.run(cfg)
    assert SECRET not in (cfg.state_dir / "runs.jsonl").read_text()


def test_missing_keychain_entry_names_fix(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path)
    backup.run(cfg)
    monkeypatch.setattr(offsite, "restic_path", lambda: "/opt/homebrew/bin/restic")
    monkeypatch.setattr(offsite, "RUNNER", lambda argv, env: (44, "not found"))
    with pytest.raises(offsite.OffsiteError, match='security add-generic-password -a "\\$USER" -s metalm-b2-key-id -w'):
        offsite.run(cfg)


def test_missing_restic_names_fix(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path)
    backup.run(cfg)
    monkeypatch.setattr(offsite, "restic_path", lambda: None)
    with pytest.raises(offsite.OffsiteError, match="brew install restic"):
        offsite.run(cfg)


def test_no_local_run_names_fix(tmp_path, calls):
    with pytest.raises(offsite.OffsiteError, match="metalm-ops backup run"):
        offsite.run(make_cfg(tmp_path))


def test_dry_run_calls_nothing(tmp_path, calls):
    cfg = make_cfg(tmp_path)
    backup.run(cfg)
    rows = offsite.run(cfg, dry_run=True)
    assert restic_calls(calls) == [] and all(r["dry_run"] for r in rows)
    assert all(json.loads(line)["kind"] == "local" for line in (cfg.state_dir / "runs.jsonl").read_text().splitlines())
