#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "Run this from inside the LEXA Git checkout." >&2; exit 2; }
cd "$REPO_ROOT"

python - <<'PYVER'
import sys
if sys.version_info < (3, 12):
    raise SystemExit(f"Phase 3 validation requires Python 3.12+; found {sys.version.split()[0]}")
PYVER

NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
if [[ "$NODE_MAJOR" != "24" ]]; then
  echo "Phase 3 validation requires Node 24.x; found $(node --version)." >&2
  exit 3
fi

python -m pip install -e "apps/api[dev]"
python -m compileall -q apps/api/app apps/api/tests scripts
python -m pytest -q tests apps/api/tests

(
  cd apps/web
  npm ci
  npm run typecheck
  npm test
  npm run build
)

printf '\nLocal validation passed. This does not replace isolated-Postgres/RLS, credentialed browser, SHA-parity, or release-gate evidence.\n'
