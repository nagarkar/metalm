"""metalm_gendocs.cli: flags, exit codes and messages, run as other repos run it."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from conftest import put

from metalm_gendocs import generate
from metalm_gendocs.cli import main


def test_exit_codes_are_zero_or_one(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--root", str(repo), "--dry-run"]) == 1
    assert main(["--root", str(repo)]) == 1
    assert "add them and commit again" in capsys.readouterr().err
    assert main(["--root", str(repo)]) == 0
    assert main(["--root", str(repo), "--dry-run"]) == 0
    put(repo, "src/shop/web.py", "def broken(:\n")
    assert main(["--root", str(repo)]) == 1
    assert capsys.readouterr().err.startswith("error: ")


def test_check_is_a_hidden_alias_of_dry_run(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--root", str(repo), "--check"]) == 1
    assert "stale: " in capsys.readouterr().out
    assert not (repo / "docs/generated").exists()
    with pytest.raises(SystemExit):
        main(["--help"])
    assert "--check" not in capsys.readouterr().out


def test_help_ends_with_an_example(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.rstrip().splitlines()[-1] == "example: metalm-gendocs --dry-run"


def test_usage_error_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--no-such-flag"])
    assert exit_info.value.code != 0


def test_imports_nothing_from_the_target_repo(repo: Path) -> None:
    put(repo, "src/shop/web.py", '"""Web: importing me would fail."""\nraise SystemExit("imported")\n')
    out = subprocess.run([sys.executable, "-m", "metalm_gendocs.cli", "--root", str(repo)], check=False, capture_output=True, text=True)
    assert out.returncode == 1, out.stderr
    assert "imported" not in out.stdout + out.stderr


def test_uncovered_languages_are_listed_for_the_agent_to_raise(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    put(repo, "src/native/Bridge.swift", "// swift\n")
    put(repo, "src/native/main.go", "// go\n")
    index = generate(repo)["docs/generated/index.md"]
    assert "## Not covered" in index and "Go (1 files), Swift (1 files)" in index
    assert "ask the owner whether to add each language" in index
    main(["--root", str(repo)])
    assert "not covered: Go, Swift" in capsys.readouterr().err


@pytest.mark.cuj("A commit that changes a docstring regenerates docs/generated/, and a stale copy fails the dry run.")
def test_docstring_change_regenerates_docs_and_stale_copy_fails(repo: Path) -> None:
    def run(*flags: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "metalm_gendocs.cli", "--root", str(repo), *flags], check=False, capture_output=True, text=True)

    assert run().returncode == 1
    assert run("--dry-run").returncode == 0
    put(repo, "src/shop/web.py", '"""Web: the HTTP surface, now with a cart."""\n')
    stale = run("--dry-run")
    assert stale.returncode == 1 and "stale: docs/generated/index.md" in stale.stdout
    assert run().returncode == 1
    assert "now with a cart" in (repo / "docs/generated/index.md").read_text()
    assert run("--dry-run").returncode == 0
