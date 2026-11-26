"""Offline repositories and CLI-agent fixtures for the owner's issue #80 journeys."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from metalm_ops.config import parse

PROPOSAL = {
    "skip": False,
    "skip_reason": "",
    "category": "readability",
    "lens": "readability",
    "claim": "The arithmetic comment is less precise than the code.",
    "evidence": [{"path": "src/sample/__init__.py", "start_line": 1, "end_line": 1, "quote": "# Add the pair."}],
    "measurement": "",
    "title": "Correct the arithmetic helper comment",
    "summary": "Correct one stale comment.",
    "why_safe": "Only a comment changes.",
    "tests_run": "The arithmetic test passed.",
}
VERDICT = {
    "verdict": "approve",
    "clear_cut": True,
    "confidence": 0.95,
    "behaviour_change": False,
    "risks": [],
    "reasons": "The comment is accurate and the change is minimal.",
}
LABELS = {
    "auto-improve-brake": ("B60205", "A visible auto-improve brake or owner-authorized resume"),
    "auto-improve": ("5319E7", "Opened by the daily auto-improve system (metalm-ops improve)"),
    "codex-automated": ("10A37F", "Written by OpenAI Codex, reviewed by Claude; no human in the loop"),
    "auto-improve-rejected": ("B60205", "Auto-improve PR closed by its reviewers, CI or gates"),
    "auto-improve-checked": ("C2E0C6", "A Claude session checked this merged auto-improve PR"),
    "auto-improve-flagged": ("FBCA04", "A Claude session flagged this auto-improve PR as risky"),
}


def git(path: Path, *arguments: str) -> str:
    """Run local Git with an isolated configuration, never a network origin."""
    environment = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    result = subprocess.run(["git", "-C", str(path), *arguments], env=environment, capture_output=True, text=True, check=True)
    return result.stdout


class World:
    """A tiny local origin, a working copy, and explicitly scripted external commands."""

    def __init__(self, root: Path, monkeypatch, names: tuple[str, ...] = ("alm",), **settings):
        from metalm_ops.improve import process, run

        self.root = root
        self.calls = []
        self.prompts = []
        self.comments = []
        self.bodies = []
        self.worktrees = []
        self.commit_messages = []
        self.sleeps = []
        self.opened_time = None
        self.checked_time = None
        self.proposal = dict(PROPOSAL)
        self.verdicts = [dict(VERDICT), dict(VERDICT)]
        self.review_count = 0
        self.verification = {"verdict": "confirmed", "counter_evidence": [], "reasons": "The claim survives disproof."}
        self.verify_count = 0
        self.verify_envelope = None
        self.review_cost = 0.1
        self.proposal_error = None
        self.proposal_exit = None  # (code, jsonl output) to simulate codex exiting non-zero
        self.review_error = None
        self.review_envelope = None
        self.open_pulls = []
        self.history = []
        self.closed_comments = []
        self.checks = (0, "tests pass\n")
        self.tests_pass = True
        self.import_inside = True
        self.crash_fetch = set()
        self.commit_fails = False
        self.comment_fails = False
        self.deploy_fails = False
        self.edit = self.default_edit
        self.repos = {}
        self.origins = {}
        self.last_branch = ""
        self.pulled = []
        self.deployed = []
        self.test_environments = []
        self.import_environments = []
        binaries = root / "bin"
        binaries.mkdir()
        for name in ("codex", "claude"):
            binary = binaries / name
            binary.write_text("#!/bin/sh\nexit 99\n")
            binary.chmod(0o755)
        monkeypatch.setenv("PATH", str(binaries) + os.pathsep + os.environ["PATH"])
        guidelines = root / "guidelines"
        guidelines.mkdir()
        (guidelines / "index.md").write_text("INDEX_SENTINEL: follow the house rules.\n")
        (guidelines / "auto-improve.md").write_text("IMPROVE_SENTINEL: exactly one safe change.\n")
        monkeypatch.setattr(run, "GUIDELINES_DIR", guidelines)
        monkeypatch.setattr(run, "SLEEP", self.sleeps.append)
        monkeypatch.setattr(process, "RUNNER", self.command)
        rows = []
        for name in names:
            repository = root / name
            repository.mkdir()
            git(repository, "init", "-b", "main")
            git(repository, "config", "user.name", "Test Author")
            git(repository, "config", "user.email", "test@example.invalid")
            git(repository, "config", "core.hooksPath", str(root / "empty-hooks"))
            (repository / "src" / "sample").mkdir(parents=True)
            (repository / "src" / "sample" / "__init__.py").write_text("# Add the pair.\ndef add(left, right):\n    return left + right\n")
            (repository / "CLAUDE.md").write_text("REPO_SENTINEL: preserve arithmetic.\n")
            (repository / ".gitignore").write_text(".venv/\n__pycache__/\n")
            git(repository, "add", "src", "CLAUDE.md", ".gitignore")
            git(repository, "commit", "-m", "Initial fixture")
            origin = root / f"{name}.git"
            origin.mkdir()
            git(origin, "init", "--bare", "--initial-branch=main")
            git(repository, "remote", "add", "origin", str(origin))
            git(repository, "push", "-u", "origin", "main")
            environment = repository / ".venv" / "bin"
            environment.mkdir(parents=True)
            (environment / "python").symlink_to(sys.executable)
            (environment / "pytest").write_text("#!/bin/sh\nexit 0\n")
            (environment / "pytest").chmod(0o755)
            self.repos[name] = repository
            self.origins[name] = origin
            rows.append({"name": name, "test": "{venv}/bin/pytest -q", "merge": "merge", "deploy": "fixture-deploy"})
        self.data = {
            "label_prefix": "com.example",
            "port": 8700,
            "state_dir": str(root / "state"),
            "backup": {"local_dir": str(root / "backups")},
            "repo": [{"name": name, "path": str(path), "github": f"example/{name}"} for name, path in self.repos.items()],
            "improve": {
                "enabled": True,
                "codex_bin": str(binaries / "codex"),
                "claude_bin": str(binaries / "claude"),
                "model": "gpt-6-astra",
                "review_model": "claude-opus-5-5",
                "repo": rows,
                **settings,
            },
        }
        self.config = parse(self.data)
        # Issue #88: brake state belongs to an isolated metalm origin, never the owner's checkout.
        self.metalm = root / "metalm-control"
        self.metalm.mkdir()
        git(self.metalm, "init", "-b", "main")
        git(self.metalm, "config", "user.name", "Test Author")
        git(self.metalm, "config", "user.email", "test@example.invalid")
        git(self.metalm, "config", "core.hooksPath", str(root / "empty-hooks"))
        (self.metalm / "improve").mkdir()
        (self.metalm / "improve/braked.toml").write_text("braked = []\n")
        git(self.metalm, "add", ".")
        git(self.metalm, "commit", "-m", "Empty brake list")
        self.metalm_origin = root / "metalm-control.git"
        self.metalm_origin.mkdir()
        git(self.metalm_origin, "init", "--bare", "--initial-branch=main")
        git(self.metalm, "remote", "add", "origin", str(self.metalm_origin))
        git(self.metalm, "push", "-u", "origin", "main")
        try:
            from metalm_ops.improve import brake
        except ImportError:
            pass  # Red-first fixtures also run before the feature module exists.
        else:
            monkeypatch.setattr(brake, "CHECKOUT", self.metalm)
        from datetime import datetime

        monkeypatch.setattr(run, "NOW", lambda: datetime.now().astimezone().replace(hour=13, minute=10, second=0, microsecond=0), raising=False)

    def configure(self, **settings):
        self.data["improve"].update(settings)
        self.config = parse(self.data)
        return self.config

    @staticmethod
    def default_edit(worktree: Path) -> None:
        path = worktree / "src" / "sample" / "__init__.py"
        path.write_text(path.read_text().replace("# Add the pair.", "# Return the sum of two numbers."))

    def completed(self, arguments, code=0, output="", error=""):
        return subprocess.CompletedProcess(arguments, code, output, error)

    def command(self, arguments, *, cwd=None, input=None, timeout=None, env=None):
        arguments = list(map(str, arguments))
        directory = Path(cwd) if cwd is not None else None
        self.calls.append((arguments, directory, timeout))
        executable = Path(arguments[0]).name
        if executable == "codex":
            worktree = Path(arguments[arguments.index("-C") + 1])
            assert worktree.is_relative_to(self.root)
            self.worktrees.append(worktree)
            self.prompts.append(("propose", input, arguments))
            if self.proposal_error:
                raise self.proposal_error
            if self.proposal_exit:
                return self.completed(arguments, code=self.proposal_exit[0], output=self.proposal_exit[1])
            self.edit(worktree)
            answer = self.proposal if isinstance(self.proposal, str) else json.dumps(self.proposal)
            Path(arguments[arguments.index("-o") + 1]).write_text(answer)
            return self.completed(arguments, output='{"type":"turn.completed"}\n')
        if executable == "claude":
            assert directory and directory.is_relative_to(self.root) and directory.exists()
            schema = json.loads(arguments[arguments.index("--json-schema") + 1])
            verifying = "confirmed" in schema["properties"]["verdict"]["enum"]
            self.prompts.append(("verify" if verifying else "review", input, arguments))
            if verifying:
                self.verify_count += 1
                envelope = self.verify_envelope
                if envelope is None:
                    envelope = {"structured_output": self.verification, "total_cost_usd": self.review_cost, "is_error": False}
                return self.completed(arguments, output=envelope if isinstance(envelope, str) else json.dumps(envelope))
            if self.review_error:
                raise self.review_error
            verdict = self.verdicts[self.review_count % 2]
            self.review_count += 1
            envelope = self.review_envelope
            if envelope is None:
                envelope = {"structured_output": verdict, "total_cost_usd": self.review_cost, "is_error": False}
            return self.completed(arguments, output=envelope if isinstance(envelope, str) else json.dumps(envelope))
        if executable == "gh":
            action = arguments[1:3]
            if action == ["pr", "list"]:
                state = arguments[arguments.index("--state") + 1]
                return self.completed(arguments, output=json.dumps(self.open_pulls if state == "open" else self.history))
            if action == ["label", "create"]:
                return self.completed(arguments)
            if action == ["pr", "create"]:
                self.opened_time = time.monotonic()
                body = Path(arguments[arguments.index("--body-file") + 1]).read_text()
                self.bodies.append(body)
                url = "https://github.com/nagarkar/metalm/pull/88" if "nagarkar/metalm" in arguments else "https://github.com/example/alm/pull/17"
                return self.completed(arguments, output=url + "\n")
            if action == ["pr", "view"]:
                if "--json" in arguments:
                    fields = arguments[arguments.index("--json") + 1]
                    answer = {
                        "number": 17,
                        "url": "https://github.com/example/alm/pull/17",
                        "body": self.bodies[-1] if self.bodies else "",
                        "comments": self.closed_comments,
                    }
                    if "--jq" in arguments:
                        selector = arguments[arguments.index("--jq") + 1]
                        if selector == ".body":
                            return self.completed(arguments, output=answer["body"])
                    return self.completed(arguments, output=json.dumps({key: answer[key] for key in fields.split(",")}))
                return self.completed(arguments, output=self.bodies[-1])
            if action == ["pr", "diff"]:
                return self.completed(
                    arguments, output="diff --git a/src/sample/__init__.py b/src/sample/__init__.py\n-# Add the pair.\n+# Return the sum of two numbers.\n"
                )
            if action == ["pr", "comment"]:
                if self.comment_fails:
                    return self.completed(arguments, 1, "fixture comment failure")
                body = (
                    Path(arguments[arguments.index("--body-file") + 1]).read_text() if "--body-file" in arguments else arguments[arguments.index("--body") + 1]
                )
                self.comments.append(body)
                return self.completed(arguments)
            if action == ["pr", "checks"]:
                self.checked_time = time.monotonic()
                if isinstance(self.checks, Exception):
                    raise self.checks
                return self.completed(arguments, *self.checks)
            if action in (["pr", "merge"], ["pr", "close"]):
                if "nagarkar/metalm" in arguments:
                    if action == ["pr", "merge"]:
                        git(self.metalm_origin, "update-ref", "refs/heads/main", f"refs/heads/{self.last_branch}")
                    return self.completed(arguments)
                assert not any(path.exists() for path in self.worktrees), "Remove the worktree before deciding"
                if action == ["pr", "merge"]:
                    repository_name = next((name for name in self.repos if f"example/{name}" in arguments), "alm")
                    git(self.origins[repository_name], "update-ref", "refs/heads/main", f"refs/heads/{self.last_branch}")
                return self.completed(arguments)
            if action == ["pr", "edit"]:
                return self.completed(arguments)
            raise AssertionError(f"Unexpected GitHub command: {arguments}")
        if executable == "superlm-notify":
            return self.completed(arguments)
        if executable == "git":
            actual = arguments[1:]
            if actual[:1] == ["-C"]:
                directory, actual = Path(actual[1]), actual[2:]
            assert directory and directory.resolve().is_relative_to(self.root.resolve()), arguments
            if actual[:1] == ["fetch"] and directory.name in self.crash_fetch:
                raise RuntimeError("fixture fetch crashed")
            if actual[:1] == ["commit"]:
                if self.commit_fails:
                    return self.completed(arguments, 1, "fixture pre-commit failure")
                result = git(directory, *actual)
                self.commit_messages.append(git(directory, "log", "-1", "--format=%B"))
                return self.completed(arguments, output=result)
            if actual[:1] == ["push"]:
                # Real transport is restricted to this test's own bare origin.
                origin = Path(git(directory, "remote", "get-url", "origin").strip())
                assert origin.is_relative_to(self.root)
                self.last_branch = actual[-1]
            if actual[:1] == ["pull"]:
                self.pulled.append(directory)
            result = subprocess.run(
                ["git", "-C", str(directory), *actual],
                capture_output=True,
                text=True,
                env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
            )
            return result
        if executable.startswith("python") and "-c" in arguments:
            self.import_environments.append((directory, env, arguments))
            package = re.search(r"import\s+([a-zA-Z_][a-zA-Z_0-9]*)", arguments[-1])
            package_name = package.group(1) if package else "sample"
            source = directory if self.import_inside else next(iter(self.repos.values()))
            return self.completed(arguments, output=str(source / "src" / package_name / "__init__.py") + "\n")
        command = " ".join(arguments)
        if "pytest" in command:
            self.test_environments.append((directory, env, arguments))
            return self.completed(arguments, 0 if self.tests_pass else 1, "1 passed" if self.tests_pass else "1 failed")
        if "fixture-deploy" in command:
            self.deployed.append(directory)
            return self.completed(arguments, 1 if self.deploy_fails else 0, "fixture deploy")
        raise AssertionError(f"Unstubbed command: {arguments}")

    def commands(self, executable: str, *prefix: str) -> list[list[str]]:
        return [arguments for arguments, _, _ in self.calls if Path(arguments[0]).name == executable and arguments[1 : 1 + len(prefix)] == list(prefix)]

    def ledger(self, table: str) -> list[dict]:
        import sqlite3

        assert table in {"run", "call"}
        with sqlite3.connect(self.config.state_dir / "improve" / "runs.sqlite") as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid')]

    def assert_cleaned(self) -> None:
        for repository in self.repos.values():
            assert "auto-improve/" not in git(repository, "branch", "--format=%(refname:short)")
            assert len(git(repository, "worktree", "list", "--porcelain").split("worktree ")) == 2
        assert not any(path.exists() for path in self.worktrees)
