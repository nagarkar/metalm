"""Strict loader for `ops.toml`, the one gitignored list of what metalm watches.

Unknown sections and keys, wrong types and negative counts are rejected by
name, so a typo never silently drops a database from the backup.
"""

from __future__ import annotations

import math
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
class ImproveRepo:
    name: str
    test: str
    merge: str = "merge"
    exclude: tuple[str, ...] = ()
    deploy: str = ""
    lenses: tuple[str, ...] | None = None
    thresholds: dict = field(default_factory=dict)  # overrides of signals.THRESHOLDS for this repo


@dataclass(frozen=True, slots=True)
class Improve:
    slots: tuple[str, ...] = ("09:10", "13:10", "17:10", "21:10")
    max_lateness_min: int = 60
    lines_per_run: int = 400
    decay: tuple[float, ...] = (1.0, 1.0, 0.75, 0.5, 0.5, 0.25, 0.25)
    enabled: bool = True
    codex_bin: str = "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"
    model: str = "gpt-6-astra"
    effort: str = "high"
    max_codex_calls_per_day: int = 20
    claude_bin: str = "~/.local/bin/claude"
    review_model: str = "claude-opus-5-5"
    max_review_cost_usd_per_day: float = 2.00
    propose_timeout_min: int = 20
    review_timeout_min: int = 8
    ci_timeout_min: int = 15
    max_files: int = 5
    max_changed_lines: int = 150
    repos: tuple[ImproveRepo, ...] = ()


@dataclass(frozen=True, slots=True)
class Config:
    label_prefix: str
    backup: Backup
    port: int  # the dashboard's loopback port: required, no default (ports live in the served-apps table)
    databases: tuple[Database, ...] = ()
    repos: tuple[Repo, ...] = field(default_factory=tuple)
    state_dir: Path = STATE_DIR
    improve: Improve | None = None

    @property
    def improve_label(self) -> str:
        return f"{self.label_prefix}.metalm.improve"

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
KNOWN["improve"] = {
    "slots": list,
    "max_lateness_min": int,
    "lines_per_run": int,
    "decay": list,
    "enabled": bool,
    "codex_bin": str,
    "model": str,
    "effort": str,
    "max_codex_calls_per_day": int,
    "claude_bin": str,
    "review_model": str,
    "max_review_cost_usd_per_day": float,
    "propose_timeout_min": int,
    "review_timeout_min": int,
    "ci_timeout_min": int,
    "max_files": int,
    "max_changed_lines": int,
    "repo": list,
}
KNOWN["improve.repo"] = {"name": str, "test": str, "merge": str, "exclude": list, "deploy": str, "lenses": list, "thresholds": dict}
TABLES = {"backup", "improve"}
ARRAYS = {"database", "repo"}


def _check(where: str, table: dict, known: dict) -> None:
    if not isinstance(table, dict):
        raise ConfigError(f"{where}: expected a table")
    for key, value in table.items():
        if key not in known:
            raise ConfigError(f"{where}: unknown key {key!r}")
        want = known[key]
        matches = isinstance(value, (int, float)) if want is float else isinstance(value, want)
        if not matches or (want in (int, float) and isinstance(value, bool)):
            raise ConfigError(f"{where}.{key}: expected {want.__name__}, got {type(value).__name__}")
        if want is float:
            try:
                finite = math.isfinite(value)
            except OverflowError:
                finite = False
            if not finite:
                raise ConfigError(f"{where}.{key}: must be finite")
        if want in (int, float) and value < 0:
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
        improve=_improve(data, repos),
    )


def _improve(data: dict, repositories: list[Repo]) -> Improve | None:
    if "improve" not in data:
        return None
    settings = data["improve"]
    _check("improve", settings, KNOWN["improve"])
    slots = settings.get("slots", Improve().slots)
    if not 1 <= len(slots) <= 8 or any(not isinstance(slot, str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", slot) for slot in slots):
        raise ConfigError("improve.slots: expected 1 to 8 HH:MM times")
    if any(left >= right for left, right in zip(slots, slots[1:])):
        raise ConfigError("improve.slots: must be strictly increasing")
    decay = settings.get("decay", Improve().decay)
    if len(decay) != 7 or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1 for value in decay):
        raise ConfigError("improve.decay: expected seven finite numbers between 0 and 1")
    if settings.get("lines_per_run", 400) < 1:
        raise ConfigError("improve.lines_per_run: must be positive")
    settings = {**settings, "slots": tuple(slots), "decay": tuple(float(value) for value in decay)}
    configured = {repository.name: repository for repository in repositories}
    selected: list[ImproveRepo] = []
    seen: set[str] = set()
    for index, row in enumerate(settings.get("repo", [])):
        location = f"improve.repo[{index}]"
        _check(location, row, KNOWN["improve.repo"])
        for key in ("name", "test"):
            if not row.get(key):
                raise ConfigError(f"{location}.{key}: is required")
        name = row["name"]
        if not NAME_RE.fullmatch(name):
            raise ConfigError(f"{location}.name: expected lowercase letters, digits, - or _")
        if name not in configured:
            raise ConfigError(f"{location}.name: {name!r} has no [[repo]] row")
        if name in seen:
            raise ConfigError(f"{location}.name: {name!r} is listed twice")
        seen.add(name)
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", configured[name].github):
            raise ConfigError(f"{location}.name: {name!r} needs repo.github in owner/repository form")
        if row.get("merge", "merge") not in {"merge", "squash", "rebase"}:
            raise ConfigError(f"{location}.merge: expected merge, squash or rebase")
        excluded = row.get("exclude", [])
        if not all(isinstance(pattern, str) and pattern for pattern in excluded):
            raise ConfigError(f"{location}.exclude: expected nonempty glob strings")
        try:
            row["test"].format(venv="venv", worktree="worktree")
        except (KeyError, ValueError, IndexError, AttributeError) as error:
            raise ConfigError(f"{location}.test: use only {{venv}} and {{worktree}} placeholders") from error
        from metalm_ops.improve.lenses import NAMES

        chosen = row.get("lenses")
        if chosen is not None and any(not isinstance(name, str) or name not in NAMES for name in chosen):
            raise ConfigError(f"{location}.lenses: unknown lens; expected {', '.join(NAMES)}")
        if chosen is not None and len(set(chosen)) != len(chosen):
            raise ConfigError(f"{location}.lenses: duplicate lens")
        from metalm_ops.improve.signals import THRESHOLDS

        limits = row.get("thresholds", {})
        for key, value in limits.items():
            if key not in THRESHOLDS:
                raise ConfigError(f"{location}.thresholds: unknown {key!r}; expected {', '.join(THRESHOLDS)}")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ConfigError(f"{location}.thresholds.{key}: expected a positive number")
        selected.append(ImproveRepo(**{**row, "exclude": tuple(excluded), "lenses": tuple(chosen) if chosen is not None else None}))
    return Improve(**{key: value for key, value in settings.items() if key != "repo"}, repos=tuple(selected))


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
