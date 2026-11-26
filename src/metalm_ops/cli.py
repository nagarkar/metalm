"""Command line for metalm-ops: backups, status, the dashboard server, doctor and launch agent plists.

Every verb prints a short board (`--json` for one JSON object with `next`),
exits 0 on success and 1 on any error, and never prints a secret or a
database's content.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from metalm_ops import backup, deploy, doctor, offsite, prompts, schedule, server, status
from metalm_ops.config import Config, ConfigError, load
from metalm_ops.improve import run as improve

# (group, verb) -> (description, example)
LEAVES = {
    ("improve", "run"): (
        "Propose one small improvement per opted-in repo; Claude reviews may incur cost. Preview with --dry-run.",
        "metalm-ops improve run --dry-run",
    ),
    ("improve", "status"): ("Show cadence, brakes and the last ten improvement runs; --repo narrows the session check.", "metalm-ops improve status"),
    ("improve", "signals"): (
        "Measure each opted-in repo's code health (size, complexity, coupling, duplication, security, docs, tests, churn); no model.",
        "metalm-ops improve signals --repo computerlm",
    ),
    ("improve", "labels"): ("Create or update the six auto-improve labels in each opted-in repo.", "metalm-ops improve labels --repo marketlm"),
    ("improve", "unbrake"): (
        "Open a brake removal PR quoting the owner; never merge it.",
        'metalm-ops improve unbrake --repo marketlm --why "resume it" --dry-run',
    ),
    ("prompts", None): ("List versioned agent prompts, schemas and content hashes.", "metalm-ops prompts --json"),
    ("backup", "run"): ("Copy every database in ops.toml to the local backup folder and verify each copy.", "metalm-ops backup run --dry-run"),
    ("backup", "offsite"): (
        "Send the newest local run to B2 with restic, apply retention, and check a 5% subset weekly.",
        "metalm-ops backup offsite --dry-run",
    ),
    ("backup", "init"): ("Create the restic repository in the B2 bucket; run once.", "metalm-ops backup init"),
    ("status", None): ("Collect every check for every repo; --alert sends one SuperLM banner when any is red.", "metalm-ops status --json"),
    ("serve", None): ("Serve the dashboard on loopback until killed (the launch agent runs this).", "metalm-ops serve --port 8700"),
    ("deploy", None): (
        "After a metalm-ops merge: pull main into the main checkout, restart the dashboard, wait for /health, collect once.",
        "metalm-ops deploy --dry-run",
    ),
    ("discover", None): ("List SQLite files in the usual places and mark which ops.toml lists; writes nothing.", "metalm-ops discover"),
    ("doctor", None): ("Check every setup step no code installs and print the fix for each miss.", "metalm-ops doctor"),
    ("schedule", "print"): ("Print the launch agent plist for backup, improve or the dashboard.", "metalm-ops schedule print backup"),
    ("help", None): ("List every verb, or show one.", "metalm-ops help backup run"),
    ("completion", None): ("Print bash completion for metalm-ops.", 'eval "$(metalm-ops completion)"'),
}
NOTIFY = None  # tests set a fake: (title, body) -> None


def _leaf(sub, group: str, verb: str | None) -> argparse.ArgumentParser:
    desc, example = LEAVES[(group, verb)]
    return sub.add_parser(verb or group, description=desc, help=desc, epilog=f"example: {example}")


def _globals(parser: argparse.ArgumentParser, default=None) -> None:
    parser.add_argument("--json", action="store_true", default=default if default is not None else False, help="print the board as one JSON object")
    parser.add_argument("--config", type=Path, default=default, help="ops.toml to read (default ~/.claude/metalm/ops.toml)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="metalm-ops", description="Backups and one health page for every *lm repo.", epilog="example: metalm-ops status")
    _globals(p)
    top = p.add_subparsers(dest="group", metavar="verb")
    groups = {}
    for group, verb in LEAVES:
        if verb is None:
            leaf = _leaf(top, group, None)
        else:
            if group not in groups:
                g = top.add_parser(group, help=f"{group} verbs", description=f"{group} verbs")
                groups[group] = g.add_subparsers(dest="verb", metavar="subverb")
            leaf = _leaf(groups[group], group, verb)
        _globals(leaf, default=argparse.SUPPRESS)  # accepted after the verb too
        leaf.set_defaults(leaf=(group, verb))
        if group == "backup" and verb in {"run", "offsite"} or group == "deploy":
            leaf.add_argument("--dry-run", action="store_true", help="say what would happen; write and send nothing")
        if (group, verb) == ("backup", "offsite"):
            leaf.add_argument("--check", action="store_true", help="run the restic subset check even if one ran this week")
        if group == "improve" and verb in {"run", "labels", "status", "unbrake", "signals"}:
            leaf.add_argument("--repo", required=verb == "unbrake", help="only this repository")
        if (group, verb) == ("improve", "unbrake"):
            leaf.add_argument("--why", required=True, help="the owner’s words authorizing resume")
            leaf.add_argument("--dry-run", action="store_true", help="preview the brake removal PR")
        if (group, verb) == ("improve", "signals"):
            leaf.add_argument("--timings", action="store_true", help="first run each suite once to record per-test timings (slow; no model)")
        if (group, verb) == ("improve", "labels"):
            leaf.add_argument("--dry-run", action="store_true", help="preview label definitions without changing GitHub")
        if (group, verb) == ("improve", "run"):
            leaf.add_argument("--lens", help="force one lens (requires --repo)")
            preview = leaf.add_mutually_exclusive_group()
            preview.add_argument("--dry-run", action="store_true", help="preview skips and caps; call no model and write nothing")
            preview.add_argument("--no-pr", action="store_true", help="run the proposer and gates, then discard; no commit or PR")
        if group == "status":
            leaf.add_argument("--alert", action="store_true", help="send one SuperLM banner when any check is red")
        if group == "serve":
            leaf.add_argument("--port", type=int, help="loopback port (default: port in ops.toml)")
        if (group, verb) == ("schedule", "print"):
            leaf.add_argument("job", choices=schedule.JOBS)
        if group == "help":
            leaf.add_argument("words", nargs="*")
    return p


def completion_script() -> str:
    groups = sorted({g for g, _ in LEAVES})
    subs = {g: sorted(v for gg, v in LEAVES if gg == g and v) for g in groups}
    cases = "".join(f'    {g}) words="{" ".join(subs[g])}";;\n' for g in groups if subs[g])
    return (
        "_metalm_ops() {\n"
        '  local cur="${COMP_WORDS[COMP_CWORD]}" words\n'
        '  if [ "$COMP_CWORD" -eq 1 ]; then words="' + " ".join(groups) + '"\n'
        '  else case "${COMP_WORDS[1]}" in\n' + cases + '    *) words="";;\n  esac; fi\n'
        '  COMPREPLY=($(compgen -W "$words --json --config --dry-run --no-pr --repo --lens --why --alert --port" -- "$cur"))\n'
        "}\ncomplete -F _metalm_ops metalm-ops\n"
    )


def _notify(title: str, body: str) -> None:
    if NOTIFY is not None:
        return NOTIFY(title, body)
    exe = doctor.NOTIFIER.expanduser()
    if not exe.exists():
        print(f"error: cannot alert: {exe} is missing. Run metalm's ./install.sh", file=sys.stderr)
        return
    subprocess.run([str(exe), "--repo", "metalm", "--title", title, "--body", body], check=False)


def _board(args, board: dict, lines: list[str]) -> None:
    if getattr(args, "json", False):
        print(json.dumps(board, sort_keys=True))
    else:
        print("\n".join(lines + ([f"next: {board['next']}"] if "next" in board else [])))


def _help(parser: argparse.ArgumentParser, words: list[str]) -> int:
    if not words:
        for (g, v), (desc, _) in LEAVES.items():
            print(f"{(g + ' ' + v) if v else g:16} {desc}")
        return 0
    key = (words[0], words[1] if len(words) > 1 else None)
    if key not in LEAVES and not any(g == words[0] for g, _ in LEAVES):
        print(f"error: unknown verb {' '.join(words)!r}. List them: metalm-ops help", file=sys.stderr)
        return 1
    parser.parse_args([*words, "--help"])
    return 0


def dispatch(args, parser: argparse.ArgumentParser) -> int:
    leaf = args.leaf
    if leaf == ("help", None):
        return _help(parser, args.words)
    if leaf == ("completion", None):
        print(completion_script(), end="")
        return 0
    if leaf == ("prompts", None):
        rows = prompts.inventory()
        _board(args, {"prompts": rows, "next": "metalm-ops improve run --dry-run"}, [f"{row['id']} v{row['version']} {row['sha256']}" for row in rows])
        return 0
    cfg: Config = load(args.config)
    if leaf[0] == "improve":
        if leaf[1] == "run":
            board = improve.run(cfg, repo=args.repo, dry_run=args.dry_run, no_pr=args.no_pr, lens=args.lens)
        elif leaf[1] == "labels":
            board = improve.labels(cfg, repo=args.repo, dry_run=args.dry_run)
        elif leaf[1] == "signals":
            board = improve.signals_board(cfg, repo=args.repo, timings=args.timings)
        elif leaf[1] == "unbrake":
            from metalm_ops.improve import brake

            board = brake.unbrake(cfg, repo=args.repo, why=args.why, dry_run=args.dry_run)
        else:
            board = improve.status(cfg, repo=args.repo)
        lines = []
        for repository in board.get("repos", []):
            if "findings" in repository:
                counts = ", ".join(f"{name}={count}" for name, count in repository["counts"].items())
                lines.append(
                    f"{repository['name']}: {repository['files']} files; {counts}"
                    + (f"; timings: {repository['timings']}" if repository.get("timings") else "")
                    + (f"; errors: {repository['errors']}" if repository["errors"] else "")
                )
                lines.extend(
                    f"  {item['signal']:<11} {item['lenses'][0]:<18} {item['path']}:{item['start_line']} {item['detail']}" for item in repository["findings"]
                )
                continue
            lines.append(
                f"{repository['name']}: {'braked' if repository.get('brake') else 'not braked'} "
                + " ".join(f"{key}={repository.get(key, '')}" for key in ("D", "T", "today", "overdue"))
            )
        for row in board.get("rows", []):
            lines.append(" ".join(" ".join(str(row.get(key, "")).split()) for key in ("repo", "started", "lens", "outcome", "pr_url", "reason")).strip())
            if row.get("title"):
                lines.append(row["title"])
            if row.get("body"):
                lines.append(row["body"])
            if "D" in row:
                lines.append(" ".join(f"{key}={row.get(key, '')}" for key in ("D", "T", "today", "overdue", "due")))
            if row.get("diff_stat"):
                lines.append(row["diff_stat"])
            if row.get("finding"):
                lines.append(
                    f"finding: {row['finding']}; proposer tokens in={row.get('tokens_in')} cached={row.get('tokens_cached')} out={row.get('tokens_out')}"
                )
            if row.get("brake_error"):
                lines.append("brake failed: " + row["brake_error"])
            if row.get("gates"):
                lines.append("gates: " + ", ".join(f"{name}={value}" for name, value in row["gates"].items()))
        usage = board.get("usage", {})
        if usage:
            lines.append(f"usage: {usage.get('calls', usage.get('codex_calls', 0))} calls; review cost ${usage.get('review_cost_usd', 0):.2f}")
        if board.get("caps"):
            lines.append("caps: " + ", ".join(f"{name}={value}" for name, value in board["caps"].items()))
        _board(args, board, lines)
        return 0 if board.get("ok", True) else 1
    if leaf == ("backup", "run"):
        row = backup.run(cfg, dry_run=args.dry_run)
        bad = [i for i in row["items"] if not i["ok"]]
        board = {**row, "next": "metalm-ops backup offsite" if not bad else "metalm-ops doctor"}
        _board(
            args,
            board,
            [f"{'would back up' if args.dry_run else 'backed up'}: {len(row['items']) - len(bad)} of {len(row['items'])} into {row['dir']}"]
            + [f"FAILED {i['repo']}/{i['name']}: {i['detail']}" for i in bad],
        )
        return 0 if not bad else 1
    if leaf == ("backup", "offsite"):
        rows = offsite.run(cfg, dry_run=args.dry_run, force_check=args.check)
        ok = all(r["ok"] for r in rows)
        _board(args, {"rows": rows, "ok": ok, "next": "metalm-ops status"}, [f"{r['kind']}: {'ok' if r['ok'] else 'FAILED'} {r['detail']}" for r in rows])
        return 0 if ok else 1
    if leaf == ("backup", "init"):
        row = offsite.init(cfg)
        _board(args, {**row, "next": "metalm-ops backup offsite"}, [f"init: {'ok' if row['ok'] else 'FAILED'} {row['detail']}"])
        return 0 if row["ok"] else 1
    if leaf == ("status", None):
        result = status.collect(cfg)
        status.save(cfg, result)
        reds = status.reds(result)
        if args.alert and reds:
            _notify("ops: red checks", "; ".join(reds)[:400])
        lines = [f"overall: {result['level']}"] + [f"{r['level']:5} {r['name']}" for r in result["repos"]] + [f"red: {r}" for r in reds]
        _board(args, {**result, "red": reds, "next": f"open the dashboard (port {cfg.port})"}, lines)
        return 0
    if leaf == ("serve", None):
        server.serve(cfg, args.port or cfg.port)
        return 0
    if leaf == ("deploy", None):
        steps = deploy.deploy(cfg, dry_run=args.dry_run)
        _board(args, {"steps": steps, "next": "open the dashboard"}, steps)
        return 0
    if leaf == ("discover", None):
        found = deploy.discover(cfg)
        new = [f for f in found if not f.listed]
        lines = [f"{'listed' if f.listed else 'NEW   '} {f.bytes / 1e6:8.1f} MB  {f.repo:13} {f.path}" for f in found]
        board = {
            "found": [{**asdict(f), "path": str(f.path)} for f in found],
            "new": len(new),
            "next": "add NEW rows that are live stores to ops.toml as [[database]]" if new else "ops.toml lists every store found",
        }
        _board(args, board, lines + [f"{len(new)} not in ops.toml"])
        return 0
    if leaf == ("doctor", None):
        found = doctor.check(cfg)
        bad = doctor.failed(found)
        lines = [f"{'ok  ' if f.ok else ('FAIL' if f.required else 'warn')} {f.name}: {f.detail}" + ("" if f.ok else f"\n     fix: {f.fix}") for f in found]
        _board(args, {"ok": not bad, "checks": [asdict(f) for f in found], "next": "metalm-ops backup run" if not bad else "run each fix above"}, lines)
        return 1 if bad else 0
    if leaf == ("schedule", "print"):
        rendered = schedule.render(cfg, args.job)
        install = schedule.install_command(cfg, args.job)
        if args.json:
            _board(args, {"job": args.job, "plist": rendered, "install": install, "next": "run the install command"}, [])
        else:
            print(rendered, end="")
            print(f"install: {install}", file=sys.stderr)
        return 0
    raise AssertionError(leaf)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1
    if not getattr(args, "leaf", None):
        if getattr(args, "group", None):
            parser.parse_args([args.group, "--help"])
        parser.print_help()
        return 0
    try:
        return dispatch(args, parser)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1
    except (ConfigError, offsite.OffsiteError, deploy.DeployError, improve.ImproveError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
