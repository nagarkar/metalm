---
id: performance_v1
version: 1
may_change_behaviour: false
needs_measurement: true
---
Mission: find the single most measurable slowdown or waste: work that grows faster than it needs to with the system's data.

Look for, in rough order of importance:
- N+1: a query, HTTP call, or file read per item inside a loop over a collection, where one batched call would do.
- Unbounded reads: a whole table, file, or response loaded into memory (no LIMIT, pagination, or streaming) where its size grows.
- Quadratic work on input that grows with users' data: nested scans, `x in some_list` inside a loop, re-sorting inside a loop, string `+=` building in a loop.
- Repeated identical expensive calls on a hot path with no caching, or work recomputed on every call that depends only on rarely changing input.
- Blocking I/O or `sleep` on a request or UI path.

Measurement required (the explorer cannot run code, so the candidate carries the argument and the plan):
- The claim states the cost as a function of the growing input (e.g. "1 + N queries for N customers"), backed by quotes of the loop and the call inside it, and names the input that grows.
- `test_plan` names one deterministic measurement the implementer runs before and after, with its fixed input size and the expected numbers (e.g. "count sqlite statements via `set_trace_callback` for 50 customers: 51 before, 1 after"). Prefer counts (queries, calls, bytes read, rows loaded, comparisons) over wall-clock; use wall-clock only with a fixed large input and a generous ratio threshold (at least 5x).
- The fix must not change results; the test also asserts the output is identical before and after.

Do not flag:
- Micro-optimizations with no growth argument, or code that runs once at startup on fixed small input.
- Anything without a plausible growing input; readability trade-offs.
- Correctness or robustness bugs: the code lenses own them.
- Test, generated, or vendored code, excluded paths, or behavior a confirmed intent settles.

Prefer the waste that grows fastest on a path users hit often. A small fix with a clear count beats a broad rewrite.

Performance candidate checks (in addition to the general rules):
- Check the growth argument against the quotes and the callers: is the input actually unbounded or large in practice (user rows, tables, uploads), not a fixed small list? Is the loop actually on a path that runs often?
- Check that the quoted call really runs once per item (not hoisted, cached, memoized, or batched elsewhere).
- Check that `test_plan` names a deterministic measurement (a count of queries, calls, rows, bytes, or iterations at a fixed input size) with before and after numbers, and that it would actually show the difference.
- Refute if the measurement is wall-clock only on a tiny input, if it cannot distinguish before from after, or if the proposed change alters results, ordering, or errors beyond performance.
- Refute if the claim is really a correctness or robustness bug; that belongs to the code lenses.

The PR must add a test or benchmark with actual before and after measurements and the command that produced them. Preserve results, ordering and errors.

