"""`metalm-ops doctor`: every owner-run step no code installs, each with its fix command.

The nightly job runs it first, so a missing piece reaches that night's alert.
"""

from __future__ import annotations

import json
import plistlib
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from metalm_ops import offsite, schedule, status
from metalm_ops.backup import unmounted_volume
from metalm_ops.config import Config

NOTIFIER = Path("~/.local/bin/superlm-notify")
WAKE_RE = re.compile(r"wake\w*\s+at\s+(\d{1,2}):(\d{2})\s*([AP]M)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Finding:
    name: str
    ok: bool
    detail: str
    fix: str = ""
    required: bool = True


def wake_times(pmset_sched: str) -> list[tuple[int, int]]:
    """Repeating wake times (hour, minute, 24 h) from `pmset -g sched` output."""
    times = []
    for hour, minute, half in WAKE_RE.findall(pmset_sched):
        h = int(hour) % 12 + (12 if half.upper() == "PM" else 0)
        times.append((h, int(minute)))
    return times


def wake_covers(job: tuple[int, int], wakes: list[tuple[int, int]]) -> bool:
    """True when some wake falls 1 to 30 minutes before the job's start."""
    start = job[0] * 60 + job[1]
    return any(1 <= (start - (h * 60 + m)) % 1440 <= 30 for h, m in wakes)


def check(cfg: Config) -> list[Finding]:
    out = []
    parent = cfg.backup.local_dir.parent
    out.append(Finding("local backup folder", parent.is_dir(), str(cfg.backup.local_dir), f"mkdir -p {parent}"))
    for db in cfg.databases:
        volume = unmounted_volume(db.path)
        ok = volume is None and db.path.is_file()
        detail = f"volume {volume} not mounted" if volume else ("present" if ok else f"missing: {db.path}")
        out.append(Finding(f"database {db.repo}/{db.name}", ok, detail, "mount the volume, or fix the path in ops.toml"))
    exe = offsite.restic_path()
    out.append(Finding("restic", exe is not None, exe or "not installed", "brew install restic"))
    out.append(Finding("b2 bucket", bool(cfg.backup.b2_bucket), cfg.backup.b2_bucket or "unset", "add b2_bucket to [backup] in ops.toml"))
    for service in offsite.KEYCHAIN.values():
        out.append(
            Finding(
                f"keychain {service}",
                offsite.keychain_has(service),
                "present" if offsite.keychain_has(service) else "missing",
                f'security add-generic-password -a "$USER" -s {service} -w',
            )
        )
    notifier = NOTIFIER.expanduser()
    out.append(Finding("superlm-notify", notifier.exists(), str(notifier), "run metalm's ./install.sh"))
    for job in schedule.JOBS:
        row = status.agent(schedule.label(cfg, job))
        out.append(
            Finding(
                f"agent {schedule.label(cfg, job)}",
                row.level != status.RED,
                row.detail,
                schedule.install_command(cfg, job),
                required=job != "improve" or cfg.improve is not None,
            )
        )
    when = schedule.start_time(schedule.installed_path(cfg, "backup"))
    if when:
        _, sched = status._run(["/usr/bin/pmset", "-g", "sched"])
        h, m = (when[0] * 60 + when[1] - 5) % 1440 // 60, (when[0] * 60 + when[1] - 5) % 60
        out.append(
            Finding(
                "daily wake before backup",
                wake_covers(when, wake_times(sched)),
                f"backup at {when[0]:02d}:{when[1]:02d}",
                f"sudo pmset repeat wakeorpoweron MTWRFSU {h:02d}:{m:02d}:00",
            )
        )
    served = status.health(cfg.port)
    out.append(
        Finding("dashboard /health", served.level == status.GREEN, served.detail, f"launchctl kickstart -k gui/$(id -u)/{cfg.serve_label}", required=False)
    )
    out.extend(improve_checks(cfg))
    return out


def failed(findings: list[Finding]) -> bool:
    return any(f.required and not f.ok for f in findings)


def _signals_check() -> Finding:
    """metalm's own ruff and one signals pass over metalm itself, so a broken measuring tool shows here."""
    from pathlib import Path

    from metalm_ops.improve import run as improve_run
    from metalm_ops.improve import signals
    from metalm_ops.schedule import CHECKOUT

    if not improve_run.RUFF_BIN.is_file():
        return Finding("improve signals", False, f"no ruff at {improve_run.RUFF_BIN}", "reinstall metalm's .venv with its dev extras")
    try:
        report = signals.measure(Path(CHECKOUT), ruff_bin=improve_run.RUFF_BIN)
    except Exception as error:
        return Finding("improve signals", False, str(error)[:200], "metalm-ops improve signals --repo metalm")
    if report["errors"]:
        return Finding(
            "improve signals",
            False,
            "; ".join(f"{item['signal']}: {item['error']}" for item in report["errors"])[:200],
            "metalm-ops improve signals --repo metalm",
        )
    return Finding("improve signals", True, f"{len(report['findings'])} findings on metalm, every signal ran")


def improve_checks(configuration: Config) -> list[Finding]:
    """Check the opt-in auto-improve dependencies without running either agent."""
    from metalm_ops.improve import agents, brake
    from metalm_ops.improve.run import LABELS, ImproveError, newest_prompt

    settings = configuration.improve
    if settings is None:
        return [Finding("auto-improve", True, "not configured; disabled", required=False)]
    from metalm_ops.improve import lenses

    try:
        for name in lenses.NAMES:
            lenses.load(name)
        for path in (agents.ROOT / "lenses").glob("*.md"):
            header = lenses.metadata(path.read_text())
            if any(header.get(key) not in {"true", "false"} for key in ("may_change_behaviour", "needs_measurement")):
                raise ValueError(f"{path.name}: invalid lens flags")
        for name in ("propose", "review_senior", "review_boundaries", "verify"):
            newest_prompt(name)
        for path in (agents.ROOT / "prompts").glob("*.md"):
            metadata = lenses.metadata(path.read_text())
            if not (agents.ROOT / "schemas" / metadata.get("output_schema", "")).is_file():
                raise ValueError(f"{path.name}: missing output schema")
        prompt_finding = Finding("improve lenses and prompts", True, "all packaged front matter parses")
    except (ValueError, OSError, ImproveError) as error:
        prompt_finding = Finding("improve lenses and prompts", False, str(error), "reinstall metalm from its main checkout")
    findings = [prompt_finding, _signals_check()]
    codex = agents.codex_binary(settings)
    claude = agents.claude_binary(settings)
    for name, executable in (("codex_bin", codex), ("claude_bin", claude)):
        exists = Path(executable).is_file() or shutil.which(executable) is not None
        findings.append(Finding(f"improve {name}", exists, executable, f"set [improve] {name} in ops.toml to the installed executable"))
    code, output = status._run([codex, "login", "status"])
    findings.append(
        Finding("improve Codex login", code == 0 and "Logged in" in output, "logged in" if "Logged in" in output else "not logged in", f"{codex} login")
    )
    code, output = status._run([status.gh(), "auth", "status"])
    findings.append(Finding("improve GitHub auth", code == 0, "authenticated" if code == 0 else status._first_line(output), "gh auth login"))
    repositories = {repository.name: repository for repository in configuration.repos}
    for selected in settings.repos:
        repository = repositories.get(selected.name)
        findings.append(
            Finding(
                f"improve {selected.name} repo",
                repository is not None,
                "configured" if repository else "missing [[repo]] row",
                "add the matching [[repo]] row in ops.toml",
            )
        )
        if repository is None:
            continue
        for name, path in (("path", repository.path), ("venv", repository.path / ".venv")):
            findings.append(Finding(f"improve {selected.name} {name}", path.is_dir(), str(path), f"set up {repository.path} and its .venv"))
        code, output = status._run([status.gh(), "label", "list", "--repo", repository.github, "--limit", "1000", "--json", "name"])
        try:
            present = {row["name"] for row in json.loads(output)} if code == 0 else set()
        except (json.JSONDecodeError, TypeError, KeyError):
            present = set()
        missing = [name for name, _, _ in LABELS if name not in present]
        findings.append(
            Finding(
                f"improve {selected.name} labels",
                not missing,
                "all six labels present" if not missing else "missing: " + ", ".join(missing),
                f"metalm-ops improve labels --repo {selected.name}",
            )
        )
    if not any(repository.github == "nagarkar/metalm" and repository.name in {row.name for row in settings.repos} for repository in configuration.repos):
        code, output = status._run([status.gh(), "label", "list", "--repo", "nagarkar/metalm", "--limit", "1000", "--json", "name"])
        try:
            present = {row["name"] for row in json.loads(output)} if code == 0 else set()
        except (json.JSONDecodeError, TypeError, KeyError):
            present = set()
        missing = [name for name, _, _ in LABELS if name not in present]
        findings.append(
            Finding(
                "improve metalm labels", not missing, "all six labels present" if not missing else "missing: " + ", ".join(missing), "metalm-ops improve labels"
            )
        )
    installed = schedule.installed_path(configuration, "improve")
    expected = [{"Hour": int(slot[:2]), "Minute": int(slot[3:])} for slot in settings.slots]
    try:
        intervals = plistlib.loads(installed.read_bytes()).get("StartCalendarInterval")
        matches = intervals == expected
        detail = ", ".join(settings.slots) if matches else "installed times differ from improve.slots"
    except (OSError, ValueError, plistlib.InvalidFileException) as error:
        matches, detail = False, str(error)
    findings.append(Finding("improve plist matches slots", matches, detail, schedule.install_command(configuration, "improve")))
    try:
        brake.read(configuration, fetch=False)
        findings.append(Finding("improve braked.toml", True, "origin/main brake entries parse"))
    except (ValueError, OSError, ImproveError) as error:
        findings.append(Finding("improve braked.toml", False, str(error), "fix improve/braked.toml in metalm through a PR"))
    return findings
