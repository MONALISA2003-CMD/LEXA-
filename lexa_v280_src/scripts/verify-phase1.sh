#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python -m compileall -q apps/api/app
pytest -q
node --test apps/web/tests/visible-product-contract.test.mjs
tsc -p tsconfig.contract.json --noEmit

echo "LEXA Phase 1 production hardening verification: PASS"
