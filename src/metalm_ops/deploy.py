"""`metalm-ops deploy` and `metalm-ops discover`: the two jobs this session kept writing by hand.

deploy: after a metalm-ops PR merges, bring the main checkout to origin/main,
restart the dashboard through its launch agent, wait for /health and collect
once. It works only on a clean main checkout on `main` (coding.md, owner rule
of 2026-10-25) and never starts a server itself.

discover: list the SQLite files in the usual places (the metalm skill's
"Finding databases"), marking which ops.toml already lists. Read-only; it
reads only the path keys of each repo's `.env`.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from metalm_ops import schedule, status
from metalm_ops.config import Config

ENV_PATH_KEY = re.compile(r"^([A-Z0-9_]+_(?:WORKSPACE|DB|DIR))\s*=\s*(.*)$")
DB_SUFFIXES = (".sqlite", ".sqlite3", ".db")
SKIP_PARTS = {"backups", "node_modules", ".venv", ".git", "cache", "zipline_root", "runs"}
SKIP_NAME = re.compile(r"before|backup|\.pre-", re.IGNORECASE)
HEALTH_WAIT = 30.0

RUNNER = None  # tests set a fake: (argv, cwd) -> (returncode, output)
POST = None  # tests set a fake: url -> status code


class DeployError(Exception):
    """deploy cannot go ahead; the message names the fix."""


def _run(argv: list[str], cwd: Path) -> tuple[int, str]:
    if RUNNER is not None:
        return RUNNER(argv, cwd)
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=300)
    return proc.returncode, proc.stdout + proc.stderr


def _post(url: str) -> int:
    if POST is not None:
        return POST(url)
    req = urllib.request.Request(url, method="POST", data=b"")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, OSError, TimeoutError):
        return 0


def deploy(cfg: Config, checkout: Path = schedule.CHECKOUT, *, dry_run: bool = False) -> list[str]:
    """Pull main into the main checkout, restart the dashboard, wait for /health, collect; return the steps done."""
    code, branch = _run(["git", "branch", "--show-current"], checkout)
    if code != 0 or branch.strip() != "main":
        raise DeployError(f"{checkout} is on {branch.strip() or 'a detached HEAD'}, not main. Commit or push that work, then: git -C {checkout} switch main")
    code, dirty = _run(["git", "status", "--porcelain", "--untracked-files=no"], checkout)
    if code != 0 or dirty.strip():
        raise DeployError(f"{checkout} has uncommitted changes. Commit or move them, then rerun: metalm-ops deploy")
    restart = ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{cfg.serve_label}"]
    plan = ["git pull --ff-only origin main", " ".join(restart), f"wait for /health on {cfg.port}", "POST /refresh"]
    if dry_run:
        return [f"would: {step}" for step in plan]
    done = []
    code, out = _run(["git", "pull", "--ff-only", "origin", "main"], checkout)
    if code != 0:
        raise DeployError(f"git pull --ff-only failed: {status._first_line(out)}")
    _, head = _run(["git", "log", "--oneline", "-1"], checkout)
    done.append(f"main at {head.strip()}")
    code, out = _run(restart, checkout)
    if code != 0:
        raise DeployError(f"restart failed: {status._first_line(out)}. Is the agent loaded? metalm-ops doctor")
    done.append(f"restarted {cfg.serve_label}")
    deadline = time.monotonic() + HEALTH_WAIT
    while status.health(cfg.port).level != status.GREEN:
        if time.monotonic() > deadline:
            raise DeployError(f"/health on {cfg.port} did not answer within {HEALTH_WAIT:.0f} s. Read ~/.local/state/metalm/ops/logs/serve.log")
        time.sleep(0.5)
    done.append("/health ok")
    code = _post(f"http://127.0.0.1:{cfg.port}/refresh")
    if code not in (200, 303):
        raise DeployError(f"refresh answered {code or 'nothing'}. Read ~/.local/state/metalm/ops/logs/serve.log")
    done.append("collected")
    return done


@dataclass(frozen=True, slots=True)
class Found:
    repo: str
    path: Path
    bytes: int
    listed: bool


def env_paths(repo_path: Path) -> list[Path]:
    """Values of the repo's .env keys ending in _WORKSPACE, _DB or _DIR; other keys are never read into memory."""
    env = repo_path / ".env"
    if not env.is_file():
        return []
    found = []
    for line in env.read_text(errors="replace").splitlines():
        m = ENV_PATH_KEY.match(line.strip())
        if m and m.group(2).strip().strip("\"'"):
            found.append(Path(m.group(2).strip().strip("\"'")).expanduser())
    return found


def cli_names(repo_path: Path) -> list[str]:
    """Console-script names from the repo's pyproject.toml files (root and one folder down, where authorllm keeps its CLI).

    A CLI may keep state under its own name (authorllm -> ~/.authorlm).
    """
    names: list[str] = []
    for pyproject in [repo_path / "pyproject.toml", *sorted(repo_path.glob("*/pyproject.toml"))]:
        try:
            names += [n for n in tomllib.loads(pyproject.read_text()).get("project", {}).get("scripts", {}) if n not in names]
        except (OSError, tomllib.TOMLDecodeError):
            continue
    return names


def _databases(root: Path, depth: int = 4) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix in DB_SUFFIXES else []
    out = []
    base = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root) if root.is_dir() else []:
        dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS and not d.endswith(".photoslibrary") and len(Path(dirpath).parts) - base < depth]
        out += [Path(dirpath) / f for f in filenames if f.endswith(DB_SUFFIXES)]
    return out


def places(cfg: Config, home: Path, volumes: Path = Path("/Volumes")) -> dict[str, list[Path]]:
    """repo -> folders and files to search, in the skill's order."""
    drives = [v for v in volumes.iterdir() if v.is_dir()] if volumes.is_dir() else []
    out = {}
    for repo in cfg.repos:
        names = [repo.name, *cli_names(repo.path)]
        out[repo.name] = env_paths(repo.path) + [home / f".{n}" for n in names] + [d / n for d in drives for n in names]
    return out


def discover(cfg: Config, home: Path | None = None, volumes: Path = Path("/Volumes")) -> list[Found]:
    """Every non-empty SQLite file in the usual places, once, with whether ops.toml lists it."""
    listed = {d.path.resolve() for d in cfg.databases}
    seen: set[Path] = set()
    found = []
    for repo, roots in places(cfg, home or Path.home(), volumes).items():
        for root in roots:
            for path in _databases(root):
                real = path.resolve()
                if real in seen or SKIP_NAME.search(path.name):
                    continue
                size = path.stat().st_size
                if size == 0:
                    continue
                seen.add(real)
                found.append(Found(repo, path, size, real in listed))
    return found
