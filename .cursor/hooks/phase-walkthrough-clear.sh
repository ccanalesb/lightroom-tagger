#!/usr/bin/env bash
# afterShellExecution: clear walkthrough flag when a browser-harness command
# captured a screenshot (Page.captureScreenshot) — evidence of fresh-page
# user-journey validation for the just-passed phase.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FLAG_FILE="$ROOT_DIR/.cursor/.tmp/phase-walkthrough-required"

if [[ ! -f "$FLAG_FILE" ]]; then
  echo '{}'
  exit 0
fi

INPUT="$(cat)"
COMMAND="$(python3 -c 'import json,sys; print((json.load(sys.stdin).get("command") or "").strip())' <<<"$INPUT" || true)"

if [[ "$COMMAND" == *browser-harness* ]] && [[ "$COMMAND" == *captureScreenshot* ]]; then
  rm -f "$FLAG_FILE"
fi

echo '{}'
