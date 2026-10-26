#!/bin/bash
# Throwaway dashboard on a spare port (operations.md#sandbox-script): copies ops.toml and the last
# status.json into a fresh temp folder, points state_dir there, and serves until Ctrl-C.
# Usage: scripts/sandbox_server.sh <port>   (a spare port; the real port in ops.toml is declined)
cd "$(dirname "$0")/.." || exit 1
PORT="$1"
if [ -z "$PORT" ]; then echo "error: no port. Pass a spare one: scripts/sandbox_server.sh <port>" >&2; exit 1; fi
REAL_CFG="$HOME/.claude/metalm/ops.toml"
REAL_PORT=$(sed -n 's/^port *= *\([0-9]*\).*/\1/p' "$REAL_CFG" | head -1)
if [ "$PORT" = "$REAL_PORT" ]; then echo "error: $PORT is the real dashboard's port. Pick a spare one: scripts/sandbox_server.sh <port>" >&2; exit 1; fi
SANDBOX=$(mktemp -d "${TMPDIR:-/tmp}/metalm-ops-sandbox.XXXXXX")
REAL_STATE="$HOME/.local/state/metalm/ops"
grep -v '^state_dir' "$REAL_CFG" | sed "1i\\
state_dir = \"$SANDBOX/state\"
" > "$SANDBOX/ops.toml"
mkdir -p "$SANDBOX/state"
[ -f "$REAL_STATE/status.json" ] && cp "$REAL_STATE/status.json" "$SANDBOX/state/"
[ -f "$REAL_STATE/runs.jsonl" ] && cp "$REAL_STATE/runs.jsonl" "$SANDBOX/state/"
echo "sandbox: http://127.0.0.1:$PORT/ (state in $SANDBOX)"
PYTHONPATH=src exec .venv/bin/python -m metalm_ops.cli serve --port "$PORT" --config "$SANDBOX/ops.toml"
