#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== LEXA Phase 0 verification =="

if git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "[1/5] Repository whitespace"
  git diff --check -- ":(exclude)docs/LEXA_Unified_Product_Architecture_Implementation_Spec_v1.1.md"
else
  echo "[1/5] Repository whitespace skipped (source package has no .git metadata)"
fi

echo "[2/5] Backend + Phase 0 tests"
python -m pytest -q

echo "[3/5] Frontend static contracts"
node --test apps/web/tests/visible-product-contract.test.mjs

echo "[4/5] Shell syntax"
bash -n scripts/verify-phase0.sh

echo "[5/5] Canonical LEXA configuration"
grep -q "wispy-mud-75323042" apps/api/app/config.py render.yaml .env.example
grep -q "br-soft-star-b1dj2m2w" apps/api/app/config.py render.yaml .env.example
grep -q 'EXPECTED_DATABASE = "neondb"' apps/api/app/health.py

echo "LEXA Phase 0 verification passed."
