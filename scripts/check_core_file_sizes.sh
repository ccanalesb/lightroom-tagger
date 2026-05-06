#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
failed=0
while IFS= read -r -d '' file; do
  lines=$(wc -l <"$file" | tr -d ' ')
  if [ "${lines}" -gt 400 ]; then
    echo "FAIL ${lines} ${file}"
    failed=1
  fi
done < <(find lightroom_tagger/core -name '*.py' ! -name 'test_*.py' -print0)
exit "${failed}"
