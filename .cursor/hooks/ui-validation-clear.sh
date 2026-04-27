#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FLAG_FILE="$ROOT_DIR/.cursor/.tmp/ui-validation-required"

INPUT="$(cat)"
COMMAND="$(python3 -c 'import json,sys; print((json.load(sys.stdin).get("command") or "").strip())' <<<"$INPUT" || true)"

if [[ "$COMMAND" == *browser-harness* ]]; then
  rm -f "$FLAG_FILE"
fi

echo '{}'
