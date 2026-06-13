#!/usr/bin/env bash
# Refresh the vendored @openuidev/browser-bundle. Maintainer chore — NOT part of
# the app build or dev loop. Pins an exact version and records SHA-256.
set -euo pipefail
VER="${1:?usage: vendor_openui.sh <exact-version>}"
DEST="$(cd "$(dirname "$0")/.." && pwd)/static/vendor/openui"
mkdir -p "$DEST"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cd "$TMP"
npm pack "@openuidev/browser-bundle@${VER}" >/dev/null
tar -xzf openuidev-browser-bundle-*.tgz
cp package/dist/openui-bundle.min.js "$DEST/openui-bundle.min.js"
cp package/dist/openui-styles.css    "$DEST/openui-styles.css"
{
  echo "# Vendored @openuidev/browser-bundle"
  echo
  echo "- version: ${VER}"
  echo "- source: npm pack @openuidev/browser-bundle@${VER}"
  echo "- retrieved: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "- public API: window.__OpenUI = { React, createRoot, Renderer, openuiChatLibrary } (stable contract)"
  echo
  echo '## SHA-256'
  ( cd "$DEST" && sha256sum openui-bundle.min.js openui-styles.css )
} > "$DEST/VENDOR.md"
echo "Vendored ${VER}. Review VENDOR.md and the diff before committing."
