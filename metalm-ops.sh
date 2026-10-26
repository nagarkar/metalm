#!/bin/bash
# Launcher for unattended runs (launchd): pins the checkout's venv without activating it.
# Interactive use: .venv/bin/metalm-ops <verb>.
cd "$(dirname "$0")" || exit 1
PYTHONPATH=src exec .venv/bin/python -m metalm_ops.cli "$@"
