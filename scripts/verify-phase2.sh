#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python -m compileall -q apps/api/app
pytest -q
node --test apps/web/tests/visible-product-contract.test.mjs
tsc -p apps/web/tsconfig.json --noEmit
tsc -p tsconfig.contract.json --noEmit
echo "LEXA Phase 2 identity, tenancy and authorization verification: PASS"
