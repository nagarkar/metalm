---
id: tests_v1
version: 1
may_change_behaviour: false
needs_measurement: false
---
Mission: find the single most important behavior that has no test, or only a weak one. The PR adds or strengthens tests only; it never edits non-test code.

Look for, in rough order of importance:
- A core path with no test at all: money (charges, refunds, totals), deletion, persistence, auth, or parsing outside input.
- An error path never exercised: malformed input, a failed write, a rejected request whose specific error the contract promises.
- A test that cannot fail: it asserts nothing, asserts only on a mock it set up itself, wraps the call in a broad try/except, or is `assert True`.
- A function whose contract is mostly about its failure modes, tested only on the happy path.
- A regression-prone branch with no boundary test: a threshold (`>=` vs `>`), rounding, an off-by-one range end, a date or timezone edge.

Do not flag:
- Coverage percentage for its own sake, trivial getters, generated or vendored code, excluded paths.
- Slow, flaky, or badly organized test infrastructure. That is not this lens.
- Live, network, or paid tests that are intentionally skipped.
- Anything a confirmed intent settles, or speculation you cannot back with a quote of the code and of the test (or show no test names it).
- A gap whose test would fail against the current code. That is a bug, which belongs to a code lens; skip it here.

A good candidate names the behavior, quotes the code that implements it and the existing test (or shows none references it), and its test_plan describes the new or stronger test, which must pass against the current code. Prefer the gap where a regression would most hurt a real user, closed by one small, sharp test.

