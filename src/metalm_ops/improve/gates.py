"""Deterministic size, path, owner-line and worktree-test gates before publishing."""

from __future__ import annotations

import fnmatch
import hashlib
import os
import shlex
import subprocess
from pathlib import Path

from metalm_ops.config import Improve, ImproveRepo, Repo
from metalm_ops.improve import process

EXCLUDES = (
    "guidelines/**",
    "improve/braked.toml",
    "CLAUDE.md",
    "AGENTS.md",
    "**/SKILL.md",
    "docs/generated/**",
    "docs/design/**",
    "**/migrations/**",
    "**/*schema*.sql",
    "**/*.sql",
    ".env*",
    "**/.env*",
    "**/*.plist",
    "scripts/**",
    ".github/**",
    ".pre-commit-config.yaml",
    "pyproject.toml",
    "uv.lock",
    "requirements*.txt",
    "**/*.sqlite*",
    "**/*.db",
)


class GateError(Exception):
    """A proposal must be discarded without a pull request."""


def command(settings: ImproveRepo, repository: Repo, worktree: Path) -> str:
    """Expand the trusted test command with shell-safe path placeholders."""
    return settings.test.format(venv=shlex.quote(str(repository.path / ".venv")), worktree=shlex.quote(str(worktree)))


def excluded(path: str, patterns: tuple[str, ...]) -> bool:
    """Match repo-relative globs, including root paths for recursive patterns."""
    return any(fnmatch.fnmatchcase(path, pattern) or (pattern.startswith("**/") and fnmatch.fnmatchcase(path, pattern[3:])) for pattern in patterns)


def _git(worktree: Path, *arguments: str) -> str:
    result = process.run(["git", *arguments], cwd=worktree)
    if result.returncode:
        raise GateError(f"git gate failed: {(result.stderr or result.stdout).strip()}")
    return result.stdout


def inspect(settings: Improve, selected: ImproveRepo, worktree: Path) -> dict:
    """Measure tracked and untracked changes without staging anything."""
    statistics = _git(worktree, "diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--numstat", "-z", "origin/main", "--")
    paths, changed_lines = [], 0
    for entry in statistics.split("\0"):
        if not entry:
            continue
        added, removed, name = entry.split("\t", 2)
        paths.append(name)
        if added == "-" or removed == "-":
            raise GateError(f"binary change cannot be counted: {name}")
        changed_lines += int(added) + int(removed)
    untracked = [name for name in _git(worktree, "ls-files", "--others", "--exclude-standard", "-z").split("\0") if name]
    paths.extend(untracked)
    if not 1 <= len(paths) <= settings.max_files:
        raise GateError(f"changed {len(paths)} files; expected 1 to {settings.max_files}")
    for name in paths:
        if excluded(name, (*EXCLUDES, *selected.exclude)):
            raise GateError(f"excluded path: {name}")
        if (worktree / name).is_symlink():
            raise GateError(f"symlink change is not allowed: {name}")
    diff = _git(worktree, "diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--unified=0", "origin/main", "--")
    in_hunk = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            in_hunk = False
        elif line.startswith("@@ "):
            in_hunk = True
        elif in_hunk and line.startswith(("+", "-")) and "(owner)" in line:
            raise GateError("added or removed line contains (owner)")
    stat = _git(worktree, "diff", "--no-ext-diff", "--no-textconv", "--stat", "origin/main", "--")
    for name in untracked:
        try:
            contents = (worktree / name).read_text()
        except (UnicodeError, OSError) as error:
            raise GateError(f"cannot count text change: {name}") from error
        if "\0" in contents:
            raise GateError(f"binary change cannot be counted: {name}")
        lines = contents.splitlines()
        if any("(owner)" in line for line in lines):
            raise GateError("added or removed line contains (owner)")
        changed_lines += len(lines)
        stat += f" {name} | {len(lines)} + (new file)\n"
    if changed_lines > settings.max_changed_lines:
        raise GateError(f"changed {changed_lines} lines; maximum is {settings.max_changed_lines}")
    # Fingerprint the resulting files, so staging a new file doesn't change it.
    digest = hashlib.sha256()
    for name in sorted(paths):
        path = worktree / name
        digest.update(name.encode() + b"\0")
        digest.update(path.read_bytes() if path.exists() else b"<deleted>")
        digest.update(str(path.stat().st_mode if path.exists() else 0).encode())
    fingerprint = digest.hexdigest()
    return {"files": paths, "changed_lines": changed_lines, "diff_stat": stat.strip(), "fingerprint": fingerprint}


def check(settings: Improve, selected: ImproveRepo, repository: Repo, worktree: Path, directory: Path) -> dict:
    """Run the configured suite against the worktree and prove its import origins."""
    measured = inspect(settings, selected, worktree)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(worktree / "src") + (os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
    test = command(selected, repository, worktree)
    try:
        result = process.run(["/bin/sh", "-c", test], cwd=worktree, env=environment, timeout=3600)
    except (OSError, subprocess.TimeoutExpired) as error:
        (directory / "tests.log").write_text(str(error))
        raise GateError(f"test command failed: {error}") from error
    (directory / "tests.log").write_text((result.stdout or "") + (result.stderr or ""))
    if result.returncode:
        raise GateError(f"test command failed (exit {result.returncode}): {test}")
    imports = []
    packages = sorted((worktree / "src").glob("*/__init__.py"))
    if not packages:
        raise GateError("no package under src/ to check that the tests imported the worktree's code")
    for package in packages:
        name = package.parent.name
        script = f"import importlib; print(importlib.import_module({name!r}).__file__)"
        try:
            result = process.run([str(repository.path / ".venv" / "bin" / "python"), "-c", script], cwd=worktree, env=environment)
        except (OSError, subprocess.TimeoutExpired) as error:
            (directory / "imports.log").write_text(str(error))
            raise GateError("tests did not import the worktree's code") from error
        output = (result.stdout or "").strip()
        imports.append(f"{name}: {output}\n{result.stderr or ''}")
        if result.returncode or not output or not Path(output).resolve().is_relative_to(worktree.resolve()):
            (directory / "imports.log").write_text("\n".join(imports))
            raise GateError("tests did not import the worktree's code")
    (directory / "imports.log").write_text("\n".join(imports))
    if inspect(settings, selected, worktree)["fingerprint"] != measured["fingerprint"]:
        raise GateError("tests changed the proposal; the changed code was not verified")
    return {**measured, "test": test, "tests": "passed", "imports": "passed"}


def check_evidence(worktree: Path, evidence: list[dict], base: str = "origin/main") -> str:
    """Match full quoted line ranges at the pinned base, normalizing only within lines."""
    for item in evidence:
        name, start, end = item["path"], item["start_line"], item["end_line"]
        reason = f"evidence quote not found: {name}:{start}-{end}"
        if not name or Path(name).is_absolute() or ".." in Path(name).parts or start < 1 or end < start:
            return reason
        result = process.run(["git", "show", f"{base}:{name}"], cwd=worktree)
        if result.returncode:
            return reason
        lines = result.stdout.removesuffix("\n").split("\n") if result.stdout else []
        quoted = item["quote"].removesuffix("\n").split("\n")

        def normalize(values: list[str]) -> list[str]:
            return [" ".join(line.split()) for line in values]

        if end > len(lines) or not quoted or normalize(lines[start - 1 : end]) != normalize(quoted):
            return reason
    return ""
