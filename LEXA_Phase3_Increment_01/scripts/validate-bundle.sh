#!/usr/bin/env bash
set -euo pipefail
BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash -n "$BUNDLE_DIR/scripts/apply-phase3-increment01.sh"
bash -n "$BUNDLE_DIR/scripts/validate-phase3-increment01.sh"
python -m compileall -q "$BUNDLE_DIR/overrides/apps/api/app/routes/organization.py"
node --test "$BUNDLE_DIR/tests/phase3-workspace-admin-contract.test.mjs"
LEXA_ROOT="$BUNDLE_DIR/fixtures/repo-root" python -m pytest -q "$BUNDLE_DIR/tests/test_phase3_organization_contract.py"
LEXA_ROOT="$BUNDLE_DIR/fixtures/runtime" python -m pytest -q "$BUNDLE_DIR/fixtures/runtime/apps/api/tests/test_phase3_organization_mutations.py"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
cp "$BUNDLE_DIR/fixtures/api-transform/api.before.ts" "$TMP_DIR/api.ts"
python "$BUNDLE_DIR/scripts/extend-api-helpers.py" "$TMP_DIR/api.ts"
cmp "$TMP_DIR/api.ts" "$BUNDLE_DIR/fixtures/api-transform/api.expected.ts"
if python "$BUNDLE_DIR/scripts/extend-api-helpers.py" "$TMP_DIR/api.ts" >/dev/null 2>&1; then
  echo "API helper patcher should reject already-applied overlays." >&2
  exit 4
fi
cmp "$TMP_DIR/api.ts" "$BUNDLE_DIR/fixtures/api-transform/api.expected.ts"

tsc_bin=""
if command -v tsc >/dev/null 2>&1; then
  tsc_bin="$(command -v tsc)"
fi
if [[ -n "$tsc_bin" ]]; then
  (cd "$BUNDLE_DIR/fixtures/typecheck" && "$tsc_bin" -p tsconfig.json --pretty false)
else
  echo "SKIP TypeScript fixture typecheck: tsc is not installed in this environment." >&2
fi

echo "Bundle self-validation passed. It is not a substitute for the pinned repository's Node 24 full suite or isolated-host acceptance."
