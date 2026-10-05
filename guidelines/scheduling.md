# Scheduling
Status: DRAFT — not yet ratified by the owner.
Scope: scheduled and unattended work: launchd jobs, local scheduled tasks, cloud routines. Served apps and their launch agents: operations.md.

## Choosing what runs a scheduled job (Ruled 2026-10-03)
Decide in this order:
1. **Does each run need judgment** (reading, deciding, writing code or prose)? No → a fixed script (2). Yes → a Claude run (3). Both → the pattern below (4).
2. **Fixed script:** needs data, devices or keys that live on this Mac → **launchd** here, with the safeguards below. Must run while the Mac is off → an always-on host (cron/systemd), or GitHub Actions if it keeps no state.
3. **Claude run:** needs local files, apps or the network → a **local scheduled task** (Claude desktop). Works from the pushed repo alone → a **cloud routine** (runs whether or not the Mac is awake).
4. **Judgment layered on a fixed job** (the preferred shape when both apply): the fixed job does the work that must be repeatable, on time, and costs nothing per run (data, money, anything irreversible). A separate Claude run reads only what the job left behind (its log, its run rows, its outputs) and summarizes, triages or proposes. The Claude run never sits inside the fixed job, never moves money or data, and its output is a report, an issue or a PR for the owner. When the Claude run is missing or wrong, the fixed job's own results stand.
- Never put money, orders or data pipelines behind an LLM run: same input must give the same output.

## launchd job safeguards (Ruled 2026-10-03)
Every launchd job script (e.g. `scripts/nightly.sh`):
- **Holds the Mac awake while it runs:** re-execs itself under `caffeinate -i -s` once (guard with an env var), so a short sleep timer cannot stop it halfway.
- **Is woken for:** a sleeping Mac does not run it on time (launchd fires it on wake, late). The owner sets a wake a few minutes before (`sudo pmset repeat wakeorpoweron MTWRFSU <HH:MM:SS>`); Claude Code leaves system settings alone and prints the command.
- **Alerts on failure only:** each step goes through a `step` helper that logs its exit code and records a failure; an `EXIT` trap sends one notification naming the failed steps, and names "the run itself" when the run was cut short. A clean run is silent (an alert every night is ignored). The notifier path is overridable by env var so tests can stub it.
- **Alerts through SuperLM:** every *lm repo notifies with `superlm-notify --repo <repo> [--title <what>] --body <message>` (metalm `bin/`, linked into `~/.local/bin` by `install.sh`; it launches the SuperLM notifier app built from `tools/notifier/`). One app, one icon, one permission for all repos; the banner's title names the repo. No fallback notifier: a banner that cannot be shown is logged with the reason. Call it by full path from launchd jobs (their PATH lacks `~/.local/bin`). `doctor` checks it is installed and built. (Ruled 2026-10-03.)
- **Long verbs announce their end:** every *lm CLI has a `notify` module (podlm `core/notify.py`, ytlm `notify.py`, gamelm `core/notify.py`) called from the one place every verb passes through. A verb that ran 60 s or longer sends one banner when it ends, ok or failed: title "<verb> <scope>", body "done in 12m 05s" or "FAILED after 3m 10s: <why>". Quick verbs, Ctrl-C and long-lived servers stay silent. The send is in the background and never fails a verb. `<REPO>_NOTIFY=0` turns it off and the test suite sets it for every test; `<REPO>_NOTIFY_CMD` points it at a stub. A repo whose output rules keep content out (ytlm D19) says only the verb, duration and exit code. (Ruled 2026-10-03.)
- **Treats "not configured" as a skip, not a failure:** a step whose setup is missing on this machine (e.g. a Sheets token) logs `skipped: …` and exits 0, so it never trips the alert.
- **Cannot report a run that never started:** the app's page shows "last successful run" from the run rows; that is the check for a missed night.
- **Checks its machine setup first:** the repo's `doctor` verb checks every owner-run step no code installs (its launch agents loaded, a daily wake 1–30 min before each launchd job's plist hour, the real server answering, `tailscale serve` fronting its port) and prints the fixing command for each miss; exit 1 on any fail. The job runs `doctor` as its first step, so a missing piece reaches that night's failure notification. Read the job's hour from its plist, never a second copy of it.
- **Is tested with stub commands:** run a copy of the script in a stand-in repo whose commands are stubs (clean run silent, failures named once and the rest still run, a killed run says so). Never test by running the real job.

## Scheduled job checklists (Ruled 2026-10-03)
Go down the list for the job's type whenever a scheduled job is created or changed, and report each line as done, owner's step pending, or not applicable. **(owner)** marks a step only the owner can do; print its command and ask, never work around it.

**launchd job** (a fixed script on this Mac)
- [ ] Script in the repo (`scripts/<job>.sh`); every step attempted, no `set -e`; one log file per run.
- [ ] Meets every safeguard above: `caffeinate` re-exec, `step` helper with a failure-only `EXIT` trap, missing setup as `skipped:`, `doctor` first (checking this job's agent and wake), `superlm-notify` by full path, tested against stub commands.
- [ ] One run row per invocation; the app's page shows "last successful run".
- [ ] Time-critical output before the slow part; independent steps kept separate.
- [ ] Plist template in `scripts/<label>.plist`; the hour lives only there.
- [ ] **(owner)** Install and load the plist: `cp scripts/<label>.plist ~/Library/LaunchAgents/ && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/<label>.plist`.
- [ ] **(owner)** Daily wake 1–30 min before the job: `sudo pmset repeat wakeorpoweron MTWRFSU <HH:MM:SS>`.
- [ ] **(owner)** metalm's `install.sh` run; notifications allowed for SuperLM (System Settings → Notifications → SuperLM); confirm with a test banner.
- [ ] After the first scheduled night: read its log and run row, and run `doctor`.

**Local scheduled task** (a Claude run on this Mac, Claude desktop)
- [ ] Only because it needs judgment and local state; otherwise launchd or a cloud routine.
- [ ] A narrow prompt: one repo, one goal, stated boundaries (what it never edits, pushes or sends).
- [ ] The exact commands it needs allow-listed in the repo's `.claude/settings.local.json`, so it never stalls on a prompt.
- [ ] A per-run and per-day spend cap.
- [ ] Output is a report, an issue or a PR for the owner; it never merges, approves, moves money or acts on a vendor.
- [ ] Reads the fixed job's leftovers (log, run rows, outputs) when it sits on top of one; never runs inside it.
- [ ] One scheduled task per repo; it runs only while the app is open and the Mac awake (one catch-up on wake).
- [ ] **(owner)** Create or enable it in Claude desktop; run it once by hand and read the run.
- [ ] When something "did not happen": check the task's last run first.

**Cloud routine** (a Claude run in the cloud on the pushed repo)
- [ ] Needs nothing on this Mac: only pushed commits, no local data, keys or network.
- [ ] Works on its own branch `routine/<name>-<date>` and opens one PR; checks for an open routine PR first; a closed PR means pick something else.
- [ ] Never merges, approves, closes, or pushes to `main`.
- [ ] Secrets only through the routine's own settings, never the repo.
- [ ] A narrow prompt with stated boundaries; a spend cap.
- [ ] **(owner)** Create it (`/schedule`); confirm the next run time; read the first run's log and PR.

## Scheduled and unattended work
- Prefer launchd (`~/Library/LaunchAgents`, `StartCalendarInterval`) over a resident daemon; launchd fires missed runs on wake. Start manual; when unattended is wanted, a `schedule install` verb writes the plist and the owner loads it.
- Run rows: `error` if any item failed, closed even on exception or Ctrl-C; retries say so on stderr.
- One idempotent `tick` verb runs every pending job from a jobs table under a lock with heartbeat (`--force` takes a dead lock); schedulers call `tick`; no resident daemon or queue broker.
- A required volume unmounted: exit with a message, create nothing, let launchd retry. Fix by mounting, never `mkdir`.
- No LLM spend runs unattended without a per-run and per-day cap (open question in authorllm).
- An irreplaceable database with no verified backup (`PRAGMA integrity_check` on a verified copy) is not deployed. Retention is the owner's call.
- Before killing a "stalled" process, confirm via log tail and output growth. Long stages run in the background; check in rather than block.
