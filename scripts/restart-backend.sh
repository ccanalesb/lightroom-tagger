#!/usr/bin/env bash
set -euo pipefail

# Safe backend restart — kills ONLY the backend listener, never the frontend.

PIDS=()
while IFS= read -r pid; do
  [[ -n "$pid" ]] && PIDS+=("$pid")
done < <(lsof -ti :5001 -sTCP:LISTEN 2>/dev/null || true)

if [[ "${#PIDS[@]}" -gt 0 ]]; then
  for pid in "${PIDS[@]}"; do
    kill "$pid"
    echo "Killed backend (pid $pid)"
  done
  sleep 2
else
  echo "No backend listener found on :5001"
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/apps/visualizer/backend"

PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
exec "$PYTHON_BIN" app.py
