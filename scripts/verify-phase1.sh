#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python -m compileall -q apps/api/app
pytest -q tests/unit/test_phase0_readiness_contract.py tests/unit/test_phase1_business_kernel_contract.py
node --test apps/web/tests/visible-product-contract.test.mjs

echo "LEXA Phase 1 source verification: PASS"
