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

from metalm_ops import backup, deploy, doctor, offsite, schedule, server, status
from metalm_ops.config import Config, ConfigError, load

# (group, verb) -> (description, example)
LEAVES = {
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
    ("schedule", "print"): ("Print the launch agent plist for the backup job or the dashboard.", "metalm-ops schedule print backup"),
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
        '  COMPREPLY=($(compgen -W "$words --json --config --dry-run --alert --port" -- "$cur"))\n'
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
        print("\n".join(lines + [f"next: {board['next']}"]))


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
    cfg: Config = load(args.config)
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
        print(schedule.render(cfg, args.job), end="")
        print(f"install: {schedule.install_command(cfg, args.job)}", file=sys.stderr)
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
    except (ConfigError, offsite.OffsiteError, deploy.DeployError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
