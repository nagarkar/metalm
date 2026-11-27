"""Versioned lens missions, applicability and oldest-completed-run rotation."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath

NAMES = ("readability", "modularity", "documentation", "duplication", "tests", "backend-robustness", "frontend-robustness", "ui", "performance", "drift")
OLD_NAMES = {"refactor": "readability", "docs": "documentation", "duplicate": "duplication"}


@dataclass(frozen=True, slots=True)
class Lens:
    name: str
    mission: str
    may_change_behaviour: bool
    needs_measurement: bool
    max_files: int | None = None  # a lens may allow a larger change than [improve] max_files (modularity)
    max_changed_lines: int | None = None


def metadata(text: str) -> dict:
    """Parse the flat front matter shared by packaged prompts and lenses."""
    if not text.startswith("---\n") or len(text.split("---", 2)) != 3:
        raise ValueError("missing front matter")
    result = {}
    for line in text.split("---", 2)[1].strip().splitlines():
        key, separator, value = line.partition(":")
        if not separator or key in result:
            raise ValueError("invalid front matter")
        result[key] = value.strip()
    if not result.get("id") or not result.get("version", "").isdigit():
        raise ValueError("front matter needs id and numeric version")
    return result


def load(name: str) -> Lens:
    """Load the latest mission and its explicit behaviour/measurement boundaries."""
    from metalm_ops.improve.run import newest_prompt

    if name not in NAMES:
        raise ValueError(f"unknown lens: {name}")
    text = newest_prompt(name, folder="lenses").read_text()
    header = metadata(text)
    for key in ("may_change_behaviour", "needs_measurement"):
        if header.get(key) not in ("true", "false"):
            raise ValueError(f"{name}: invalid {key}")
    limits = {key: int(header[key]) for key in ("max_files", "max_changed_lines") if key in header}
    return Lens(name, text.split("---", 2)[2].strip(), header["may_change_behaviour"] == "true", header["needs_measurement"] == "true", **limits)


def applicable(selected, tracked: list[str]) -> tuple[str, ...]:
    """Limit lenses by configuration and tracked front-end files, in rotation order."""
    frontend = any(
        PurePosixPath(path).suffix in {".html", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte"}
        and not set(PurePosixPath(path).parts) & {"node_modules", ".venv", "docs", "tests"}
        for path in tracked
    )
    return tuple(name for name in NAMES if (selected.lenses is None or name in selected.lenses) and (frontend or name not in {"frontend-robustness", "ui"}))


PROPOSER_SKIP = "proposer found nothing: "  # a lens the proposer searched counts as done, so the next run moves on


def completed(rows: list[dict]) -> dict[str, datetime]:
    """Latest completion for each lens, including historical categories. A run that never reached the
    proposer's judgement (a failure, a cap or limit skip) does not count: the lens was not looked at."""
    result = {}
    for row in rows:
        if row["outcome"] == "failed" or (row["outcome"] == "skipped" and not row.get("reason", "").startswith(PROPOSER_SKIP)):
            continue
        name = row.get("lens") or row.get("category")
        name = OLD_NAMES.get(name, name)
        when = datetime.fromisoformat(row["finished"])
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if name in NAMES and (name not in result or when > result[name]):
            result[name] = when
    return result


def choose(names: tuple[str, ...], rows: list[dict]) -> str | None:
    """Pick the never-run or oldest completed lens; table order breaks ties."""
    latest = completed(rows)
    return min(names, key=lambda name: (latest.get(name, datetime.min.replace(tzinfo=timezone.utc)), NAMES.index(name))) if names else None
