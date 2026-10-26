"""Launch agent plists for the nightly backup and the dashboard, rendered from package templates.

The templates hold placeholders, never the owner's label prefix or paths; the
owner installs the rendered copy (operations.md#launch-agents).
"""

from __future__ import annotations

import plistlib
from importlib import resources
from pathlib import Path

from metalm_ops.config import Config

CHECKOUT = Path(__file__).resolve().parents[2]
JOBS = ("backup", "serve")


def label(cfg: Config, job: str) -> str:
    return cfg.backup_label if job == "backup" else cfg.serve_label


def render(cfg: Config, job: str, checkout: Path = CHECKOUT) -> str:
    text = resources.files("metalm_ops").joinpath("templates", f"{job}.plist").read_text()
    for key, value in {"@LABEL@": label(cfg, job), "@CHECKOUT@": str(checkout), "@LOGDIR@": str(cfg.state_dir / "logs")}.items():
        text = text.replace(key, value)
    return text


def installed_path(cfg: Config, job: str) -> Path:
    return Path("~/Library/LaunchAgents").expanduser() / f"{label(cfg, job)}.plist"


def install_command(cfg: Config, job: str) -> str:
    dest = installed_path(cfg, job)
    launcher = CHECKOUT / "metalm-ops.sh"  # rendered from the checkout the agent will run
    return f"mkdir -p {cfg.state_dir / 'logs'} && {launcher} schedule print {job} > {dest} && launchctl bootstrap gui/$(id -u) {dest}"


def start_time(plist: Path) -> tuple[int, int] | None:
    """(hour, minute) from an installed plist's StartCalendarInterval, or None."""
    if not plist.exists():
        return None
    with plist.open("rb") as fh:
        when = plistlib.load(fh).get("StartCalendarInterval")
    if not isinstance(when, dict) or "Hour" not in when:
        return None
    return when["Hour"], when.get("Minute", 0)
