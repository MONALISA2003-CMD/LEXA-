# LEXA 2.12.0 — Phase 7 Increment 03: backend payment validation and release audit

**Date:** 22 October 2026  
**Status:** Source-only repair candidate; NOT accepted for production.  
**Baseline commit inspected:** `b920c8719079741ed3c2fb2288de67c7de8a0d37`.

## Fix included

Render logs repeatedly showed a Pydantic warning that `SupplierPaymentCreate.validate_allocations` overrides an earlier `@model_validator`. Inspection found two methods with the same name. The surviving method called `validate_payment_allocations` without importing it, so supplier payment validation could raise a runtime `NameError` rather than consistently rejecting unsafe allocation requests. Increment 03 imports the shared pure-rule helper, retains one model validator, and exercises the class definition in regression tests.

## Local verification

- Backend: 211 passed; 1 skipped because the local offline environment lacks the Redis Python package. The Redis-dependent auth-refresh integration test must run in connected CI without a skip.
- Frontend contracts: 38 passed.
- Frontend action/destination audit: passed (29 files; 153 controls, 35 forms, 33 links).
- Python compilation: passed.
- Strict migration source reconciliation: passed for approved source dispositions; historical byte parity is not claimed.
- 43-input migration plan: passed, SHA-256 `2d446ba3c0df5903b06ed0dbb92e1c2239f353aa69cc40e80d452ecb78ec1674`.
- Separately, the ordered migration SQL inputs were executed against isolated disposable Neon database `LEXA-PHASE7-REPLAY-20261022 / lexa_replay_ci`; schema/security assertions passed and `scripts/check_phase6_replay_evidence.py --expected-commit b920c8719079741ed3c2fb2288de67c7de8a0d37` now passes against a checksummed artifact. This was manually collected remote evidence, not a GitHub Actions run or Actions artifact.

## Live-platform findings

- Vercel deployment `dpl_EAd6M7k5R4KZGhKjd91XjgKjnzYV` is `READY` for the baseline SHA `b920c8719079741ed3c2fb2288de67c7de8a0d37`; its build completed TypeScript and generated 21 static pages. This build does not include the new Increment 03 API fix.
- Render LEXA deployment `dep-dbchjh0473hc73ahsm40` is still live on older SHA `dd4069109d5c94143f5c5e28e758128b90dee55a`. The `healthCheckPath` setting is blank although `render.yaml` specifies `/ready`; logs show the readiness endpoint responding 200, but the config drift must be corrected through the Render dashboard/Blueprint sync.
- Current GitHub `main` does not contain `.github/workflows/lexa-ci.yml`, and no workflow run is associated with SHA `b920...`. The connected GitHub write integration returned 403 for branch and workflow writes; no source patch or workflow restoration was committed by this repair pass.
- Neon canonical application branch `lexa-live` still has 31 migration-ledger entries through migration 031. Migration 039 and its six supplier-finance tables are absent. The root branch called `production` does not expose `public.schema_migrations`; do not infer its schema from that error.
- Neon reports no snapshots or automatic snapshot schedule. Creating a snapshot on `lexa-live` failed because it is a non-root branch. A new branch in the canonical project was rejected due to the current branch limit. The project exposes six-hour history retention. No production SQL was executed.

## Release gate

**NO-GO for production.** The API fix is only in this archive; exact-SHA GitHub CI, a Redis-backed complete suite, a newly deployed Render candidate, authenticated isolated staging E2E, exact-SHA Render/Vercel parity, backup/restore demonstration, measured migration lock/duration review, and explicit production approval remain open. No Phase 7 migration was applied to canonical production.

The six historical Phase 3 migrations remain permanently dispositioned by the existing approved replacement decision; this increment does not reopen byte recovery.
