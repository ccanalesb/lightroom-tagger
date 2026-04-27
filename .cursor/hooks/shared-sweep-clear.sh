#!/usr/bin/env bash
# afterShellExecution: clear shared-sweep flag entries whose stems appear
# in an rg/grep/git-grep command (evidence of a DRY callsite sweep).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FLAG_FILE="$ROOT_DIR/.cursor/.tmp/shared-sweep-required"

if [[ ! -f "$FLAG_FILE" ]]; then
  echo '{}'
  exit 0
fi

INPUT="$(cat)"
COMMAND="$(python3 -c 'import json,sys; print((json.load(sys.stdin).get("command") or "").strip())' <<<"$INPUT" || true)"

# Recognize sweep-style commands.
if ! [[ "$COMMAND" =~ (^|[[:space:]])(rg|grep|ripgrep|ag)([[:space:]]|$) ]] \
   && ! [[ "$COMMAND" =~ git[[:space:]]+grep ]]; then
  echo '{}'
  exit 0
fi

TMP_FILE="$(mktemp)"
while IFS= read -r STEM; do
  [[ -z "$STEM" ]] && continue
  if [[ "$COMMAND" == *"$STEM"* ]]; then
    continue
  fi
  printf '%s\n' "$STEM" >> "$TMP_FILE"
done < "$FLAG_FILE"

if [[ -s "$TMP_FILE" ]]; then
  mv "$TMP_FILE" "$FLAG_FILE"
else
  rm -f "$FLAG_FILE" "$TMP_FILE"
fi

echo '{}'
