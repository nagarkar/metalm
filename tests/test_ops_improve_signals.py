"""The deterministic signals find each planted problem in a real git repo, with metalm's ruff (#97)."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from metalm_ops.improve import signals

RUFF = Path(sys.executable).parent / "ruff"
NOW = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)


def git(root: Path, *arguments: str, date: str = "2026-11-25T12:00:00+00:00") -> None:
    environment = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date, "PATH": "/usr/bin:/bin", "HOME": str(root)}
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *arguments], cwd=root, check=True, capture_output=True, env=environment)


DUPLICATE = "\n".join(f"    total = total + value * {number} - offset" for number in range(14))


def plant(root: Path) -> Path:
    package = root / "src" / "pkg"
    (package / "sub").mkdir(parents=True)
    (root / "tests").mkdir()
    (package / "__init__.py").write_text('"""Package."""\n')
    (package / "sub" / "__init__.py").write_text('"""Sub."""\n')
    (package / "long.py").write_text(
        '"""Long."""\n\n\ndef long_function():\n    """Doc."""\n' + "".join(f"    x{n} = {n}\n" for n in range(70)) + "    return x0\n"
    )
    branches = "".join(f"    if value == {n}:\n        return {n}\n" for n in range(12))
    (package / "tangled.py").write_text(f'"""Tangled."""\n\n\ndef tangled(value):\n    """Doc."""\n{branches}    return -1\n')
    (package / "a.py").write_text('"""A."""\nfrom pkg import b\n\nVALUE = 1\n')
    (package / "b.py").write_text('"""B."""\nfrom pkg import a\n\nVALUE = 2\n')
    (package / "dup_one.py").write_text(f'"""One."""\n\n\ndef first(value, offset):\n    """Doc."""\n    total = 0\n{DUPLICATE}\n    return total\n')
    (package / "dup_two.py").write_text(f'"""Two."""\n\n\ndef second(value, offset):\n    """Doc."""\n    total = 0\n{DUPLICATE}\n    return total\n')
    (package / "unsafe.py").write_text('"""Unsafe."""\nimport pickle\n\n\ndef load(blob):\n    """Doc."""\n    return pickle.loads(blob)\n')
    (package / "nodoc.py").write_text("def public():\n    return 1\n")
    (package / "lonely.py").write_text('"""Lonely."""\n' + "".join(f'\n\ndef f{n}():\n    """Doc."""\n    return {n}\n' for n in range(12)))
    (root / "tests" / "test_long.py").write_text("from pkg import long\n\n\ndef test_long():\n    assert long.long_function() == 0\n")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "plant", date="2026-11-01T12:00:00+00:00")
    (package / "unsafe.py").write_text((package / "unsafe.py").read_text() + '\n\ndef again():\n    """Doc."""\n    return 2\n')
    git(root, "commit", "-qam", "recent change")
    return root


@pytest.fixture
def report(tmp_path):
    root = plant(tmp_path / "repo")
    return root, signals.measure(root, ruff_bin=RUFF, now=NOW)


def by(report: dict, signal: str) -> list[dict]:
    return [item for item in report["findings"] if item["signal"] == signal]


def test_every_signal_runs_without_errors(report):
    assert report[1]["errors"] == []


def test_size_finds_the_long_function_only(report):
    found = by(report[1], "size")
    assert [(item["path"], item["symbol"]) for item in found] == [("src/pkg/long.py", "long_function")]


def test_complexity_comes_from_ruff_with_the_standard_limit(report):
    found = by(report[1], "complexity")
    assert any(item["path"] == "src/pkg/tangled.py" and item["metric"] == "C901" and item["value"] > 10 for item in found)


def test_coupling_finds_the_import_cycle(report):
    cycles = [item for item in by(report[1], "coupling") if item["metric"] == "import cycle"]
    assert len(cycles) == 1 and "pkg.a -> pkg.b" in cycles[0]["detail"] and cycles[0]["related"] == ["src/pkg/b.py"]


def test_duplication_finds_the_copied_block_across_files(report):
    found = by(report[1], "duplication")
    assert found and found[0]["path"] == "src/pkg/dup_one.py" and found[0]["other"]["path"] == "src/pkg/dup_two.py"
    assert found[0]["value"] >= 12


def test_security_and_docs_come_from_ruff(report):
    assert any(item["path"] == "src/pkg/unsafe.py" and item["metric"] == "S301" for item in by(report[1], "security"))
    assert any(item["path"] == "src/pkg/nodoc.py" for item in by(report[1], "docs"))


def test_untested_finds_modules_no_test_imports(report):
    found = {item["path"] for item in by(report[1], "untested")}
    assert "src/pkg/lonely.py" in found and "src/pkg/long.py" not in found


def test_churn_names_recently_changed_files_only(report):
    assert [item["path"] for item in by(report[1], "churn")] == ["src/pkg/unsafe.py"]


def test_slow_tests_come_from_the_junit_timings(tmp_path):
    root = plant(tmp_path / "repo")
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<testsuites><testsuite><testcase classname="tests.test_long" name="test_long" time="3.5"/><testcase classname="tests.test_long" name="quick" time="0.1"/></testsuite></testsuites>'
    )
    found = by(signals.measure(root, ruff_bin=RUFF, junit=junit, now=NOW), "slow-tests")
    assert [(item["path"], item["value"]) for item in found] == [("tests/test_long.py", 3.5)]


def test_excludes_and_thresholds_are_respected(tmp_path):
    root = plant(tmp_path / "repo")
    measured = signals.measure(root, ruff_bin=RUFF, excludes=("src/pkg/long.py",), thresholds={"function_lines": 500}, now=NOW)
    assert not by(measured, "size") and all(item["path"] != "src/pkg/long.py" for item in measured["findings"])


def test_a_broken_tool_is_reported_and_the_other_signals_still_run(tmp_path):
    root = plant(tmp_path / "repo")
    measured = signals.measure(root, ruff_bin=tmp_path / "no-ruff", now=NOW)
    assert [error["signal"] for error in measured["errors"]] == ["ruff"] and by(measured, "size")


def test_candidates_prefer_measured_findings_in_recently_changed_files(report):
    first = signals.candidates(report[1], "backend-robustness", seed="s")[0]
    assert first["signal"] == "security" and first["path"] == "src/pkg/unsafe.py"
    drift = signals.candidates(report[1], "drift", seed="s")
    assert [item["signal"] for item in drift] == ["churn"]


def test_candidates_skip_avoided_fingerprints_and_rotate_by_seed(report):
    docs = signals.candidates(report[1], "documentation", seed="s")
    rest = signals.candidates(report[1], "documentation", avoid={docs[0]["fingerprint"]}, seed="s")
    assert docs[0] not in rest and len(rest) == len(docs) - 1


def test_target_files_hold_the_finding_its_related_file_and_its_tests(report):
    cycle = next(item for item in by(report[1], "coupling") if item["metric"] == "import cycle")
    assert signals.target_files(report[1], cycle) == ["src/pkg/a.py", "src/pkg/b.py"]
    long = by(report[1], "size")[0]
    assert signals.target_files(report[1], long) == ["src/pkg/long.py", "tests/test_long.py"]


def test_improved_needs_the_finding_gone_or_smaller(report):
    before = by(report[1], "size")[0]
    assert signals.improved(before, {"findings": []})[0]
    assert signals.improved(before, {"findings": [{**before, "value": before["value"] - 5}]})[0]
    worse = signals.improved(before, {"findings": [before]})
    assert not worse[0] and worse[1].startswith("finding not improved")
    assert signals.improved(by(report[1], "churn")[0], {"findings": []})[0]
