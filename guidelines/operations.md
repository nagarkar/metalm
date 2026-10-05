# Operations
Status: DRAFT — not yet ratified by the owner.
Scope: served apps on this Mac, their servers and launch agents, scheduled and unattended work, and checking pages in a browser.

## Served apps (Ruled 2026-10-01)
- Every app serves its page on loopback behind `tailscale serve`. All share one tailnet name, `imac.tail4b7b35.ts.net`, one HTTPS port each:

| app | tailnet HTTPS port | local server | launch agent |
|---|---|---|---|
| authorllm (audiobook page) | 443 (bare name) | 127.0.0.1:8792 | proposed, does not exist yet |
| supplylm (review page) | 8443 | 127.0.0.1:8777 | proposed, does not exist yet |
| tradelm (approvals, accounts, dashboard) | 9443 | 127.0.0.1:9443 | `~/Library/LaunchAgents/com.nagarkar.tradelm.serve.plist` (installed 2026-10-01) |
| gamelm (Vocingo review) | 10443 | 127.0.0.1:8778 | proposed, does not exist yet |

- This table is the one place ports are recorded. A repo's skill may repeat its own row; it never assigns a port.
- One port per app. Never map paths under one port: Tailscale forwards the prefix and pages use root-relative routes. Never use `--set-path`. Never take another app's port.
- The app binds loopback only; `tailscale serve` fronts it. Answer only Host headers naming this machine (loopback, `*.ts.net`), else 421.
- The page the owner looks at is the app's one real server. A running server keeps the code it started with, so a change does not exist for the owner until that server is restarted onto it.
- One local server process per app hosts all its pages (job UI, dashboard, approvals); no cloud hosting until missed runs prove a need. One server per unit of work where the app has units (e.g. gamelm: one SKU per server, named on the command line).
- `doctor` checks Tailscale is connected and prints the URL. It should warm the cert: the first HTTPS hit takes ~12 s.
- `doctor` checks the real server is not older than its code: it compares the server process's start time with the newest commit touching served code and fails with "server is older than HEAD: `launchctl kickstart -k gui/501/com.nagarkar.<app>.serve`". A merge that skipped the restart is caught by the next `doctor` run instead of by the owner. (Ruled 2026-10-05.)
- A new app takes the next free tailnet port and gets a row in this table, a launch agent, and a sandbox script before its first UI change.

## tailscale serve
- `tailscale serve` changes exposure: run it only on the owner's word in chat.
- One form only: `tailscale serve --bg --https=<port> http://127.0.0.1:<local>`. Always pass `--https` explicitly; a bare `--bg <port>` takes the 443 slot. Superseded forms: `--https=8443 8777` (no URL), bare `serve --bg <port>`.
- Confirm with `tailscale serve status`.
- Run Tailscale commands unsandboxed or ask the owner to run them in a terminal (the sandbox fails with "The Tailscale GUI failed to start"). CLI path on the iMac: `/usr/local/bin/tailscale`.

## Launch agents
- The real server runs under a launch agent: starts at login, restarts if it dies, logs to `~/.<app>/logs/serve.log`.
- The plist template lives in the repo under `scripts/` (`scripts/com.nagarkar.<app>.serve.plist`); the installed copy in `~/Library/LaunchAgents/` is machine-specific and not committed.
- The owner installs launch agents. Claude Code will not add anything that starts at login; print the install command instead.
- Restart only with `launchctl kickstart -k gui/501/com.nagarkar.<app>.serve`, allowed for that one command in the repo's `.claude/settings.local.json`.
- launchd wins over `nohup`. Never start a server detached with `nohup`, not even as a fallback when `/health` fails.
- An app without a launch agent yet: ask the owner to install one before relying on restarts. Until then ask the owner to restart the server; do not start or stop it yourself.

## After every change that touches an app's pages
1. Run the tests.
2. Restart the real server through its launch agent (`launchctl kickstart -k …`). Never stop the server's process by hand.
3. Check the change on the real server, read-only, in the browser, in every state the page draws differently (with and without a chosen item, default and custom settings). Look only: no clicks that write.
4. For states the real data lacks, use the repo's sandbox script.
5. Report what was checked, in which states, and anything that could not be checked.
- Restart and check are part of "done". If the restart is not possible (no launch agent, permission missing), say so plainly and ask the owner to restart.
- Never report a change as visible until the real server has been restarted onto it and checked.

## Sandbox script
- Every served app has one: `scripts/sandbox_server.sh [port]`.
- It starts a throwaway server on a spare port and declines the real port.
- Each start makes a fresh copy of the app's data outside the real data directory (declines a path inside it). Copy SQLite with `sqlite3 … ".backup"` so it is consistent while the real server runs.
- It strips credentials that act outside the Mac (brokers, email, payments) from the environment, so nothing tapped in the sandbox reaches anywhere.
- Change anything there; stop it when done. Its state is lost on next start.

## Boundaries
- No second server against an app's real data, ever. Two code versions on one database overwrite each other's caches, and the owner's server keeps showing the old code.
- Never kill the real server's process by hand.
- Never run `tailscale serve` without the owner's word.
- Keep an old surface (and its scheduled sync) running until the new one has carried a real session.

## Handing out links
- Before handing out an app link, verify it is live: `curl` its `/health`, and `tailscale serve status`. Then reply with just the link.
- Phone review pages have a measured size budget; over it, split into linked parts. Never trim content or guess a bigger budget.
- Self-contained HTML review pages need no local server; publish with the same file path so the URL stays stable on republish.

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
- [ ] Re-execs itself under `caffeinate -i -s` once.
- [ ] Steps go through a `step` helper; an `EXIT` trap notifies on failure only, naming the steps or "the run itself" if cut short.
- [ ] A missing setup is a logged `skipped:`, exit 0, not a failure.
- [ ] Runs `doctor` first; `doctor` checks this job's agent and its wake.
- [ ] One run row per invocation; the app's page shows "last successful run".
- [ ] Time-critical output before the slow part; independent steps kept separate.
- [ ] Plist template in `scripts/<label>.plist`; the hour lives only there.
- [ ] Tested against stub commands (clean run silent, failures named, killed run reported).
- [ ] **(owner)** Install and load the plist: `cp scripts/<label>.plist ~/Library/LaunchAgents/ && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/<label>.plist`.
- [ ] **(owner)** Daily wake 1–30 min before the job: `sudo pmset repeat wakeorpoweron MTWRFSU <HH:MM:SS>`.
- [ ] Alerts through `superlm-notify --repo <repo>` by full path (`~/.local/bin/superlm-notify`), stubbed by env var in tests.
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
- Plists are machine-specific and not committed. Changing the hour is a plist edit, not code.
- Local scheduled tasks (Claude desktop) run only while the app is open and the Mac awake, with one catch-up on wake. Use them, not cloud routines, when state lives on the Mac; one scheduled task per repo.
- Unattended tasks stall on permission prompts nobody answers (gamelm: 51 decisions sat 5 days; the task died holding the lock). Allow-list the exact commands in the repo's `.claude/settings.local.json` (e.g. `Bash(./gamelm.sh vocingo *)`).
- When a scheduled request "did not go through", check the task's last run first.
- Jobs attempt every step whether an earlier one failed (no `set -e`); one log file per run; one run row per invocation, `error` if any item failed, closed even on exception or Ctrl-C; retries say so on stderr; the page shows "last successful run".
- One idempotent `tick` verb runs every pending job from a jobs table under a lock with heartbeat (`--force` takes a dead lock); schedulers call `tick`; no resident daemon or queue broker.
- Keep independent steps separate so one does not consume another's retry budget or pass/fail status. Put the time-critical output before the slow part.
- A required volume unmounted: exit with a message, create nothing, let launchd retry. Fix by mounting, never `mkdir`.
- No LLM spend runs unattended without a per-run and per-day cap (open question in authorllm).
- Cloud routines see only pushed commits; each works on its own branch `routine/<name>-<date>` and opens one PR. Check open routine PRs first to avoid duplicates; a closed PR means pick something else.
- An irreplaceable database with no verified backup (`PRAGMA integrity_check` on a verified copy) is not deployed. Retention is the owner's call.
- Before killing a "stalled" process, confirm via log tail and output growth. Long stages run in the background; check in rather than block.

## Browser checks
- Check pages in real Chrome, driven with `mcp__claude-in-chrome__*`, at desktop width and at 375 px mobile width.
- This holds for diagnosis too. When the owner reports a page as missing or broken, check it in real Chrome or with `curl` against the tailnet URL, never the Browser pane: its blocked fetches look like a broken page and send the diagnosis the wrong way.
- Exception: the pane blocks fetches only on the tailnet name; on `http://127.0.0.1:<port>` they work. Its `mobile` preset is then the one true 375 px check: real Chrome will not size a window below ~500 px, and headless Chrome renders at 500 px whatever `--window-size` says. Use it on loopback for layout only, read-only, and say so. (Ruled 2026-10-05.)
- Beyond "it renders", the check answers the readability questions in `ui.md`.
- The Claude desktop Browser pane (`mcp__Claude_Browser__*`) cannot run local fetch-based apps: every fetch and API POST fails `net::ERR_BLOCKED_BY_CLIENT`. Never use it to check a served app. It also suppresses native `confirm()`, so pages use inline confirms.
- The in-app preview renders local files statically; Chrome tools cannot click inside an Artifact frame. Verify Artifact page logic with a headless jsdom harness (optional dev check behind a node/jsdom presence test).
- Every review ask carries a phone-ready page link in the same message.

## Sandboxed shell quirks
- Sandboxed Bash lacks LLM keys and the `claude` CLI; LLM-dependent commands run in the owner's terminal. Install skills with `npx skills add … --copy`.
- Browser-opening logins (OAuth) run via Bash, never MCP, and only on the owner's request in chat; say a browser will open first; long timeout (≥5 min). Only the `login` verb opens a browser; every other verb stops with "run <login>" when auth lapses.
- Run heavy installs sequentially (parallel installs exhausted vnodes).

## Credentials
- Each repo has its own OAuth client and token in its gitignored `.env` / `.config/` (token file mode 600); never reuse another repo's client or token.
- Minimal scopes (e.g. `gmail.modify`; Sheets `drive.file` so only self-created files are visible).
- Separate credentials for test and production (paper/live). Live requires an exact confirmation-phrase env var, not a boolean; a mismatch raises, never falls back.
