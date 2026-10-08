## Merging

- Standing authorization (owner, {{DATE}}): this repo has one owner, so the agent merges its own PR once the pre-commit hooks and the test suite pass. It still waits for the owner's word on a PR that changes a rule marked `(owner)` or a metalm guideline, and on one whose first run spends money or migrates live data.
- Revisit trigger: when this repo gets a second contributor, a second user, or runs as a shared service, stop merging on this authorization and ask the owner to update this section.
