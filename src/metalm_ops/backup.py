"""Local backups: a verified SQLite copy of every listed database, one folder per run.

A run writes `<local_dir>/<UTC stamp>.partial/<repo>/<name>.sqlite`, renames
the folder to `<UTC stamp>` when every database was tried, keeps the newest
`keep_local` folders and appends one row to `runs.jsonl`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from metalm_ops.config import Config, Database

STAMP_FORMAT = "%Y%m%dT%H%M%SZ"
STAMP_RE = re.compile(r"^\d{8}T\d{6}Z$")


@dataclass(frozen=True, slots=True)
class Item:
    repo: str
    name: str
    ok: bool
    detail: str  # bytes copied, or why it failed
    bytes: int = 0


def unmounted_volume(path: Path) -> str | None:
    """The /Volumes/<name> a path needs when that volume is not mounted, else None."""
    parts = path.parts
    if len(parts) > 2 and parts[1] == "Volumes":
        volume = Path("/", "Volumes", parts[2])
        if not os.path.ismount(volume):
            return str(volume)
    return None


def integrity(path: Path) -> str:
    """`PRAGMA integrity_check` on a file: "ok", or what SQLite found wrong."""
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            return con.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            con.close()
    except sqlite3.DatabaseError as exc:
        return str(exc)


def copy_database(source: Path, dest: Path) -> int:
    """Copy one SQLite database with the online backup API, check the copy, return its size.

    Raises OSError or sqlite3.Error; a copy that fails its integrity check is
    removed before the error is raised.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        out = sqlite3.connect(dest)
        try:
            src.backup(out)
        finally:
            out.close()
    finally:
        src.close()
    result = integrity(dest)
    if result != "ok":
        dest.unlink(missing_ok=True)
        raise sqlite3.DatabaseError(f"integrity_check on the copy said: {result}")
    return dest.stat().st_size


def back_up(db: Database, run_dir: Path) -> Item:
    volume = unmounted_volume(db.path)
    if volume:
        return Item(db.repo, db.name, False, f"volume {volume} is not mounted")
    if not db.path.is_file():
        return Item(db.repo, db.name, False, f"no database at {db.path}")
    try:
        size = copy_database(db.path, run_dir / db.repo / f"{db.name}.sqlite")
    except (OSError, sqlite3.Error) as exc:
        return Item(db.repo, db.name, False, f"copy failed: {exc}")
    return Item(db.repo, db.name, True, f"{size} bytes", size)


def run_dirs(local_dir: Path) -> list[Path]:
    """Finished run folders, oldest first."""
    if not local_dir.is_dir():
        return []
    return sorted(p for p in local_dir.iterdir() if p.is_dir() and STAMP_RE.match(p.name))


def prune(local_dir: Path, keep: int) -> list[Path]:
    """Delete all but the newest `keep` run folders and any leftover .partial folders; return what went."""
    gone = []
    for p in local_dir.iterdir() if local_dir.is_dir() else []:
        if p.is_dir() and p.name.endswith(".partial") and STAMP_RE.match(p.name.removesuffix(".partial")):
            shutil.rmtree(p)
            gone.append(p)
    finished = run_dirs(local_dir)
    for p in finished[: max(0, len(finished) - keep)]:
        shutil.rmtree(p)
        gone.append(p)
    return gone


def record(cfg: Config, row: dict) -> None:
    """Append one run row to runs.jsonl in the state folder."""
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    with (cfg.state_dir / "runs.jsonl").open("a") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def read_runs(cfg: Config) -> list[dict]:
    path = cfg.state_dir / "runs.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a torn last line from a killed run; the next run appends a whole one
    return rows


def run(cfg: Config, *, now: datetime | None = None, dry_run: bool = False) -> dict:
    """Back up every listed database; return the run row (also recorded unless dry_run)."""
    started = time.monotonic()
    now = now or datetime.now(UTC)
    stamp = now.strftime(STAMP_FORMAT)
    local_dir = cfg.backup.local_dir
    if dry_run:
        items = [Item(d.repo, d.name, True, f"would copy {d.path}") for d in cfg.databases]
        return {"kind": "local", "ts": now.isoformat(), "ok": True, "dry_run": True, "dir": str(local_dir / stamp), "items": [asdict(i) for i in items]}
    if not local_dir.parent.is_dir():
        raise FileNotFoundError(f"{local_dir.parent} does not exist")
    partial = local_dir / f"{stamp}.partial"
    partial.mkdir(parents=True, exist_ok=True)
    items = [back_up(db, partial) for db in cfg.databases]
    final = local_dir / stamp
    partial.rename(final)
    pruned = prune(local_dir, cfg.backup.keep_local)
    row = {
        "kind": "local",
        "ts": now.isoformat(),
        "ok": all(i.ok for i in items),
        "dir": str(final),
        "items": [asdict(i) for i in items],
        "pruned": len(pruned),
        "duration_ms": int((time.monotonic() - started) * 1000),
    }
    record(cfg, row)
    return row


def latest_copies(cfg: Config) -> dict[tuple[str, str], datetime]:
    """When each database was last copied successfully, from the run folders on disk."""
    found: dict[tuple[str, str], datetime] = {}
    for d in run_dirs(cfg.backup.local_dir):
        when = datetime.strptime(d.name, STAMP_FORMAT).replace(tzinfo=UTC)
        for db in cfg.databases:
            if (d / db.repo / f"{db.name}.sqlite").is_file():
                found[(db.repo, db.name)] = when
    return found
