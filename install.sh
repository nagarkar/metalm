#!/usr/bin/env bash
# Install metalm for the current user. Idempotent; see guidelines/install-scripts.md.
#   ./install.sh             install or refresh
#   ./install.sh --dry-run   print what would change, change nothing
#   ./install.sh --uninstall remove the symlinks and the managed block
set -euo pipefail

MODE=install
case "${1:-}" in
  --dry-run) MODE=dry ;;
  --uninstall) MODE=uninstall ;;
  "") ;;
  *) echo "usage: $0 [--dry-run|--uninstall]" >&2; exit 2 ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
LINK="$CLAUDE_DIR/metalm"
BIN_DIR="$HOME/.local/bin"
NOTIFY_LINK="$BIN_DIR/superlm-notify"
NOTIFIER="$ROOT/tools/notifier"
GLOBAL_MD="$CLAUDE_DIR/CLAUDE.md"
BEGIN='<!-- metalm:begin -->'
END='<!-- metalm:end -->'

for cmd in git gh; do
  command -v "$cmd" >/dev/null || echo "warning: '$cmd' not found; metalm-setup needs it" >&2
done
# Only the SuperLM notifier needs these (Xcode command line tools: xcode-select --install).
NOTIFIER_OK=1
for cmd in swift swiftc iconutil sips codesign shasum; do
  command -v "$cmd" >/dev/null || {
    echo "warning: '$cmd' not found; the SuperLM notifier is not built (xcode-select --install)" >&2
    NOTIFIER_OK=0
  }
done

run() { if [ "$MODE" = dry ]; then echo "would: $*"; else "$@"; fi; }

backup() {
  [ -f "$1" ] || return 0
  local bak; bak="$1.bak.$(date +%Y%m%d-%H%M%S)"
  run cp -p "$1" "$bak"
  echo "backup: $bak"
}

# symlink TARGET LINKPATH: create; leaves an existing file, dir or foreign link alone.
symlink() {
  local target="$1" path="$2"
  if [ -L "$path" ]; then
    [ "$(readlink "$path")" = "$target" ] && { echo "ok: $path"; return; }
    echo "skipped: $path points to $(readlink "$path"); remove it and rerun" >&2
  elif [ -e "$path" ]; then
    echo "skipped: $path exists and is not a symlink; move it aside and rerun" >&2
  else
    run ln -s "$target" "$path"; echo "linked: $path -> $target"
  fi
}

unlink_if_ours() {
  local path="$1"
  if [ -L "$path" ] && [[ "$(readlink "$path")" == "$ROOT"* ]]; then
    run rm "$path"; echo "removed: $path"
  fi
}

block() {
  cat <<EOF
$BEGIN
## metalm (managed by $ROOT/install.sh; edits inside this block are overwritten)

- Engineering rules for my repos live in metalm (\`~/.claude/metalm\`, a symlink to $ROOT); metalm governs.
- A repo opts in with \`@~/.claude/metalm/guidelines/index.md\` in its \`CLAUDE.md\`.
- "Set up a repo", "make the repo compliant with guidelines", "adopt metalm" / "grandfather this repo", or "check conformance with metalm" means: run the \`metalm-setup\` skill. It replaces \`/setup-matt-pocock-skills\`.
- Unattended or long-running work alerts with \`superlm-notify --repo <repo> [--title T] --body <message>\` (\`~/.local/bin\`, the SuperLM notifier).
$END
EOF
}

# Write the managed block: replace it in place if present, else append.
write_block() {
  local tmp; tmp="$(mktemp)"
  if [ -f "$GLOBAL_MD" ] && grep -qF "$BEGIN" "$GLOBAL_MD"; then
    awk -v b="$BEGIN" -v e="$END" -v f="$1" '
      $0==b {while ((getline l < f) > 0) print l; skip=1; next}
      $0==e {skip=0; next}
      !skip' "$GLOBAL_MD" > "$tmp"
  else
    { [ -f "$GLOBAL_MD" ] && cat "$GLOBAL_MD" && echo; cat "$1"; } > "$tmp"
  fi
  if [ -f "$GLOBAL_MD" ] && cmp -s "$tmp" "$GLOBAL_MD"; then
    echo "ok: $GLOBAL_MD block current"; rm "$tmp"; return
  fi
  diff -u "$GLOBAL_MD" "$tmp" 2>/dev/null || true
  if [ "$MODE" = dry ]; then rm "$tmp"; return; fi
  backup "$GLOBAL_MD"
  mv "$tmp" "$GLOBAL_MD"; echo "updated: $GLOBAL_MD"
}

remove_block() {
  [ -f "$GLOBAL_MD" ] && grep -qF "$BEGIN" "$GLOBAL_MD" || return 0
  local tmp; tmp="$(mktemp)"
  awk -v b="$BEGIN" -v e="$END" '
    $0==b {if (held && prev!="") print prev; held=0; skip=1; next}
    $0==e {skip=0; next}
    skip {next}
    {if (held) print prev; prev=$0; held=1}
    END {if (held) print prev}' "$GLOBAL_MD" > "$tmp"
  diff -u "$GLOBAL_MD" "$tmp" || true
  if [ "$MODE" = dry ]; then rm "$tmp"; return; fi
  backup "$GLOBAL_MD"; mv "$tmp" "$GLOBAL_MD"; echo "removed block: $GLOBAL_MD"
  [ -s "$GLOBAL_MD" ] || { rm "$GLOBAL_MD"; echo "removed empty: $GLOBAL_MD"; }
}

# The SuperLM notifier app: built inside the clone (tools/notifier/build/, git-ignored),
# and only when its sources changed since the last build.
build_notifier() {
  [ "$NOTIFIER_OK" = 1 ] || return 0
  local want have
  want="$("$NOTIFIER/stamp.sh")"
  have="$(cat "$NOTIFIER/build/.stamp" 2>/dev/null || true)"
  if [ "$want" = "$have" ] && [ -x "$NOTIFIER/build/SuperLM Notifier.app/Contents/MacOS/superlm-notifier" ]; then
    echo "ok: SuperLM notifier current"; return
  fi
  if [ "$MODE" = dry ]; then echo "would: build $NOTIFIER/build/SuperLM Notifier.app"; return; fi
  "$NOTIFIER/build.sh"
  NOTIFIER_BUILT=1
}
NOTIFIER_BUILT=0

if [ "$MODE" = uninstall ]; then
  unlink_if_ours "$NOTIFY_LINK"
  unlink_if_ours "$LINK"
  for s in "$ROOT"/skills/*/; do unlink_if_ours "$CLAUDE_DIR/skills/$(basename "$s")"; done
  remove_block
  exit 0
fi

run mkdir -p "$CLAUDE_DIR/skills"
symlink "$ROOT" "$LINK"
for s in "$ROOT"/skills/*/; do
  symlink "${s%/}" "$CLAUDE_DIR/skills/$(basename "$s")"
done
f="$(mktemp)"; block > "$f"; write_block "$f"; rm "$f"
build_notifier
run mkdir -p "$BIN_DIR"
symlink "$ROOT/bin/superlm-notify" "$NOTIFY_LINK"
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) echo "note: $BIN_DIR is not on PATH; call $NOTIFY_LINK by its full path" ;; esac
if [ "$NOTIFIER_BUILT" = 1 ]; then
  echo "owner: the first banner asks to allow notifications from SuperLM; allow them, or turn them on in System Settings → Notifications → SuperLM"
fi
echo "done. Update later with: git -C $ROOT pull && $ROOT/install.sh"
