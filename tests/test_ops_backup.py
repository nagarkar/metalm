"""Local backups and ops.toml validation.

Sources: the owner's rules in metalm_ops (nightly local copies, keep 7, one
central gitignored list) and scheduling.md (an irreplaceable database needs a
verified copy; an unmounted volume is an error, never a created folder).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from metalm_ops import backup
from metalm_ops.config import ConfigError, parse
from ops_fixtures import make_cfg, make_db


def test_copy_is_complete_and_verified(tmp_path):
    cfg = make_cfg(tmp_path)
    row = backup.run(cfg, now=datetime(2026, 10, 26, 10, 30, tzinfo=UTC))
    assert row["ok"] and row["items"][0]["ok"]
    copy = tmp_path / "backups" / "20261026T103000Z" / "alm" / "store.sqlite"
    assert sqlite3.connect(copy).execute("SELECT count(*) FROM t").fetchone()[0] == 3
    assert backup.read_runs(cfg)[-1]["dir"] == str(copy.parents[1])


def test_copy_while_writer_holds_wal(tmp_path):
    db = make_db(tmp_path / "data" / "live.sqlite")
    writer = sqlite3.connect(db)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("INSERT INTO t (v) VALUES ('uncheckpointed')")
    writer.commit()  # the row sits in the -wal file; a plain file copy would miss it
    cfg = make_cfg(tmp_path, databases=[{"repo": "alm", "name": "live", "path": str(db)}])
    row = backup.run(cfg)
    copy = backup.run_dirs(cfg.backup.local_dir)[-1] / "alm" / "live.sqlite"
    assert row["ok"]
    assert sqlite3.connect(copy).execute("SELECT count(*) FROM t").fetchone()[0] == 4
    writer.close()


def test_corrupt_copy_fails(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path)
    monkeypatch.setattr(backup, "integrity", lambda path: "*** in database main ***\nPage 2 is never used")
    row = backup.run(cfg)
    assert not row["ok"]
    assert "integrity_check on the copy said: *** in database main" in row["items"][0]["detail"]
    assert not (backup.run_dirs(cfg.backup.local_dir)[-1] / "alm" / "store.sqlite").exists()


def test_integrity_sees_real_damage(tmp_path):
    db = make_db(tmp_path / "d.sqlite", rows=500)
    assert backup.integrity(db) == "ok"
    raw = bytearray(db.read_bytes())
    raw[4096 : 4096 + 12] = b"\x07" * 12  # break the b-tree header of page 2, the table
    db.write_bytes(bytes(raw))
    assert backup.integrity(db) != "ok"


def test_unmounted_volume_is_error(tmp_path):
    cfg = make_cfg(tmp_path, databases=[{"repo": "alm", "name": "x", "path": "/Volumes/NoSuchDrive-metalm-test/alm/x.sqlite"}])
    row = backup.run(cfg)
    assert row["items"][0] == {"repo": "alm", "name": "x", "ok": False, "detail": "volume /Volumes/NoSuchDrive-metalm-test is not mounted", "bytes": 0}
    assert not row["ok"]


def test_missing_database_is_error_others_still_copied(tmp_path):
    good = make_db(tmp_path / "data" / "good.sqlite")
    cfg = make_cfg(
        tmp_path, databases=[{"repo": "alm", "name": "gone", "path": str(tmp_path / "nope.sqlite")}, {"repo": "blm", "name": "good", "path": str(good)}]
    )
    row = backup.run(cfg)
    assert [i["ok"] for i in row["items"]] == [False, True]


def test_keeps_last_seven_runs(tmp_path):
    cfg = make_cfg(tmp_path)
    start = datetime(2026, 10, 1, 10, 30, tzinfo=UTC)
    for day in range(9):
        backup.run(cfg, now=start + timedelta(days=day))
    names = [p.name for p in backup.run_dirs(cfg.backup.local_dir)]
    assert names == [(start + timedelta(days=d)).strftime("%Y%m%dT%H%M%SZ") for d in range(2, 9)]


def test_leftover_partial_folder_is_removed(tmp_path):
    cfg = make_cfg(tmp_path)
    (cfg.backup.local_dir / "20261001T000000Z.partial").mkdir(parents=True)
    backup.run(cfg)
    assert not any(p.name.endswith(".partial") for p in cfg.backup.local_dir.iterdir())


def test_missing_backup_parent_creates_nothing(tmp_path):
    cfg = make_cfg(tmp_path, local_dir=str(tmp_path / "absent" / "lm"))
    with pytest.raises(FileNotFoundError):
        backup.run(cfg)
    assert not (tmp_path / "absent").exists()


def test_dry_run_writes_nothing(tmp_path):
    cfg = make_cfg(tmp_path)
    row = backup.run(cfg, dry_run=True)
    assert row["dry_run"] and not cfg.backup.local_dir.exists() and not cfg.state_dir.exists()


def test_latest_copies_per_database(tmp_path):
    cfg = make_cfg(tmp_path)
    when = datetime(2026, 10, 26, 10, 30, tzinfo=UTC)
    backup.run(cfg, now=when)
    assert backup.latest_copies(cfg) == {("alm", "store"): when}


@pytest.mark.parametrize(
    "change, message",
    [
        ({"colour": 1}, "unknown key 'colour'"),
        ({"backup": {"local_dir": "/x", "keep_local": "7"}}, "backup.keep_local: expected int"),
        ({"backup": {"local_dir": "/x", "keep_local": 0}}, "keep_local: must be at least 1"),
        ({"backup": {"local_dir": "/x", "keep_daily": -1}}, "backup.keep_daily: must not be negative"),
        ({"backup": {"local_dir": "/x", "check_subset": "five"}}, "check_subset"),
        ({"backup": {}}, "local_dir is required"),
        ({"database": [{"repo": "a", "name": "b"}]}, "database[0]: path is required"),
        ({"database": [{"repo": "A!", "name": "b", "path": "/x"}]}, "lowercase"),
        ({"database": [{"repo": "a", "name": "b", "path": "/x"}, {"repo": "a", "name": "b", "path": "/y"}]}, "listed twice"),
        ({"database": {"repo": "a"}}, "write [[database]]"),
        ({"repo": [{"name": "a", "path": "/x", "ports": [True]}]}, "repo[0].ports: expected port numbers"),
        ({"repo": [{"name": "a", "path": "/x", "port": 1}]}, "unknown key 'port'"),
        ({"label_prefix": "bad label"}, "label_prefix is required"),
        ({"port": 0}, "port is required"),
    ],
)
def test_config_rejects_by_name(change, message):
    data = {"label_prefix": "com.example", "port": 8700, "backup": {"local_dir": "/x"}}
    data.update(change)
    with pytest.raises(ConfigError, match=message.replace("[", r"\[").replace("]", r"\]").replace(".", r"\.")):
        parse(data)


def test_example_config_parses():
    import tomllib
    from pathlib import Path

    cfg = parse(tomllib.loads((Path(__file__).parents[1] / "ops.example.toml").read_text()))
    assert (cfg.backup.keep_local, cfg.backup.keep_daily, cfg.backup.keep_weekly, cfg.backup.keep_monthly) == (7, 7, 4, 12)
    assert cfg.port == 8700
