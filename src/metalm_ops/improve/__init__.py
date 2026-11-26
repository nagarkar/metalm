"""Activity-driven small improvements, proposed by Codex and independently reviewed by Claude.

Python owns the worktrees, gates, publishing, decisions and run ledger; agents
only edit a proposal or judge a diff. Configuration opts repositories in.

Decisions:
- A dry run calls no agent and writes nothing; `--no-pr` rehearses the proposal and gates without publishing. (owner)
- Codex proposes; a Claude verifier must confirm the quoted claim, then two independent Claude calls review; both must approve clearly with confidence at least 0.8, and checks must pass, before Python merges. (owner)
- The system never updates a live checkout unless it is clean and on main. (owner)
- Configured daytime slots never wake the Mac; changed-line demand supplements a weekly floor for every applicable lens. (owner)
- Three judge-rejected PRs or five qualifying runs without a PR publish a visible brake in metalm; only the owner can resume it through an unbrake PR. (owner)

Terms:
- **improve run**: one serial pass over the opted-in repositories, with a durable row per repository.
- **call ledger**: the provider, prompt hashes, duration, outcome and reported cost of every attempted agent call.
"""
