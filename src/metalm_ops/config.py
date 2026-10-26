"""Strict loader for `ops.toml`, the one gitignored list of what metalm watches.

Unknown sections and keys, wrong types and negative counts are rejected by
name, so a typo never silently drops a database from the backup.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PATH = Path("~/.claude/metalm/ops.toml")  # ~/.claude/metalm links to the main metalm checkout
STATE_DIR = Path("~/.local/state/metalm/ops")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class ConfigError(Exception):
    """ops.toml is missing or wrong; the message names the key."""


@dataclass(frozen=True, slots=True)
class Backup:
    local_dir: Path
    keep_local: int = 7
    b2_bucket: str = ""
    restic_path: str = "metalm"
    keep_daily: int = 7
    keep_weekly: int = 4
    keep_monthly: int = 12
    check_subset: str = "5%"

    @property
    def restic_repo(self) -> str:
        return f"b2:{self.b2_bucket}:{self.restic_path}"


@dataclass(frozen=True, slots=True)
class Database:
    repo: str
    name: str
    path: Path


@dataclass(frozen=True, slots=True)
class Repo:
    name: str
    path: Path
    github: str = ""
    ports: tuple[int, ...] = ()  # loopback ports of its served apps, each answering /health
    agents: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Config:
    label_prefix: str
    backup: Backup
    port: int  # the dashboard's loopback port: required, no default (ports live in the served-apps table)
    databases: tuple[Database, ...] = ()
    repos: tuple[Repo, ...] = field(default_factory=tuple)
    state_dir: Path = STATE_DIR

    @property
    def backup_label(self) -> str:
        return f"{self.label_prefix}.metalm.backup"

    @property
    def serve_label(self) -> str:
        return f"{self.label_prefix}.metalm.ops.serve"


KNOWN = {
    "": {"label_prefix": str, "port": int, "state_dir": str},
    "backup": {
        "local_dir": str,
        "keep_local": int,
        "b2_bucket": str,
        "restic_path": str,
        "keep_daily": int,
        "keep_weekly": int,
        "keep_monthly": int,
        "check_subset": str,
    },
    "database": {"repo": str, "name": str, "path": str},
    "repo": {"name": str, "path": str, "github": str, "ports": list, "agents": list},
}
TABLES = {"backup"}
ARRAYS = {"database", "repo"}


def _check(where: str, table: dict, known: dict) -> None:
    for key, value in table.items():
        if key not in known:
            raise ConfigError(f"{where}: unknown key {key!r}")
        want = known[key]
        if not isinstance(value, want) or (want is int and isinstance(value, bool)):
            raise ConfigError(f"{where}.{key}: expected {want.__name__}, got {type(value).__name__}")
        if want is int and value < 0:
            raise ConfigError(f"{where}.{key}: must not be negative")


def _path(text: str) -> Path:
    return Path(text).expanduser()


def parse(data: dict) -> Config:
    """Validate a parsed ops.toml and build the Config."""
    top = {k: v for k, v in data.items() if k not in TABLES | ARRAYS}
    _check("ops.toml", top, KNOWN[""])
    for key in data:
        if key in ARRAYS and not isinstance(data[key], list):
            raise ConfigError(f"ops.toml: [{key}] must be an array of tables: write [[{key}]]")
    if "label_prefix" not in top or not LABEL_RE.match(top["label_prefix"]):
        raise ConfigError('ops.toml: label_prefix is required, e.g. label_prefix = "com.example"')
    if not 0 < top.get("port", 0) < 65536:
        raise ConfigError("ops.toml: port is required: the dashboard's loopback port from the served-apps table")
    raw_backup = data.get("backup")
    if not isinstance(raw_backup, dict) or "local_dir" not in raw_backup:
        raise ConfigError("ops.toml: [backup] local_dir is required")
    _check("backup", raw_backup, KNOWN["backup"])
    if not re.fullmatch(r"\d{1,2}%", raw_backup.get("check_subset", "5%")):
        raise ConfigError('backup.check_subset: expected a percentage such as "5%"')
    backup = Backup(**{**raw_backup, "local_dir": _path(raw_backup["local_dir"])})
    if backup.keep_local < 1:
        raise ConfigError("backup.keep_local: must be at least 1")

    databases = []
    seen: set[tuple[str, str]] = set()
    for i, row in enumerate(data.get("database", [])):
        where = f"database[{i}]"
        _check(where, row, KNOWN["database"])
        for key in ("repo", "name", "path"):
            if key not in row:
                raise ConfigError(f"{where}: {key} is required")
        if not NAME_RE.match(row["repo"]) or not NAME_RE.match(row["name"]):
            raise ConfigError(f"{where}: repo and name must be lowercase letters, digits, - or _")
        if (row["repo"], row["name"]) in seen:
            raise ConfigError(f"{where}: {row['repo']}/{row['name']} is listed twice")
        seen.add((row["repo"], row["name"]))
        databases.append(Database(row["repo"], row["name"], _path(row["path"])))

    repos = []
    for i, row in enumerate(data.get("repo", [])):
        where = f"repo[{i}]"
        _check(where, row, KNOWN["repo"])
        for key in ("name", "path"):
            if key not in row:
                raise ConfigError(f"{where}: {key} is required")
        agents = row.get("agents", [])
        if not all(isinstance(a, str) and LABEL_RE.match(a) for a in agents):
            raise ConfigError(f"{where}.agents: expected launch agent labels")
        ports = row.get("ports", [])
        if not all(isinstance(p, int) and not isinstance(p, bool) and 0 < p < 65536 for p in ports):
            raise ConfigError(f"{where}.ports: expected port numbers")
        repos.append(Repo(row["name"], _path(row["path"]), row.get("github", ""), tuple(ports), tuple(agents)))

    return Config(
        label_prefix=top["label_prefix"],
        backup=backup,
        port=top["port"],
        databases=tuple(databases),
        repos=tuple(repos),
        state_dir=_path(top.get("state_dir", str(STATE_DIR))),
    )


def load(path: Path | None = None) -> Config:
    """Read ops.toml (default ~/.claude/metalm/ops.toml)."""
    path = (path or DEFAULT_PATH).expanduser()
    if not path.exists():
        raise ConfigError(f"no {path}. Copy ops.example.toml there and fill it in")
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    return parse(data)
