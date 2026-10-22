#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== LEXA Phase 0 verification =="

if git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "[1/6] Repository whitespace"
  git diff --check -- ":(exclude)docs/LEXA_Unified_Product_Architecture_Implementation_Spec_v1.1.md"
else
  echo "[1/6] Repository whitespace skipped (source package has no .git metadata)"
fi

echo "[2/6] Backend + Phase 0 tests"
python -m pytest -q tests apps/api/tests

echo "[3/6] Frontend static contracts"
node --test apps/web/tests/*.test.mjs

echo "[4/6] Shell and Python utility syntax"
bash -n scripts/verify-phase0.sh scripts/apply-deletion-manifest.sh
python -m py_compile scripts/check_migration_sources.py scripts/smoke_phase0.py

echo "[5/6] Migration source reconciliation (documented gaps remain release blockers in strict mode)"
python scripts/check_migration_sources.py

echo "[6/6] Canonical LEXA configuration"
grep -q "wispy-mud-75323042" apps/api/app/config.py render.yaml .env.example
grep -q "br-soft-star-b1dj2m2w" apps/api/app/config.py render.yaml .env.example
grep -q 'EXPECTED_DATABASE = "neondb"' apps/api/app/health.py

echo "Local Phase 0 source checks passed. Full Phase 0 acceptance remains BLOCKED until exact historical migration sources are recovered, strict replay passes, Render health-check settings are reconciled, and hosted auth E2E passes."
