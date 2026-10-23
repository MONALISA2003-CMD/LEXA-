#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

printf '\n== Python backend and integration tests ==\n'
PYTHONPATH=apps/api pytest -q
printf '\n== Frontend contract and report export tests ==\n'
(cd apps/web && node --test tests/*.test.mjs)
printf '\n== Python source compilation ==\n'
python -m compileall -q apps/api/app
printf 'Python compilation passed.\n'
printf '\n== Stage 1 migration recovery manifest consistency ==\n'
python scripts/check_migration_recovery_manifest.py

printf '\n== Stage 1 migration source reconciliation (semantic replay remains separate) ==\n'
python scripts/check_migration_sources.py --strict

printf '\n== Stage 1–5 frontend action and destination audit ==\n'
node scripts/audit_frontend_actions.mjs

printf '\n== Migration manifest / hash validation (plan only) ==\n'
python scripts/run_clean_migration_replay.py --plan-only

printf '\n== Node version and production frontend checks ==\n'
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
if [[ "$NODE_MAJOR" == "24" ]]; then
  (cd apps/web && npm ci && npm run typecheck && npm run build)
else
  echo "BLOCKED: full typecheck/build requires Node 24.x; found $(node -v)."
  if [[ "${LEXA_REQUIRE_FULL_ACCEPTANCE:-0}" == "1" ]]; then exit 2; fi
fi

printf '\n== Clean disposable PostgreSQL replay ==\n'
if [[ "${LEXA_ALLOW_DISPOSABLE_REPLAY:-0}" == "1" ]]; then
  python scripts/run_clean_migration_replay.py --apply
  EXPECTED_SOURCE="${GITHUB_SHA:-${LEXA_SOURCE_COMMIT:-}}"
  if [[ -n "$EXPECTED_SOURCE" ]]; then
    python scripts/check_phase6_replay_evidence.py --evidence artifacts/phase6-replay-evidence.json --expected-commit "$EXPECTED_SOURCE"
  else
    echo "BLOCKED: replay evidence is not tied to an immutable source commit; set GITHUB_SHA or LEXA_SOURCE_COMMIT."
    if [[ "${LEXA_REQUIRE_FULL_ACCEPTANCE:-0}" == "1" ]]; then exit 2; fi
  fi
else
  echo "NOT RUN: set LEXA_ALLOW_DISPOSABLE_REPLAY=1 and a guarded loopback DATABASE_URL for a disposable empty test database. Neon and production hosts are rejected."
  if [[ "${LEXA_REQUIRE_FULL_ACCEPTANCE:-0}" == "1" ]]; then exit 2; fi
fi

printf '\n== Authenticated read-only browser acceptance ==\n'
if [[ -n "${LEXA_PHASE8_STORAGE_STATE:-}" && -n "${LEXA_BROWSER_BASE_URL:-}" && "${LEXA_PHASE8_ALLOW_STAGING_READS:-0}" == "1" ]]; then
  (cd apps/web && npx playwright test --config=playwright.config.ts e2e/phase8-reports-acceptance.spec.ts)
else
  echo "NOT RUN: requires Node 24 dependencies, an authenticated QA storage state, and explicit staging read-only opt-in."
  if [[ "${LEXA_REQUIRE_FULL_ACCEPTANCE:-0}" == "1" ]]; then exit 2; fi
fi

printf '\n== Authenticated sales journey acceptance (staging writes only) ==\n'
if [[ "${LEXA_PHASE5_ALLOW_STAGING_WRITES:-0}" == "1" && -n "${LEXA_PHASE5_ACCEPTANCE_FIXTURE_JSON:-}" && -n "${LEXA_PHASE5_STORAGE_STATE:-${LEXA_PHASE4_STORAGE_STATE:-}}" && -n "${LEXA_BROWSER_BASE_URL:-}" ]]; then
  (cd apps/web && npx playwright test --config=playwright.config.ts e2e/phase5-sales-acceptance.spec.ts)
else
  echo "NOT RUN: requires a disposable staging fixture, authenticated QA state, allow-listed host, Node 24 dependencies and LEXA_PHASE5_ALLOW_STAGING_WRITES=1."
  if [[ "${LEXA_REQUIRE_FULL_ACCEPTANCE:-0}" == "1" ]]; then exit 2; fi
fi

printf '\n== Authenticated purchasing journey acceptance (staging writes only) ==\n'
if [[ "${LEXA_PHASE7_ALLOW_STAGING_WRITES:-0}" == "1" && -n "${LEXA_PHASE7_ACCEPTANCE_FIXTURE_JSON:-}" && -n "${LEXA_PHASE7_STORAGE_STATE:-${LEXA_PHASE5_STORAGE_STATE:-${LEXA_PHASE4_STORAGE_STATE:-}}}" && -n "${LEXA_BROWSER_BASE_URL:-}" ]]; then
  (cd apps/web && npx playwright test --config=playwright.config.ts e2e/phase7-purchasing-acceptance.spec.ts)
else
  echo "NOT RUN: requires a disposable staging fixture, authenticated QA state, allow-listed host, Node 24 dependencies and LEXA_PHASE7_ALLOW_STAGING_WRITES=1."
  if [[ "${LEXA_REQUIRE_FULL_ACCEPTANCE:-0}" == "1" ]]; then exit 2; fi
fi

printf '\nCandidate checks completed. Currency safety and journal posting contracts are included; see the Phase 3–5 report for every check marked blocked or not run.\n'
