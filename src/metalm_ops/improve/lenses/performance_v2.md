---
id: performance_v2
version: 2
may_change_behaviour: false
needs_measurement: false
---
Fix the measured slowdown or waste the finding names, with identical results. The system measures: a static finding (a query, HTTP call, subprocess or file read per item inside a loop; a needless copy or conversion in a loop; a try/except inside a hot loop) must disappear when re-measured, and a slow test must run at least 20% faster in the next timed run.
Typical fixes: batch the per-item call into one call before or after the loop (one query with IN, one read, one request); hoist work that does not depend on the loop variable; build a set or dict once instead of `x in list` inside a loop; join strings once instead of `+=` in a loop; in a slow test, replace sleeps and real waits with a fake clock or a smaller fixed input that still proves the same behaviour.
State the cost as a function of the growing input in the claim (e.g. "1 + N queries for N rows"), quote the loop and the call, and add or adjust a test that asserts the results are unchanged (for an N+1, also the call count). Do not flag code that runs once on small fixed input, and do not trade correctness or readability for micro-speed.
