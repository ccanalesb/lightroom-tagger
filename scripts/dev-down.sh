#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"

stop_pid_file() {
  local name="$1"
  local file="$2"

  if [[ ! -f "$file" ]]; then
    echo "$name: no pid file"
    return
  fi

  local pid
  pid="$(cat "$file")"

  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    echo "$name: stopped pid $pid"
  else
    echo "$name: pid $pid is not running"
  fi

  rm -f "$file"
}

stop_pid_file "backend" "$BACKEND_PID_FILE"
stop_pid_file "frontend" "$FRONTEND_PID_FILE"

kill_port_if_busy() {
  local port="$1"
  local label="$2"

  if ! command -v fuser >/dev/null 2>&1; then
    echo "$label: 'fuser' not found; skip port cleanup for $port"
    return
  fi

  if fuser "${port}/tcp" >/dev/null 2>&1; then
    fuser -k "${port}/tcp" >/dev/null 2>&1 || true
    echo "$label: killed process(es) on port $port"
  else
    echo "$label: port $port already free"
  fi
}

kill_port_if_busy 5000 "backend"
kill_port_if_busy 5173 "frontend"

