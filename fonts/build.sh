#!/usr/bin/env bash
# Read fonts/manifest.json, download each entry's files from
# github.com/google/fonts into $1 (target directory). Then copy any
# user-provided fonts from fonts/custom/ alongside. Runs during docker build
# so the final image has every font pre-baked — no runtime network calls,
# no Google Fonts CDN dependency.
set -euo pipefail

TARGET="${1:-/usr/share/fonts/cutstorm}"
HERE="$(cd "$(dirname "$0")" && pwd)"
MANIFEST="$HERE/manifest.json"
CUSTOM_DIR="$HERE/custom"

mkdir -p "$TARGET"

python3 - "$MANIFEST" "$TARGET" <<'PY'
import json
import os
import sys
import urllib.parse
import urllib.request

manifest_path, target = sys.argv[1], sys.argv[2]
with open(manifest_path) as f:
    manifest = json.load(f)

base = "https://raw.githubusercontent.com/google/fonts/main"
count = 0
for font in manifest.get("fonts", []):
    slug = font["slug"]
    license_dir = font.get("license_dir", "ofl")
    for file in font.get("files", []):
        url = f"{base}/{license_dir}/{slug}/{urllib.parse.quote(file)}"
        dst = os.path.join(target, file)
        print(f"[fonts] {font['family']:<20} <- {license_dir}/{slug}/{file}")
        urllib.request.urlretrieve(url, dst)
        count += 1
print(f"[fonts] downloaded {count} file(s) into {target}")
PY

# User-provided fonts (optional). Supports ttf, otf, woff, woff2.
if [ -d "$CUSTOM_DIR" ]; then
    shopt -s nullglob
    custom_count=0
    for f in "$CUSTOM_DIR"/*.ttf "$CUSTOM_DIR"/*.otf "$CUSTOM_DIR"/*.woff "$CUSTOM_DIR"/*.woff2; do
        cp -v "$f" "$TARGET/"
        custom_count=$((custom_count + 1))
    done
    shopt -u nullglob
    if [ "$custom_count" -gt 0 ]; then
        echo "[fonts] copied $custom_count custom font(s) from $CUSTOM_DIR"
    fi
fi

# Refresh fontconfig so Chromium and ffmpeg see the new fonts.
if command -v fc-cache >/dev/null 2>&1; then
    fc-cache -fv "$TARGET" >/dev/null 2>&1 || true
    echo "[fonts] fc-cache refreshed"
fi
