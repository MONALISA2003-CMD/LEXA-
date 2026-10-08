# LEXA Integration Repair v1.7.1

This patch hardens the browser -> Next.js proxy -> FastAPI -> Neon workspace bootstrap path.

## Repairs

1. Frontend readiness now treats `200 {"status":"not_ready"}` as not ready and retries boot.
2. Frontend retries transient `/health`, `/ready`, and development-session failures.
3. Frontend re-runs health/readiness after establishing a workspace session.
4. The Next.js proxy has a safe default to the canonical LEXA API origin while still allowing deployment environment variables to override it.
5. The proxy preserves `Retry-After` for upstream 5xx responses.
6. The development workspace seed imports `Decimal`, preventing first-run `dev-session` failures while seeding product pricing.
7. Existing tenant/RLS/security paths are preserved.

## Verified

- Backend pytest: 58 passed
- Frontend visible/hardening contract: PASS
- Python compilation: PASS

A full TypeScript check requires the web project's npm dependencies to be installed; the extracted source package does not contain `node_modules`.

## Deployment note

The source patch is ready, but the current Vercel connector scope cannot inspect or promote the live `lexa` deployment, and the Render service cannot be reached from the current tool network. Therefore this package is a verified source repair, not a claim that production has already been redeployed.


## Phase 2 follow-on

The v1.8.0 package builds on this integration repair and adds the Universal Business Engine without changing the canonical Neon target.
