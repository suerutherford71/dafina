#!/bin/bash
# Dafina installer — https://github.com/suerutherford71/dafina
#
#   curl -fsSL https://raw.githubusercontent.com/suerutherford71/dafina/main/install.sh | bash
#
# Installs Dafina into ~/Dafina (or $DAFINA_DIR), then starts it.
# Running it again updates the app files and never touches your library:
# sources/, catalogue.json and trash/ are always kept.
set -euo pipefail

REPO="suerutherford71/dafina"
BRANCH="main"
DEST="${DAFINA_DIR:-$HOME/Dafina}"
ZIP_URL="https://github.com/$REPO/archive/refs/heads/$BRANCH.zip"

say()  { printf '\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\n\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

[ "$(uname)" = "Darwin" ] || fail "Dafina runs on a Mac (macOS) only."

# 1. Python 3. On a fresh Mac, /usr/bin/python3 is only a stub that asks to
#    install Apple's Command Line Tools, so check for those first.
PY=""
for p in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if command -v "$p" >/dev/null 2>&1 && [ "$(command -v "$p")" != "/usr/bin/python3" ]; then PY="$(command -v "$p")"; break; fi
done
if [ -z "$PY" ]; then
  if xcode-select -p >/dev/null 2>&1; then
    PY=/usr/bin/python3
  else
    say "Dafina needs Python, which comes with Apple's free Command Line Tools."
    say "A window will open: click Install and wait for it to finish (a few minutes)."
    xcode-select --install >/dev/null 2>&1 || true
    fail "When it has finished, paste the install command into Terminal again."
  fi
fi
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' \
  || fail "Dafina needs Python 3.8 or newer ($PY is too old)."

# 2. Download the app (files fetched by curl aren't flagged by macOS Gatekeeper).
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
say "Downloading Dafina…"
curl -fsSL "$ZIP_URL" -o "$TMP/dafina.zip" || fail "Couldn't download $ZIP_URL"
unzip -q "$TMP/dafina.zip" -d "$TMP"
SRC="$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -1)"
[ -f "$SRC/server.py" ] || fail "The download doesn't look like Dafina (no server.py)."

# 3. Copy app files in; keep the user's library if it's already there.
mkdir -p "$DEST"
UPDATING=0; [ -f "$DEST/catalogue.json" ] && UPDATING=1
for item in server.py index.html "Start Catalogue.command" chrome-extension figma-plugin .claude CLAUDE.md README.md LICENCE.txt; do
  [ -e "$SRC/$item" ] || continue
  rm -rf "$DEST/$item"
  cp -R "$SRC/$item" "$DEST/$item"
done
[ -f "$DEST/catalogue.json" ] || echo '{"entries": []}' > "$DEST/catalogue.json"
if [ ! -d "$DEST/sources" ]; then
  # A fresh library starts with the same 17 category folders as the Starter Kit.
  for c in "brand boards" brochures cards clipart "colour palettes" "digital paper" emails images \
           journals logos "mixed media" mockups paintings patterns textures "ui kits" "web design"; do
    mkdir -p "$DEST/sources/$c"
  done
fi
chmod +x "$DEST/Start Catalogue.command" 2>/dev/null || true

if [ "$UPDATING" = 1 ]; then say "Updated Dafina in $DEST (your library was left as it is)."
else say "Installed Dafina in $DEST"; fi

# 4. Start it. Stop an older copy that's still running first.
OLD="$(lsof -tiTCP:4610 -sTCP:LISTEN 2>/dev/null || true)"
if [ -n "$OLD" ] && ps -o command= -p "$OLD" | grep -q "server.py"; then kill "$OLD"; sleep 1; fi

say ""
say "Next time, just double-click “Start Catalogue” in the Dafina folder."
say "Starting Dafina at http://localhost:4610 — keep this window open while you use it."
open "$DEST"
cd "$DEST"
exec "$PY" server.py --open </dev/null
