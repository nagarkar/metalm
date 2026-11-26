"""Deterministic local-day activity, slot lateness and oldest-lens demand.

Only first-parent mainline changes contribute, excluding automatic merges,
generated documents, lockfiles and binary numstats. Preview never fetches.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath

from metalm_ops.config import Config, Improve, ImproveRepo, Repo
from metalm_ops.improve import lenses, process, store


def _git(repository: Repo, *arguments: str) -> str:
    result = process.run(["git", "-C", str(repository.path), *arguments])
    if result.returncode:
        raise ValueError(f"activity git failed: {(result.stderr or result.stdout).strip()}")
    return result.stdout


def slot(settings: Improve, now: datetime) -> tuple[str, int]:
    """Latest configured slot at or before now, including yesterday's final slot."""
    candidates = []
    for text in settings.slots:
        hour, minute = map(int, text.split(":"))
        instant = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if instant > now:
            instant -= timedelta(days=1)
        candidates.append((instant, text))
    instant, text = max(candidates)
    return text, int((now - instant).total_seconds() // 60)


def activity(repository: Repo, now: datetime, fetch: bool = True) -> dict[str, int]:
    """Count eligible added+deleted lines per local day in the trailing week."""
    if fetch:
        _git(repository, "fetch", "origin")
    earliest = now.date() - timedelta(days=6)
    # A day margin handles differing commit offsets; filter by the local day below.
    output = _git(
        repository,
        "log",
        "origin/main",
        "--first-parent",
        "--diff-merges=first-parent",
        "--no-renames",
        "--numstat",
        "-z",
        "--format=%x1e%ct%x00%P%x00%B%x00",
        f"--since-as-filter={(earliest - timedelta(days=1)).isoformat()}",
    )
    counts = {(now.date() - timedelta(days=offset)).isoformat(): 0 for offset in range(7)}
    for record in output.split("\x1e"):
        if not record.strip("\x00\n "):
            continue
        timestamp, parents, message, changes = record.split("\x00", 3)
        day = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).astimezone(now.tzinfo).date().isoformat()
        if day not in counts or (len(parents.split()) > 1 and re.search(r"auto-improve/[^\s'\"]+", message)):
            continue
        for change in changes.split("\x00"):
            change = change.lstrip("\n")
            if not change:
                continue
            added, removed, path = change.split("\t", 2)
            name = PurePosixPath(path).name
            if (
                added == "-"
                or removed == "-"
                or path.startswith("docs/generated/")
                or name.endswith(".lock")
                or name in {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}
            ):
                continue
            counts[day] += int(added) + int(removed)
    return counts


def demand(changes: dict[str, int], now: datetime, decay: tuple[float, ...]) -> float:
    """Sum independent changed-line impulses at the configured seven daily weights."""
    return sum(decay[offset] * changes.get((now.date() - timedelta(days=offset)).isoformat(), 0) for offset in range(7))


def plan(config: Config, selected: ImproveRepo, repository: Repo, now: datetime, fetch: bool = True, forced_lens: str | None = None) -> dict:
    """One shared decision for status, preview and live selection; never calls an agent."""
    settings = config.improve
    assert settings is not None
    changes = activity(repository, now, fetch=fetch)
    tracked = _git(repository, "ls-tree", "-r", "--name-only", "-z", "origin/main").split("\0")
    applicable = lenses.applicable(selected, tracked)
    rows = store.read_runs(config, repository.name, limit=1000000)
    latest = lenses.completed(rows)
    overdue = [name for name in applicable if name not in latest or now - latest[name] >= timedelta(days=7)]
    score = demand(changes, now, settings.decay)
    target = min(len(settings.slots), math.ceil(score / settings.lines_per_run))
    today = sum(row["outcome"] != "skipped" and datetime.fromisoformat(row["finished"]).astimezone(now.tzinfo).date() == now.date() for row in rows)
    chosen = forced_lens or lenses.choose(applicable, rows)
    due = bool(applicable and (overdue or today < target))
    reason = (
        "overdue lens: " + ", ".join(overdue) if overdue else (f"activity demand: {today} of {target} runs today" if today < target else "cadence satisfied")
    )
    if chosen not in applicable:
        due, reason = False, "no applicable lens" if chosen is None else f"lens {chosen} is not applicable"
    oldest = min((latest.get(name, datetime.min.replace(tzinfo=timezone.utc)) for name in overdue), default=now)
    return {
        "repo": repository.name,
        "D": score,
        "T": target,
        "today": today,
        "overdue": overdue,
        "due": due,
        "reason": reason,
        "lens": chosen,
        "oldest": oldest.isoformat(),
    }


def order(board: dict) -> tuple:
    """Overdue repositories first, then oldest overdue lens, demand and name."""
    return (not bool(board["overdue"]), datetime.fromisoformat(board["oldest"]), -board["D"], board["repo"])
