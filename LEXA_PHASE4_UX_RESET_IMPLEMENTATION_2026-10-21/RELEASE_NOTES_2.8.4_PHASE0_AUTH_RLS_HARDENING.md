# LEXA v2.8.4 — Phase 0 final auth/RLS/runtime hardening

## Fixed
- Refresh-token lookup uses a narrowly scoped SECURITY DEFINER function to find the tenant for an opaque token before tenant RLS context exists. The API then establishes tenant/user context and locks the session row before rotating the token.
- Added `GET /api/v1/auth/me` as the authoritative identity, workspace, membership, role and permission contract. Session restoration waits for this check before the workspace unlocks.
- Protected requests set both `app.tenant_id` and `app.user_id`, required by branch-aware RLS policies.
- Migration 028 normalizes empty tenant/user GUCs in existing RLS policy expressions and assigns a read-only `Member` role only to already-active memberships that have no role. It never grants Owner/Admin, does not attach users to a tenant, and does not reset data.
- The API logs correlated server tracebacks while returning sanitized errors to the browser.
- Vercel proxy preserves request IDs and multiple `Set-Cookie` headers.
- Updated the stale regression assertion that still required `credentials: same-origin`; the browser same-origin proxy uses `credentials: include`.

## Validation
- Python API tests: 10 passed, 1 skipped because optional API dependencies are unavailable in this environment.
- Frontend contract tests: 2 passed.
- Python source compilation: passed.
- TypeScript/TSX syntax: 27 files checked, zero parse errors.
- Full Next.js production build and live auth smoke test must still run after deployment.

## Required deployment order
1. Inspect the canonical Neon `schema_migrations` ledger; confirm 028 is not already applied.
2. Apply only `migrations/028_phase0_auth_rls_runtime_hardening.sql` to the canonical Neon branch.
3. Deploy API to Render, then frontend to Vercel.
4. Test login, cookie refresh, `/auth/me`, hard reload, protected inventory/dashboard and logout. Correlate any 5xx using `X-Request-ID`.
