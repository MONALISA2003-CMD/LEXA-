# LEXA Full Deployment & Integration Audit v1.9.1

Date: 22 September 2026
Canonical database boundary: `wispy-mud-75323042 / br-soft-star-b1dj2m2w / neondb`

## Release blockers found

### 1. Render startup blocker
`apps/api/app/main.py` imported `kernel` from `apps/api/app/routes`, but the canonical kernel implementation is `apps/api/app/kernel.py`.

Observed Render failure:
`ImportError: cannot import name 'kernel' from 'app.routes'`

Repair:
- remove `kernel` from the `.routes` import list;
- import `router` from `.kernel`;
- register `kernel_router` at `/api/v1`.

### 2. Vercel TypeScript blocker
`apps/web/app/business-engine/page.tsx` passed numeric `quantity: 1` into `createBusinessTransaction`, while the frontend API contract models transaction quantities as strings because PostgreSQL Decimal values are serialized as strings.

Repair:
`quantity: "1"`.

### 3. Workspace bootstrap hardening
A workspace could have a valid health/readiness response but a stale browser token. The frontend now performs an authenticated `getBusinessCapabilities()` probe after readiness before treating the workspace as connected. Stale tokens are cleared and the development bootstrap retries.

## Database verification

Only the canonical LEXA Neon target was inspected/modified.

Verified:
- database: `neondb`
- project: `wispy-mud-75323042`
- branch: `br-soft-star-b1dj2m2w`
- Phase 2 migration: `013_phase2_universal_business_engine`
- Phase 3 migration: `014_phase3_inventory_foundation`
- 10 Phase 2 tables with forced RLS
- 9 Phase 3 inventory tables with forced RLS
- Phase 3 permissions installed
- inventory ledger UPDATE/DELETE privileges revoked for `lexa_app`
- business capabilities and transaction types seeded
- live inventory ledger currently contains 0 rows; no test inventory data was inserted into `lexa-live`

## Backend audit

- Python compilation: PASS
- Backend test suite: 70 passed
- Route surface: 92 API endpoints statically inspected
- Protected domain routes use `require_permission(...)`
- Tenant context is established through `app.tenant_id`
- Phase 2/3 migration assets exist and are additive
- Render configuration points at `apps/api` and `uvicorn app.main:app`

## Frontend audit

- Visible product contract: PASS
- Frontend hardening contract: PASS
- Vercel's reported quantity type mismatch is repaired
- Next.js production build was not runnable inside this sandbox because npm dependency installation has no network access. This is an environment limitation; Vercel's own previous log confirms its cached dependency installation succeeds.

## Infrastructure limitation

The connected GitHub integration is currently returning HTTP 403 `Resource not accessible by integration` for branch/file writes. Therefore the repaired source could not be pushed to `MONALISA2003-CMD/LEXA-` from this session.

The repaired working copy and deterministic patch script are included in this release package.

## Deployment acceptance sequence

1. Apply `scripts/apply_deployment_repairs.py` to the repository at or after commit `66704bc`.
2. Commit to `main`.
3. Allow Vercel and Render auto-deploys to run.
4. Require Vercel build status READY.
5. Require Render startup to reach `/health` successfully.
6. Require `/ready` to report `status=ready` for the canonical Neon identity.
7. Open the workspace and require successful authenticated Business Engine access.
8. Verify Inventory and Products can load under the authenticated tenant.

No additional Neon migration is required for these source repairs.
