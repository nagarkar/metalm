# Testing

Status: DRAFT — not yet ratified by the owner.
Scope: how agents write, run and report tests and verification in every `*lm` repo.

A test exists to fail when behaviour a user relies on breaks. A test that cannot fail, endorses the current bug, or checks the wrong thing is worse than none: it reads as proof.

## Non-negotiables

- Never weaken, loosen, delete, skip or `xfail` a test to get green. Changing an assertion requires a requirement change (see Anti-gaming b).
- Run the WHOLE suite (every suite in the repo, not just near the change) before changing anything and again after. Leave out only live/network/paid suites, each listed with why. Note pre-existing failures.
- New failure = failing now, passed before. Fix until none, or report it. Never open a PR with new failures. A run that is not the full suite ends with no PR.
- Report results verbatim (command + summary line). Label untested paths "untested".
- Passes-on-rerun without a code change = flaky-test finding, filed, not a pass. Prove zero flakes with two identical full runs after large changes; establish a trusted subset of a new repo by running the full suite 3x.
- Every code change adds or updates a test (lessons and fixes included). A fix proposal carries its encoded test.
- Test-run artifacts are never committed.
- Record the suite size with a date (e.g. "1,085 checks, 2026-08-20") in the repo's test plan; a drop without a stated reason is a finding.

## Anti-gaming

(a) **Red-first proof, always.** Every new or changed test is shown failing: against pre-change code for a fix/feature, or against a deliberately broken copy for existing behaviour. Paste the red output in the PR.
- Bug fix: write the regression test first, confirm it fails on pre-fix code, record the output. Reproduce the failure shape (e.g. the off-grid duration that broke it), not a convenient neighbour.
- Exception: a test-only PR covering a gap must pass on current code; it never edits non-test code. A gap whose test would fail is a bug and goes with a code fix.

(b) **Expected values come from the spec, not the code.**
- Each test cites its source: requirement ID (`ORD-3`), incident (date + failure, in the module docstring), or design decision (doc name).
- Derive the expected value independently (by hand, a reference engine, a worked example), then check the code agrees. Never paste the code's current output as the expectation. Real dated scenarios become fixtures. Reference samples are oracle and regression target, never input (never infer layout or behaviour from them).
- First capture of a golden/snapshot file needs owner review or a ratified doc that pins it.
- Changing an existing assertion cites the requirement change that justifies it.

(c) **Blind test-writer for core paths only** (money, deletion, persistence, auth, user data): a subagent that sees the requirement and the public interface, not the implementation, writes the tests.

(d) **Periodic mutation testing of core modules** (on demand or weekly, not per change; tools in Toolchain). A surviving mutant becomes a GitHub issue.

Tests that cannot fail (find and fix them): asserts nothing; asserts only on its own mock; broad `try/except` around the assertion; `assert True`; failure contract tested only on the happy path; passes because a key happened to be exported.

## Kinds of tests

Wrong kinds to avoid: mocking the unit under test; asserting implementation details (private calls, call order) instead of observable behaviour; coverage chasing or trivial getters; unit-testing model quality (that is an experiment, below).

Priority when choosing what to add: core path with no test; error path never exercised (malformed input, failed write, the exact rejection error); boundaries (`>=` vs `>`, rounding, off-by-one range end, date/timezone edge). Prefer one small sharp test where a regression would hurt a user most.

| Kind | Use for | Rule |
|---|---|---|
| Unit | pure logic, verdict functions | synthetic inputs; assert within tolerance of the generator's params |
| Contract | each adapter (service, LLM, subprocess) | fake reply shape + hand-crafted bad replies; mock the subprocess runner and inspect args |
| Golden file | deterministic stages | same input bytes → same output bytes; rebuild is byte-identical; a rerun is a no-op |
| Table-driven | gates, graph edges, config | one row per case; gates assert the exact reason string the board prints |
| Property-based | parsers, math, invariants | generator + invariant, not examples |
| Parity | surfaces (CLI, MCP, skill, pages) | walk the parser: every leaf verb resolves to a named API function; MCP exposes exactly the curated set |
| Shape | CLI/schema/style | every leaf has description + example; `help` lists every leaf; `--json` parses and has `next`; public defs typed + docstring; every schema has a valid and invalid doc, every property a description |
| Reference parity | refactors, ported engines | same decisions as the old code/reference engine on seeded data; existing tests unchanged; env skip flag in the test module (e.g. `TRADELM_SKIP_ZIPLINE_PARITY=1`) |
| Tripwire / policy | cost, outbound, boundaries | docstring says editing the test is the act that changes the policy |
| Schema-vs-doc | documented schemas | fails if the doc's schema differs from code DDL |
| Graph-vs-code drift | dependency graphs | build order equals declared graph; every built node declared; every shipped node has a builder; edge × change-kind table |
| Config mutation | config loaders | each key set to wrong type/unknown value → rejection naming the key |
| End-to-end | one journey through the API | through the API hand-off, fake externals, no network |
| Live smoke | real service contract | one module behind an env flag, never in the default suite |

Tripwire/policy examples worth copying:
- A billed model id reappearing in shipped config fails the suite.
- Only named verbs may call the LLM (spending moments pinned).
- A GET writes nothing: compare every other table before and after.
- Nothing outbound without approval: approval call sites enumerated.
- Import boundaries between packages enforced in both directions.
- Every committed data file has a provenance sidecar.
- Structural invariants: all pages share one stylesheet; every CSS token used is defined in every theme.
- Adding a path pins the legacy path unchanged (a `...AreUnchanged` test).
- Pipelines with a swappable processor inject the fake and assert downstream has no remote-specific branch.

Suite structure:
- Tests mirror `src/<pkg>/` one-to-one.
- Infra/generic tests run on a synthetic fixture project and never import a real project. Project-specific tests prove only that project's customisation and never re-assert what infra already enforces. No third top-level suite.
- When a data model changes, list the new tests and the existing ones to update (schema, graph, CLI shape) in the PR.
- Optional-dependency tests skip with a stated reason, never error. Optional tool absence at runtime is reported, not fatal.
- External vendor/validator checks are acceptance steps, not tests.

## Offline by default

- No network in the default suite. Each external service has one fake behind the same adapter interface the code uses. No HTTP cassette library: tests are about our behaviour, not wire formats.
- Fixtures: JSON captured once from the real service, sanitized (no auth headers, no keys). Capture is a verb (e.g. `dev capture`), so a refresh is deliberate; the fixture diff is the review; note the per-capture cost. Rerun capture only when the contract or settings change, never per CI run.
- Fixture set covers each behaviour class (present / absent / degraded / sources disagree; reorder, missing, duplicate, corrupt, path traversal, drift). Whole pipeline runs offline in seconds.
- Build tiny fixtures so suites are fully cache-free rather than skipping. Synthetic fixtures miss real formats: also probe one real-format sample.
- Never check in a fixture whose mere presence changes behaviour; copy fixtures to a temp dir and add it there. Tests on fresh dirs create them explicitly; clean slates are hermetic.
- Live-LLM and live-service tests use generated sample data only, never the user's real content, reset to the same state every run.

LLM tiers:
1. **Scripted**: canned replies per purpose (e.g. `tests/fixtures/llm/<purpose>/<tag>.json`, selected by an env var such as `SUPPLYLM_LLM_SCRIPTS`, read in the repo's LLM client). Contract tests on good replies; behaviour tests on bad ones.
2. **Record/replay**: cache at `tests/llm_cache/<sha256>.json`, key = sha256 of (model, prompt, inputs). Unchanged suite makes zero live calls and runs without a key. Changing prompt/sample/model re-records only affected calls. No key + incomplete cache → skip LOUDLY. A failing recorded test deletes only its own recordings.
3. **Live smoke**: one module behind `<REPO>_LIVE=1` (e.g. `YTLM_LIVE=1`, read in that test module), costs cents, never in the default suite. Run it after any model or config change: it catches what hermetic suites cannot (rejected params, key resolution).

Key scrubbing tripwire:
- Before any import, scrub every `*_API_KEY` and point config/env paths (e.g. `AUTHORLM_CONFIG`, `AUTHORLM_ENV`) at throwaways; set client selectors to none (e.g. `AUTHORLM_CLIENT=none`). Do it in the suite's `conftest.py`/setup, so a checkout's config never leaks into tests.
- A tripwire test asserts the scrub held. Only the live module loads `.env`, explicitly.
- Every new test file goes through that setup; a file that bypasses it makes live billed calls.

Spend gates:
- Paid services: ONE opt-in paid smoke behind an env gate plus an interactive spend confirmation, minimal billed size. Free read-only contract smoke only when credentials exist.
- Anything that runs unattended has a per-run and per-day spend cap (proposed, does not exist yet in most repos: `usd_per_tick`/`usd_per_day` in the repo's config file, modelled on supplylm's `Client._guard`).

## Test plans

Write one per area at `docs/test-plan.md` (or `docs/<area>-test-plan.md`).
- Organize by critical user journey: goal, preconditions, steps (page and CLI), expected result, interactions, coverage marked auto / page / live. Add a feature × journey matrix.
- Order cheapest and most load-bearing first: offline deterministic plumbing before anything costing tokens or human labeling time.
- Pin expected behaviour (acceptance matrix) for not-yet-built pieces before building them.
- Name what is NOT covered and why, so gaps read as decisions, not oversights. Keep a gaps-to-close list.
- Live checklist in order, each step with cost and what it leaves behind.
- Cross-cutting checks: one store / every surface; nothing outbound without approval; audit trail; errors are one line.
- Done-when is concrete: exact command, expected output, tolerance (pixel/frame diff, duration tolerance, timing via sleeping mocks), plus one real measurement (e.g. wall-clock in the stage log).
- Keep a dated "how to test it today" section: exact steps, expected outputs, timing.

## Verification beyond tests

- A "verified" claim names which check found what. Mechanical checks alone are not "verified".
- **Real server**: a page change is done only after tests, a restart of the real server, and a read-only check in every state the page draws differently. Procedure, sandbox for states real data lacks, and boundaries: operations.md.
- Pages are checked in a real browser at desktop and 375 px widths before handing them over.
- Verify on real-but-bounded data (one chapter, one ticker) and run the repo's verify/check verb on real artifacts before asking the owner to approve. Larger checks run outside the test runner on a copy of the production workspace; record measured results and timings in the design doc, each timing with its context (machine, sample size, date). A rehearsal (paper/test) runs at the size and configuration production will face; never test small and run bigger.
- Deterministic output checks on every item (e.g. a per-region OCR read-back at fixed DPI; pixel or frame diff against a rendered reference with a config tolerance) prove fidelity; whole-image heuristics do not.
- **Performance**: one deterministic measurement before/after at a fixed input size with expected numbers. Prefer counts (queries, calls, bytes, rows) over wall-clock, e.g. sqlite statements via `set_trace_callback` for 50 customers: 51 before, 1 after. Wall-clock only with a fixed large input and a ≥5x ratio. Assert output identical before and after.
- **Classifiers, graders, thresholds**: calibrate before trust. Classifier ≥90% correct on fixtures including misclassification traps, every miss below its confidence threshold. Grader ≥0.9 agreement with owner labels before grading anything. Thresholds/ranks tested on human-made data, reporting per-item agreement and coverage.
- Each prompt/lens has at least one fixture with a planted problem and one clean control.
- Model/prompt changes are experiments, recorded (hypothesis, configs, metrics, conclusion; failed ones kept) in the repo's design doc; replay the new prompt against the same cached inputs before shipping.
- Measure the verifier and the loop: periodically audit a refuted candidate for false refutation; show learning metrics with n (acceptance, repeat-rejection, revert rate). Approval alone is not proof of quality; record reverts as outcomes.
- Score a policy against its road not taken on every occurrence, paper/test included.
- Human quality sign-off is a release gate separate from automated correctness.

## Toolchain

| Concern | Python | Node.js/TS | Rust |
|---|---|---|---|
| runner | pytest | vitest | cargo test / cargo-nextest |
| mutation | mutmut | StrykerJS (`@stryker-mutator/core`) | cargo-mutants |
| property | hypothesis | fast-check | proptest |
| coverage (informational, never a target) | coverage.py | `vitest --coverage` (v8) | cargo-llvm-cov |
| lint/format | `ruff check` / `ruff format` | eslint + prettier (or biome) | `clippy -D warnings` / rustfmt |
| types | pyright or mypy, public API typed | TS strict, no `any` in public API | compiler |
| fakes | fake behind adapter interface, no cassette lib | same | trait-based fake |
| data objects (coding.md#data-objects) | `@dataclass(frozen=True, slots=True)`; JSON Schema at edges | `readonly` types/interfaces; `zod` at edges | structs `#[derive(Clone, Debug, PartialEq)]`; `serde` at edges |

- Run tools from the repo's own environment (e.g. `.venv/bin/pytest`, `.venv/bin/ruff check src tests`); the exact commands live in the repo's `CLAUDE.md`; otherwise find them (README, CI, manifests), never configure them by hand.
- A fixture shared across languages (one directory, asserted by both suites) pins cross-language agreement.

## Test report

Every implementation hand-off and PR body carries:

```
test_commands: [exact commands run]
full_suite: true|false
skipped: [{suite, why}]
before: <verbatim summary line before the change>
after: <verbatim summary line after the change>
new_failures: [test ids] (must be empty for a PR)
red_first: [test id → pasted failing output]
flaky: [test ids seen passing on rerun without a code change]
not_covered: [paths labelled untested, and why]
verified: [check → state/data → result]   # beyond tests
notes: pre-existing failures, suite size + date
```
