#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== LEXA Phase 1 security + stability verification =="

bash scripts/verify-phase0.sh

echo "[Phase 1] Runtime-role security regression tests"
python -m pytest -q apps/api/tests/test_phase1_runtime_security.py

echo "[Phase 1] Python syntax and shell syntax"
python -m compileall -q apps/api/app apps/api/tests scripts
bash -n scripts/verify-phase1.sh scripts/verify-phase0.sh scripts/apply-deletion-manifest.sh

echo "[Phase 1] Production login-role configuration contract"
grep -q "DATABASE_LOGIN_ROLE" .env.example render.yaml apps/api/app/config.py

echo "[Phase 1] Migration source manifest consistency"
python scripts/check_migration_sources.py

echo "Phase 1 local checks passed. Live role migration and production readiness remain gated on isolated-branch SQL validation and explicit release approval."
