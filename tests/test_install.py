"""install.sh against a throwaway home: first run, rerun, dry run, a taken link, uninstall (install-scripts.md#tests)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OWNER_TEXT = "# My global notes\n\n- keep this line\n"


def install(home: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if key != "CLAUDE_CONFIG_DIR"}
    env["HOME"] = str(home)
    return subprocess.run([str(ROOT / "install.sh"), *flags], check=False, capture_output=True, text=True, env=env)


def snapshot(home: Path) -> dict[str, str]:
    """Every path under home: file text, or the link target for a symlink."""
    found: dict[str, str] = {}
    for folder, dirs, files in os.walk(home):  # does not follow links into the metalm clone
        for name in dirs + files:
            path = Path(folder) / name
            rel = path.relative_to(home).as_posix()
            if path.is_symlink():
                found[rel] = "-> " + os.readlink(path)
            elif path.is_file():
                found[rel] = path.read_text()
    return found


@pytest.fixture
def home(tmp_path: Path) -> Path:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude/CLAUDE.md").write_text(OWNER_TEXT)
    return tmp_path


@pytest.mark.cuj("The owner runs install.sh: the global CLAUDE.md gains the metalm block with a backup, a rerun changes nothing, and --uninstall restores it.")
def test_install_rerun_and_uninstall_restore_the_owner_file(home: Path) -> None:
    first = install(home)
    assert first.returncode == 0, first.stderr
    global_md = (home / ".claude/CLAUDE.md").read_text()
    assert global_md.startswith(OWNER_TEXT) and "<!-- metalm:begin -->" in global_md
    assert os.readlink(home / ".claude/metalm") == str(ROOT)
    assert os.readlink(home / ".claude/skills/metalm-setup") == str(ROOT / "skills/metalm-setup")
    assert os.readlink(home / ".local/bin/superlm-notify") == str(ROOT / "bin/superlm-notify")
    assert [p.name for p in (home / ".claude").glob("CLAUDE.md.bak.*")]

    before = snapshot(home)
    rerun = install(home)
    assert rerun.returncode == 0, rerun.stderr
    assert snapshot(home) == before
    assert "linked:" not in rerun.stdout and "updated:" not in rerun.stdout

    removed = install(home, "--uninstall")
    assert removed.returncode == 0, removed.stderr
    assert (home / ".claude/CLAUDE.md").read_text() == OWNER_TEXT
    assert not (home / ".claude/metalm").exists() and not (home / ".local/bin/superlm-notify").exists()


def test_dry_run_writes_nothing(home: Path) -> None:
    """Source: install-scripts.md#rules: --dry-run writes nothing and prints what would change."""
    before = snapshot(home)
    result = install(home, "--dry-run")
    assert result.returncode == 0, result.stderr
    assert snapshot(home) == before
    assert "would: link" in result.stdout and "would: back up and update" in result.stdout
    assert "backup: " not in result.stdout


def test_a_link_taken_by_something_else_stops_before_any_write(home: Path) -> None:
    """Source: install-scripts.md#rules: an existing link pointing elsewhere stops the install and is reported."""
    (home / ".local/bin").mkdir(parents=True)
    (home / ".local/bin/superlm-notify").symlink_to("/usr/bin/true")
    before = snapshot(home)
    result = install(home)
    assert result.returncode == 1
    assert result.stderr.startswith("error: ") and "points to /usr/bin/true" in result.stderr
    assert snapshot(home) == before


def test_unknown_option_exits_one(home: Path) -> None:
    """Source: cli.md#output-and-errors: exit 1 on any error, with `error:`."""
    result = install(home, "--bogus")
    assert result.returncode == 1 and result.stderr.startswith("error: unknown option")
