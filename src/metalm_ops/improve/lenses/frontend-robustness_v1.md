---
id: frontend-robustness_v1
version: 1
may_change_behaviour: true
needs_measurement: false
---
Mission: find the single most important robustness problem in UI code (unhandled errors, state bugs, broken accessibility).

Look for, in rough order of importance:
- A request whose failure is ignored, so the UI shows stale or empty data as if it were real (a swallowed `.catch`, no `res.ok` check, an error that only reaches `console.error`).
- A core path with no error or loading state: the user cannot tell a failure from "nothing here" or "still working".
- User or server text rendered as HTML (`dangerouslySetInnerHTML`, `innerHTML =`, `v-html`, `{@html}`) without sanitizing.
- State that can go inconsistent: an older, slower response overwriting a newer one; a stale closure; an effect missing a dependency that changes what it does.
- A destructive action (delete, discard, overwrite) with no confirmation or undo.
- A core control that a keyboard or screen-reader user cannot use: a clickable div or span with no role or key handler, an icon button or image with no label or alt, a form input with no label.

Do not flag:
- Styling, layout, visual taste, naming, or formatting.
- Component size alone. A large component that works is not a problem.
- Re-render or bundle performance; the performance lens owns speed and resource problems.
- Anything in test, story, generated, vendored, or build-output files, or in excluded paths.
- Behavior a confirmed intent says is deliberate.
- Speculative problems you cannot point to with a quote.

Prefer the problem most likely to mislead or lock out a real user. A small, sure fix beats a sweeping refactor.

