"""A serial, locked improvement pass with deterministic gates and durable outcomes.

Each repository owns its failure boundary. The owner's checkout is read-only
until a successful merge, when only clean main may fast-forward and deploy.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Iterator

from metalm_ops import status as health
from metalm_ops.config import Config, ImproveRepo, Repo
from metalm_ops.improve import agents, brake, cadence, gates, lenses, process, signals, store

GUIDELINES_DIR = Path("~/.claude/metalm/guidelines")
SLEEP = time.sleep


def NOW() -> datetime:
    """Local clock seam for deterministic scheduling tests."""
    return datetime.now().astimezone()


LABELS = (
    ("auto-improve", "5319E7", "Opened by the daily auto-improve system (metalm-ops improve)"),
    ("codex-automated", "10A37F", "Written by OpenAI Codex, reviewed by Claude; no human in the loop"),
    ("auto-improve-rejected", "B60205", "Auto-improve PR closed by its reviewers, CI or gates"),
    ("auto-improve-checked", "C2E0C6", "A Claude session checked this merged auto-improve PR"),
    ("auto-improve-flagged", "FBCA04", "A Claude session flagged this auto-improve PR as risky"),
    ("auto-improve-brake", "B60205", "A visible auto-improve brake or owner-authorized resume"),
)


class ImproveError(Exception):
    """A run prerequisite or external command failed, with an actionable reason."""


@contextmanager
def _termination_signal() -> Iterator[None]:
    """Give a terminated CLI invocation the same cleanup path as an interrupt."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def terminate(signal_number: int, frame: object) -> None:
        raise SystemExit(f"run interrupted by {signal.Signals(signal_number).name}")

    previous = signal.signal(signal.SIGTERM, terminate)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def _selected(config: Config, name: str | None) -> list[tuple[ImproveRepo, Repo]]:
    selected = list(config.improve.repos) if config.improve else []
    if name is not None:
        selected = [item for item in selected if item.name == name]
        if not selected:
            raise ImproveError(f"repo {name!r} is not opted in. Add [[improve.repo]] in ops.toml")
    repositories = {repository.name: repository for repository in config.repos}
    return [(item, repositories[item.name]) for item in selected]


def _command(arguments: list[str], *, cwd: Path | None = None, directory: Path | None = None, timeout: float = 300, env: dict | None = None) -> str:
    result = process.run(arguments, cwd=cwd, timeout=timeout, env=env)
    if directory is not None:
        with (directory / "steps.log").open("a") as output:
            output.write(f"{arguments[0]} {arguments[1] if len(arguments) > 1 else ''}: exit {result.returncode}\n")
            output.write((result.stdout or "") + (result.stderr or "") + "\n")
    if result.returncode:
        raise ImproveError(f"{arguments[0]} failed (exit {result.returncode}): {(result.stderr or result.stdout).strip()}")
    return result.stdout or ""


def _github(repository: Repo, *arguments: str, directory: Path | None = None, timeout: float = 300) -> str:
    if not repository.github:
        raise ImproveError(f"repo {repository.name}: github is missing. Set repo.github in ops.toml")
    return _command([health.gh(), *arguments, "--repo", repository.github], directory=directory, timeout=timeout)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


@contextmanager
def _lock(config: Config) -> Iterator[None]:
    folder = config.state_dir / "improve"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            lock.seek(0)
            previous = lock.read().strip()
            raise ImproveError(f"another improve run holds the lock (pid {previous or 'unknown'})") from error
        try:
            lock.seek(0)
            previous = lock.read().strip()
            if previous.isdigit() and int(previous) > 0 and _alive(int(previous)):
                raise ImproveError(f"another improve run holds the lock (pid {previous})")
            lock.seek(0)
            lock.truncate()
            lock.write(str(os.getpid()))
            lock.flush()
            try:
                yield
            finally:
                lock.seek(0)
                lock.truncate()
                lock.flush()
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


REVIEW_RESERVE_USD = 0.60  # three judge calls at the observed ~$0.15-0.20 each


LIMIT_FILE = "codex-limit-until"  # state_dir/improve/; written when Codex reports its usage limit
LIMIT_BACKOFF = timedelta(hours=6)  # when the reset time cannot be read from Codex's message


def limit_until(message: str, now: datetime) -> datetime:
    """The reset time Codex names ("try again at Nov 28th, 2026 8:03 PM"), else a fixed back-off."""
    found = re.search(r"try again at ([A-Z][a-z]{2})[a-z]* (\d{1,2})(?:st|nd|rd|th)?, (\d{4}) (\d{1,2}):(\d{2}) ?([AP]M)", message)
    if not found:
        return now + LIMIT_BACKOFF
    month, day, year, hour, minute, half = found.groups()
    stamp = datetime.strptime(f"{month} {day} {year} {hour}:{minute} {half}", "%b %d %Y %I:%M %p")
    return stamp.replace(tzinfo=now.tzinfo) if now.tzinfo else stamp


def _record_limit(config: Config, message: str) -> None:
    folder = config.state_dir / "improve"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / LIMIT_FILE).write_text(limit_until(message, NOW()).isoformat() + "\n")


def codex_limit(config: Config, now: datetime | None = None) -> str:
    """The reset time while the Codex usage limit holds, else empty."""
    path = config.state_dir / "improve" / LIMIT_FILE
    try:
        until = datetime.fromisoformat(path.read_text().strip())
    except (OSError, ValueError):
        return ""
    now = now or NOW()
    if until.tzinfo is None and now.tzinfo is not None:
        until = until.replace(tzinfo=now.tzinfo)
    return until.isoformat() if until > now else ""


def _cap(config: Config, *, reviews_only: bool = False) -> str:
    settings = config.improve
    if settings is None:
        return "improve is not configured"
    if not reviews_only and codex_limit(config):
        return f"system: Codex usage limit until {codex_limit(config)}"
    usage = store.usage(config)
    if not reviews_only and usage["codex_calls"] >= settings.max_codex_calls_per_day:
        return "daily cap reached (Codex calls)"
    if usage["review_cost_usd"] >= settings.max_review_cost_usd_per_day:
        return "daily cap reached (Claude review cost)"
    if not reviews_only and usage["review_cost_usd"] + REVIEW_RESERVE_USD > settings.max_review_cost_usd_per_day:
        # Start a proposal only when the budget covers all three judges, so no PR is closed for lack of budget.
        return "daily cap reached (Claude review cost, reserve for three judges)"
    return ""


def _skip(config: Config, repository: Repo, *, dry_run: bool = False, directory: Path | None = None) -> str:
    settings = config.improve
    if settings is None or not settings.enabled:
        return "improve is disabled"
    folder = config.state_dir / "improve"
    if (folder / "PAUSE").exists():
        return "system PAUSE file exists"
    cap = _cap(config)
    if cap:
        return cap
    opened = json.loads(
        _github(repository, "pr", "list", "--label", "auto-improve", "--state", "open", "--limit", "1", "--json", "number", directory=directory)
    )
    if opened:
        return "an open auto-improve PR exists"
    return ""


def _history(repository: Repo, directory: Path) -> str:
    history = json.loads(
        _github(
            repository,
            "pr",
            "list",
            "--label",
            "auto-improve",
            "--state",
            "all",
            "--limit",
            "60",
            "--json",
            "number,title,state,closedAt,body",
            directory=directory,
        )
    )
    for item in history:
        if item["state"] == "CLOSED":
            comments = json.loads(_github(repository, "pr", "view", str(item["number"]), "--json", "comments", directory=directory))
            reasons = [
                line for comment in comments.get("comments", []) for line in comment.get("body", "").splitlines() if line.startswith("Closed by auto-improve:")
            ]
            item["reason"] = reasons[-1] if reasons else "No system close reason recorded"
    return json.dumps(history, ensure_ascii=False)


def labels(config: Config, *, repo: str | None = None, dry_run: bool = False, include_metalm: bool = True) -> dict:
    """Create or update the six attribution and review labels in opted-in repos (and metalm, for brake PRs)."""
    rows = []
    repositories = [repository for _, repository in _selected(config, repo)]
    metalm = brake.repository(config)
    if include_metalm and all(repository.github != metalm.github for repository in repositories):
        repositories.append(metalm)
    for repository in repositories:
        if dry_run:
            rows.append({"repo": repository.name, "ok": True, "reason": "would create or update six labels"})
            continue
        try:
            for name, colour, description in LABELS:
                _github(repository, "label", "create", name, "--force", "--color", colour, "--description", description)
            rows.append({"repo": repository.name, "ok": True, "reason": "six labels created or updated"})
        except (ImproveError, OSError, subprocess.TimeoutExpired) as error:
            rows.append({"repo": repository.name, "ok": False, "reason": str(error)})
    return {"rows": rows, "ok": all(row["ok"] for row in rows), "next": "metalm-ops doctor"}


def signals_board(config: Config, *, repo: str | None = None, now: datetime | None = None) -> dict:
    """Measure each opted-in repo at origin/main in a throwaway worktree; never calls a model."""
    now = now or NOW()
    repositories = []
    for selected, repository in _selected(config, repo):
        folder = config.state_dir / "improve" / "worktrees" / f"{repository.name}-signals-{uuid.uuid4().hex[:8]}"
        entry = {"name": selected.name, "files": 0, "counts": {}, "errors": [], "findings": []}
        try:
            _command(["git", "-C", str(repository.path), "fetch", "origin"])
            folder.parent.mkdir(parents=True, exist_ok=True)
            _command(["git", "-C", str(repository.path), "worktree", "add", "--detach", str(folder), "origin/main"])
            try:
                report = signals.measure(
                    folder,
                    ruff_bin=RUFF_BIN,
                    excludes=(*gates.EXCLUDES, *selected.exclude),
                    thresholds=selected.thresholds,
                    junit=_junit(config, repository.name),
                    now=now,
                )
            finally:
                _command(["git", "-C", str(repository.path), "worktree", "remove", "--force", str(folder)])
            counts: dict[str, int] = {}
            for item in report["findings"]:
                counts[item["signal"]] = counts.get(item["signal"], 0) + 1
            ranked = sorted(
                report["findings"], key=lambda item: (item["signal"] == "churn", -(item["value"] / item["threshold"] if item["threshold"] else item["value"]))
            )
            entry.update(files=report["files"], counts=counts, errors=report["errors"], findings=ranked[:10])
        except Exception as error:
            entry["errors"] = [{"signal": "all", "error": str(error)[:300]}]
        repositories.append(entry)
    return {"repos": repositories, "ok": not any(item["errors"] for item in repositories), "next": "metalm-ops improve run --dry-run"}


def status(config: Config, *, repo: str | None = None, now: datetime | None = None) -> dict:
    """Cadence, visible brake and ten recent runs, including a stable opt-out reply."""
    if repo is not None and (config.improve is None or not any(item.name == repo for item in config.improve.repos)):
        return {"opted_in": False}
    now = now or NOW()
    repositories, rows = [], []
    brake_error = ""
    try:
        entries = {entry["repo"]: entry for entry in brake.read(config)} if config.improve else {}
    except Exception as error:  # offline: still answer the session-start check with JSON
        entries, brake_error = {}, f"could not read improve/braked.toml: {error}"
    for selected, repository in _selected(config, repo):
        history = store.read_runs(config, selected.name, limit=1000000)
        recent = history[:10]
        last_pr = next((row for row in history if row.get("pr_url")), None)
        try:
            board = cadence.plan(config, selected, repository, now)
        except Exception as error:
            board = {"repo": selected.name, "D": None, "T": None, "today": None, "overdue": [], "lens": None, "due": False, "reason": str(error), "error": True}
        entry = entries.get(selected.name)
        if entry:
            entry = {**entry, "pr": brake.lookup(config, selected.name)}
        paused = bool(entry or not config.improve.enabled or (config.state_dir / "improve" / "PAUSE").exists())
        if paused:
            board.update(due=False, reason=brake.reason(entry) if entry else "system paused")
        repositories.append({**board, "name": selected.name, "paused": paused, "brake": entry, "runs": recent, "last_pr": last_pr})
        rows.extend(recent)
    board = {
        "opted_in": True,
        "repos": repositories,
        "rows": rows,
        "usage": store.usage(config),
        "ok": not brake_error and not any(item.get("error") for item in repositories),
        "brake_error": brake_error,
        "codex_limit_until": codex_limit(config),
        "next": "metalm-ops improve run --dry-run",
    }
    if repo is not None:
        board.update(repositories[0])
    return board


def unbrake(config: Config, *, repo: str, why: str, dry_run: bool = False) -> dict:
    """Open a resume PR quoting the owner's words; never merge it."""
    return brake.unbrake(config, repo, why, dry_run=dry_run)


def decision(senior: dict, boundaries: dict, category: str, verifier: dict | None = None) -> str:
    """The first failing merge condition, or an empty reason when reviews pass."""
    if verifier is not None and verifier["verdict"] != "confirmed":
        return f"verifier {verifier['verdict']}: {verifier['reasons'].splitlines()[0] if verifier['reasons'] else 'no reason given'}"
    for name, review in (("senior engineer", senior), ("boundaries", boundaries)):
        if review["verdict"] != "approve":
            return f"{name} reviewer rejected: {review['reasons'].splitlines()[0] if review['reasons'] else 'no reason given'}"
    for name, review in (("senior engineer", senior), ("boundaries", boundaries)):
        if not review["clear_cut"]:
            return f"{name} reviewer did not find a clear-cut improvement"
    for name, review in (("senior engineer", senior), ("boundaries", boundaries)):
        if review["confidence"] < 0.8:
            return f"{name} reviewer confidence {review['confidence']:g} is below 0.8"
    if boundaries["behaviour_change"] and not lenses.load(lenses.OLD_NAMES.get(category, category)).may_change_behaviour:
        return "boundaries reviewer found a behaviour change outside the selected lens"
    return ""


def opening(config: Config, run_id: str) -> str:
    """Shared attribution for improvement and safety-brake pull requests."""
    settings = config.improve
    return (
        f"> **Opened by the auto-improve system:** OpenAI Codex (`codex exec`, model {settings.model}, effort {settings.effort}), "
        f"run by `metalm-ops improve` on the owner's Mac, run `{run_id}`.\n"
        "> **Why:** one small improvement per run under metalm `guidelines/auto-improve.md`.\n\n"
    )


def _body(config: Config, run_id: str, proposal: dict, measured: dict, repository: Repo, base: str, target: dict | None = None, change: str = "") -> str:
    from urllib.parse import quote

    evidence = "\n\n".join(
        f"[{item['path']}:{item['start_line']}-{item['end_line']}](https://github.com/{repository.github}/blob/{base}/{quote(item['path'], safe='/')}#L{item['start_line']}-L{item['end_line']})\n\n"
        + "\n".join("> " + line for line in item["quote"].splitlines())
        for item in proposal["evidence"]
    )
    measurement = f"## Measurement\n\n{proposal['measurement']}\n\n" if lenses.load(proposal["lens"]).needs_measurement else ""
    return (
        opening(config, run_id)
        + (
            f"## Finding\n\n{target['signal']}: {target['detail']} ({target['path']}:{target['start_line']}-{target['end_line']}). {change}\n\n"
            if target
            else ""
        )
        + f"## Lens\n\n{proposal['lens']}\n\n## Claim\n\n{proposal['claim']}\n\n## Evidence\n\n{evidence}\n\n{measurement}"
        f"## What\n\n{proposal['summary']}\n\nCategory: {proposal['category']}\n\n"
        f"## Why it is safe\n\n{proposal['why_safe']}\n\n"
        f"## Tests\n\nCommand: `{measured['test']}`\n\nResult: passed; worktree imports passed.\n\n{proposal['tests_run']}\n\n"
        f"## Files\n\n```text\n{measured['diff_stat']}\n```\n"
    )


def newest_prompt(name: str, folder: str = "prompts") -> Path:
    """The highest-numbered `<name>_vN.md`: a new version supersedes the old one, which stays for history."""
    versions = [
        (int(m.group(1)), path) for path in (agents.ROOT / folder).glob(f"{name}_v*.md") if (m := re.fullmatch(rf"{re.escape(name)}_v(\d+)\.md", path.name))
    ]
    if not versions:
        raise ImproveError(f"no prompt file {name}_v<N>.md in {agents.ROOT / 'prompts'}")
    return max(versions)[1]


def _link_env(repository: Repo, worktree: Path) -> None:
    """Link the checkout's ignored `.env` into the worktree for the gate's test run only. It is linked
    after the proposer has answered, so the model never sees the secrets, and kept out of the diff."""
    source, link = repository.path / ".env", worktree / ".env"
    if not source.is_file() or link.exists() or link.is_symlink():
        return
    link.symlink_to(source)
    if subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=worktree, capture_output=True).returncode != 0:
        exclude = Path(_command(["git", "rev-parse", "--git-path", "info/exclude"], cwd=worktree).strip())
        exclude = exclude if exclude.is_absolute() else worktree / exclude
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a") as handle:
            handle.write("/.env\n")


def _link_node_modules(repository: Repo, worktree: Path) -> None:
    """Give the worktree the checkout's installed node_modules folders (ignored by git, so a fresh worktree
    lacks them), so JS-backed tests such as ytlm's tests/js run in the gate as they do in the checkout."""
    found = process.run(["git", "-C", str(repository.path), "ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z"])
    for entry in (found.stdout or "").split("\0"):
        relative = entry.rstrip("/")
        if not relative or PurePosixPath(relative).name != "node_modules" or ".venv" in PurePosixPath(relative).parts:
            continue
        source, link = repository.path / relative, worktree / relative
        if source.is_dir() and not link.exists() and link.parent.is_dir():
            link.symlink_to(source, target_is_directory=True)
            # A `node_modules/` ignore pattern does not match a symlink; keep the link out of the diff.
            if subprocess.run(["git", "check-ignore", "-q", relative], cwd=worktree, capture_output=True).returncode != 0:
                exclude = Path(_command(["git", "rev-parse", "--git-path", "info/exclude"], cwd=worktree).strip())
                exclude = exclude if exclude.is_absolute() else worktree / exclude
                exclude.parent.mkdir(parents=True, exist_ok=True)
                with exclude.open("a") as handle:
                    handle.write(f"/{relative}\n")


def _link_venv(repository: Repo, worktree: Path, directory: Path) -> None:
    """Give the worktree the repo's `.venv` as a symlink, so pre-commit hooks with a relative
    `entry: .venv/bin/...` (computerlm's import-contracts) run at commit time. The link must stay
    out of the diff: `.venv/` in a .gitignore does not match a symlink, so if git does not ignore
    it, `.venv` is added to the repository's shared `info/exclude` (it already ignores the folder)."""
    source = repository.path / ".venv"
    link = worktree / ".venv"
    if not source.is_dir() or link.exists() or link.is_symlink():
        return
    link.symlink_to(source, target_is_directory=True)
    ignored = subprocess.run(["git", "check-ignore", "-q", ".venv"], cwd=worktree, capture_output=True)
    if ignored.returncode != 0:
        exclude = Path(_command(["git", "rev-parse", "--git-path", "info/exclude"], cwd=worktree, directory=directory).strip())
        exclude = exclude if exclude.is_absolute() else worktree / exclude
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a") as handle:
            handle.write("\n.venv\n")


RUFF_BIN = Path(sys.executable).parent / "ruff"  # metalm's own pinned ruff (beside its interpreter) measures every repo the same way
JUNIT_DIR = "junit"  # state_dir/improve/junit/<repo>.xml: timings from the last green gate run
WINDOW = 150  # lines shown either side of the finding in a long primary file
SHORT = 400  # files up to this length are shown whole
SUPPORT_LINES = 200  # a long related or test file shows its head only
SILENCERS = ("noqa", "pragma: no cover", "type: ignore", "nosec")  # adding one hides a finding instead of fixing it


def _junit(config: Config, repo: str) -> Path:
    return config.state_dir / "improve" / JUNIT_DIR / f"{repo}.xml"


def _keep_junit(config: Config, repo: str, directory: Path) -> None:
    source = directory / "junit.xml"
    if source.exists():
        destination = _junit(config, repo)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())


def recent_targets(config: Config, repo: str, now: datetime) -> set[str]:
    """Findings not to retry: a PR in the last 30 days, or a proposer skip or failed gate in the last 14."""
    avoid = set()
    for row in store.read_runs(config, repo, limit=1000000):
        if not row.get("finding") or not row.get("finished"):
            continue
        finished = datetime.fromisoformat(row["finished"])
        age = (now.replace(tzinfo=None) - finished.replace(tzinfo=None)).days
        if (row.get("pr_url") and age < 30) or (row["outcome"] in {"skipped", "gate-failed"} and age < 14):
            avoid.add(row["finding"])
    return avoid


def _target_text(worktree: Path, paths: list[str], target: dict | None = None) -> str:
    """Target files with line numbers: short files whole; long files as windows around the finding and,
    for duplication, around the other copy (which may be in the same file); other long files' heads."""
    focus: dict[str, list[tuple[int, int]]] = {}
    if target:
        focus.setdefault(target["path"], []).append((target["start_line"], max(target["end_line"], target["start_line"])))
        other = target.get("other")
        if other:
            focus.setdefault(other["path"], []).append((other["start_line"], other["end_line"]))
    blocks = []
    for path in paths:
        try:
            lines = (worktree / path).read_text().splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        if len(lines) <= SHORT:
            spans = [(1, len(lines))]
        elif path in focus:
            spans = sorted((max(1, first - WINDOW), min(len(lines), last + WINDOW)) for first, last in focus[path])
            merged = [spans[0]]
            for first, last in spans[1:]:
                if first <= merged[-1][1] + 1:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], last))
                else:
                    merged.append((first, last))
            spans = merged
        else:
            spans = [(1, min(len(lines), SUPPORT_LINES))]
        shown = sum(last - first + 1 for first, last in spans)
        note = f" note='{shown} of {len(lines)} lines shown; ask nothing, skip if the fix needs unseen code'" if shown < len(lines) else ""
        body = "\n...\n".join("\n".join(f"{number}: {lines[number - 1]}" for number in range(first, last + 1)) for first, last in spans)
        blocks.append(f'<file path="{path}"{note}>\n{body}\n</file>')
    return "\n".join(blocks)


def _format(repository: Repo, worktree: Path, paths: list[str]) -> None:
    """Format the edited Python files with the repo's own ruff and config, as its ruff-format hook would;
    a single-shot answer cannot run the formatter itself, and a reformat at commit time aborts the commit."""
    ruff = repository.path / ".venv" / "bin" / "ruff"
    files = sorted({path for path in paths if path.endswith(".py") and (worktree / path).is_file()})
    if ruff.is_file() and files:
        process.run([str(ruff), "format", "--quiet", *files], cwd=worktree)


def apply_edits(worktree: Path, edits: list[dict]) -> None:
    """Apply a single-shot proposal's exact search/replace edits; any edit that does not match exactly once fails the gate."""
    if not edits:
        raise gates.GateError("proposal has no edits: no file changed")
    root = worktree.resolve()
    for number, item in enumerate(edits, 1):
        path = (worktree / item["path"]).resolve()
        if not path.is_relative_to(root) or ".git" in Path(item["path"]).parts:
            raise gates.GateError(f"edit {number}: path outside the repository: {item['path']}")
        if item["search"] == "":
            if path.exists():
                raise gates.GateError(f"edit {number}: {item['path']} already exists; an empty search only creates files")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(item["replace"])
            continue
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError) as error:
            raise gates.GateError(f"edit {number}: cannot read {item['path']}: {error}") from error
        count = text.count(item["search"])
        if count != 1:
            raise gates.GateError(f"edit {number}: search text found {count} times in {item['path']}, expected exactly once")
        path.write_text(text.replace(item["search"], item["replace"], 1))


def _silences(worktree: Path, directory: Path) -> str:
    """An added line that silences a linter or coverage, if any: such a change hides the finding."""
    _command(["git", "add", "-A", "--intent-to-add"], cwd=worktree, directory=directory)
    diff = _command(["git", "diff", "--no-color", "-U0", "HEAD"], cwd=worktree, directory=directory)
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++") and any(word in line.lower() for word in SILENCERS):
            return line[1:].strip()[:120]
    return ""


def _test_files_command(repository: Repo, tests: list[str]) -> str:
    if not tests:
        return "no test files target this module; add a focused test file only if the lens calls for one"
    python = repository.path / ".venv" / "bin" / "python"
    arguments = ", ".join(repr(path) for path in tests)
    return f"{python} -c \"import sys; sys.modules['readline'] = None; import pytest; sys.exit(pytest.main(['-q', {arguments}]))\""


def tokens(jsonl: Path) -> dict:
    """The proposer's token use from Codex's final turn.completed event."""
    usage = {}
    try:
        for line in jsonl.read_text().splitlines():
            if '"turn.completed"' in line:
                usage = json.loads(line).get("usage") or usage
    except (OSError, ValueError):
        return {}
    return {"tokens_in": usage.get("input_tokens"), "tokens_cached": usage.get("cached_input_tokens"), "tokens_out": usage.get("output_tokens")}


def _prompt(name: str, values: dict) -> tuple[str, str]:
    template = newest_prompt(name).read_text()
    return template, template.split("---", 2)[2].strip().format(**values)


def _update(repository: Repo, selected: ImproveRepo, directory: Path) -> tuple[bool, str]:
    branch = _command(["git", "branch", "--show-current"], cwd=repository.path, directory=directory).strip()
    if branch != "main":
        return False, f"checkout not updated: {branch or 'detached HEAD'}"
    dirty = _command(["git", "status", "--porcelain"], cwd=repository.path, directory=directory)
    if dirty.strip():
        return False, "checkout not updated: uncommitted changes"
    _command(["git", "-C", str(repository.path), "pull", "--ff-only"], directory=directory)
    if selected.deploy:
        try:
            _command(["/bin/sh", "-c", selected.deploy], cwd=repository.path, directory=directory)
        except (ImproveError, OSError, subprocess.TimeoutExpired) as error:
            return True, f"merged; checkout updated; deploy failed: {error}"
    return True, "merged; checkout updated" + (" and deployed" if selected.deploy else "")


def _run_repo(
    config: Config, selected: ImproveRepo, repository: Repo, run_id: str, no_pr: bool, forced_lens: str | None = None, now: datetime | None = None
) -> dict:
    settings = config.improve
    assert settings is not None
    started = now or NOW()
    directory = config.state_dir / "improve" / "runs" / run_id / repository.name
    row = {
        "run_id": run_id,
        "repo": repository.name,
        "started": started.isoformat(),
        "finished": "",
        "outcome": "failed",
        "pr_number": None,
        "pr_url": None,
        "category": forced_lens,
        "lens": forced_lens,
        "title": None,
        "reason": "",
        "codex_calls": 0,
        "model": settings.model,
        "checkout_updated": False,
    }
    worktree = config.state_dir / "improve" / "worktrees" / f"{repository.name}-{run_id}"
    branch = f"auto-improve/{started:%Y%m%d}-{run_id}"
    created = False
    branch_created = False

    def remove_worktree() -> None:
        nonlocal created
        if branch_created and not created:
            registered = _command(["git", "-C", str(repository.path), "worktree", "list", "--porcelain"], directory=directory)
            created = any(
                line.startswith("worktree ") and Path(line.removeprefix("worktree ")).resolve() == worktree.resolve() for line in registered.splitlines()
            )
        if created:
            _command(["git", "-C", str(repository.path), "worktree", "remove", "--force", str(worktree)], directory=directory)
            created = False

    try:
        directory.mkdir(parents=True, exist_ok=True)
        reason = _skip(config, repository, directory=directory)
        if reason:
            row.update(outcome="skipped", reason=reason)
            return row
        _command(["git", "-C", str(repository.path), "fetch", "origin"], directory=directory)
        worktree.parent.mkdir(parents=True, exist_ok=True)
        branch_created = True  # even a failed add can leave a branch or a registered worktree
        _command(["git", "-C", str(repository.path), "worktree", "add", "-b", branch, str(worktree), "origin/main"], directory=directory)
        created = True
        _link_venv(repository, worktree, directory)
        _link_node_modules(repository, worktree)
        available = lenses.applicable(selected, _command(["git", "ls-files", "-z"], cwd=worktree, directory=directory).split("\0"))
        chosen = forced_lens or lenses.choose(available, store.read_runs(config, repository.name, limit=1000000))
        if chosen not in available:
            row.update(outcome="skipped", reason="no applicable lens" if chosen is None else f"lens {chosen} is not applicable")
            return row
        mission = lenses.load(chosen)
        row.update(category=chosen, lens=chosen)
        base = _command(["git", "rev-parse", "HEAD"], cwd=worktree, directory=directory).strip()
        excludes = (*gates.EXCLUDES, *selected.exclude)
        report = signals.measure(
            worktree, ruff_bin=RUFF_BIN, excludes=excludes, thresholds=selected.thresholds, junit=_junit(config, repository.name), now=started
        )
        (directory / "signals.json").write_text(json.dumps(report, indent=2, default=str))
        picked = signals.candidates(report, chosen, avoid=recent_targets(config, repository.name, started), seed=f"{repository.name}|{started:%Y-%m-%d}")
        if not picked:
            # Nothing measured for this lens: done for the weekly floor, and no Codex call spent looking.
            row.update(outcome="skipped", reason=lenses.PROPOSER_SKIP + f"no measured finding for {chosen}")
            return row
        target = picked[0]
        row["finding"] = target["fingerprint"]
        target_paths = signals.target_files(report, target)
        index_md = (GUIDELINES_DIR.expanduser() / "index.md").read_text()
        auto_improve_md = (GUIDELINES_DIR.expanduser() / "auto-improve.md").read_text()
        claude_md = (worktree / "CLAUDE.md").read_text() if (worktree / "CLAUDE.md").is_file() else "No CLAUDE.md"
        common = {
            "lens": chosen,
            "mission": mission.mission,
            "may_change_behaviour": mission.may_change_behaviour,
            "excludes": ", ".join((*gates.EXCLUDES, *selected.exclude)),
            "claude_md": claude_md,
        }
        template, prompt = _prompt(
            "propose",
            {
                **common,
                "max_files": settings.max_files,
                "max_changed_lines": settings.max_changed_lines,
                "test": gates.command(selected, repository, worktree),
                "index_md": index_md,
                "auto_improve_md": auto_improve_md,
                "history": _history(repository, directory),
                "finding": json.dumps(
                    {
                        key: target[key]
                        for key in ("signal", "metric", "value", "threshold", "path", "start_line", "end_line", "detail", "other")
                        if key in target
                    },
                    indent=2,
                ),
                "target_files": _target_text(worktree, target_paths, target),
                "test_files_command": _test_files_command(repository, [path for path in target_paths if signals.is_test(path)]),
            },
        )
        row["codex_calls"] += 1
        proposal = agents.call(
            config, run_id=run_id, repo=repository.name, role="propose", worktree=worktree, directory=directory, prompt=prompt, template=template
        )
        row.update(tokens(directory / "propose.jsonl"))
        if proposal["skip"]:
            if proposal.get("limit"):
                _record_limit(config, proposal["skip_reason"])
            if proposal.get("failed"):
                # A proposer that could not run is a failure, never "found nothing": it must not mark the lens done or hide from the brake.
                row.update(outcome="failed", reason=proposal["skip_reason"])
            else:
                row.update(outcome="skipped", reason=lenses.PROPOSER_SKIP + proposal["skip_reason"])
            return row
        if proposal["lens"] != chosen or proposal["category"] != chosen:
            raise gates.GateError(f"proposal must use selected lens {chosen}")
        if "edits" in proposal:
            apply_edits(worktree, proposal["edits"])
            _format(repository, worktree, [item["path"] for item in proposal["edits"]])
        row.update(title=proposal["title"])
        quote_error = gates.check_evidence(worktree, proposal["evidence"], base)
        if quote_error:
            raise gates.GateError(quote_error)
        if mission.needs_measurement and not proposal["measurement"].strip():
            raise gates.GateError("performance lens needs a before/after measurement")
        if chosen == "tests":
            paths = gates.inspect(settings, selected, worktree)["files"]
            if any(
                not (
                    "tests" in Path(path).parts
                    or Path(path).name.startswith("test_")
                    or Path(path).name.endswith(("_test.py", ".test.js", ".test.ts", ".spec.ts", ".spec.js"))
                )
                for path in paths
            ):
                raise gates.GateError("tests lens may change tests only")
        if _command(["git", "rev-parse", "HEAD"], cwd=worktree, directory=directory).strip() != base:
            raise gates.GateError("proposer created a commit; only Python may commit")
        silenced = _silences(worktree, directory)
        if silenced:
            raise gates.GateError(f"proposal silences a check instead of fixing it: {silenced}")
        _link_env(repository, worktree)
        measured = gates.check(settings, selected, repository, worktree, directory)
        _keep_junit(config, repository.name, directory)
        after = signals.measure(worktree, ruff_bin=RUFF_BIN, excludes=excludes, thresholds=selected.thresholds, junit=directory / "junit.xml", now=started)
        better, change = signals.improved(target, after)
        if not better:
            raise gates.GateError(change)
        row["finding_change"] = change
        row.update(
            diff_stat=measured["diff_stat"],
            gates={"tests": "passed", "imports": "passed", "files": len(measured["files"]), "changed_lines": measured["changed_lines"]},
        )
        if no_pr:
            row.update(outcome="no-pr", reason="proposal and gates passed; discarded without a PR")
            return row
        _command(["git", "status", "--porcelain"], cwd=worktree, directory=directory)
        _command(["git", "add", "-A"], cwd=worktree, directory=directory)
        message = f"{proposal['title']}\n\nAuto-improve-run: {run_id}\nCo-Authored-By: Codex <noreply@openai.com>\n"
        try:
            # Hooks such as import-linter import the package: point them at the worktree's code, not the checkout's.
            hooks_env = {**os.environ, "PYTHONPATH": str(worktree / "src") + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")}
            _command(["git", "commit", "-m", message], cwd=worktree, directory=directory, env=hooks_env)
        except ImproveError as error:
            raise gates.GateError(f"commit or pre-commit hook failed: {error}") from error
        if gates.inspect(settings, selected, worktree)["fingerprint"] != measured["fingerprint"]:
            raise gates.GateError("pre-commit changed the tested proposal")
        if _command(["git", "status", "--porcelain"], cwd=worktree, directory=directory).strip():
            raise gates.GateError("pre-commit left uncommitted changes")
        head = _command(["git", "rev-parse", "HEAD"], cwd=worktree, directory=directory).strip()
        _command(["git", "push", "-u", "origin", branch], cwd=worktree, directory=directory)
        label_result = labels(config, repo=repository.name, include_metalm=False)
        if not label_result["ok"]:
            raise ImproveError(next(row["reason"] for row in label_result["rows"] if not row["ok"]))
        body = _body(config, run_id, proposal, measured, repository, base, target, row.get("finding_change", ""))
        body_file = directory / "pr-body.md"
        body_file.write_text(body)
        output = _github(
            repository,
            "pr",
            "create",
            "--base",
            "main",
            "--head",
            branch,
            "--title",
            "[auto-improve] " + proposal["title"],
            "--label",
            "auto-improve",
            "--label",
            "codex-automated",
            "--body-file",
            str(body_file),
            directory=directory,
        )
        urls = re.findall(r"https://[^\s]+/pull/(\d+)", output)
        if not urls:
            raise ImproveError("gh pr create returned no PR URL")
        row.update(pr_number=int(urls[-1]), pr_url=re.findall(r"https://[^\s]+/pull/\d+", output)[-1])
        diff = _github(repository, "pr", "diff", str(row["pr_number"]), directory=directory)
        review_values = {**common, "pr_body": body, "diff": diff, "guidelines": index_md + "\n" + auto_improve_md}
        reason = _cap(config, reviews_only=True)
        if reason:
            verification = {"verdict": "uncertain", "counter_evidence": [], "reasons": reason}
        else:
            base_files = {}
            for path in measured["files"]:
                result = process.run(["git", "show", f"{base}:{path}"], cwd=worktree)
                base_files[path] = result.stdout if result.returncode == 0 else "File absent at base commit"
            template, prompt = _prompt(
                "verify",
                {
                    "claim": proposal["claim"],
                    "evidence": json.dumps(proposal["evidence"]),
                    "measurement": proposal["measurement"],
                    "diff": diff,
                    "mission": mission.mission,
                    "base_files": "\n\n".join(f"File: {path}\n{contents}" for path, contents in base_files.items()),
                },
            )
            verification = agents.call(
                config, run_id=run_id, repo=repository.name, role="verify", worktree=worktree, directory=directory, prompt=prompt, template=template
            )
            if verification["verdict"] == "refuted":
                invalid = (
                    gates.check_evidence(worktree, verification["counter_evidence"], base)
                    if verification["counter_evidence"]
                    else "refutation has no counter-evidence"
                )
                if invalid:
                    verification = {**verification, "verdict": "uncertain", "reasons": invalid + "; " + verification["reasons"]}
        comment = directory / "verify-comment.md"
        comment.write_text(
            f"### auto-improve review: verifier (Claude {settings.review_model})\n\n<!-- auto-improve -->\nVerdict: {verification['verdict']}\n\n{verification['reasons']}\n\nCounter-evidence: {json.dumps(verification['counter_evidence'])}\n"
        )
        _github(repository, "pr", "comment", str(row["pr_number"]), "--body-file", str(comment), directory=directory)
        reviews = []
        for name, title in (("senior", "senior engineer"), ("boundaries", "boundaries")) if verification["verdict"] == "confirmed" else ():
            reason = _cap(config, reviews_only=True)
            if reason:
                review = agents.rejected(reason)
            else:
                template, prompt = _prompt(f"review_{name}", review_values)
                review = agents.call(
                    config, run_id=run_id, repo=repository.name, role=f"review-{name}", worktree=worktree, directory=directory, prompt=prompt, template=template
                )
            reviews.append(review)
            comment = directory / f"review-{name}-comment.md"
            comment.write_text(
                f"### auto-improve review: {title} (Claude {settings.review_model})\n\n<!-- auto-improve -->\n"
                f"Verdict: {review['verdict']}\nConfidence: {review['confidence']}\nRisks: {json.dumps(review['risks'])}\n\n{review['reasons']}\n"
            )
            _github(repository, "pr", "comment", str(row["pr_number"]), "--body-file", str(comment), directory=directory)
        remove_worktree()
        reason = decision(*(reviews or [agents.rejected("not called"), agents.rejected("not called")]), proposal["category"], verification)
        if not reason:
            SLEEP(20)
            try:
                result = process.run(
                    [health.gh(), "pr", "checks", str(row["pr_number"]), "--watch", "--fail-fast", "--repo", repository.github],
                    timeout=settings.ci_timeout_min * 60,
                )
                output = (result.stdout or "") + (result.stderr or "")
                (directory / "checks.log").write_text(output)
                if result.returncode and "no checks reported" not in output.lower():
                    reason = "CI checks failed: " + next(iter(output.strip().splitlines()), f"exit {result.returncode}")
            except subprocess.TimeoutExpired:
                reason = "CI checks timed out"
        if reason:
            _github(repository, "pr", "close", str(row["pr_number"]), "--delete-branch", "--comment", "Closed by auto-improve: " + reason, directory=directory)
            _github(repository, "pr", "edit", str(row["pr_number"]), "--add-label", "auto-improve-rejected", directory=directory)
            row.update(outcome="rejected", reason=reason)
        else:
            _github(
                repository, "pr", "merge", str(row["pr_number"]), "--" + selected.merge, "--delete-branch", "--match-head-commit", head, directory=directory
            )
            row.update(outcome="merged", reason="merged")
            try:
                updated, detail = _update(repository, selected, directory)
                row.update(checkout_updated=updated, reason=detail)
            except (ImproveError, OSError, subprocess.TimeoutExpired) as error:
                row["reason"] = f"merged; checkout update failed: {error}"
        return row
    except gates.GateError as error:
        row.update(outcome="gate-failed", reason=str(error))
        return row
    except Exception as error:
        row.update(outcome="failed", reason=str(error))
        if row.get("pr_number") and row.get("outcome") != "merged":
            # A PR left open would block this repo every later night (an open auto-improve PR skips the run).
            try:
                _github(
                    repository,
                    "pr",
                    "close",
                    str(row["pr_number"]),
                    "--delete-branch",
                    "--comment",
                    "Closed by auto-improve: the run failed: " + str(error)[:300],
                    directory=directory,
                )
            except Exception as close_error:
                row["reason"] = f"{error}; closing the PR also failed: {close_error}"
        return row
    except (KeyboardInterrupt, SystemExit) as error:
        row.update(outcome="failed", reason=f"run interrupted by {type(error).__name__}: {error}")
        raise
    finally:
        try:
            remove_worktree()
        except Exception as error:
            row.update(outcome="failed", reason=f"{row['reason']}; worktree cleanup failed: {error}")
        try:
            if branch_created:
                # gh --delete-branch may already have removed the local branch.
                found = _command(["git", "-C", str(repository.path), "branch", "--list", branch], directory=directory)
                if found.strip():
                    _command(["git", "-C", str(repository.path), "branch", "-D", branch], directory=directory)
        except Exception as error:
            row.update(outcome="failed", reason=f"{row['reason']}; branch cleanup failed: {error}")
        row["finished"] = NOW().isoformat()  # when the run ended, not when the pass began
        try:
            (directory / "result.json").write_text(json.dumps(row, indent=2))
        except OSError as error:
            row.update(outcome="failed", reason=f"{row['reason']}; could not write run artifact: {error}")
        store.record_run(config, row)


def _outcome(config: Config, run_id: str, repository: str, now: datetime, outcome: str, reason: str, lens: str | None = None) -> dict:
    row = {
        "run_id": run_id,
        "repo": repository,
        "started": now.isoformat(),
        "finished": now.isoformat(),
        "outcome": outcome,
        "pr_number": None,
        "pr_url": None,
        "category": lens,
        "lens": lens,
        "title": None,
        "reason": reason,
        "codex_calls": 0,
        "model": config.improve.model,
        "checkout_updated": False,
    }
    directory = config.state_dir / "improve" / "runs" / run_id / repository
    try:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "result.json").write_text(json.dumps(row, indent=2))
    except OSError as error:
        row.update(outcome="failed", reason=f"{reason}; could not write run artifact: {error}")
    store.record_run(config, row)
    return row


def _pass(config: Config, selected: list, run_id: str, now: datetime, repo: str | None, lens: str | None, dry_run: bool, no_pr: bool) -> list[dict]:
    settings = config.improve
    if settings is None:
        return []
    disabled = not settings.enabled or (config.state_dir / "improve" / "PAUSE").exists()
    try:
        entries = {entry["repo"]: entry for entry in brake.read(config, fetch=not dry_run)} if not disabled else {}
    except Exception as error:
        if dry_run:
            return [{"repo": repository.name, "outcome": "failed", "reason": str(error)} for _, repository in selected]
        return [_outcome(config, run_id, repository.name, now, "failed", f"system: could not read metalm's brake list: {error}") for _, repository in selected]
    plans = []
    for entry, repository in selected:
        try:
            board = (
                cadence.plan(config, entry, repository, now, fetch=not dry_run, forced_lens=lens)
                if not disabled
                else {
                    "repo": repository.name,
                    "lens": None,
                    "D": 0,
                    "T": 0,
                    "today": 0,
                    "overdue": [],
                    "due": False,
                    "reason": "system paused",
                    "oldest": now.isoformat(),
                }
            )
            plans.append((entry, repository, board))
        except Exception as error:
            plans.append(
                (
                    entry,
                    repository,
                    {
                        "repo": repository.name,
                        "lens": lens,
                        "D": 0,
                        "T": 0,
                        "today": 0,
                        "overdue": [],
                        "due": False,
                        "reason": str(error),
                        "error": True,
                        "oldest": now.isoformat(),
                    },
                )
            )
    if len(plans) > 1 and all(board.get("error") for _, _, board in plans):
        # Every repo failed to plan: a shared outage (network, gh auth), not something to brake each repo for.
        for _, _, board in plans:
            board["reason"] = "system: " + board["reason"]
    plans.sort(key=lambda item: cadence.order(item[2]))
    rows = []
    for entry, repository, board in plans:
        failure = board.get("error", False)
        reason = board["reason"] if failure else ""
        braked = entries.get(repository.name)
        trigger = brake.trigger(store.read_runs(config, repository.name, limit=1000000), brake.last_brake(config, repository.name)) if not disabled else None
        brake_failure = ""
        attempted_brake = False
        if trigger and not dry_run and not no_pr:
            attempted_brake = True
            try:
                result = brake.apply(config, repository.name, trigger, run_id, now)
                if not result.get("acknowledged"):
                    braked = result.get("entry") or braked
                    failure = False
                    reason = brake.reason(braked) if braked else "brake pending: " + str(trigger.get("summary", "repeated unsuccessful runs"))
                if not result["ok"]:
                    brake_failure = result["reason"]
            except Exception as error:
                reason, brake_failure, failure = "brake pending", str(error), False
        if trigger and (dry_run or no_pr) and not braked and not reason and not brake.acknowledged(config, repository.name, trigger):
            reason = "brake pending: " + trigger["summary"]
        if not failure and not reason:
            reason = (
                "improve is disabled" if not settings.enabled else "system PAUSE file exists" if disabled else brake.reason(braked) if braked else _cap(config)
            )
        if not reason and not board["due"] and repo is None:
            reason = board["reason"]
        if not reason and board["lens"] is None:
            reason = "no applicable lens"
        if dry_run:
            try:
                reason = reason or _skip(config, repository, dry_run=True)
            except Exception as error:
                reason, failure = str(error), True
            rows.append(
                {
                    **board,
                    "due": not bool(reason),
                    "outcome": "failed" if failure else "skipped" if reason else "would-run",
                    "reason": reason or board["reason"],
                    "brake": braked,
                }
            )
            continue
        if reason:
            row = _outcome(config, run_id, repository.name, now, "failed" if failure else "skipped", reason, board["lens"])
        else:
            row = _run_repo(config, entry, repository, run_id, no_pr, board["lens"], now)
        trigger = brake.trigger(store.read_runs(config, repository.name, limit=1000000), brake.last_brake(config, repository.name))
        if trigger and not no_pr and not disabled and not attempted_brake:
            try:
                result = brake.apply(config, repository.name, trigger, run_id, now)
                if not result["ok"]:
                    brake_failure = result["reason"]
            except Exception as error:
                brake_failure = str(error)
        if brake_failure:
            row["brake_error"] = brake_failure
        rows.append({**board, **row})
    return rows


def run(config: Config, *, repo: str | None = None, dry_run: bool = False, no_pr: bool = False, lens: str | None = None, now: datetime | None = None) -> dict:
    """Preview cadence without writes, or run due repositories under a serial lock."""
    if dry_run and no_pr:
        raise ImproveError("--dry-run and --no-pr cannot be combined")
    if lens is not None and (repo is None or lens not in lenses.NAMES):
        raise ImproveError("--lens requires --repo and a known lens")
    selected = _selected(config, repo)
    settings = config.improve
    now = now or NOW()
    caps = (
        {"max_codex_calls_per_day": settings.max_codex_calls_per_day, "max_review_cost_usd_per_day": settings.max_review_cost_usd_per_day} if settings else {}
    )
    run_id = now.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    if dry_run:
        rows = _pass(config, selected, run_id, now, repo, lens, True, no_pr)
    else:
        with _termination_signal(), _lock(config):
            store.initialize(config)
            when, late = cadence.slot(settings, now) if settings else ("", 0)
            if settings and repo is None and late > settings.max_lateness_min:
                rows = [_outcome(config, run_id, "slot", now, "skipped", f"slot {when} missed by {late} min (Mac asleep)")]
            else:
                rows = _pass(config, selected, run_id, now, repo, lens, False, no_pr)
    return {
        "rows": rows,
        "ok": all(row["outcome"] != "failed" and not row.get("brake_error") for row in rows),
        "usage": store.usage(config),
        "caps": caps,
        "dry_run": dry_run,
        "no_pr": no_pr,
        "next": "metalm-ops improve run --no-pr" if dry_run else "metalm-ops improve status",
    }
