#!/bin/bash
# Regenerate background.png for the DMG install window from background.html.
# Requires Google Chrome (headless screenshot) and sips; run from anywhere.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [ ! -x "$CHROME" ]; then
    printf 'Google Chrome is required to render the DMG background.\n' >&2
    exit 1
fi

# The dialog mockup embeds the real app icon.
sips -s format png --resampleWidth 64 "$ROOT/apps/toccata-studio/Resources/AppIcon.icns" \
    --out "$HERE/appicon.png" >/dev/null
trap 'rm -f "$HERE/appicon.png"' EXIT

"$CHROME" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
    --force-device-scale-factor=2 --window-size=960,740 --virtual-time-budget=3000 \
    --screenshot="$HERE/background.png" "file://$HERE/background.html" >/dev/null 2>&1
# 2x pixels at 144 dpi so Finder lays it out as 960x740 points, retina-sharp.
sips -s dpiWidth 144 -s dpiHeight 144 "$HERE/background.png" >/dev/null
printf 'Rendered: %s\n' "$HERE/background.png"