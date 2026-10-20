#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "Run this from inside a LEXA Git checkout." >&2; exit 2; }
cd "$REPO_ROOT"

EXPECTED_HEAD="f48e201fc8c4ed0a9ff1551c0b99451a7eb500dd"
ACTUAL_HEAD="$(git rev-parse HEAD)"
if [[ "$ACTUAL_HEAD" != "$EXPECTED_HEAD" ]]; then
  echo "Refusing to apply: expected base $EXPECTED_HEAD, found $ACTUAL_HEAD." >&2
  echo "Rebase/review this increment against the current LEXA head first." >&2
  exit 3
fi
if [[ -n "$(git status --porcelain --untracked-files=normal)" ]]; then
  echo "Refusing to apply over a dirty worktree (including untracked files). Use a clean worktree." >&2
  exit 4
fi

verify_blob() {
  local path="$1" expected="$2" actual
  actual="$(git hash-object "$path")"
  if [[ "$actual" != "$expected" ]]; then
    echo "Refusing to apply: $path changed (expected blob $expected, found $actual)." >&2
    exit 5
  fi
}
verify_blob "apps/api/app/routes/organization.py" "5150e386c1aed49daf46ed0f63264ee36eea04d9"
verify_blob "apps/web/lib/api.ts" "d62b1f64fc78bc333c1017a6bcda2690b8f3cb23"
verify_blob "apps/web/app/administration/page.tsx" "8ef73f5db57131b9e2f5783583157dc43c3462cc"

python "$BUNDLE_DIR/scripts/extend-api-helpers.py" "$REPO_ROOT/apps/web/lib/api.ts"

cp "$BUNDLE_DIR/overrides/apps/api/app/routes/organization.py" "apps/api/app/routes/organization.py"
cp "$BUNDLE_DIR/overrides/apps/web/app/administration/page.tsx" "apps/web/app/administration/page.tsx"
cp "$BUNDLE_DIR/tests/test_phase3_organization_contract.py" "apps/api/tests/test_phase3_organization_contract.py"
cp "$BUNDLE_DIR/tests/test_phase3_organization_mutations.py" "apps/api/tests/test_phase3_organization_mutations.py"
cp "$BUNDLE_DIR/tests/phase3-workspace-admin-contract.test.mjs" "apps/web/tests/phase3-workspace-admin-contract.test.mjs"

echo "Phase 3 Increment 01 source overlay applied. No migrations were run and no deployment was triggered."
echo "Review the diff, run the full root/API/web suites under Node 24, and use an isolated database branch for integration tests."
