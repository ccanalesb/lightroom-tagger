#!/usr/bin/env bash
# Reproduce the contract drift gate locally (see .sandcastle/ci-drift-gate.yml).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT/../.." && pwd)"
PYTHON="${PYTHON:-$REPO_ROOT/.venv/bin/python}"

echo "==> 1/3 Regenerate frontend types and check for drift"
cd "$ROOT/frontend"
npm run generate:api
git diff --exit-code src/types/api.gen.ts

echo "==> 2/3 Typecheck frontend"
npx tsc --noEmit

echo "==> 3/3 Backend pytest (spectree validates Jobs responses)"
cd "$ROOT/backend"
"$PYTHON" -m pytest tests/ --ignore=tests/e2e -q

echo "Contract gate: OK"
