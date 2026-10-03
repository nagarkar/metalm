# Jev decision example

Reference for `guidelines/coding.md#typed-decisions-jev`. Stdlib only.

- `questions/ticket_triage_v1.json`: one decision; each question with its `bars`.
- `jevkit.py`: load, one batched call, frozen `Decision` with gated reads.
- `apps.py`: one app per type (Noul, Choice, Score) and a combined router.

```bash
python3 -m unittest discover -s tests -v
```

Live (billed, ~560 input tokens per ticket): `TYPESAFE_API_KEY=… python3 live_smoke.py`. Tested 2026-10-03 on `jev-1.13.0`.
