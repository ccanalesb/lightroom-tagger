#!/usr/bin/env bash
# Reproduce the contract drift gate locally (see .sandcastle/ci-drift-gate.yml).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> 1/5 Regenerate frontend types and check for drift"
cd "$ROOT/frontend"
npm run generate:api
git diff --exit-code src/types/api.gen.ts

echo "==> 2/5 Typecheck frontend"
npx tsc --noEmit

echo "==> 3/5 Frontend tests"
npx vitest run

echo "==> 4/5 Typecheck backend"
cd "$ROOT/backend-ts"
npm run typecheck

echo "==> 5/5 Backend tests"
npm test

echo "Contract gate: OK"
