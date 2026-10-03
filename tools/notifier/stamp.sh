#!/usr/bin/env bash
# A hash of the notifier's sources; build.sh records it, install.sh compares it.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cat "$HERE/Notifier.swift" "$HERE/Info.plist" "$HERE/make_icon.swift" "$HERE/build.sh" | shasum -a 256 | cut -d' ' -f1
