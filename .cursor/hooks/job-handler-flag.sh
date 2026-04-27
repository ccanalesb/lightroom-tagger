#!/usr/bin/env bash
# afterFileEdit: when the backend job handlers file is edited, set a flag
# requiring proof of UI trigger + log contract before final submit.
# Also runs a heuristic lint and writes findings to .cursor/.tmp/job-handler-issues.txt.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FLAG_DIR="$ROOT_DIR/.cursor/.tmp"
FLAG_FILE="$FLAG_DIR/job-ui-contract-required"
LINT_FILE="$FLAG_DIR/job-handler-issues.txt"
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

if [[ "$REL_PATH" != "apps/visualizer/backend/jobs/handlers.py" ]]; then
  echo '{}'
  exit 0
fi

touch "$FLAG_FILE"

HANDLERS_FILE="$ROOT_DIR/apps/visualizer/backend/jobs/handlers.py"
if [[ ! -f "$HANDLERS_FILE" ]]; then
  echo '{}'
  exit 0
fi

ISSUES="$(HANDLERS_FILE="$HANDLERS_FILE" ROOT_DIR="$ROOT_DIR" python3 - <<'PY'
import os, re, subprocess
from pathlib import Path

handlers_path = Path(os.environ["HANDLERS_FILE"])
root = Path(os.environ["ROOT_DIR"])
src = handlers_path.read_text(encoding="utf-8")
src_lines = src.splitlines()

# Compute line numbers (1-based) that changed vs HEAD. Hooks fire after edits
# but before commit, so `git diff HEAD` reflects unstaged + staged work.
changed_lines: set[int] = set()
try:
    rel = handlers_path.resolve().relative_to(root.resolve())
    diff = subprocess.run(
        ["git", "-C", str(root), "diff", "HEAD", "--unified=0", "--", str(rel)],
        capture_output=True, text=True, check=False,
    ).stdout
    for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", diff, re.M):
        start = int(m.group(1))
        length = int(m.group(2)) if m.group(2) else 1
        for i in range(start, start + max(length, 1)):
            changed_lines.add(i)
except Exception:
    # If git is unavailable or file not tracked, lint all handlers (safe default).
    changed_lines = set(range(1, len(src_lines) + 2))

def_re = re.compile(r"^def\s+(\w+)\s*\(", re.M)
matches = list(def_re.finditer(src))

def line_of(offset: int) -> int:
    return src.count("\n", 0, offset) + 1

spans = {}
for i, m in enumerate(matches):
    name = m.group(1)
    start = m.start()
    end = matches[i + 1].start() if i + 1 < len(matches) else len(src)
    spans[name] = (start, end, line_of(start), line_of(end - 1))

issues = []
for name, (start, end, ln_start, ln_end) in spans.items():
    if not name.startswith("handle_batch_"):
        continue
    inner_name = "_" + name + "_inner"
    inner_span = spans.get(inner_name)

    # Only report if THIS edit actually touched the wrapper or its inner.
    touched = any(ln_start <= ln <= ln_end for ln in changed_lines)
    if inner_span and not touched:
        i_start, i_end, i_ln_start, i_ln_end = inner_span
        touched = any(i_ln_start <= ln <= i_ln_end for ln in changed_lines)
    if not touched:
        continue

    body = src[start:end]
    if inner_span:
        i_start, i_end, _, _ = inner_span
        body = body + "\n" + src[i_start:i_end]

    findings = []
    has_throttle = (
        "_SUMMARY_EVERY" in body
        or re.search(r"%\s*\d+\s*==\s*0", body) is not None
        or re.search(r"%\s*_[A-Z_]+\s*==\s*0", body) is not None
        or "maybe_log_summary" in body
        or "summary_log_every" in body.lower()
        or "_run_describe_pass" in body
        or "_run_score_pass" in body
    )
    if not has_throttle:
        findings.append("no throttled progress (expected _SUMMARY_EVERY constant or modulo log throttle)")

    if "skipped" not in body.lower() and "skip" not in body.lower():
        findings.append("no bucketed skip counters/messages (expected 'skipped_*' or skip-reason logging)")

    if body.count("add_job_log(") < 2:
        findings.append("fewer than 2 add_job_log() calls; missing start or final-outcome narrative?")

    if findings:
        issues.append(f"- {name}: " + "; ".join(findings))

print("\n".join(issues))
PY
)"

if [[ -n "$ISSUES" ]]; then
  printf '%s\n' "$ISSUES" > "$LINT_FILE"
else
  rm -f "$LINT_FILE"
fi

echo '{}'
