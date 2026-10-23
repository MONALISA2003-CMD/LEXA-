#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHONPATH=apps/api python -m pytest -q
python -m compileall -q apps/api/app scripts tests
node --test apps/web/tests/*.test.mjs tests/phase3-increments-02-03.test.mjs
if command -v tsc >/dev/null 2>&1; then
  (cd fixtures/typecheck && tsc --noEmit -p tsconfig.json)
else
  echo "SKIPPED: TypeScript contract fixture check (tsc is not installed)." >&2
fi
