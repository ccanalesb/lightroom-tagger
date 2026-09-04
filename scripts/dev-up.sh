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

if [[ ! -x "$BACKEND_DIR/node_modules/.bin/tsx" ]]; then
  echo "Backend dependencies missing; installing..."
  (
    cd "$BACKEND_DIR"
    npm install
  )
fi

# Wait until a port is bindable, retrying briefly. A just-stopped server can
# linger in TIME_WAIT (or a racing `make dev-down` may still be tearing down),
# so poll for ~5s instead of failing on the first conflict. Only give up — and
# print the manual-recovery hint — once the port stays busy the whole window.
wait_for_port_free() {
  local port="$1"
  local attempt

  for attempt in {1..20}; do
    if node -e '
const net = require("node:net");
const s = net.createServer();
s.once("error", () => process.exit(1));
s.listen(Number(process.argv[1]), "127.0.0.1", () => s.close(() => process.exit(0)));
' "$port"
    then
      if [[ "$attempt" -gt 1 ]]; then
        echo "Port $port is now free."
      fi
      return 0
    fi
    sleep 0.25
  done

  echo "Port $port is already in use."
  echo "Run 'make dev-down' first, or stop the process using that port."
  echo "Tip: 'fuser -k ${port}/tcp' (Linux/WSL) can free it quickly."
  return 1
}

wait_for_port_free "$BACKEND_PORT" || exit 1
wait_for_port_free 5173 || exit 1

echo "Starting backend on http://127.0.0.1:$BACKEND_PORT ..."
(
  cd "$BACKEND_DIR"
  # `node --env-file-if-exists` rather than a dotenv dependency; see src/config.ts.
  exec node --env-file-if-exists=.env --import tsx src/server.ts
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
