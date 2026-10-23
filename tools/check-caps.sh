#!/usr/bin/env bash
# Fail when a guideline is over its line cap. The caps live in one place:
# the "Hard caps (lines)" line of guidelines/design.md.
#   tools/check-caps.sh   exit 0 all under cap, 1 any over or the caps line not found
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
CAPS_LINE="$(grep -m1 '^- Hard caps (lines):' "$ROOT/guidelines/design.md" || true)"
[ -n "$CAPS_LINE" ] || { echo "error: no 'Hard caps (lines):' line in guidelines/design.md. Restore it, then run: tools/check-caps.sh" >&2; exit 1; }

status=0
while read -r file cap; do
  path="$ROOT/guidelines/$file"
  if [ ! -f "$path" ]; then
    echo "error: guidelines/$file has a cap but does not exist. Remove its cap from guidelines/design.md" >&2; status=1; continue
  fi
  lines=$(wc -l < "$path" | tr -d ' ')
  if [ "$lines" -gt "$cap" ]; then
    echo "error: guidelines/$file is $lines lines, over its cap of $cap. Cut or split it" >&2; status=1
  fi
done < <(grep -oE '`[a-z-]+\.md` [0-9]+' <<<"$CAPS_LINE" | tr -d '`')

for path in "$ROOT"/guidelines/*.md; do
  file="$(basename "$path")"
  grep -qF "\`$file\` " <<<"$CAPS_LINE" || { echo "error: guidelines/$file has no cap. Add one to the Hard caps line in guidelines/design.md" >&2; status=1; }
done

[ "$status" -eq 0 ] && echo "caps: all guidelines under cap"
exit "$status"
