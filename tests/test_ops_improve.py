"""Independent offline acceptance tests for nagarkar/metalm#80, owner 2026-11-26.

The requirement, not implementation output, supplies decisions and limits.
All Git repositories and executable-agent fixtures live under pytest tmp_path.
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest

from metalm_ops.improve import run, store
from improve_fixtures import LABELS, PROPOSAL, VERDICT, World, git


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def result(world, **options):
    board = run.run(world.config, **options)
    assert "next" in board and "usage" in board
    assert len(board["rows"]) == len(world.config.improve.repos)
    return board, board["rows"][0]


def test_dry_run_calls_no_agents_and_writes_nothing(world):
    before = {str(path.relative_to(world.root)): path.read_bytes() for path in world.root.rglob("*") if path.is_file()}
    board, row = result(world, dry_run=True)
    after = {str(path.relative_to(world.root)): path.read_bytes() for path in world.root.rglob("*") if path.is_file()}
    assert before == after
    assert not world.prompts and not world.bodies
    assert not world.config.state_dir.exists()
    assert board["caps"] and board["usage"]["codex_calls"] == 0
    assert "alm" in json.dumps(row)


def test_no_pr_runs_real_gates_but_creates_no_commit_or_pr(world):
    board, row = result(world, no_pr=True)
    assert row["outcome"] == "no-pr"
    assert "__init__.py" in row["diff_stat"]
    assert row["gates"]["tests"] == "passed" and row["gates"]["imports"] == "passed"
    assert len(world.prompts) == 1 and world.test_environments and world.import_environments
    assert not world.commit_messages and not world.commands("gh", "label") and not world.bodies
    assert not world.commands("gh", "pr", "merge") and not world.review_count
    assert world.ledger("run")[0]["outcome"] == "no-pr"
    assert board["usage"]["codex_calls"] == 1
    world.assert_cleaned()


@pytest.mark.parametrize("mode", ["disabled", "pause", "open", "paused", "codex-cap", "review-cap"])
def test_skip_reasons_are_recorded_without_agents(world, mode):
    if mode == "disabled":
        world.configure(enabled=False)
    elif mode in {"pause", "paused"}:
        path = world.config.state_dir / "improve" / ("PAUSE" if mode == "pause" else "paused-alm")
        path.parent.mkdir(parents=True)
        path.write_text("owner pause")
    elif mode == "open":
        world.open_pulls = [{"number": 12, "title": "already proposed", "state": "OPEN"}]
    elif mode == "codex-cap":
        world.configure(max_codex_calls_per_day=0)
    else:
        world.configure(max_review_cost_usd_per_day=0.0)
    board, row = result(world)
    assert board["ok"] and row["outcome"] == "skipped" and row["reason"]
    assert not world.prompts and not world.commit_messages
    assert world.ledger("run")[0]["outcome"] == "skipped"
    if "cap" in mode:
        assert "daily cap reached" in row["reason"]


def test_three_closed_unmerged_prs_pause_until_owner_deletes_marker(world):
    world.history = [
        {"number": number, "title": f"Old {number}", "state": "CLOSED", "closedAt": f"2026-11-{number:02d}T10:00:00Z", "body": ""} for number in (25, 24, 23)
    ]
    _, row = result(world)
    assert row["outcome"] == "skipped"
    marker = world.config.state_dir / "improve" / "paused-alm"
    assert marker.exists() and not world.prompts
    marker.unlink()
    _, row = result(world, no_pr=True)
    assert row["outcome"] == "no-pr", "Deleting the marker must actually unpause the repo despite unchanged historical PRs"


def test_merged_pr_breaks_rejection_streak(world):
    world.history = [
        {"number": number, "title": "old", "state": state, "closedAt": "2026-11-25T10:00:00Z", "body": ""}
        for number, state in [(3, "CLOSED"), (2, "MERGED"), (1, "CLOSED")]
    ]
    _, row = result(world, no_pr=True)
    assert row["outcome"] == "no-pr"
    assert not (world.config.state_dir / "improve" / "paused-alm").exists()


def test_live_lock_refuses_second_run(world):
    lock = world.config.state_dir / "improve" / "lock"
    lock.parent.mkdir(parents=True)
    lock.write_text(str(os.getpid()))
    with pytest.raises(run.ImproveError, match=rf"another improve run holds the lock \(pid {os.getpid()}\)"):
        run.run(world.config)
    assert not world.prompts and lock.read_text() == str(os.getpid())


def test_dead_lock_is_taken_over(world):
    lock = world.config.state_dir / "improve" / "lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("2147483647")
    _, row = result(world, no_pr=True)
    assert row["outcome"] == "no-pr"
    world.assert_cleaned()


@pytest.mark.parametrize("count", [0, 6])
def test_file_count_gate_includes_new_files(world, count):
    def edit(worktree):
        for index in range(count):
            (worktree / f"new-{index}.txt").write_text("one new line\n")

    world.edit = edit
    _, row = result(world)
    assert row["outcome"] == "gate-failed" and "file" in row["reason"].lower()
    assert not world.bodies
    world.assert_cleaned()


@pytest.mark.parametrize("lines, expected", [(150, "no-pr"), (151, "gate-failed")])
def test_changed_line_cap_includes_untracked_file(world, lines, expected):
    world.edit = lambda worktree: (worktree / "notes.txt").write_text("new line\n" * lines)
    _, row = result(world, no_pr=True)
    assert row["outcome"] == expected


@pytest.mark.parametrize(
    "path",
    [
        "guidelines/rules.md",
        "CLAUDE.md",
        "AGENTS.md",
        "skills/example/SKILL.md",
        "SKILL.md",
        "docs/generated/index.md",
        "docs/design/choice.md",
        "app/migrations/001.py",
        "migrations/001.py",
        "app/schema.sql",
        "schema.sql",
        "app/query.sql",
        "query.sql",
        ".env",
        ".env.local",
        "app/.env.local",
        "app/agent.plist",
        "agent.plist",
        "scripts/run.sh",
        ".github/workflows/check.yml",
        ".pre-commit-config.yaml",
        "pyproject.toml",
        "uv.lock",
        "requirements-dev.txt",
        "app/store.sqlite",
        "store.sqlite",
        "app/store.sqlite-wal",
        "app/store.db",
        "store.db",
    ],
)
def test_excluded_paths_never_reach_a_pr(world, path):
    def edit(worktree):
        target = worktree / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("new forbidden content\n")

    world.edit = edit
    _, row = result(world)
    assert row["outcome"] == "gate-failed" and path in row["reason"]
    assert not world.commit_messages and not world.bodies


def test_repo_excludes_extend_global_list(world):
    world.data["improve"]["repo"][0]["exclude"] = ["private/**"]
    world.configure()

    def edit(worktree):
        (worktree / "private").mkdir()
        (worktree / "private" / "draft.txt").write_text("owner content\n")

    world.edit = edit
    _, row = result(world)
    assert row["outcome"] == "gate-failed" and "private/draft.txt" in row["reason"]


@pytest.mark.parametrize("removed", [False, True])
def test_owner_line_additions_and_removals_are_blocked(world, removed):
    if removed:
        source = world.repos["alm"] / "src" / "sample" / "__init__.py"
        source.write_text("# Preserve arithmetic. (owner)\n" + source.read_text())
        git(world.repos["alm"], "add", "src/sample/__init__.py")
        git(world.repos["alm"], "commit", "-m", "Owner rule fixture")
        git(world.repos["alm"], "push", "origin", "main")

    def edit(worktree):
        source = worktree / "src" / "sample" / "__init__.py"
        source.write_text(source.read_text().replace("# Preserve arithmetic. (owner)\n", "") if removed else source.read_text() + "# New rule (owner)\n")

    world.edit = edit
    _, row = result(world)
    assert row["outcome"] == "gate-failed" and "(owner)" in row["reason"]


def test_failing_tests_do_not_open_pr(world):
    world.tests_pass = False
    _, row = result(world)
    assert row["outcome"] == "gate-failed" and "test" in row["reason"].lower()
    assert not world.bodies


def test_green_tests_that_import_live_checkout_are_rejected(world):
    world.import_inside = False
    _, row = result(world)
    assert row["outcome"] == "gate-failed"
    assert "tests did not import the worktree's code" in row["reason"]
    assert not world.bodies


def test_tests_and_import_check_use_worktree_pythonpath(world):
    _, row = result(world, no_pr=True)
    assert row["outcome"] == "no-pr"
    for directory, environment, _ in world.test_environments + world.import_environments:
        assert str(directory / "src") == environment["PYTHONPATH"].split(os.pathsep)[0]
        assert directory in world.worktrees
    assert all(str(world.repos["alm"] / ".venv" / "bin" / "python") in arguments[0] for _, _, arguments in world.import_environments)


@pytest.mark.cuj(
    "The nightly job calls the improve.run API, proposes one change through Codex, and merges only after both Claude reviewers approve and gates and CI pass"
)
def test_two_approvals_and_green_ci_merge_with_provenance(world):
    board, row = result(world)
    assert board["ok"] and row["outcome"] == "merged"
    assert row["pr_number"] == 17 and row["pr_url"] == "https://github.com/example/alm/pull/17"
    create = world.commands("gh", "pr", "create")[0]
    assert create[create.index("--title") + 1] == "[auto-improve] " + PROPOSAL["title"]
    assert create[create.index("--base") + 1] == "main"
    assert {create[index + 1] for index, value in enumerate(create) if value == "--label"} == {"auto-improve", "codex-automated"}
    expected = (
        f"> **Opened by the auto-improve system:** OpenAI Codex (`codex exec`, model gpt-6-astra, effort high), run by `metalm-ops improve` on the owner's Mac, run `{row['run_id']}`.\n"
        "> **Why:** one small daily improvement per repo, under metalm `guidelines/auto-improve.md`. Two Claude reviewers (Anthropic, a different provider from the writer) judge it next. It merges only if both approve and CI is green; otherwise it is closed.\n"
    )
    assert world.bodies[0].startswith(expected)
    for heading in ("## What", "## Why it is safe", "## Tests", "## Files"):
        assert heading in world.bodies[0]
    message = world.commit_messages[0]
    assert message.splitlines()[0] == PROPOSAL["title"]
    assert f"Auto-improve-run: {row['run_id']}" in message
    assert "Co-Authored-By: Codex <noreply@openai.com>" in message
    assert len(world.comments) == 2
    assert world.comments[0].startswith("### auto-improve review: senior engineer (Claude claude-opus-5-5)")
    assert world.comments[1].startswith("### auto-improve review: boundaries (Claude claude-opus-5-5)")
    assert "--merge" in world.commands("gh", "pr", "merge")[0]
    assert "--delete-branch" in world.commands("gh", "pr", "merge")[0]
    assert not world.commands("gh", "pr", "close")
    assert world.checked_time - world.opened_time + sum(world.sleeps) >= 20
    checks = world.commands("gh", "pr", "checks")[0]
    assert "--watch" in checks and "--fail-fast" in checks
    assert world.ledger("run")[0]["outcome"] == "merged"
    world.assert_cleaned()


def test_labels_use_exact_names_colours_and_descriptions(world):
    run.labels(world.config)
    commands = world.commands("gh", "label", "create")
    assert len(commands) == 5
    for command in commands:
        name = command[3]
        assert name in LABELS and "--force" in command
        assert command[command.index("--color") + 1] == LABELS[name][0]
        assert command[command.index("--description") + 1] == LABELS[name][1]


@pytest.mark.parametrize(
    "reviewer, field, value, words",
    [
        (0, "verdict", "reject", "senior"),
        (1, "verdict", "reject", "boundaries"),
        (0, "clear_cut", False, "clear"),
        (1, "clear_cut", False, "clear"),
        (0, "confidence", 0.79, "confidence"),
        (1, "confidence", 0.79, "confidence"),
        (1, "behaviour_change", True, "behaviour"),
    ],
)
def test_every_failing_review_condition_closes_and_labels(world, reviewer, field, value, words):
    world.verdicts[reviewer] = {**VERDICT, field: value, "reasons": "Specific independent objection."}
    _, row = result(world)
    assert row["outcome"] == "rejected" and words in row["reason"].lower()
    close = world.commands("gh", "pr", "close")[0]
    assert "--delete-branch" in close
    assert close[close.index("--comment") + 1] == "Closed by auto-improve: " + row["reason"]
    edit = world.commands("gh", "pr", "edit")[0]
    assert edit[edit.index("--add-label") + 1] == "auto-improve-rejected"
    assert not world.commands("gh", "pr", "merge")
    world.assert_cleaned()


@pytest.mark.parametrize("confidence", [0.8, 1.0])
def test_confidence_boundary_is_inclusive(world, confidence):
    world.verdicts = [{**VERDICT, "confidence": confidence}] * 2
    assert result(world)[1]["outcome"] == "merged"


def test_ui_can_change_visible_behaviour(world):
    world.proposal = {**PROPOSAL, "category": "ui"}
    world.verdicts[1] = {**VERDICT, "behaviour_change": True}
    assert result(world)[1]["outcome"] == "merged"


@pytest.mark.parametrize(
    "checks, expected",
    [((1, "no checks reported on the branch"), "merged"), ((1, "build failed"), "rejected"), (subprocess.TimeoutExpired("gh", 900), "rejected")],
)
def test_ci_absent_failed_and_timeout(world, checks, expected):
    world.checks = checks
    assert result(world)[1]["outcome"] == expected


@pytest.mark.parametrize(
    "answer",
    ["not json", {}, {**PROPOSAL, "extra": "wrong"}, {**PROPOSAL, "skip": "false"}, {**PROPOSAL, "title": "x" * 73}, {**PROPOSAL, "category": "feature"}],
)
def test_invalid_proposal_skips_once(world, answer):
    world.proposal = answer
    _, row = result(world)
    assert row["outcome"] == "skipped" and row["reason"]
    assert len(world.prompts) == 1 and not world.bodies
    assert len(world.ledger("call")) == 1
    world.assert_cleaned()


@pytest.mark.parametrize(
    "answer",
    [
        "not json",
        {},
        {"structured_output": VERDICT, "is_error": True, "total_cost_usd": 0.2},
        {"structured_output": {**VERDICT, "confidence": 1.01}, "total_cost_usd": 0.2},
        {"structured_output": {**VERDICT, "confidence": True}, "total_cost_usd": 0.2},
    ],
)
def test_invalid_reviewer_rejects(world, answer):
    world.review_envelope = answer
    assert result(world)[1]["outcome"] == "rejected"
    assert not world.commands("gh", "pr", "merge")


def test_proposer_skip_is_recorded_without_pr(world):
    world.proposal = {**PROPOSAL, "skip": True, "skip_reason": "Nothing is clear-cut."}
    _, row = result(world)
    assert row["outcome"] == "skipped" and row["reason"] == "Nothing is clear-cut."
    assert not world.bodies


@pytest.mark.parametrize("role, expected", [("propose", "skipped"), ("review", "rejected")])
def test_agent_timeouts_are_recorded_and_do_not_escape(world, role, expected):
    if role == "propose":
        world.proposal_error = subprocess.TimeoutExpired("codex", 1200)
    else:
        world.review_error = subprocess.TimeoutExpired("claude", 480)
    assert result(world)[1]["outcome"] == expected
    assert world.ledger("call")
    world.assert_cleaned()


def test_exact_codex_and_claude_flags_keep_contexts_isolated(world):
    world.verdicts[0] = {**VERDICT, "reasons": "SENIOR_PRIVATE_ANSWER"}
    result(world)
    proposer = world.commands("codex")[0]
    assert proposer[1:9] == ["exec", "--ignore-user-config", "--ephemeral", "--color", "never", "--json", "-m", "gpt-6-astra"]
    assert 'model_reasoning_effort="high"' in proposer
    assert 'approval_policy="never"' in proposer
    assert proposer[proposer.index("-s") + 1] == "workspace-write"
    assert proposer[-1] == "-"
    assert "--full-auto" not in proposer and "--dangerously-bypass-approvals-and-sandbox" not in proposer
    for arguments in world.commands("claude"):
        expected = [
            "-p",
            "--model",
            "claude-opus-5-5",
            "--output-format",
            "json",
            "--json-schema",
            arguments[arguments.index("--json-schema") + 1],
            "--tools",
            "",
            "--no-session-persistence",
            "--setting-sources",
            "",
            "--strict-mcp-config",
            "--max-turns",
            "3",
        ]
        assert arguments[1:] == expected
    reviews = [prompt for role, prompt, _ in world.prompts if role == "review"]
    assert len(reviews) == 2
    assert all("SENIOR_PRIVATE_ANSWER" not in prompt for prompt in reviews)
    for prompt in reviews:
        assert all(sentinel in prompt for sentinel in ("INDEX_SENTINEL", "IMPROVE_SENTINEL", "REPO_SENTINEL"))
        assert "diff --git" in prompt


def test_clean_main_is_pulled_then_deployed(world):
    _, row = result(world)
    assert row["outcome"] == "merged" and row["checkout_updated"]
    assert world.pulled == [world.repos["alm"]] and world.deployed == [world.repos["alm"]]
    assert "Return the sum" in (world.repos["alm"] / "src" / "sample" / "__init__.py").read_text()


@pytest.mark.parametrize("state", ["dirty", "other-branch"])
def test_dirty_or_off_main_checkout_is_untouched(world, state):
    repository = world.repos["alm"]
    if state == "dirty":
        (repository / "owners-notes.txt").write_text("unsaved owner content\n")
    else:
        git(repository, "switch", "-c", "owners-work")
    before = git(repository, "status", "--porcelain")
    _, row = result(world)
    assert row["outcome"] == "merged" and not row["checkout_updated"]
    assert "checkout not updated:" in row["reason"]
    assert ("uncommitted changes" if state == "dirty" else "owners-work") in row["reason"]
    assert not world.pulled and not world.deployed
    assert git(repository, "status", "--porcelain") == before


def test_precommit_failure_stops_before_push_and_pr(world):
    world.commit_fails = True
    assert result(world)[1]["outcome"] == "gate-failed"
    assert not world.last_branch and not world.bodies
    world.assert_cleaned()


def test_one_repo_crash_does_not_stop_the_next(tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch, names=("alm", "blm"))
    world.crash_fetch.add("alm")
    board = run.run(world.config, no_pr=True)
    assert [(row["repo"], row["outcome"]) for row in board["rows"]] == [("alm", "failed"), ("blm", "no-pr")]
    assert not board["ok"]
    assert "fixture fetch crashed" in board["rows"][0]["reason"]
    assert [row["outcome"] for row in world.ledger("run")] == ["failed", "no-pr"]
    world.assert_cleaned()


@pytest.mark.parametrize("cap", ["codex", "review"])
def test_daily_caps_stop_remaining_repos(tmp_path, monkeypatch, cap):
    settings = {"max_codex_calls_per_day": 1} if cap == "codex" else {"max_review_cost_usd_per_day": 0.2}
    world = World(tmp_path, monkeypatch, names=("alm", "blm"), **settings)
    board = run.run(world.config)
    assert board["rows"][1]["outcome"] == "skipped"
    assert "daily cap reached" in board["rows"][1]["reason"]
    assert sum(role == "propose" for role, _, _ in world.prompts) == 1
    assert store.usage(world.config)["codex_calls"] == 1


def test_every_call_has_persistent_provenance_and_raw_artifacts(world):
    _, row = result(world)
    calls = world.ledger("call")
    assert len(calls) == 3 and len(world.ledger("run")) == 1
    assert {call["provider"] for call in calls} == {"openai", "anthropic"}
    assert {call["model"] for call in calls} == {"gpt-6-astra", "claude-opus-5-5"}
    for call in calls:
        assert call["run_id"] == row["run_id"] and call["repo"] == "alm"
        assert call["prompt_id"] and call["outcome"]
        assert len(call["prompt_sha256"]) == 64 and len(call["payload_sha256"]) == 64
        assert call["duration"] >= 0
        assert set(call["prompt_sha256"]) <= set("0123456789abcdef")
        if call["provider"] == "openai":
            assert call["cost"] is None and call["billing"] == "chatgpt-subscription"
        else:
            assert call["cost"] == pytest.approx(0.1)
    usage = store.usage(world.config)
    assert usage["codex_calls"] == 1 and usage["review_cost_usd"] == pytest.approx(0.2)
    directory = world.config.state_dir / "improve" / "runs" / row["run_id"] / "alm"
    for filename in ("propose.jsonl", "propose.json", "review-senior.json", "review-boundaries.json"):
        assert (directory / filename).is_file()


def test_status_returns_last_seven_runs_and_pause_state(world):
    world.configure(enabled=False)
    for _ in range(8):
        run.run(world.config)
    marker = world.config.state_dir / "improve" / "paused-alm"
    marker.write_text("owner pause")
    board = run.status(world.config)
    assert board["next"] and len(board["repos"]) == 1
    assert board["repos"][0]["name"] == "alm" and board["repos"][0]["paused"]
    assert len(board["repos"][0]["runs"]) == 7
    assert all(row["outcome"] == "skipped" for row in board["repos"][0]["runs"])


def test_daily_codex_cap_survives_separate_invocations(world):
    world.configure(max_codex_calls_per_day=1)
    assert result(world, no_pr=True)[1]["outcome"] == "no-pr"
    _, row = result(world, no_pr=True)
    assert row["outcome"] == "skipped" and "daily cap reached" in row["reason"]
    assert len(world.ledger("call")) == 1


def test_dry_run_reports_history_pause_without_writing_marker(world):
    world.history = [{"number": number, "title": "rejected", "state": "CLOSED", "closedAt": "2026-11-25T10:00:00Z", "body": ""} for number in (3, 2, 1)]
    _, row = result(world, dry_run=True)
    assert row["outcome"] == "skipped"
    assert not world.config.state_dir.exists()


def test_review_cost_is_counted_even_when_reviewer_errors(world):
    world.review_envelope = {"structured_output": VERDICT, "is_error": True, "total_cost_usd": 0.25}
    assert result(world)[1]["outcome"] == "rejected"
    assert store.usage(world.config)["review_cost_usd"] == pytest.approx(0.5)


def test_review_cap_reached_between_reviewers_prevents_second_call(world):
    world.configure(max_review_cost_usd_per_day=0.05)
    _, row = result(world)
    assert row["outcome"] == "rejected"
    assert world.review_count == 1
    assert not world.commands("gh", "pr", "merge")


def test_proposal_history_includes_closed_reason_without_leaking_to_reviewers(world):
    world.history = [{"number": 15, "title": "OLD_IDEA_SENTINEL", "state": "CLOSED", "closedAt": "2026-11-25T10:00:00Z", "body": "old summary"}]
    world.closed_comments = [{"body": "Closed by auto-improve: CLOSED_REASON_SENTINEL"}]
    result(world)
    proposer_prompt = world.prompts[0][1]
    assert "OLD_IDEA_SENTINEL" in proposer_prompt and "CLOSED_REASON_SENTINEL" in proposer_prompt
    assert all("OLD_IDEA_SENTINEL" not in prompt and "CLOSED_REASON_SENTINEL" not in prompt for role, prompt, _ in world.prompts if role == "review")


def test_model_timeouts_are_each_configured_in_minutes(world):
    world.configure(propose_timeout_min=3, review_timeout_min=2, ci_timeout_min=4)
    result(world)
    timed = [(arguments, timeout) for arguments, _, timeout in world.calls]
    assert next(timeout for arguments, timeout in timed if arguments[0].endswith("/codex")) == 180
    assert [timeout for arguments, timeout in timed if arguments[0].endswith("/claude")] == [120, 120]
    assert next(timeout for arguments, timeout in timed if arguments[1:3] == ["pr", "checks"]) == 240


def test_multiple_source_packages_are_each_import_checked(world):
    repository = world.repos["alm"]
    (repository / "src" / "second").mkdir()
    (repository / "src" / "second" / "__init__.py").write_text("VALUE = 2\n")
    git(repository, "add", "src/second/__init__.py")
    git(repository, "commit", "-m", "Second package fixture")
    git(repository, "push", "origin", "main")
    assert result(world, no_pr=True)[1]["outcome"] == "no-pr"
    import_programs = " ".join(arguments[-1] for _, _, arguments in world.import_environments)
    assert "sample" in import_programs and "second" in import_programs


def test_agent_staged_changes_still_count_toward_gates(world):
    def edit(worktree):
        for index in range(6):
            (worktree / f"extra-{index}.txt").write_text("new\n")
        git(worktree, "add", "--", *(f"extra-{index}.txt" for index in range(6)))

    world.edit = edit
    assert result(world)[1]["outcome"] == "gate-failed"
    assert not world.bodies


@pytest.mark.parametrize(
    "role, change, category, reason",
    [
        ("senior", {}, "docs", ""),
        ("senior", {"verdict": "reject", "reasons": "Too speculative."}, "docs", "senior"),
        ("boundaries", {"verdict": "reject", "reasons": "Changes money."}, "refactor", "boundaries"),
        ("senior", {"clear_cut": False}, "docs", "clear"),
        ("boundaries", {"clear_cut": False}, "docs", "clear"),
        ("senior", {"confidence": 0.799999}, "docs", "confidence"),
        ("boundaries", {"confidence": 0.799999}, "docs", "confidence"),
        ("senior", {"confidence": 0.8}, "docs", ""),
        ("boundaries", {"confidence": 0.8}, "docs", ""),
        ("boundaries", {"behaviour_change": True}, "docs", "behaviour"),
        ("boundaries", {"behaviour_change": True}, "ui", ""),
        ("senior", {"behaviour_change": True}, "docs", ""),
    ],
)
def test_merge_decision_unit_contract(role, change, category, reason):
    verdicts = {"senior": dict(VERDICT), "boundaries": dict(VERDICT)}
    verdicts[role].update(change)
    actual = run.decision(verdicts["senior"], verdicts["boundaries"], category)
    assert reason in actual.lower() if reason else actual == ""


def test_first_rejection_is_used_before_later_failures():
    senior = {**VERDICT, "verdict": "reject", "reasons": "Senior concern."}
    boundaries = {**VERDICT, "verdict": "reject", "reasons": "Boundary concern.", "confidence": 0.1}
    reason = run.decision(senior, boundaries, "docs")
    assert "senior" in reason.lower() and "Senior concern." in reason


@pytest.mark.parametrize(
    "path, pattern, expected",
    [
        ("src/file.py", "scripts/**", False),
        ("scripts/file.py", "scripts/**", True),
        ("nested/agent.plist", "**/*.plist", True),
        ("agent.plist", "**/*.plist", True),
        ("module/queries.sql", "**/*.sql", True),
        ("queries.sql", "**/*.sql", True),
        ("ordinary.txt", "**/*.sql", False),
        ("private/draft.md", "private/**", True),
    ],
)
def test_exclusion_matching_unit_contract(path, pattern, expected):
    from metalm_ops.improve.gates import excluded

    assert excluded(path, (pattern,)) is expected


def test_schema_validator_rejects_unknown_missing_and_wrong_types():
    from metalm_ops.improve.agents import validate

    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["confidence"],
        "properties": {"confidence": {"type": "number", "minimum": 0, "maximum": 1}},
    }
    validate({"confidence": 0.8}, schema)
    for bad in ({}, {"confidence": True}, {"confidence": 1.01}, {"confidence": -0.1}, {"confidence": 0.8, "extra": 1}):
        with pytest.raises(ValueError):
            validate(bad, schema)


def test_partial_worktree_creation_failure_cleans_branch_and_worktree(world, monkeypatch):
    """Issue #80 step 2: cleanup happens whatever failed, including partial git worktree add."""
    from metalm_ops.improve import process

    def partial_creation(arguments, **options):
        completed = world.command(arguments, **options)
        if "worktree" in arguments and "add" in arguments:
            raise RuntimeError("fixture failure after worktree creation")
        return completed

    monkeypatch.setattr(process, "RUNNER", partial_creation)
    _, row = result(world)
    assert row["outcome"] == "failed" and "after worktree creation" in row["reason"]
    world.assert_cleaned()


def test_failed_first_run_directory_does_not_stop_next_repo(tmp_path, monkeypatch):
    """Issue #80 step 10: every repo writes a failed row even when setup itself fails."""
    from pathlib import Path

    world = World(tmp_path, monkeypatch, names=("alm", "blm"))
    create_directory = Path.mkdir

    def fail_first_directory(path, *arguments, **options):
        if path.name == "alm" and "runs" in path.parts and path.is_relative_to(world.config.state_dir):
            raise OSError("fixture run directory is unwritable")
        return create_directory(path, *arguments, **options)

    monkeypatch.setattr(Path, "mkdir", fail_first_directory)
    board = run.run(world.config, no_pr=True)
    assert [(row["repo"], row["outcome"]) for row in board["rows"]] == [("alm", "failed"), ("blm", "no-pr")]
    rows = world.ledger("run")
    assert len(rows) == 2 and rows[0]["outcome"] == "failed"
    assert "unwritable" in rows[0]["reason"]
    world.assert_cleaned()


def test_interrupted_proposer_records_failed_run_and_cleans_up(world):
    """Issue #80 cleanup and scheduling.md: an interrupted invocation is still recorded."""
    world.proposal_error = KeyboardInterrupt()
    try:
        run.run(world.config)
    except KeyboardInterrupt:
        pass
    rows = world.ledger("run")
    assert len(rows) == 1 and rows[0]["outcome"] == "failed"
    assert rows[0]["reason"], "An interruption needs a readable reason even when str(KeyboardInterrupt()) is empty"
    world.assert_cleaned()


def test_timeout_terminates_agent_children_before_cleanup(tmp_path, monkeypatch):
    """Issue #80 timeout/cleanup: a spawned agent tool must not outlive its timed-out caller."""
    import sys
    import time

    from metalm_ops.improve import process

    monkeypatch.setattr(process, "RUNNER", None)
    child = tmp_path / "child.py"
    child.write_text(
        "import pathlib, sys, time\n"
        "pathlib.Path(sys.argv[1]).write_text('child started')\n"
        "time.sleep(1.5)\n"
        "pathlib.Path(sys.argv[2]).write_text('escaped timeout')\n"
    )
    parent = tmp_path / "parent.py"
    parent.write_text("import subprocess, sys, time\n" "subprocess.Popen([sys.executable, sys.argv[1], sys.argv[2], sys.argv[3]])\n" "time.sleep(10)\n")
    ready = tmp_path / "ready"
    escaped = tmp_path / "escaped"
    with pytest.raises(subprocess.TimeoutExpired):
        process.run([sys.executable, str(parent), str(child), str(ready), str(escaped)], cwd=tmp_path, timeout=1)
    assert ready.exists(), "The regression must actually start a descendant before testing its timeout"
    time.sleep(0.75)
    assert not escaped.exists(), "The timed-out agent's descendant kept writing after cleanup"


@pytest.mark.parametrize("field", ["confidence", "total_cost_usd"])
def test_extreme_review_numbers_reject_instead_of_abandoning_pr(world, field):
    """Issue #80 strict parsing: even valid JSON integers too large for float must reject safely."""
    world.review_envelope = {"structured_output": dict(VERDICT), "total_cost_usd": 0.1}
    if field == "confidence":
        world.review_envelope["structured_output"]["confidence"] = 10**400
    else:
        world.review_envelope["total_cost_usd"] = 10**400
    _, row = result(world)
    assert row["outcome"] == "rejected"
    assert world.commands("gh", "pr", "close") and not world.commands("gh", "pr", "merge")


def test_schema_validator_rejects_integer_too_large_for_float():
    from metalm_ops.improve.agents import validate

    schema = {"type": "number", "minimum": 0, "maximum": 1}
    with pytest.raises(ValueError):
        validate(10**400, schema)


def test_interruption_terminates_agent_children_before_cleanup(tmp_path, monkeypatch):
    """Issue #80 cleanup: an interrupt cannot leave a spawned agent tool editing afterward."""
    import sys
    import time

    from metalm_ops.improve import process

    monkeypatch.setattr(process, "RUNNER", None)
    ready = tmp_path / "ready"
    escaped = tmp_path / "escaped"
    child = tmp_path / "child.py"
    child.write_text(
        "import pathlib, sys, time\n"
        "pathlib.Path(sys.argv[1]).write_text('child started')\n"
        "time.sleep(0.7)\n"
        "pathlib.Path(sys.argv[2]).write_text('escaped interrupt')\n"
    )
    parent = tmp_path / "parent.py"
    parent.write_text("import subprocess, sys, time\nsubprocess.Popen([sys.executable, *sys.argv[1:]])\ntime.sleep(10)\n")
    start_process = subprocess.Popen
    processes = []

    def interrupt_after_child_starts(*arguments, **options):
        running = start_process(*arguments, **options)
        processes.append(running)
        communicate = running.communicate
        interrupted = False

        def interrupt_once(*arguments, **options):
            nonlocal interrupted
            if not interrupted:
                deadline = time.monotonic() + 3
                while not ready.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                assert ready.exists(), "The descendant must start before the interruption"
                interrupted = True
                raise KeyboardInterrupt()
            return communicate(*arguments, **options)

        running.communicate = interrupt_once
        return running

    monkeypatch.setattr(subprocess, "Popen", interrupt_after_child_starts)
    try:
        with pytest.raises(KeyboardInterrupt):
            process.run([sys.executable, str(parent), str(child), str(ready), str(escaped)], cwd=tmp_path)
        time.sleep(0.8)
        assert not escaped.exists(), "The interrupted agent's descendant kept writing after cleanup"
    finally:
        for running in processes:
            if running.poll() is None:
                running.kill()
            running.wait(timeout=3)


def test_termination_signal_records_failure_cleans_up_and_restores_handler(world):
    """Issue #80 cleanup and scheduling.md require a killed run to leave an explanatory row."""
    import signal

    previous_handler = signal.getsignal(signal.SIGTERM)

    def terminate_during_proposal(worktree):
        assert signal.getsignal(signal.SIGTERM) != previous_handler, "Install cleanup protection before calling the agent"
        os.kill(os.getpid(), signal.SIGTERM)

    world.edit = terminate_during_proposal
    with pytest.raises(SystemExit, match="SIGTERM"):
        run.run(world.config)
    rows = world.ledger("run")
    assert len(rows) == 1 and rows[0]["outcome"] == "failed"
    assert "SIGTERM" in rows[0]["reason"]
    assert signal.getsignal(signal.SIGTERM) == previous_handler
    world.assert_cleaned()
