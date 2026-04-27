#!/usr/bin/env bash
set -euo pipefail

INPUT="$(cat)"
COMMAND="$(python3 -c 'import json,sys; print((json.load(sys.stdin).get("command") or "").strip())' <<<"$INPUT")"

# Allow dependency/package maintenance commands that merely reference playwright.
if [[ "$COMMAND" =~ (^|[[:space:]])(npm|pnpm|yarn|bun)[[:space:]]+(i|install|add|remove|uninstall|up|update|list)([[:space:]]|$) ]]; then
  echo '{ "permission": "allow" }'
  exit 0
fi

if [[ "$COMMAND" == *playwright* ]]; then
  echo '{
    "permission": "deny",
    "user_message": "Use browser-harness for UI validation in this repo. Playwright shell commands are blocked by project policy.",
    "agent_message": "Blocked Playwright command. Re-run the validation with browser-harness."
  }'
  exit 0
fi

echo '{ "permission": "allow" }'
