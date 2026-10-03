#!/usr/bin/env bash
# Builds "SuperLM Notifier.app" into tools/notifier/build/ (git-ignored) from the
# sources beside this script: draws the icon, makes the .icns, compiles, signs ad
# hoc. install.sh runs it, and only when a source changed (build/.stamp holds a
# hash of them). Needs the Xcode command line tools: swiftc, iconutil, sips, codesign.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
OUT="$HERE/build"
APP="$OUT/SuperLM Notifier.app"
rm -rf "$OUT"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$OUT/AppIcon.iconset"
swift "$HERE/make_icon.swift" "$OUT/icon.png"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$OUT/icon.png" --out "$OUT/AppIcon.iconset/icon_${size}x${size}.png" >/dev/null
  sips -z $((size * 2)) $((size * 2)) "$OUT/icon.png" --out "$OUT/AppIcon.iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$OUT/AppIcon.iconset" -o "$APP/Contents/Resources/AppIcon.icns"
cp "$HERE/Info.plist" "$APP/Contents/Info.plist"
swiftc -O "$HERE/Notifier.swift" -o "$APP/Contents/MacOS/superlm-notifier"
codesign --force --sign - "$APP" >/dev/null 2>&1
"$HERE/stamp.sh" > "$OUT/.stamp"
echo "built: $APP"
