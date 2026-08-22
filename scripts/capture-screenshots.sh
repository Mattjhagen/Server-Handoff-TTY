#!/usr/bin/env bash
set -euo pipefail
browser="${CHROMIUM_BIN:-$(command -v chromium || command -v chromium-browser || true)}"
if [[ -z "$browser" ]]; then
  echo "Chromium not found; set CHROMIUM_BIN" >&2
  exit 1
fi
url="${DASHBOARD_URL:-http://127.0.0.1:8422/}"
out="${1:-artifacts/screenshots}"
mkdir -p "$out"
"$browser" --headless --disable-gpu --hide-scrollbars --window-size=1920,1080 --screenshot="$out/kiosk-1920x1080.png" "$url"
"$browser" --headless --disable-gpu --hide-scrollbars --window-size=1280,800 --screenshot="$out/compact-1280x800.png" "$url"
echo "Screenshots written to $out"
