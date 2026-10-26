"""`metalm-ops doctor`: every owner-run step no code installs, each with its fix command.

The nightly job runs it first, so a missing piece reaches that night's alert.
"""

from __future__ import annotations

import re
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
        out.append(Finding(f"agent {schedule.label(cfg, job)}", row.level != status.RED, row.detail, schedule.install_command(cfg, job)))
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
    return out


def failed(findings: list[Finding]) -> bool:
    return any(f.required and not f.ok for f in findings)
