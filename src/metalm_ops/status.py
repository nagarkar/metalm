"""Status collector: one green/amber/red row per check, per repo, for the dashboard and `status`.

Reads only local facts plus `gh`: run rows and backup folders on disk, each
app's `/health` on loopback, `launchctl list`, `git`, `gh`, and
`metalm-gendocs --dry-run`. It never opens a repo's database.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from metalm_ops import backup
from metalm_ops.config import Config, Repo

GREEN, AMBER, RED = "green", "amber", "red"
ORDER = {GREEN: 0, AMBER: 1, RED: 2}
FRESH = timedelta(hours=26)
STALE = timedelta(hours=50)
HEALTH_TIMEOUT = 3.0
OLD_PR = timedelta(days=7)
REPOS_MD = Path(__file__).resolve().parents[2] / "docs" / "repos.md"

RUNNER = None  # tests set a fake: (argv, cwd) -> (returncode, output)
FETCH = None  # tests set a fake: url -> status code (0 when unreachable)


@dataclass(frozen=True, slots=True)
class Check:
    check: str
    level: str
    detail: str


def _run(argv: list[str], cwd: Path | None = None) -> tuple[int, str]:
    if RUNNER is not None:
        return RUNNER(argv, cwd)
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)
    return proc.returncode, proc.stdout + proc.stderr


def _fetch(url: str) -> int:
    if FETCH is not None:
        return FETCH(url)
    try:
        with urllib.request.urlopen(url, timeout=HEALTH_TIMEOUT) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, OSError, TimeoutError):
        return 0


def age_level(age: timedelta | None) -> str:
    """Green under 26 h, amber from 26 h to 50 h, red over 50 h or never. (owner)"""
    if age is None or age > STALE:
        return RED
    return GREEN if age < FRESH else AMBER


def _age_text(age: timedelta | None) -> str:
    if age is None:
        return "never"
    hours = age.total_seconds() / 3600
    return f"{hours:.0f} h ago" if hours >= 1 else f"{age.total_seconds() / 60:.0f} min ago"


def health(port: int) -> Check:
    code = _fetch(f"http://127.0.0.1:{port}/health")
    if code == 200:
        return Check(f"app :{port} /health", GREEN, f"port {port}: 200")
    return Check(f"app :{port} /health", RED, f"port {port}: " + (f"HTTP {code}" if code else "no answer in 3 s"))


def agent(label: str) -> Check:
    code, out = _run(["/bin/launchctl", "list", label])
    if code != 0:
        return Check(f"agent {label}", RED, "not loaded")
    pid = re.search(r'"PID"\s*=\s*(\d+)', out)
    status = re.search(r'"LastExitStatus"\s*=\s*(-?\d+)', out)
    last = int(status.group(1)) if status else 0
    running = f"running (pid {pid.group(1)})" if pid else "not running"
    if last != 0:
        return Check(f"agent {label}", AMBER, f"loaded, {running}, last exit {last}")
    return Check(f"agent {label}", GREEN, f"loaded, {running}")


def checkout_row(repo: Repo) -> Check:
    """Red when the repo's main checkout is not on `main` (coding.md, owner rule of 2026-10-25)."""
    code, out = _run(["git", "branch", "--show-current"], repo.path)
    branch = out.strip()
    if code != 0:
        return Check("main checkout on main", RED, "git failed")
    if branch == "main":
        return Check("main checkout on main", GREEN, "main")
    return Check("main checkout on main", RED, f"on {branch or 'a detached HEAD'}: commit or push it, then git switch main")


def git_rows(repo: Repo, now: datetime) -> list[Check]:
    rows = [checkout_row(repo)]
    code, out = _run(["git", "branch", "--format=%(refname:short)", "--no-merged", "main"], repo.path)
    if code == 0:
        branches = [b for b in out.split() if b]
        rows.append(Check("unmerged branches", AMBER if branches else GREEN, f"{len(branches)}"))
    else:
        rows.append(Check("unmerged branches", AMBER, "git failed"))
    if not repo.github:
        return rows
    code, out = _run(["gh", "pr", "list", "--repo", repo.github, "--state", "open", "--json", "number,createdAt", "--limit", "200"])
    if code == 0:
        prs = json.loads(out or "[]")
        old = [p for p in prs if now - datetime.fromisoformat(p["createdAt"].replace("Z", "+00:00")) > OLD_PR]
        rows.append(Check("open PRs", AMBER if old else GREEN, f"{len(prs)} open, {len(old)} over 7 days"))
    else:
        rows.append(Check("open PRs", AMBER, "gh failed"))
    code, out = _run(["gh", "issue", "list", "--repo", repo.github, "--state", "open", "--json", "number", "--limit", "1000"])
    rows.append(Check("open issues", GREEN, f"{len(json.loads(out or '[]'))}") if code == 0 else Check("open issues", AMBER, "gh failed"))
    return rows


def docs_row(repo: Repo) -> Check | None:
    if not (repo.path / "docs" / "generated").is_dir():
        return None
    gendocs = Path(sys.executable).with_name("metalm-gendocs")
    code, out = _run([str(gendocs), "--dry-run", "--root", str(repo.path)])
    if code == 0:
        return Check("generated docs", GREEN, "current")
    stale = [line.split(": ", 1)[1] for line in out.splitlines() if line.startswith("stale: ")]
    return Check("generated docs", AMBER, f"stale: {', '.join(stale)}" if stale else "could not check")


def conformance(repos_md: str) -> dict[str, str]:
    """repo -> status column of docs/repos.md."""
    found = {}
    for line in repos_md.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[2] in {"compliant", "adopted", "attempted", "unchecked"}:
            found[cells[0]] = cells[2]
    return found


def collect(cfg: Config, *, now: datetime | None = None) -> dict:
    """Every check for every repo, plus the backup jobs themselves."""
    now = now or datetime.now(UTC)
    copies = backup.latest_copies(cfg)
    runs = backup.read_runs(cfg)
    offsite_ok = [r for r in runs if r.get("kind") == "offsite" and r.get("ok")]
    offsite_age = now - datetime.fromisoformat(offsite_ok[-1]["ts"]) if offsite_ok else None
    checks_run = [r for r in runs if r.get("kind") == "check"]
    rows_md = conformance(REPOS_MD.read_text()) if REPOS_MD.exists() else {}

    jobs = [agent(cfg.backup_label), agent(cfg.serve_label)]
    local_runs = [r for r in runs if r.get("kind") == "local"]
    if local_runs and not local_runs[-1]["ok"]:
        failed = [f"{i['repo']}/{i['name']}: {i['detail']}" for i in local_runs[-1]["items"] if not i["ok"]]
        jobs.append(Check("last local run", RED, "; ".join(failed)))
    jobs.append(Check("B2 snapshot", age_level(offsite_age), _age_text(offsite_age)))
    if checks_run and not checks_run[-1]["ok"]:
        jobs.append(Check("restic check", RED, checks_run[-1].get("detail", "failed")))

    names = [r.name for r in cfg.repos] + sorted({d.repo for d in cfg.databases} - {r.name for r in cfg.repos})
    by_name = {r.name: r for r in cfg.repos}
    repos = []
    for name in names:
        rows: list[Check] = []
        for db in (d for d in cfg.databases if d.repo == name):
            when = copies.get((db.repo, db.name))
            age = now - when if when else None
            rows.append(Check(f"backup {db.name}", age_level(age), _age_text(age)))
        repo = by_name.get(name)
        if repo:
            rows.extend(health(port) for port in repo.ports)
            rows.extend(agent(label) for label in repo.agents)
            if repo.path.is_dir():
                rows.extend(git_rows(repo, now))
                doc = docs_row(repo)
                if doc:
                    rows.append(doc)
            else:
                rows.append(Check("checkout", AMBER, f"no folder at {repo.path}"))
            status = rows_md.get(name, "not listed")
            rows.append(Check("metalm row", GREEN if status in {"compliant", "adopted"} else AMBER, status))
        repos.append({"name": name, "level": worst(rows), "checks": [asdict(c) for c in rows]})
    every = jobs + [Check(c["check"], c["level"], c["detail"]) for r in repos for c in r["checks"]]
    return {"generated": now.isoformat(), "level": worst(every), "jobs": [asdict(c) for c in jobs], "repos": repos}


def worst(checks: list[Check]) -> str:
    return max((c.level for c in checks), key=ORDER.__getitem__, default=GREEN)


def reds(status: dict) -> list[str]:
    """'<repo>: <check> (<detail>)' for every red check."""
    out = [f"backups: {c['check']} ({c['detail']})" for c in status["jobs"] if c["level"] == RED]
    for r in status["repos"]:
        out += [f"{r['name']}: {c['check']} ({c['detail']})" for c in r["checks"] if c["level"] == RED]
    return out


def save(cfg: Config, status: dict) -> Path:
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    path = cfg.state_dir / "status.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(status, indent=1, sort_keys=True))
    tmp.replace(path)
    return path
