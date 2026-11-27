"""Owner issue #84: independent evidence, lens rotation and verifier acceptance tests."""

from __future__ import annotations

from copy import deepcopy

import pytest

from improve_fixtures import PROPOSAL, VERDICT, World, git
from metalm_ops.improve import gates, run, store


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def proposed(world, lens="readability", **fields):
    world.proposal = {**deepcopy(PROPOSAL), "category": lens, "lens": lens, **fields}


def execute(world, lens="readability", **options):
    return run.run(world.config, repo="alm", lens=lens, **options)["rows"][0]


def recorded(world, lens, finished, outcome="no-pr"):
    store.initialize(world.config)
    store.record_run(
        world.config,
        {
            "run_id": lens + finished + outcome,
            "repo": "alm",
            "started": finished,
            "finished": finished,
            "outcome": outcome,
            "category": lens,
            "lens": lens,
            "title": "prior",
            "reason": "fixture",
            "codex_calls": 1,
            "model": "fixture",
            "checkout_updated": False,
        },
    )


@pytest.mark.parametrize("quote", ["# Add the pair.", "#   Add\tthe  pair."])
def test_base_evidence_accepts_only_whitespace_within_lines(world, quote):
    evidence = [{"path": "src/sample/__init__.py", "start_line": 1, "end_line": 1, "quote": quote}]
    assert not gates.check_evidence(world.repos["alm"], evidence)


@pytest.mark.parametrize(
    "fields",
    [
        {"start_line": 2, "end_line": 2},
        {"path": "missing.py"},
        {"quote": "# Add the\npair."},
        {"quote": "# Return the sum of two numbers."},
        {"start_line": 0},
        {"start_line": 2, "end_line": 1},
    ],
)
def test_base_evidence_rejects_wrong_location_or_changed_text(world, fields):
    evidence = {**PROPOSAL["evidence"][0], **fields}
    reason = gates.check_evidence(world.repos["alm"], [evidence])
    assert reason == f"evidence quote not found: {evidence['path']}:{evidence['start_line']}-{evidence['end_line']}"


def test_quote_check_uses_base_not_the_proposers_edited_worktree(world):
    proposed(world, evidence=[{**PROPOSAL["evidence"][0], "quote": "# Return the sum of two numbers."}])
    row = execute(world)
    assert row["outcome"] == "gate-failed"
    assert row["reason"] == "evidence quote not found: src/sample/__init__.py:1-1"
    assert not world.bodies and not world.verify_count


@pytest.mark.parametrize("resolved, outcome", [(True, "merged"), (False, "gate-failed")])
def test_performance_is_re_measured_by_the_system_not_claimed_by_codex(world, resolved, outcome):
    proposed(world, "performance", measurement="")
    if not resolved:
        world.after_report = world.report
    row = execute(world, "performance")
    assert row["outcome"] == outcome
    if resolved:
        assert "## What is wrong" in world.bodies[0]
    else:
        assert row["reason"].startswith("finding not improved")


@pytest.mark.parametrize("verdict", ["refuted", "uncertain"])
def test_unconfirmed_claim_closes_without_spending_on_reviewers(world, verdict):
    world.verification = {
        "verdict": verdict,
        "counter_evidence": deepcopy(PROPOSAL["evidence"]),
        "reasons": "The claimed defect is intentional.\nAnother reason.",
    }
    row = execute(world)
    assert row["outcome"] == "rejected"
    assert row["reason"] == f"verifier {verdict}: The claimed defect is intentional."
    assert world.verify_count == 1 and world.review_count == 0
    assert not world.commands("gh", "pr", "merge")
    assert world.commands("gh", "pr", "close")
    assert any("auto-improve-rejected" in edit for edit in world.commands("gh", "pr", "edit"))
    assert world.comments[0].startswith("### auto-improve review: verifier (Claude claude-opus-5-5)")
    assert [call["role"] for call in world.ledger("call")] == ["propose", "verify"]
    world.assert_cleaned()


def test_refutation_with_false_counter_evidence_is_uncertain(world):
    world.verification = {"verdict": "refuted", "counter_evidence": [{**PROPOSAL["evidence"][0], "quote": "fabricated quotation"}], "reasons": "Disproved."}
    row = execute(world)
    assert row["outcome"] == "rejected" and row["reason"].startswith("verifier uncertain:")
    assert world.review_count == 0 and "uncertain" in world.comments[0]


@pytest.mark.parametrize("envelope", ["not JSON", {}, {"structured_output": {"verdict": "confirmed", "counter_evidence": [], "reasons": "yes", "extra": 1}}])
def test_malformed_verifier_never_reaches_reviewers_or_merge(world, envelope):
    world.verify_envelope = envelope
    row = execute(world)
    assert row["outcome"] == "rejected" and row["reason"].startswith("verifier uncertain:")
    assert world.review_count == 0 and not world.commands("gh", "pr", "merge")


def test_verifier_sees_claim_and_full_base_files_not_why_safe(world):
    proposed(world, why_safe="PRIVATE_SAFETY_REASON_SENTINEL")
    row = execute(world)
    assert row["outcome"] == "merged"
    assert [role for role, _, _ in world.prompts] == ["propose", "verify", "review", "review"]
    verification = next(prompt for role, prompt, _ in world.prompts if role == "verify")
    assert PROPOSAL["claim"] in verification
    assert "# Add the pair." in verification
    assert "def add(left, right):\n    return left + right" in verification
    assert "diff --git" in verification and "readability" in verification
    assert "PRIVATE_SAFETY_REASON_SENTINEL" not in verification
    assert len(world.ledger("call")) == 4
    assert store.usage(world.config)["review_cost_usd"] == pytest.approx(0.3)


@pytest.mark.parametrize(
    "lens, permits",
    [
        ("readability", False),
        ("documentation", False),
        ("duplication", False),
        ("backend-robustness", True),
        ("frontend-robustness", True),
        ("ui", True),
        ("performance", False),
        ("drift", True),
    ],
)
def test_behaviour_changes_follow_lens_policy(world, lens, permits):
    frontend = world.repos["alm"] / "app.js"
    frontend.write_text("console.log('hello');\n")
    git(world.repos["alm"], "add", "app.js")
    git(world.repos["alm"], "commit", "-m", "Frontend fixture")
    git(world.repos["alm"], "push", "origin", "main")
    proposed(world, lens, measurement="bench: 20 before, 1 after" if lens == "performance" else "")
    world.verdicts[1] = {**VERDICT, "behaviour_change": True}
    row = execute(world, lens)
    assert row["outcome"] == ("merged" if permits else "rejected")


def test_pr_has_ordered_evidence_sections_and_pinned_base_link(world):
    base = git(world.repos["alm"], "rev-parse", "origin/main").strip()
    assert execute(world)["outcome"] == "merged"
    body = world.bodies[0]
    headings = [
        "## What is wrong",
        "## Options considered",
        "## What changed",
        "## How it was tested",
        "## Reviewer concerns",
        "## Where to start",
        "<details>",
    ]
    assert [body.index(heading) for heading in headings] == sorted(body.index(heading) for heading in headings)
    assert "## Measurement" not in body
    assert f"https://github.com/example/alm/blob/{base}/src/sample/__init__.py#L1" in body
    assert "# Add the pair." in body and "readability" in body


def test_forced_lens_requires_explicit_repo(world):
    with pytest.raises((ValueError, run.ImproveError), match="repo"):
        run.run(world.config, lens="documentation")
    assert not world.prompts and not world.config.state_dir.exists()


def test_rotation_picks_never_run_then_oldest_completed_lens(world):
    world.data["improve"]["repo"][0]["lenses"] = ["duplication", "documentation", "readability"]
    world.configure()
    recorded(world, "readability", "2026-11-01T00:00:00+00:00")
    proposed(world, "documentation")
    row = run.run(world.config, repo="alm", no_pr=True)["rows"][0]
    assert row["lens"] == "documentation" and row["outcome"] == "no-pr"
    proposed(world, "duplication")
    row = run.run(world.config, repo="alm", no_pr=True)["rows"][0]
    assert row["lens"] == "duplication" and row["outcome"] == "no-pr"
    proposed(world, "readability")
    assert run.run(world.config, repo="alm", no_pr=True)["rows"][0]["lens"] == "readability"


def test_skipped_lens_does_not_advance_rotation(world):
    recorded(world, "readability", "2026-11-25T00:00:00+00:00", outcome="skipped")
    assert run.run(world.config, repo="alm", no_pr=True)["rows"][0]["lens"] == "readability"


@pytest.mark.parametrize(
    "path, enabled", [("app.tsx", True), ("docs/example.html", False), ("tests/fixture.js", False), ("node_modules/a.js", False), (".venv/a.html", False)]
)
def test_frontend_lenses_depend_on_tracked_non_excluded_source(world, path, enabled):
    target = world.repos["alm"] / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("frontend fixture\n")
    git(world.repos["alm"], "add", "-f", path)
    git(world.repos["alm"], "commit", "-m", "Tracked frontend fixture")
    git(world.repos["alm"], "push", "origin", "main")
    world.data["improve"]["repo"][0]["lenses"] = ["frontend-robustness", "ui", "drift"]
    world.configure()
    lens = "frontend-robustness" if enabled else "drift"
    proposed(world, lens)
    row = run.run(world.config, repo="alm", no_pr=True)["rows"][0]
    assert row["lens"] == lens and row["outcome"] == "no-pr"


def test_old_category_rows_remain_readable_in_status(world):
    for category in ("refactor", "docs", "duplicate", "ui"):
        recorded(world, category, "2026-11-01T00:00:00+00:00")
    rows = run.status(world.config)["repos"][0]["runs"]
    assert {row["category"] for row in rows} == {"refactor", "docs", "duplicate", "ui"}
    assert all(row.get("lens") for row in rows)


@pytest.mark.parametrize("evidence", [[], [{"path": "src/sample/__init__.py", "start_line": 1.5, "end_line": 1, "quote": "# Add the pair."}]])
def test_proposal_evidence_contract_rejects_missing_or_nonintegral_locations(world, evidence):
    proposed(world, evidence=evidence)
    row = execute(world)
    assert row["outcome"] == "failed"
    assert not world.bodies and not world.verify_count


def test_tests_lens_cannot_edit_production_code(world):
    proposed(world, "tests")
    row = execute(world, "tests")
    assert row["outcome"] == "gate-failed" and "tests" in row["reason"]
    assert not world.bodies


def test_verified_claim_still_requires_both_reviewer_approvals(world):
    world.verdicts[1] = {**VERDICT, "verdict": "reject", "reasons": "One reviewer still rejects."}
    row = execute(world)
    assert row["outcome"] == "rejected" and "boundaries" in row["reason"]
    assert world.verify_count == 1 and world.review_count == 2
    assert not world.commands("gh", "pr", "merge")


def test_verifier_cost_can_exhaust_review_budget_before_reviewers(world, monkeypatch):
    monkeypatch.setattr(run, "REVIEW_RESERVE_USD", 0.0)
    world.configure(max_review_cost_usd_per_day=0.05)
    row = execute(world)
    assert row["outcome"] == "rejected" and "cap" in row["reason"]
    assert world.verify_count == 1 and world.review_count == 0
    assert store.usage(world.config)["review_cost_usd"] == pytest.approx(0.1)


@pytest.mark.parametrize("value", [["unknown"], "readability", [False], ["docs"]])
def test_configuration_rejects_unknown_or_wrong_shape_lenses(world, value):
    from metalm_ops.config import ConfigError

    world.data["improve"]["repo"][0]["lenses"] = value
    with pytest.raises(ConfigError, match="lenses"):
        world.configure()


def test_configuration_accepts_each_lens_and_empty_opt_out(world):
    names = ["readability", "documentation", "duplication", "tests", "backend-robustness", "frontend-robustness", "ui", "performance", "drift"]
    world.data["improve"]["repo"][0]["lenses"] = names
    assert world.configure().improve.repos[0].lenses == tuple(names)
    world.data["improve"]["repo"][0]["lenses"] = []
    world.configure()
    row = run.run(world.config, repo="alm", no_pr=True)["rows"][0]
    assert row["outcome"] == "skipped" and "lens" in row["reason"]
    assert not world.prompts


def test_cli_lens_flag_reaches_run_and_without_repo_errors(world, monkeypatch, capsys):
    from metalm_ops import cli

    monkeypatch.setattr(cli, "load", lambda path: world.config)
    assert cli.main(["improve", "run", "--lens", "documentation", "--dry-run"]) == 1
    assert "repo" in capsys.readouterr().err
    proposed(world, "documentation")
    assert cli.main(["improve", "run", "--repo", "alm", "--lens", "documentation", "--no-pr", "--json"]) == 0
    assert '"lens": "documentation"' in capsys.readouterr().out
    assert "--lens" in cli.completion_script()


def test_doctor_rejects_bad_lens_front_matter(world, monkeypatch):
    from metalm_ops import doctor, status

    monkeypatch.setattr(status, "RUNNER", lambda *arguments, **keywords: (1, "fixture unavailable"))
    findings = doctor.improve_checks(world.config)
    assert next(finding for finding in findings if finding.name == "improve lenses and prompts").ok
    broken = world.root / "bad_lens.md"
    broken.write_text("---\nid: readability_v1\nversion: 1\nmay_change_behaviour: perhaps\nneeds_measurement: false\n---\nMission\n")
    original = run.newest_prompt
    monkeypatch.setattr(run, "newest_prompt", lambda name, folder="prompts": broken if name == "readability" else original(name, folder))
    finding = next(finding for finding in doctor.improve_checks(world.config) if finding.name == "improve lenses and prompts")
    assert not finding.ok and "may_change_behaviour" in finding.detail


@pytest.mark.parametrize("stem", ["readability", "verify"])
def test_doctor_reports_missing_mandatory_lens_or_prompt(world, monkeypatch, stem):
    from metalm_ops import doctor, status

    monkeypatch.setattr(status, "RUNNER", lambda *arguments, **keywords: (1, "fixture unavailable"))
    original = run.newest_prompt

    def missing(name, folder="prompts"):
        if name == stem:
            raise run.ImproveError(f"missing prompt: {stem}")
        return original(name, folder)

    monkeypatch.setattr(run, "newest_prompt", missing)
    finding = next(finding for finding in doctor.improve_checks(world.config) if finding.name == "improve lenses and prompts")
    assert not finding.ok and stem in finding.detail


def test_duplicate_lens_configuration_is_rejected(world):
    from metalm_ops.config import ConfigError

    world.data["improve"]["repo"][0]["lenses"] = ["readability", "readability"]
    with pytest.raises(ConfigError, match="lenses"):
        world.configure()


@pytest.mark.parametrize("separator", ["\f", "\u2028", "\u2029"])
def test_evidence_line_numbers_count_lf_not_unicode_whitespace(world, separator):
    path = world.repos["alm"] / "source.txt"
    path.write_text(f"first{separator}still first\nsecond\n")
    git(world.repos["alm"], "add", "source.txt")
    git(world.repos["alm"], "commit", "-m", "Whitespace fixture")
    git(world.repos["alm"], "push", "origin", "main")
    correct = {"path": "source.txt", "start_line": 2, "end_line": 2, "quote": "second"}
    assert not gates.check_evidence(world.repos["alm"], [correct])
    wrong = {**correct, "quote": "still first"}
    assert gates.check_evidence(world.repos["alm"], [wrong]) == "evidence quote not found: source.txt:2-2"


def test_empty_base_file_has_no_line_one(world):
    """Issue #84 exact base line ranges cannot quote a nonexistent empty-file line."""
    path = world.repos["alm"]
    (path / "empty.txt").write_text("")
    git(path, "add", "empty.txt")
    git(path, "commit", "-m", "Empty file fixture")
    git(path, "push", "origin", "main")
    assert gates.check_evidence(path, [{"path": "empty.txt", "start_line": 1, "end_line": 1, "quote": " "}]) == "evidence quote not found: empty.txt:1-1"


@pytest.mark.parametrize("value", [{"unknown": 3}, {"size_lines": 0}, {"size_lines": True}, {"size_lines": "600"}])
def test_configuration_rejects_unknown_or_invalid_thresholds(world, value):
    from metalm_ops.config import ConfigError

    world.data["improve"]["repo"][0]["thresholds"] = value
    with pytest.raises(ConfigError, match="thresholds"):
        world.configure()


def test_configuration_accepts_threshold_overrides(world):
    world.data["improve"]["repo"][0]["thresholds"] = {"size_lines": 600, "slow_test_seconds": 1.5}
    world.configure()
    assert world.config.improve.repos[0].thresholds == {"size_lines": 600, "slow_test_seconds": 1.5}


def test_failed_runs_do_not_count_as_a_lens_done():
    from metalm_ops.improve import lenses

    rows = [
        {"outcome": "failed", "reason": "system: Codex usage limit", "lens": "readability", "finished": "2026-11-26T09:41:00+00:00"},
        {
            "outcome": "skipped",
            "reason": "proposer found nothing: no measured finding for documentation",
            "lens": "documentation",
            "finished": "2026-11-26T09:41:00+00:00",
        },
        {"outcome": "skipped", "reason": "daily cap reached", "lens": "tests", "finished": "2026-11-26T09:41:00+00:00"},
    ]
    assert set(lenses.completed(rows)) == {"documentation"}


def test_the_modularity_lens_allows_a_larger_change():
    from metalm_ops.improve import lenses

    lens = lenses.load("modularity")
    assert (lens.max_files, lens.max_changed_lines) == (6, 300) and not lens.may_change_behaviour
    assert lenses.load("performance").needs_measurement is False  # the system re-measures


def test_verifier_also_sees_the_finding_file_when_only_a_new_test_changes(world):
    # 2026-11-27: musiclm and gamelm tests-lens PRs were rejected "uncertain" because the verifier saw only the new test file.
    def edit(worktree):
        (worktree / "tests").mkdir(exist_ok=True)
        (worktree / "tests" / "test_extra.py").write_text("def test_extra():\n    assert True\n")

    world.edit = edit
    proposed(world)
    row = execute(world)
    assert row["outcome"] == "merged", row["reason"]
    verification = next(prompt for role, prompt, _ in world.prompts if role == "verify")
    assert "File: tests/test_extra.py\nFile absent at base commit" in verification
    assert "File: src/sample/__init__.py" in verification and "def add(left, right):" in verification


def test_commit_hooks_find_pre_commit_on_the_repo_venv_path(world):
    # 2026-11-27: publishinglm's hook pointed at a deleted worktree's interpreter and launchd's PATH had no pre-commit.
    proposed(world)
    assert execute(world)["outcome"] == "merged"
    first, second = world.commit_env["PATH"].split(":")[:2]
    assert first == str(world.repos["alm"] / ".venv" / "bin") and second.endswith("bin")


def test_final_description_lists_each_reviewer_concern_with_resolution_and_outcome(world):
    proposed(world)
    assert execute(world)["outcome"] == "merged"
    opened, final = world.bodies[0], world.edited_bodies[-1]
    assert "Pending." in opened and "Pending." not in final
    assert "The comment above the arithmetic helper says less than the code does" in final
    assert "1. **Chosen:** Reword the comment to match the code." in final
    assert "Not blocking: The wording could drift again. *Resolution:* Acceptable" in final
    assert "**Outcome:** merged:" in final and "Read src/sample/__init__.py first." in final


def test_closed_description_states_why(world):
    proposed(world)
    world.verdicts[1] = {**VERDICT, "verdict": "reject", "concerns": [{"concern": "Renames a term.", "blocking": True, "resolution": "Keep the old name."}]}
    assert execute(world)["outcome"] == "rejected"
    final = world.edited_bodies[-1]
    assert "Blocking: Renames a term. *Resolution:* Keep the old name." in final and "**Outcome:** closed:" in final
