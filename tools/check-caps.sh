#!/usr/bin/env bash
# Fail when a guideline is over its line cap. The caps live in one place:
# the "Hard caps (lines)" line of docs/design/guideline-authoring.md.
#   tools/check-caps.sh   exit 0 all under cap, 1 any over, 2 caps line not found
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
CAPS_LINE="$(grep -m1 '^- Hard caps (lines):' "$ROOT/docs/design/guideline-authoring.md" || true)"
[ -n "$CAPS_LINE" ] || { echo "caps: no 'Hard caps (lines):' line in docs/design/guideline-authoring.md" >&2; exit 2; }

status=0
while read -r file cap; do
  path="$ROOT/guidelines/$file"
  if [ ! -f "$path" ]; then
    echo "caps: $file has a cap but does not exist" >&2; status=1; continue
  fi
  lines=$(wc -l < "$path" | tr -d ' ')
  if [ "$lines" -gt "$cap" ]; then
    echo "over cap: guidelines/$file $lines lines, cap $cap: cut or split" >&2; status=1
  fi
done < <(grep -oE '`[a-z-]+\.md` [0-9]+' <<<"$CAPS_LINE" | tr -d '`')

for path in "$ROOT"/guidelines/*.md; do
  file="$(basename "$path")"
  grep -qF "\`$file\` " <<<"$CAPS_LINE" || { echo "caps: guidelines/$file has no cap" >&2; status=1; }
done

[ "$status" -eq 0 ] && echo "caps: all guidelines under cap"
exit "$status"
