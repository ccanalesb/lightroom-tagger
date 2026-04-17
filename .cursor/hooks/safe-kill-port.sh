#!/usr/bin/env bash
# Hook: prevent blind "kill everything on port X" commands that nuke the frontend.
# Instead, rewrite to only kill the TCP LISTEN holder (the actual server), or
# block and suggest using scripts/restart-backend.sh.

set -euo pipefail

input=$(cat)
command=$(echo "$input" | jq -r '.command // empty')

# Only care about commands that kill processes on port 5001
if echo "$command" | grep -qE 'lsof.*:5001.*kill|kill.*(5001|lsof.*:5001)|pkill.*app\.py'; then
  # Block if the command does a raw "lsof -ti :5001 | xargs kill" without -sTCP:LISTEN
  if echo "$command" | grep -qE 'lsof -ti\s+:5001' && ! echo "$command" | grep -q 'sTCP:LISTEN'; then
    echo '{
      "permission": "deny",
      "user_message": "Blocked: this kill command would also nuke the frontend dev server (Vite proxies to :5001). Use scripts/restart-backend.sh or add -sTCP:LISTEN to only kill the backend.",
      "agent_message": "STOP. Your kill command targets ALL processes with connections on port 5001, including the Vite frontend. Use: lsof -ti :5001 -sTCP:LISTEN | xargs kill -9   OR   bash scripts/restart-backend.sh"
    }'
    exit 0
  fi
fi

echo '{ "permission": "allow" }'
exit 0
