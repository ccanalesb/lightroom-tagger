#!/usr/bin/env bash
# afterFileEdit: when a *-VERIFICATION.md is updated to status: passed,
# flag a phase-exit walkthrough screenshot requirement.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FLAG_DIR="$ROOT_DIR/.cursor/.tmp"
FLAG_FILE="$FLAG_DIR/phase-walkthrough-required"
mkdir -p "$FLAG_DIR"

INPUT="$(cat)"

PATH_CANDIDATE="$(
INPUT_JSON="$INPUT" python3 - <<'PY'
import json, os

def maybe_append(paths, v):
    if isinstance(v, str) and v.strip():
        paths.append(v.strip())

try:
    data = json.loads(os.environ.get("INPUT_JSON", ""))
except Exception:
    print("")
    raise SystemExit(0)

paths = []
for k in ("path", "file_path", "target_file", "targetFile"):
    maybe_append(paths, data.get(k))

for container in ("tool_input", "toolInput", "input", "arguments", "args"):
    obj = data.get(container)
    if isinstance(obj, dict):
        for k in ("path", "file_path", "target_file", "targetFile"):
            maybe_append(paths, obj.get(k))

edits = data.get("edits")
if isinstance(edits, list):
    for edit in edits:
        if isinstance(edit, dict):
            for k in ("path", "file_path", "target_file", "targetFile"):
                maybe_append(paths, edit.get(k))

print(paths[0] if paths else "")
PY
)"

if [[ -z "$PATH_CANDIDATE" ]]; then
  echo '{}'
  exit 0
fi

REL_PATH="$PATH_CANDIDATE"
if [[ "$REL_PATH" == "$ROOT_DIR/"* ]]; then
  REL_PATH="${REL_PATH#"$ROOT_DIR/"}"
fi

if ! [[ "$REL_PATH" =~ ^\.planning/.*VERIFICATION\.md$ ]]; then
  echo '{}'
  exit 0
fi

ABS_PATH="$ROOT_DIR/$REL_PATH"
if [[ ! -f "$ABS_PATH" ]]; then
  echo '{}'
  exit 0
fi

# Set the flag if status is passed.
if grep -qE '^[[:space:]]*status:[[:space:]]*passed[[:space:]]*$' "$ABS_PATH"; then
  printf '%s\n' "$REL_PATH" > "$FLAG_FILE"
fi

echo '{}'
