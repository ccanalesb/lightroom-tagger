#!/usr/bin/env bash
# afterFileEdit: clear job-ui-contract flag when a Processing-tab UI surface
# is edited (evidence that a UI trigger / view exists for the new job_type).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FLAG_FILE="$ROOT_DIR/.cursor/.tmp/job-ui-contract-required"
LINT_FILE="$ROOT_DIR/.cursor/.tmp/job-handler-issues.txt"

if [[ ! -f "$FLAG_FILE" ]]; then
  echo '{}'
  exit 0
fi

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

if [[ "$REL_PATH" =~ (__tests__/|\.test\.|\.spec\.) ]]; then
  echo '{}'
  exit 0
fi

# Trigger surfaces: any Processing-tab tsx/ts (non-test) qualifies as evidence.
if [[ "$REL_PATH" =~ ^apps/visualizer/frontend/src/components/processing/.*\.(tsx|ts)$ ]] \
   || [[ "$REL_PATH" =~ ^apps/visualizer/frontend/src/pages/ProcessingPage\.tsx$ ]]; then
  rm -f "$FLAG_FILE" "$LINT_FILE"
fi

echo '{}'
