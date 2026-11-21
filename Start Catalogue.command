#!/bin/bash
# Double-click to start Dafina, your design inspiration catalogue. Close this window to stop it.
cd "$(dirname "$0")"
URL=http://localhost:4610

# Already running the current version? Just open it.
NOW=$(stat -f %m server.py)
RUNNING=$(curl -s -f "$URL/api/build" | sed -n 's/.*"build": *"\([0-9]*\)".*/\1/p')
if [ -n "$RUNNING" ] && [ "$RUNNING" = "$NOW" ]; then
  open "$URL"
  echo "Catalogue already running — opened $URL"
  exit 0
fi

# An older version of the catalogue still holding the port? Stop it so the new one can start.
OLD=$(lsof -tiTCP:4610 -sTCP:LISTEN 2>/dev/null)
if [ -n "$OLD" ] && ps -o command= -p $OLD | grep -q "server.py"; then
  echo "Updating: stopping the older catalogue server (pid $OLD)…"
  kill $OLD; sleep 1
fi

python3 server.py --open
