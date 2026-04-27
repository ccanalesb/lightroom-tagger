#!/usr/bin/env bash
# afterFileEdit: when a SHARED frontend component is edited, set a flag
# requiring a callsite sweep before final submit. Catches DRY violations
# where consumers duplicate logic that should be lifted into the shared site.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FLAG_DIR="$ROOT_DIR/.cursor/.tmp"
FLAG_FILE="$FLAG_DIR/shared-sweep-required"
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

# Skip test files; they're not the shared site, only consumers of it.
if [[ "$REL_PATH" =~ (__tests__/|\.test\.|\.spec\.) ]]; then
  echo '{}'
  exit 0
fi

# Shared sites whose edit forces a sweep of all consumers.
SHARED_PATTERNS=(
  '^apps/visualizer/frontend/src/components/image-view/(ImageTile|adapters|ImageMetadataBadges|imageTileVariants|formatImageDate|index|PrimaryScorePill|ModalCloseButton)\.(tsx|ts)$'
  '^apps/visualizer/frontend/src/components/ui/[^/]+\.(tsx|ts)$'
  '^apps/visualizer/frontend/src/components/ui/[^/]+/[^/]+\.(tsx|ts)$'
  '^apps/visualizer/frontend/src/services/api\.ts$'
  '^apps/visualizer/frontend/src/data/useQuery\.ts$'
  '^apps/visualizer/frontend/src/data/index\.ts$'
)

MATCHED=0
for pat in "${SHARED_PATTERNS[@]}"; do
  if [[ "$REL_PATH" =~ $pat ]]; then
    MATCHED=1
    break
  fi
done

if [[ "$MATCHED" -eq 1 ]]; then
  BASENAME="$(basename "$REL_PATH")"
  STEM="${BASENAME%.*}"
  if [[ -f "$FLAG_FILE" ]]; then
    if ! grep -Fx -- "$STEM" "$FLAG_FILE" >/dev/null 2>&1; then
      printf '%s\n' "$STEM" >> "$FLAG_FILE"
    fi
  else
    printf '%s\n' "$STEM" > "$FLAG_FILE"
  fi
fi

echo '{}'
