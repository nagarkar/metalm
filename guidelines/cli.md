# Command line
Scope: how every `*lm` repo's CLI is declared, documented, completed, printed and tested. Distilled from authorlm, ytlm and beelm; shared mechanics live in `corpuslm.clikit` (parser, describe, help text, global options, completion), which a repo imports and never copies.

## Declare and launch
- The CLI is always built first, before any MCP or page. One console script `<tool>` (`[project.scripts]`) is the entry point. A launcher `<tool>.sh` exists only where an unattended run (launchd, cron) needs the venv pinned without activation (coding.md#layout); it execs the module and never sources `.env`.
- Read `.env` in the program, as data; a real environment variable wins; `<TOOL>_ENV` relocates the file (coding.md#where-env-lives).
- One `build_parser()` builds the whole tree; every leaf verb maps to exactly one function in the typed API. Group related verbs as `group verb` (`corpus add`), never a free-form action argument.
- Global options are accepted anywhere on the line (`--json`; `--set SECTION.KEY=VALUE` where config can be overridden); a literal after `--` is left alone.

## Help and completion
- Every leaf has a description and an `example:` epilog. `help` lists every leaf; `help <verb> [<subverb>]` shows one; a group verb alone shows its subverbs; an unknown verb exits 1 and names the fix. A verb that can bill says so in its help.
- Shell completion is generated from the parser each time it is printed, never kept by hand: `<tool> completion` for bash (3.2-safe) offering verbs, subverbs, long flags and the global options. A name that lives in data (a corpus, a document) is completed by a hidden helper verb that prints the live names, not by a table in the script.
- An interactive shell (history, prompt, in-process verbs) is built only for a tool with a session to hold (authorlm); a stateless tool does not have one.

## Output and errors
- `--dry-run` is the one preview flag: any verb that changes data or spends money accepts it, prints what it would do and what it would cost, writes nothing and calls no model. Without it the verb runs live. A verb that spends refuses to start without a spend cap in config and a priced model. (owner, 2026-10-09)
- Every verb prints a short board (counts, paths, hashes, a `next` hint), never content, payloads or images. `--json` prints the same board as one JSON object.
- Unscoped queries return a summary plus narrowing guidance (relevance over offset; no pagination, no full dumps).
- Per-verdict operations stay singular when each explanation is evidence; batch only naturally plural curation (one call, an operations array, a status per operation).
- Exit 0 on success and 1 on any error, usage errors included. A pipe closed by `| head` is success and prints nothing.
- Errors read `error: <what>. <the exact fix command>` on stderr; a missing prerequisite names the setting or verb that fixes it. Never create a database, folder or workspace to get past a missing one.
- Trace verb names, exit codes and durations, never raw argv (positional arguments can hold text).

## Setup and doctor
- `setup` records the workspace pointer in `.env` (only inside the tool's marked block, after a timestamped backup, with a diff; `--dry-run`; a second run says nothing changed). It creates nothing else.
- `doctor` lists each check with its state, detail and fix, exits 1 when a required check fails, and every scheduled job runs it first.

## Tests that hold the surface
- One test per rule: every leaf has a description and an example; `help` lists every leaf; every leaf resolves to an API function; `--json` boards parse and carry `next`; a usage error exits 1; the completion script loads in a real bash and offers a subverb; the repo skill names every leaf verb; no verb prints content; the MCP tool set (if any) equals its declared list, with each CLI-only verb justified.
