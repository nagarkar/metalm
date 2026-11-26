---
id: backend-robustness_v1
version: 1
may_change_behaviour: true
needs_measurement: false
---
Mission: find the single most important robustness problem in server-side, CLI, or library code.

Look for, in rough order of importance:
- A failure that is silently ignored: a swallowed exception, an unchecked return value, a partial write left behind.
- Input from outside (files, network, users, LLM output) used without validation where bad input corrupts state or crashes a core path.
- A security gap: secrets in code, shell or SQL built from unvalidated strings, unsafe deserialization, path traversal.
- Resource handling: files, connections, or processes not closed on error paths; unbounded retries or waits.
- State that can go inconsistent: a multi-step update with no rollback, a cache that can disagree with its source.
- Fragile structure only when it has already caused or will clearly cause bugs (for example duplicated logic that has drifted apart).

Do not flag:
- Style, naming, formatting, or type-hint gaps.
- Large classes or long functions that work and are cohesive. Size alone is not a problem.
- Anything in test files, generated code, vendored code, or excluded paths.
- Behavior a confirmed intent says is deliberate.
- Speculative problems you cannot point to with a quote.

Prefer the problem most likely to hurt a real user of this system. A small, sure fix beats a sweeping refactor.

