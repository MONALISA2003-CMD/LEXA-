# LEXA end-to-end forensic audit — 13 October 2026

## Executive finding

The reported screen (“LEXA could not verify your session”) mapped to a concrete production failure, not merely a green-status mismatch. Render logs for the LEXA API show `POST /api/v1/auth/refresh` returning HTTP 500 at `2026-10-13T10:15:30Z`. The database exception was `psycopg.errors.UndefinedFunction`: `public.lexa_find_session_by_refresh_hash(unknown) does not exist`. The deployed refresh handler called that exact function.

The function was missing from the canonical Neon branch at the time of audit. Following explicit user approval, migration `028_phase0_auth_rls_runtime_hardening` was promoted to Neon project `LEXA` (`wispy-mud-75323042`), branch `lexa-live` (`br-soft-star-b1dj2m2w`), database `neondb`. Post-migration queries verified the ledger row, function, executor grant, SECURITY DEFINER flag, RLS-bypassing owner, and safe tenant policy expressions. A hash from the previously failing refresh request now resolves to one unrevoked, unexpired session through the new lookup function.

**The confirmed database-side cause is repaired. A real post-migration browser/API round trip is still needed before declaring the entire frontend → Vercel → Render → Neon path fully accepted.** No application code was pushed or deployment manually triggered as part of this work; the updated source ZIP is provided below.

## 1. Neon: live migration 028 applied and verified

Canonical target:

- Neon project: `LEXA`
- Project ID: `wispy-mud-75323042`
- Branch: `lexa-live`
- Branch ID: `br-soft-star-b1dj2m2w`
- Database: `neondb`

Before migration, the ledger ended at `027_release_convergence` and `public.lexa_find_session_by_refresh_hash(text)` was absent. The `sessions` table already contained the columns required by the lookup (`id`, `tenant_id`, `user_id`, `refresh_token_hash`, `expires_at`, `revoked_at`).

The tested migration was promoted after explicit approval. The temporary migration branch was deleted as part of promotion. Post-promotion read-only checks returned:

- `028_phase0_auth_rls_runtime_hardening` ledger rows: **1**.
- `public.lexa_find_session_by_refresh_hash(text)` function count: **1**.
- `lexa_app` can execute the function: **true**.
- Function is `SECURITY DEFINER`: **true**.
- Function owner has `BYPASSRLS`: **true**.
- A synthetic non-matching token hash returns: **0 rows**.
- Raw tenant-policy predicates casting `current_setting('app.tenant_id', true)` without `NULLIF`: **0**.
- The token hash from the earlier failed refresh now finds **1** currently unrevoked, unexpired session. The sensitive hash value is intentionally not copied into this report.

The migration's role backfill did not create a new `Member` role on this live data set: the two observed active memberships already had two role assignments. It did not add memberships or elevate existing roles.

## 2. Render: exact runtime error confirmed

The confirmed service is **LEXA** in Render **My Workspace**:

- Service ID: `srv-dakm8k95efls73egg9a0`
- Public API host: `https://lexa-n10e.onrender.com`
- Repository configured on the service: `https://github.com/MONALISA2003-CMD/LEXA-`
- Branch: `main`
- Root directory: `apps/api`
- Auto-deploy on commit: enabled

The latest Render deployment inspected was `dep-db6vpgss728c739cok10`, on commit `fd59d989a8c4ecc3c6a3689dbc2ece315376f34b`, created at `2026-10-13T09:41:23Z`, and finished successfully at `2026-10-13T09:42:34Z`. Its deployment status was `live`.

At `2026-10-13T10:15:30Z`, that service logged the missing-function SQL exception in the refresh handler followed by `POST /api/v1/auth/refresh` → `500 Internal Server Error`. This aligns directly with the user's screenshot and confirms the frontend reached the API; this was not just a disconnected frontend. The specific refresh hash from that request now resolves to an active session through the newly installed function on canonical `lexa-live`.

There were no Render request logs or post-fix refresh success records in the interval inspected after the fix. The last app log in the retrieved window was a normal process shutdown at `2026-10-13T10:30:30Z`. Therefore this audit does **not** claim a successful live browser/API retry yet.

## 3. Deployment/readiness drift still to close

The audit found two ways the green service indicators could be misleading:

1. Render's live service configuration reports an empty `healthCheckPath`, while the repository's `render.yaml` declares `/ready`. Thus the live Render service is not configured to use the intended readiness endpoint as a health check.
2. The current GitHub `main` version of `apps/api/app/health.py` checks database reachability and required tables, but does not verify migration 028, the refresh function, the `lexa_app` execute grant, or SECURITY DEFINER/RLS owner properties. The updated ZIP includes those checks so `/ready` fails closed when the auth contract is missing.

The GitHub `main` migration file also differed from the corrected migration in the ZIP: it contains a generic policy-rewrite loop that may wrap predicates that are already wrapped when re-run. The delivered ZIP instead uses explicit, idempotent ALTER POLICY statements for the 12 raw policies observed on `lexa-live`, matching the successfully applied migration. This source discrepancy is documented rather than silently writing to the repository.

### Vercel frontend configuration and source alignment

A read-only Vercel project/deployment lookup succeeded when called in the default account scope. Project `lexa` aliases include `lexa-green.vercel.app`. Its latest production deployment is `READY`, on commit `fd59d989a8c4ecc3c6a3689dbc2ece315376f34b` (`chore: automatically extract LEXA ZIP package [lexa-extractor]`). That commit matches the latest Render LEXA deployment inspected above, so frontend and backend deployment provenance is aligned.

Both production routing variables, `LEXA_API_URL` and `NEXT_PUBLIC_API_URL`, are configured to `https://lexa-n10e.onrender.com`, matching the LEXA Render service. This rules out an obvious frontend-to-wrong-backend URL mismatch. Vercel runtime-error/log APIs still returned 403 in the connected scope, and direct HTTP checks from this environment were unavailable, so post-migration Vercel runtime/request success could not be independently confirmed.

No Render service settings were changed and no GitHub or Vercel deployment was triggered. The deployed commit still contains the older readiness check; the new readiness contract in this ZIP is not yet deployed.

## 4. Source package changes in the updated ZIP

- `apps/api/app/health.py` checks the canonical Neon identity, required tables, migration 028, refresh lookup function, execute grant for `lexa_app`, SECURITY DEFINER and the function owner's RLS bypass.
- `migrations/028_phase0_auth_rls_runtime_hardening.sql` matches the explicit policy alterations used in the successfully applied migration; it creates the minimal token-hash lookup, grants execution only to `lexa_app`, hardens the 12 known empty tenant-context policies, performs a least-privilege Member-role backfill only when needed, and records migration 028.
- Refresh rotation, `/api/v1/auth/me`, tenant/user context setup, request-ID diagnostics, Set-Cookie forwarding, and cookie-based restoration contracts from the previous patch remain included.
- `render.yaml` declares `/ready` as the health check path. The deployed Render service's setting still needs to be reconciled with that source configuration.

## 5. Validation

Source checks previously run on the package:

- `python -m pytest -q`: **97 passed, 1 skipped** (optional API dependency unavailable in sandbox).
- `node --test apps/web/tests/*.test.mjs`: **2 passed, 0 failed**.
- `python -m compileall -q apps/api/app apps/api/tests`: passed.
- TypeScript/TSX parser: 26 non-declaration frontend TS/TSX files checked, zero syntax parse errors.
- Full dependency-backed Next.js production build: not run in this environment.

Live database checks were repeated after promotion and passed as listed in section 1. A credentialed production smoke test was not possible here because no browser cookie or sign-in secret was available, and I did not request or expose credentials.

## 6. Final status and next acceptance gate

**Completed:** exact Render exception identified; migration 028 applied to canonical Neon `lexa-live`; database function, privileges and RLS policy hardening verified; failed refresh hash can now resolve to a live session; Vercel production deployment and API origin were verified and align with Render; refreshed ZIP updated with the verified production state and readiness fix.

**Still outstanding:** deploy the reviewed source in this ZIP to the LEXA GitHub/Render/Vercel pipeline; configure the actual Render service health-check path to `/ready`; the Vercel runtime error API was not accessible for post-fix logs; then perform a real browser login → refresh-cookie rotation → `/api/v1/auth/me` → dashboard/catalog/inventory reads → logout/revocation test. The user should retry the app now; if the browser still shows a connection issue, sign in again and capture the current request ID and Render logs. Do not mark Phase 0 fully accepted until that flow succeeds.

Only LEXA's Neon project/branch and LEXA Render service were inspected or changed. No other workspace services, databases or projects were modified.


## 7. Phase 0 candidate follow-up implementation

The follow-up source package corrects the broken dynamic policy SQL in `migrations/022_phase6a_brain_foundation.sql`. Policy identifiers are now built as a single identifier (`table_name || '_tenant_isolation'`) and `current_setting('app.tenant_id', true)` uses an explicit empty-string normalization. This is a source repair only; it has not been executed against canonical Neon.

The initial candidate had eight applied migration versions without matching SQL files. Migration `019_phase4a_customer_credit_allocation` was subsequently recovered byte-for-byte from historical GitHub commit `d850ce04c8930134f01a63cd65c5d1947a17b17d` and its Git blob SHA verified. Seven SQL sources remain unavailable in the inspected GitHub history: `010_phase2_catalog_intelligence`, `011_phase2_catalog_runtime_constraints`, `023_phase4_purchasing_core`, `024_phase4_purchasing_security`, `025_phase4_purchasing_permissions`, `026_phase4_membership_branch_integrity`, and `027_release_convergence`. The duplicate numeric `023` prefix is separately documented. `migrations/source_gaps.json` and `migrations/live_ledger_snapshot_2026-10-13.json` make this discrepancy machine-checkable. Do not fabricate replacement migrations.

`docs/DEPLOYMENT_RENDER_VERCEL.md` now distinguishes liveness `/health` from readiness `/ready`. The source declares `/ready`, but Render's live dashboard still reports an empty health-check path; that control-plane setting was not changed. The CI workflow now runs both frontend contract tests and includes a strict gate that intentionally remains red until the missing exact migration sources have been recovered.

Validation to run from the package root:

```bash
bash scripts/verify-phase0.sh
python scripts/check_migration_sources.py --strict  # expected to fail while the seven documented gaps remain
cd apps/web && npm run typecheck && npm test && npm run build
```

The Python and frontend static contract suites pass in the local environment. A full Next.js dependency-backed build could not be completed in this network-restricted environment because `apps/web/package-lock.json` is absent and the npm registry could not be resolved. No Vercel/Render settings, GitHub refs, or live database objects were changed by this follow-up implementation.
