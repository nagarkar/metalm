"""Off-site backups: encrypt the newest local run with restic and send it to Backblaze B2.

Secrets come from the login keychain at call time and reach restic only
through its environment; they are never written, logged or printed.
"""

from __future__ import annotations

import getpass
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from metalm_ops import backup
from metalm_ops.config import Config

KEYCHAIN = {
    "B2_ACCOUNT_ID": "metalm-b2-key-id",
    "B2_ACCOUNT_KEY": "metalm-b2-app-key",
    "RESTIC_PASSWORD": "metalm-restic-password",
}
RESTIC_PLACES = ("/opt/homebrew/bin/restic", "/usr/local/bin/restic")  # launchd's PATH has neither
CHECK_EVERY = timedelta(days=7) - timedelta(hours=12)  # weekly, with slack for a late night
TAG = "metalm"

RUNNER = None  # tests set a fake: (argv, env) -> (returncode, output)


class OffsiteError(Exception):
    """Off-site backup cannot run; the message names the fix."""


def _run(argv: list[str], env: dict[str, str]) -> tuple[int, str]:
    if RUNNER is not None:
        return RUNNER(argv, env)
    proc = subprocess.run(argv, env=env, capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr)[-2000:]


def restic_path() -> str | None:
    found = shutil.which("restic")
    if found:
        return found
    return next((p for p in RESTIC_PLACES if Path(p).is_file()), None)


def keychain_has(service: str) -> bool:
    """True when the login keychain has an entry for `service`; reads no secret."""
    code, _ = _run(["/usr/bin/security", "find-generic-password", "-a", getpass.getuser(), "-s", service], {})
    return code == 0


def secret_env(cfg: Config) -> dict[str, str]:
    env = {"PATH": "/usr/bin:/bin", "HOME": os.path.expanduser("~"), "RESTIC_REPOSITORY": cfg.backup.restic_repo}
    for var, service in KEYCHAIN.items():
        code, out = _run(["/usr/bin/security", "find-generic-password", "-a", getpass.getuser(), "-s", service, "-w"], {})
        if code != 0:
            raise OffsiteError(f'keychain has no {service}. Add it: security add-generic-password -a "$USER" -s {service} -w')
        env[var] = out.strip()
    return env


def _restic(cfg: Config, *args: str) -> tuple[int, str]:
    exe = restic_path()
    if exe is None:
        raise OffsiteError("restic is not installed. Install it: brew install restic")
    if not cfg.backup.b2_bucket:
        raise OffsiteError('ops.toml [backup] has no b2_bucket. Add b2_bucket = "<bucket name>"')
    return _run([exe, *args], secret_env(cfg))


def init(cfg: Config) -> dict:
    """Create the restic repository in the bucket (once)."""
    code, out = _restic(cfg, "init")
    lines = out.strip().splitlines()
    return {"kind": "init", "ok": code == 0, "detail": lines[0] if lines else ""}  # "created restic repository <id> at <repo>"


def _due_check(cfg: Config, now: datetime) -> bool:
    checks = [r for r in backup.read_runs(cfg) if r.get("kind") == "check" and r.get("ok")]
    if not checks:
        return True
    return now - datetime.fromisoformat(checks[-1]["ts"]) >= CHECK_EVERY


def run(cfg: Config, *, now: datetime | None = None, dry_run: bool = False, force_check: bool = False) -> list[dict]:
    """Send the newest local run to B2, apply retention, and check a subset weekly; return the rows recorded."""
    now = now or datetime.now(UTC)
    dirs = backup.run_dirs(cfg.backup.local_dir)
    if not dirs:
        raise OffsiteError(f"no local run in {cfg.backup.local_dir}. Run first: metalm-ops backup run")
    newest = dirs[-1]
    b = cfg.backup
    steps = [
        ("offsite", ["backup", "--tag", TAG, "--host", TAG, str(newest)]),
        (
            "forget",
            [
                "forget",
                "--tag",
                TAG,
                "--group-by",
                "host,tags",
                "--keep-daily",
                str(b.keep_daily),
                "--keep-weekly",
                str(b.keep_weekly),
                "--keep-monthly",
                str(b.keep_monthly),
                "--prune",
            ],
        ),
    ]
    if force_check or _due_check(cfg, now):
        steps.append(("check", ["check", f"--read-data-subset={b.check_subset}"]))
    if dry_run:
        return [{"kind": kind, "ts": now.isoformat(), "ok": True, "dry_run": True, "detail": "restic " + " ".join(args)} for kind, args in steps]
    rows = []
    for kind, args in steps:
        started = time.monotonic()
        code, out = _restic(cfg, *args)
        lines = out.strip().splitlines()
        row = {
            "kind": kind,
            "ts": now.isoformat(),
            "ok": code == 0,
            "source": newest.name,
            "detail": lines[-1] if lines else "",
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        backup.record(cfg, row)
        rows.append(row)
        if kind == "offsite" and code != 0:
            break  # nothing new reached B2; leave retention alone
    return rows
