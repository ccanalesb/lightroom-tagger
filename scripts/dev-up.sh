#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/apps/visualizer/backend"
FRONTEND_DIR="$ROOT_DIR/apps/visualizer/frontend"
RUN_DIR="$ROOT_DIR/.run"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"

BACKEND_PORT=5001
if [[ -f "$BACKEND_DIR/.env" ]]; then
  _port="$(grep -E '^FLASK_PORT=' "$BACKEND_DIR/.env" | cut -d= -f2 | tr -d '[:space:]')"
  [[ -n "$_port" ]] && BACKEND_PORT="$_port"
fi

if [[ ! -d "$BACKEND_DIR" || ! -d "$FRONTEND_DIR" ]]; then
  echo "Expected apps/visualizer/backend/ and apps/visualizer/frontend/ under: $ROOT_DIR"
  exit 1
fi

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  rm -f "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE"
}

trap cleanup EXIT INT TERM

mkdir -p "$RUN_DIR"

if [[ ! -x "$FRONTEND_DIR/node_modules/.bin/vite" ]]; then
  echo "Frontend dependencies missing; installing..."
  (
    cd "$FRONTEND_DIR"
    npm install --legacy-peer-deps
  )
fi

PYTHON_BIN="python3"
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
fi

if ! "$PYTHON_BIN" - "$BACKEND_PORT" <<'PY'
import socket, sys
s = socket.socket()
try:
    s.bind(("127.0.0.1", int(sys.argv[1])))
except OSError:
    raise SystemExit(1)
finally:
    s.close()
PY
then
  echo "Port $BACKEND_PORT is already in use."
  echo "Run 'make dev-down' first, or stop the process using that port."
  echo "Tip: 'fuser -k ${BACKEND_PORT}/tcp' (Linux/WSL) can free it quickly."
  exit 1
fi

if ! "$PYTHON_BIN" - <<'PY'
import socket
s = socket.socket()
try:
    s.bind(("127.0.0.1", 5173))
except OSError:
    raise SystemExit(1)
finally:
    s.close()
PY
then
  echo "Port 5173 is already in use."
  echo "Run 'make dev-down' first, or stop the process using that port."
  echo "Tip: 'fuser -k 5173/tcp' (Linux/WSL) can free it quickly."
  exit 1
fi

echo "Starting backend on http://127.0.0.1:$BACKEND_PORT ..."
(
  cd "$BACKEND_DIR"
  exec env PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}" "$PYTHON_BIN" app.py
) &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$BACKEND_PID_FILE"

echo "Starting frontend on http://localhost:5173 ..."
(
  cd "$FRONTEND_DIR"
  exec "$FRONTEND_DIR/node_modules/.bin/vite"
) &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$FRONTEND_PID_FILE"

echo
echo "Both services started. Press Ctrl+C to stop both."
echo

wait "$BACKEND_PID" "$FRONTEND_PID"
