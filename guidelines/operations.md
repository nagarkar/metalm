# Operations
Status: DRAFT — not yet ratified by the owner.
Scope: served apps on this Mac, their servers and launch agents, and checking pages in a browser. Scheduled and unattended work: scheduling.md.

## Served apps (Ruled 2026-10-01)
- Every app serves its page on loopback behind `tailscale serve`, all apps under one tailnet name, one HTTPS port each.
- The tailnet name and the port table (app, tailnet HTTPS port, local server, launch agent) live in the owner's global `~/.claude/CLAUDE.md` under `## Served apps (this Mac)`, never in git. It is the one place ports are recorded. (owner)
- User-specific details (host names, tailnet names, ports of this Mac, account ids, personal paths) never enter git: not in guidelines, skills, docs, tests or fixtures. Tests use placeholders such as `host.example.ts.net`; a skill says "the tailnet name in `~/.claude/CLAUDE.md`". (owner)
- One port per app. Never map paths under one port: Tailscale forwards the prefix and pages use root-relative routes. Never use `--set-path`. Never take another app's port.
- The app binds loopback only; `tailscale serve` fronts it. Answer only Host headers naming this machine (loopback, `*.ts.net`), else 421.
- The page the owner looks at is the app's one real server. A running server keeps the code it started with, so a change does not exist for the owner until that server is restarted onto it.
- One local server process per app hosts all its pages (job UI, dashboard, approvals); no cloud hosting until missed runs prove a need. One server per unit of work where the app has units (e.g. gamelm: one SKU per server, named on the command line).
- `doctor` checks Tailscale is connected and prints the URL. It should warm the cert: the first HTTPS hit takes ~12 s.
- `doctor` checks the real server is not older than its code: it compares the server process's start time with the newest commit touching served code and fails with "server is older than HEAD: `launchctl kickstart -k gui/501/com.nagarkar.<app>.serve`". A merge that skipped the restart is caught by the next `doctor` run instead of by the owner. (Ruled 2026-10-05.)
- A new app takes the next free tailnet port and gets a row in the owner's table (`~/.claude/CLAUDE.md`), a launch agent, and a sandbox script before its first UI change.

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
- Report a change as visible after the real server has been restarted with the change and checked.
- Restart and check are part of "done". If the restart is not possible (no launch agent, permission missing), say so plainly and ask the owner to restart.

## Sandbox script
- Every served app has one: `scripts/sandbox_server.sh [port]`.
- It starts a throwaway server on a spare port and declines the real port.
- Each start makes a fresh copy of the app's data outside the real data directory (declines a path inside it). Copy SQLite with `sqlite3 … ".backup"` so it is consistent while the real server runs.
- It strips credentials that act outside the Mac (brokers, email, payments) from the environment, so nothing tapped in the sandbox reaches anywhere.
- Change anything there; stop it when done. Its state is lost on next start.

## Boundaries
- Stop the real server only by asking the owner to unload its agent (`launchctl bootout gui/501/com.nagarkar.<app>.serve`). A process killed by hand is restarted by launchd on the old code or leaves the port held.
- No second server against an app's real data, ever. Two code versions on one database overwrite each other's caches, and the owner's server keeps showing the old code.
- Keep an old surface (and its scheduled sync) running until the new one has carried a real session.

## Handing out links
- Before handing out an app link, verify it is live: `curl` its `/health`, and `tailscale serve status`. Then reply with just the link.
- Phone review pages have a measured size budget; over it, split into linked parts. Never trim content or guess a bigger budget.
- Self-contained HTML review pages need no local server; publish with the same file path so the URL stays stable on republish.

## Browser checks
- Check pages in real Chrome, driven with `mcp__claude-in-chrome__*`, at desktop width and at 375 px mobile width.
- This holds for diagnosis too. When the owner reports a page as missing or broken, check it in real Chrome or with `curl` against the tailnet URL, never the Browser pane: its blocked fetches look like a broken page and send the diagnosis the wrong way.
- Exception: the pane blocks fetches only on the tailnet name; on `http://127.0.0.1:<port>` they work. Its `mobile` preset is then the one true 375 px check: real Chrome will not size a window below ~500 px, and headless Chrome renders at 500 px whatever `--window-size` says. Use it on loopback for layout only, read-only, and say so. (Ruled 2026-10-05.)
- Beyond "it renders", the check answers the readability questions in `ui.md`.
- The Claude desktop Browser pane (`mcp__Claude_Browser__*`) cannot run local fetch-based apps: every fetch and API POST fails `net::ERR_BLOCKED_BY_CLIENT`. Never use it to check a served app. It also suppresses native `confirm()`, so pages use inline confirms.
- The in-app preview renders local files statically; Chrome tools cannot click inside an Artifact frame. Verify Artifact page logic with a headless jsdom harness (optional dev check behind a node/jsdom presence test).

## Sandboxed shell quirks
- Install skills with `npx skills add … --copy`.
- Browser-opening logins (OAuth) run via Bash, never MCP, and only on the owner's request in chat; say a browser will open first; long timeout (≥5 min). Only the `login` verb opens a browser; every other verb stops with "run <login>" when auth lapses.
- Run heavy installs sequentially (parallel installs exhausted vnodes).

## Credentials
- Each repo has its own OAuth client and token in its gitignored `.env` / `.config/` (token file mode 600); never reuse another repo's client or token.
- Minimal scopes (e.g. `gmail.modify`; Sheets `drive.file` so only self-created files are visible).
- Separate credentials for test and production (paper/live). Live requires an exact confirmation-phrase env var, not a boolean; a mismatch raises, never falls back.
