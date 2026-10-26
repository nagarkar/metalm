"""Shared builders for the metalm_ops tests: a config over throwaway folders and real SQLite files."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from metalm_ops.config import parse


def make_db(path: Path, rows: int = 3) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    con.executemany("INSERT INTO t (v) VALUES (?)", [(f"row {i}",) for i in range(rows)])
    con.commit()
    con.close()
    return path


def make_cfg(tmp: Path, databases: list[dict] | None = None, repos: list[dict] | None = None, **backup):
    data = {
        "label_prefix": "com.example",
        "port": 8700,
        "state_dir": str(tmp / "state"),
        "backup": {"local_dir": str(tmp / "backups"), "b2_bucket": "example-bucket", **backup},
        "database": databases if databases is not None else [{"repo": "alm", "name": "store", "path": str(make_db(tmp / "data" / "store.sqlite"))}],
        "repo": repos or [],
    }
    return parse(data)
