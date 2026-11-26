"""Visible repository brakes, published through resumable, ledgered metalm PRs."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from metalm_ops.config import NAME_RE, Config, Repo
from metalm_ops.improve import process, store
from metalm_ops.improve.lenses import PROPOSER_SKIP
from metalm_ops.schedule import CHECKOUT


def repository(config: Config) -> Repo:
    """Resolve metalm independently of the repository being improved."""
    return next((item for item in config.repos if item.name == "metalm"), Repo("metalm", CHECKOUT, "nagarkar/metalm"))


def parse(text: str) -> list[dict]:
    """Validate every field of the tracked brake list at its input boundary."""
    from metalm_ops.improve.run import ImproveError

    try:
        document = tomllib.loads(text)
        if set(document) != {"braked"} or not isinstance(document["braked"], list):
            raise ValueError("expected only a braked array")
        names = set()
        for entry in document["braked"]:
            if not isinstance(entry, dict) or set(entry) != {"repo", "since", "reason", "summary", "runs", "prs"}:
                raise ValueError("each braked entry requires repo, since, reason, summary, runs, prs")
            for field in ("repo", "since", "reason", "summary"):
                if not isinstance(entry[field], str) or not entry[field].strip():
                    raise ValueError(f"braked.{field} must be a nonempty string")
            if not NAME_RE.fullmatch(entry["repo"]) or entry["repo"] in names:
                raise ValueError("braked.repo must be a unique repository name")
            names.add(entry["repo"])
            if datetime.fromisoformat(entry["since"]).tzinfo is None:
                raise ValueError("braked.since must be an ISO time with a timezone")
            if entry["reason"] not in {"rejected", "stalled"}:
                raise ValueError("braked.reason must be rejected or stalled")
            if len(entry["summary"].splitlines()) != 1:
                raise ValueError("braked.summary must be one line")
            if not isinstance(entry["runs"], list) or not entry["runs"] or any(not isinstance(value, str) or not value for value in entry["runs"]):
                raise ValueError("braked.runs must contain run IDs")
            if len(set(entry["runs"])) != len(entry["runs"]):
                raise ValueError("braked.runs must be unique")
            if not isinstance(entry["prs"], list):
                raise ValueError("braked.prs must be an array")
            for item in entry["prs"]:
                if not isinstance(item, dict) or set(item) != {"url", "reason"}:
                    raise ValueError("braked.prs requires url and reason")
                if any(not isinstance(item[key], str) or not item[key].strip() for key in item):
                    raise ValueError("braked.prs fields must be nonempty strings")
                if not re.fullmatch(r"https://[^\s]+/pull/\d+", item["url"]):
                    raise ValueError("braked.prs.url must be a PR URL")
        return document["braked"]
    except (ValueError, TypeError) as error:
        raise ImproveError(f"improve/braked.toml: {error}") from error


def _serialize(entries: list[dict]) -> str:
    text = (
        "\n".join(
            "[[braked]]\n"
            + "\n".join(f"{key} = {json.dumps(value)}" for key, value in entry.items() if key != "prs")
            + "\nprs = ["
            + ", ".join("{ url = " + json.dumps(item["url"]) + ", reason = " + json.dumps(item["reason"]) + " }" for item in entry["prs"])
            + "]\n"
            for entry in entries
        )
        if entries
        else "braked = []\n"
    )
    parse(text)
    return text


def read(config: Config, fetch: bool = True) -> list[dict]:
    """Read only fetched origin/main, never a potentially edited working file."""
    from metalm_ops.improve.run import _command

    metalm = repository(config)
    if fetch:
        _command(["git", "-C", str(metalm.path), "fetch", "origin"])
    return parse(_command(["git", "-C", str(metalm.path), "show", "origin/main:improve/braked.toml"]))


def reason(entry: dict) -> str:
    return f"braked since {entry['since']}: {entry['summary']}"


def _after(row: dict, after: str | None) -> bool:
    if after is None:
        return True

    def moment(text: str) -> datetime:
        value = datetime.fromisoformat(text)
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    return moment(row["finished"]) > moment(after)


def last_brake(config: Config, repo: str) -> str | None:
    """When this repo's latest brake lifecycle recorded a step; older runs never count toward a new brake."""
    times = [row["recorded"] for row in store.read_steps(config, repo)]
    return (
        max(
            times,
            key=lambda text: datetime.fromisoformat(text) if datetime.fromisoformat(text).tzinfo else datetime.fromisoformat(text).replace(tzinfo=timezone.utc),
        )
        if times
        else None
    )


def trigger(rows: list[dict], after: str | None = None) -> dict | None:
    """Find judge rejection or no-proposal streaks in newest-first history, counting only runs after the last brake."""
    rows = [row for row in rows if _after(row, after)]
    judged = []
    for row in rows:
        if row["outcome"] == "merged":
            break
        detail = row.get("reason", "")
        if row["outcome"] != "rejected" or not row.get("pr_url"):
            continue
        if "daily cap" in detail:
            # Closed for budget, not judged: neither counts nor breaks the streak.
            continue
        if detail.startswith("CI "):
            # A CI rejection is not the judges' verdict and interrupts their rejection streak.
            break
        judged.append(row)
        if len(judged) == 3:
            return _trigger("rejected", judged, "three consecutive PRs rejected by the judges")
    eligible = [
        row
        for row in rows
        if not row.get("reason", "").startswith(
            (
                "daily cap",
                "daily Codex call cap",
                "daily Claude review cost cap",
                "slot ",
                "system: ",
                "braked since ",
                "cadence:",
                "cadence satisfied",
                "brake pending",
                "no applicable lens",
                "system PAUSE",
                "improve is disabled",
                "an open auto-improve PR",
            )
        )
    ]
    recent = eligible[:5]
    # A proposer that searched and found nothing is the system working, not stalling: it breaks the streak.
    if len(recent) == 5 and all(
        not row.get("pr_url") and row["outcome"] in {"skipped", "gate-failed", "failed", "error"} and not row.get("reason", "").startswith(PROPOSER_SKIP)
        for row in recent
    ):
        return _trigger("stalled", recent, "five consecutive runs failed without a PR")
    return None


def _trigger(kind: str, rows: list[dict], summary: str) -> dict:
    return {
        "reason": kind,
        "summary": summary,
        "runs": [row["run_id"] for row in rows],
        "prs": [{"url": row["pr_url"], "reason": row["reason"]} for row in rows if row.get("pr_url")],
        "rows": rows,
    }


def lookup(config: Config, repo: str) -> dict | None:
    """Find a brake PR by its label and exact title prefix, including merged PRs."""
    from metalm_ops.improve.run import _github

    entries = json.loads(
        _github(
            repository(config),
            "pr",
            "list",
            "--label",
            "auto-improve-brake",
            "--state",
            "all",
            "--search",
            f"Brake {repo}",
            "--limit",
            "100",
            "--json",
            "number,title,url,state,headRefName,headRefOid",
        )
    )
    return next((entry for entry in entries if entry["title"].startswith(f"[auto-improve] Brake {repo}:")), None)


def _body(config: Config, repo: str, event: dict, run_id: str) -> str:
    from metalm_ops.improve.run import opening

    details = "\n".join(
        (
            f"- [{row['run_id']}]({row['pr_url']}): {row['reason']}"
            if row.get("pr_url")
            else f"- run `{row['run_id']}` (ledger on the owner's Mac): {row['reason']}"
        )
        for row in event.get("rows", [])
    )
    return (
        opening(config, run_id) + f"{event['summary']}\n\n{details}\n\nThe next Claude session in {repo} reports this and proposes a fix. "
        "Resume: on the owner's word, a session removes this entry.\n"
    )


def apply(config: Config, repo: str | Repo, trigger: dict, run_id: str, now: datetime) -> dict:
    """Publish or resume one brake; failures remain visible and retry next slot."""
    from metalm_ops.improve.run import LABELS, ImproveError, _command, _github, _link_venv

    name = repo.name if isinstance(repo, Repo) else repo
    metalm = repository(config)
    fingerprint = hashlib.sha256(json.dumps([name, trigger["reason"], trigger["runs"]]).encode()).hexdigest()
    events = store.read_steps(config, name, fingerprint)
    completed = {event["step"]: event["details"] for event in events if event["outcome"] == "ok"}
    entry = completed.get("entry", {"repo": name, "since": now.isoformat(), **{key: trigger[key] for key in ("reason", "summary", "runs", "prs")}})
    branch = f"auto-improve/brake-{name}-{datetime.fromisoformat(entry['since']):%Y%m%d}"
    directory = config.state_dir / "improve" / "runs" / run_id / (name + "-brake")
    directory.mkdir(parents=True, exist_ok=True)
    worktree = config.state_dir / "improve" / "worktrees" / (name + "-brake-" + run_id)
    created = False
    attempted_worktree = False
    result = {"ok": False, "entry": entry, "pr_url": completed.get("pr", {}).get("url"), "reason": ""}

    def record(step: str, outcome: str, details: dict) -> None:
        store.record_step(config, run_id=run_id, repo=name, fingerprint=fingerprint, step=step, outcome=outcome, details=details)

    def command(step: str, arguments: list[str], cwd: Path | None = None) -> str:
        record(step, "started", {})
        try:
            output = _command(arguments, cwd=cwd, directory=directory)
        except Exception as error:
            record(step, "failed", {"reason": str(error)})
            raise
        record(step, "ok", {"output": output})
        return output

    try:
        parse(_serialize([entry]))
        if "entry" not in completed:
            record("entry", "ok", entry)
        current = read(config)
        matching = next((item for item in current if item["repo"] == name), None)
        if not matching and "alert" in completed:
            return {"ok": True, "entry": None, "acknowledged": True, "pr_url": result["pr_url"], "reason": "previous brake lifted by owner"}
        existing = lookup(config, name)
        if existing and (existing.get("headRefName") != branch or (not matching and existing.get("state") == "MERGED" and "pr" not in completed)):
            existing = None
        if not matching and (not existing or existing["state"] == "OPEN"):
            worktree.parent.mkdir(parents=True, exist_ok=True)
            found = _command(["git", "-C", str(metalm.path), "branch", "--list", branch])
            attempted_worktree = True
            command(
                "worktree",
                [
                    "git",
                    "-C",
                    str(metalm.path),
                    "worktree",
                    "add",
                    *([] if found.strip() else ["-b", branch]),
                    str(worktree),
                    branch if found.strip() else f"origin/{branch}" if existing else "origin/main",
                ],
            )
            created = True
            _link_venv(metalm, worktree, directory)
            main_head = _command(["git", "rev-parse", "origin/main"], cwd=worktree).strip()
            ancestor = _command(["git", "merge-base", "HEAD", "origin/main"], cwd=worktree).strip()
            merging = ancestor != main_head
            if merging:
                changed = _command(["git", "diff", "--name-only", "origin/main...HEAD"], cwd=worktree).splitlines()
                if any(path != "improve/braked.toml" for path in changed):
                    raise ImproveError("brake retry branch has unrelated changes; refusing to reconcile")
                record("reconcile", "started", {"main": main_head})
                merged = process.run(["git", "merge", "--no-commit", "--no-ff", "origin/main"], cwd=worktree)
                with (directory / "steps.log").open("a") as handle:
                    handle.write((merged.stdout or "") + (merged.stderr or ""))
                if merged.returncode:
                    conflicts = _command(["git", "diff", "--name-only", "--diff-filter=U"], cwd=worktree).splitlines()
                    if conflicts != ["improve/braked.toml"]:
                        raise ImproveError(f"brake reconciliation failed: {(merged.stderr or merged.stdout).strip()}")
            target = worktree / "improve" / "braked.toml"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_serialize([*current, entry]))
            record("append", "ok", entry)
            command("add", ["git", "add", "improve/braked.toml"], worktree)
            staged = _command(["git", "diff", "--cached", "--name-only"], cwd=worktree).strip()
            if staged or merging:
                command(
                    "commit",
                    ["git", "commit", "-m", f"Brake {name}: {entry['reason']}\n\nAuto-improve-run: {run_id}\nCo-Authored-By: Codex <noreply@openai.com>"],
                    worktree,
                )
            else:
                # A successful git commit may precede a crash or a failed ledger write.
                committed = parse(_command(["git", "show", "HEAD:improve/braked.toml"], cwd=worktree))
                message = _command(["git", "log", "-1", "--format=%B"], cwd=worktree)
                known_runs = {event["run_id"] for event in events} | {run_id}
                if entry not in committed or not any(f"Auto-improve-run: {identifier}" in message.splitlines() for identifier in known_runs):
                    raise ImproveError("existing brake commit does not match this recorded trigger")
            head = command("head", ["git", "rev-parse", "HEAD"], worktree).strip()
            record("commit", "ok", {"head": head, "entry": entry})
            if merging:
                record("reconcile", "ok", {"head": head, "main": main_head})
            command("push", ["git", "push", "-u", "origin", branch], worktree)
            if existing:
                existing = {**existing, "headRefOid": head}
                record("pr", "ok", existing)
        if not matching and not existing:
            for label, color, description in LABELS:
                if label not in {"auto-improve", "auto-improve-brake"}:
                    continue
                record("label", "started", {"label": label})
                _github(metalm, "label", "create", label, "--force", "--color", color, "--description", description, directory=directory)
                record("label", "ok", {"label": label})
            body = directory / "brake-body.md"
            body.write_text(_body(config, name, trigger, run_id))
            record("pr", "started", {})
            output = _github(
                metalm,
                "pr",
                "create",
                "--base",
                "main",
                "--head",
                branch,
                "--title",
                f"[auto-improve] Brake {name}: {entry['reason']}",
                "--label",
                "auto-improve",
                "--label",
                "auto-improve-brake",
                "--body-file",
                str(body),
                directory=directory,
            )
            urls = re.findall(r"https://[^\s]+/pull/\d+", output)
            if not urls:
                raise ImproveError("brake PR creation returned no URL")
            existing = {"url": urls[-1], "state": "OPEN", "headRefOid": head}
            record("pr", "ok", existing)
        if existing:
            result["pr_url"] = existing["url"]
            if existing["state"] == "CLOSED":
                raise ImproveError("brake PR was closed without merging; owner intervention needed")
            if existing["state"] != "MERGED":
                record("merge", "started", existing)
                _github(
                    metalm, "pr", "merge", existing["url"], "--merge", "--delete-branch", "--match-head-commit", existing["headRefOid"], directory=directory
                )
                record("merge", "ok", existing)
        if not result["pr_url"]:
            raise ImproveError("brake entry exists but its PR could not be found")
        if "pull" not in completed:
            branch_name = _command(["git", "branch", "--show-current"], cwd=metalm.path).strip()
            dirty = _command(["git", "status", "--porcelain"], cwd=metalm.path).strip()
            if branch_name == "main" and not dirty:
                command("pull", ["git", "pull", "--ff-only"], metalm.path)
            else:
                detail = "checkout pull skipped: dirty or off main"
                with (directory / "steps.log").open("a") as handle:
                    handle.write(detail + "\n")
                record("pull", "ok", {"reason": detail})
        if "alert" not in completed:
            command(
                "alert",
                [
                    str(Path("~/.local/bin/superlm-notify").expanduser()),
                    "--repo",
                    name,
                    "--title",
                    f"auto-improve braked {name}",
                    "--body",
                    f"{entry['summary']}; {result['pr_url']}",
                ],
            )
        result.update(ok=True, reason=reason(entry))
    except Exception as error:
        result["reason"] = f"brake failed: {error}"
        record("apply", "failed", {"reason": str(error)})
    finally:
        if attempted_worktree and not created:
            try:
                registered = _command(["git", "-C", str(metalm.path), "worktree", "list", "--porcelain"], directory=directory)
                created = any(line == f"worktree {worktree}" for line in registered.splitlines())
            except Exception as error:
                result.update(ok=False, reason=f"{result['reason']}; worktree inspection failed: {error}")
        if created:
            try:
                command("cleanup", ["git", "-C", str(metalm.path), "worktree", "remove", "--force", str(worktree)])
            except Exception as error:
                result.update(ok=False, reason=f"{result['reason']}; cleanup failed: {error}")
        # Keep the branch on failure: it is the resumable committed artifact.
        if result["ok"]:
            try:
                found = _command(["git", "-C", str(metalm.path), "branch", "--list", branch])
                if found.strip():
                    command("branch-cleanup", ["git", "-C", str(metalm.path), "branch", "-D", branch])
            except Exception as error:
                result.update(ok=False, reason=f"{result['reason']}; branch cleanup failed: {error}")
    return result


def unbrake(config: Config, repo: str | Repo, why: str, dry_run: bool = False) -> dict:
    """Propose removing a brake on the owner's words; never merge the PR."""
    from metalm_ops.improve.run import ImproveError, _command, _github, _link_venv

    repo = repo.name if isinstance(repo, Repo) else repo
    if not why.strip():
        raise ImproveError("unbrake --why requires the owner's words")
    entries = read(config, fetch=not dry_run)
    if not any(entry["repo"] == repo for entry in entries):
        raise ImproveError(f"repo {repo!r} is not braked")
    title = f"[auto-improve] Unbrake {repo}"
    body = f"Remove the brake for {repo} on the owner's word:\n\n" + "\n".join("> " + line for line in why.splitlines()) + "\n"
    board = {
        "ok": True,
        "dry_run": dry_run,
        "rows": [{"repo": repo, "title": title, "body": body, "outcome": "would-open"}],
        "next": "Review and merge the unbrake PR on the owner's word",
    }
    if dry_run:
        return board
    metalm = repository(config)
    stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%f")
    branch = f"auto-improve/unbrake-{repo}-{stamp}"
    directory = config.state_dir / "improve" / "runs" / ("unbrake-" + stamp)
    directory.mkdir(parents=True, exist_ok=True)
    worktree = config.state_dir / "improve" / "worktrees" / ("unbrake-" + stamp)
    worktree.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        _command(["git", "-C", str(metalm.path), "worktree", "add", "-b", branch, str(worktree), "origin/main"], directory=directory)
        created = True
        _link_venv(metalm, worktree, directory)
        (worktree / "improve" / "braked.toml").write_text(_serialize([entry for entry in entries if entry["repo"] != repo]))
        _command(["git", "add", "improve/braked.toml"], cwd=worktree, directory=directory)
        _command(
            ["git", "commit", "-m", f"Unbrake {repo}\n\n{why}\n\nAuto-improve-run: unbrake-{stamp}\nCo-Authored-By: Codex <noreply@openai.com>"],
            cwd=worktree,
            directory=directory,
        )
        _command(["git", "push", "-u", "origin", branch], cwd=worktree, directory=directory)
        body_file = directory / "body.md"
        body_file.write_text(body)
        output = _github(
            metalm,
            "pr",
            "create",
            "--base",
            "main",
            "--head",
            branch,
            "--title",
            title,
            "--label",
            "auto-improve-brake",
            "--body-file",
            str(body_file),
            directory=directory,
        )
        urls = re.findall(r"https://[^\s]+/pull/\d+", output)
        if not urls:
            raise ImproveError("unbrake PR creation returned no URL")
        board["rows"][0].update(outcome="opened", pr_url=urls[-1])
        return board
    finally:
        if created:
            _command(["git", "-C", str(metalm.path), "worktree", "remove", "--force", str(worktree)], directory=directory)


def acknowledged(config: Config, repo: str, event: dict) -> bool:
    """Whether this exact trigger already completed its brake and alert lifecycle."""
    fingerprint = hashlib.sha256(json.dumps([repo, event["reason"], event["runs"]]).encode()).hexdigest()
    return any(row["step"] == "alert" and row["outcome"] == "ok" for row in store.read_steps(config, repo, fingerprint))
