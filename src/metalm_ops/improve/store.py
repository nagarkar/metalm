"""Durable run and call rows; all reporting opens SQLite read-only.

Call rows are reserved before invoking a provider, so a crashed process still
counts against the daily Codex cap. Days follow the owner's local timezone.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from metalm_ops.config import Config

SCHEMA = """
CREATE TABLE IF NOT EXISTS run (
 run_id TEXT NOT NULL, repo TEXT NOT NULL, started TEXT NOT NULL,
 finished TEXT NOT NULL, outcome TEXT NOT NULL, pr_number INTEGER,
 pr_url TEXT, category TEXT, title TEXT, reason TEXT NOT NULL,
 codex_calls INTEGER NOT NULL, model TEXT NOT NULL,
 checkout_updated INTEGER NOT NULL, PRIMARY KEY(run_id, repo)
);
CREATE TABLE IF NOT EXISTS call (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, repo TEXT NOT NULL,
 started TEXT NOT NULL, day TEXT NOT NULL, role TEXT NOT NULL,
 provider TEXT NOT NULL, model TEXT NOT NULL, prompt_id TEXT NOT NULL,
 prompt_sha256 TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 duration REAL NOT NULL, outcome TEXT NOT NULL, cost REAL,
 billing TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS call_day ON call(day);
CREATE TABLE IF NOT EXISTS step (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, repo TEXT NOT NULL,
 fingerprint TEXT NOT NULL, step TEXT NOT NULL, outcome TEXT NOT NULL,
 recorded TEXT NOT NULL, details TEXT NOT NULL
);
"""


# Columns added after the first ledgers existed (nagarkar/metalm#97); initialize adds any that are missing.
ADDED_COLUMNS = (("finding", "TEXT"), ("tokens_in", "INTEGER"), ("tokens_cached", "INTEGER"), ("tokens_out", "INTEGER"))


def path(config: Config) -> Path:
    """The improvement ledger in this configuration's state directory."""
    return config.state_dir / "improve" / "runs.sqlite"


def initialize(config: Config) -> None:
    """Create the ledger for a real invocation, never for a preview or status."""
    database = path(config)
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database)) as connection:
        connection.executescript(SCHEMA)
        present = {row[1] for row in connection.execute("PRAGMA table_info(run)")}
        for column, kind in ADDED_COLUMNS:
            if column not in present:
                connection.execute(f"ALTER TABLE run ADD COLUMN {column} {kind}")
        connection.commit()


def record_run(config: Config, row: dict) -> None:
    """Append a completed repository outcome using the fixed public run columns."""
    columns = (
        "run_id",
        "repo",
        "started",
        "finished",
        "outcome",
        "pr_number",
        "pr_url",
        "category",
        "title",
        "reason",
        "codex_calls",
        "model",
        "checkout_updated",
        *(column for column, _ in ADDED_COLUMNS),
    )
    with closing(sqlite3.connect(path(config))) as connection:
        connection.execute(f"INSERT INTO run ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", [row.get(column) for column in columns])
        connection.commit()


def reserve_call(config: Config, row: dict) -> int:
    """Persist an attempted call before executing the provider command."""
    columns = (
        "run_id",
        "repo",
        "started",
        "day",
        "role",
        "provider",
        "model",
        "prompt_id",
        "prompt_sha256",
        "payload_sha256",
        "duration",
        "outcome",
        "cost",
        "billing",
    )
    with closing(sqlite3.connect(path(config))) as connection:
        cursor = connection.execute(f"INSERT INTO call ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", [row[column] for column in columns])
        connection.commit()
        return int(cursor.lastrowid)


def finish_call(config: Config, call_id: int, *, duration: float, outcome: str, cost: float | None) -> None:
    """Finish precisely the reserved call, including failed and malformed replies."""
    with closing(sqlite3.connect(path(config))) as connection:
        connection.execute("UPDATE call SET duration=?, outcome=?, cost=? WHERE id=?", (duration, outcome, cost, call_id))
        connection.commit()


def read_runs(config: Config, repo: str | None = None, limit: int = 7) -> list[dict]:
    """Newest completed rows, with no directory or database creation."""
    if not path(config).exists():
        return []
    with closing(sqlite3.connect(path(config).resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        query = "SELECT * FROM run"
        parameters: list = []
        if repo is not None:
            query += " WHERE repo=?"
            parameters.append(repo)
        query += " ORDER BY finished DESC, rowid DESC LIMIT ?"
        parameters.append(limit)
        rows = [dict(row) for row in connection.execute(query, parameters)]
        from metalm_ops.improve.lenses import OLD_NAMES

        return [{**row, "lens": OLD_NAMES.get(row["category"], row["category"])} for row in rows]


def usage(config: Config) -> dict:
    """Today's provider calls and reported Claude cost, read without writing."""
    if not path(config).exists():
        return {"codex_calls": 0, "review_cost_usd": 0.0, "calls": 0}
    with closing(sqlite3.connect(path(config).resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        row = connection.execute(
            "SELECT COALESCE(SUM(provider='openai'), 0), COALESCE(SUM(cost), 0), COUNT(*) FROM call WHERE day=?",
            (datetime.now().astimezone().date().isoformat(),),
        ).fetchone()
        return {"codex_calls": row[0], "review_cost_usd": row[1], "calls": row[2]}


def record_step(config: Config, *, run_id: str, repo: str, fingerprint: str, step: str, outcome: str, details: dict) -> None:
    """Append an immutable brake attempt or completion, including its remote IDs."""
    initialize(config)
    with closing(sqlite3.connect(path(config))) as connection:
        connection.execute(
            "INSERT INTO step (run_id,repo,fingerprint,step,outcome,recorded,details) VALUES (?,?,?,?,?,?,?)",
            (run_id, repo, fingerprint, step, outcome, datetime.now().astimezone().isoformat(), json.dumps(details)),
        )
        connection.commit()


def read_steps(config: Config, repo: str, fingerprint: str | None = None) -> list[dict]:
    """Read chronological brake events without creating or migrating a ledger."""
    if not path(config).exists():
        return []
    with closing(sqlite3.connect(path(config).resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='step'").fetchone():
            return []
        connection.row_factory = sqlite3.Row
        query = "SELECT * FROM step WHERE repo=?"
        parameters = [repo]
        if fingerprint is not None:
            query += " AND fingerprint=?"
            parameters.append(fingerprint)
        return [{**dict(row), "details": json.loads(row["details"])} for row in connection.execute(query + " ORDER BY id", parameters)]
