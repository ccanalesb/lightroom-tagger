#!/usr/bin/env bash
# beforeSubmitPrompt: aggregator gate. Blocks (permission: ask) if any of the
# pending validation flags are set. Prints actionable next steps for the agent
# and a concise notice for the user. Replaces ui-validation-enforce.sh.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP_DIR="$ROOT_DIR/.cursor/.tmp"

UI_FLAG="$TMP_DIR/ui-validation-required"
SHARED_FLAG="$TMP_DIR/shared-sweep-required"
JOB_FLAG="$TMP_DIR/job-ui-contract-required"
JOB_LINT="$TMP_DIR/job-handler-issues.txt"
WALK_FLAG="$TMP_DIR/phase-walkthrough-required"

USER_LINES=()
AGENT_LINES=()

if [[ -f "$UI_FLAG" ]]; then
  USER_LINES+=("- UI source files were edited; browser-harness validation required.")
  AGENT_LINES+=("- Run browser-harness across affected pages (and one nearby surface) before final response.")
fi

if [[ -f "$SHARED_FLAG" ]]; then
  STEMS_CSV="$(tr '\n' ',' < "$SHARED_FLAG" | sed 's/,$//')"
  USER_LINES+=("- Shared component(s) edited: ${STEMS_CSV}. DRY callsite sweep required.")
  AGENT_LINES+=("- For each stem above, run \`rg <stem>\` over apps/visualizer/frontend/src. Confirm no consumer duplicates the same derivation; if any do, lift the logic into the shared component before final response.")
fi

if [[ -f "$JOB_FLAG" ]]; then
  EXTRA=""
  if [[ -f "$JOB_LINT" ]]; then
    while IFS= read -r line; do
      [[ -z "$line" ]] && continue
      EXTRA="${EXTRA}\n  ${line}"
    done < "$JOB_LINT"
  fi
  USER_LINES+=("- Backend job handler edited; UI trigger + log contract required.${EXTRA}")
  AGENT_LINES+=("- (1) Ensure a UI trigger exists in apps/visualizer/frontend/src/components/processing/ for any new job_type; (2) verify handler logs at minimum: a start line with input snapshot, throttled progress, bucketed skip counters, and a final outcome line; (3) confirm update_job_status preserves started_at via COALESCE.")
fi

if [[ -f "$WALK_FLAG" ]]; then
  PHASE_PATH="$(head -n1 "$WALK_FLAG")"
  USER_LINES+=("- Phase verification marked passed in ${PHASE_PATH}; user-journey walkthrough screenshot required.")
  AGENT_LINES+=("- Open the most-changed page in browser-harness, perform the user task fresh, capture /tmp/phase-N-walkthrough.png with cdp Page.captureScreenshot, and embed the path in VERIFICATION.md.")
fi

if [[ "${#USER_LINES[@]}" -eq 0 ]]; then
  echo '{ "permission": "allow" }'
  exit 0
fi

USER_BLOCK="$(printf '%s\n' "${USER_LINES[@]}")"
AGENT_BLOCK="$(printf '%s\n' "${AGENT_LINES[@]}")"

USER_BLOCK="$USER_BLOCK" AGENT_BLOCK="$AGENT_BLOCK" python3 - <<'PY'
import json, os
print(json.dumps({
    "permission": "ask",
    "user_message": "Validation gates pending:\n" + os.environ["USER_BLOCK"],
    "agent_message": "Resolve before final response:\n" + os.environ["AGENT_BLOCK"],
}))
PY
