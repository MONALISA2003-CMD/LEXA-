# Phase 3 closeout remediation — 2026-10-21

## Implemented in this source package
- Added the missing uq_brands_tenant_id(tenant_id,id) composite key to root migration 004 and its replay-equivalent copy.
- Repaired root migration 021 from the valid lexa_v280_src equivalent. The original root file contained escaped newline text and trailing non-SQL code; this is a repaired substitute, not proof of original-byte recovery.
- Materialized replay-only SQL paths that the manifest referenced but that existed only under the Phase 3 override package.
- Added migration 031 to enable and force RLS on the remaining five public tables: permissions, schema_migrations, users, tenants, and registration_requests.
- Updated registration/login routes to set narrowly scoped pre-tenant context, constrain user visibility to the requested email and registration-request visibility to its idempotency key, and preserve tenant/user context across login commit.
- Added source-contract regression tests and a GitHub Actions workflow to run backend checks, Node 24 typecheck/tests/build, dependency audit, and migration-manifest path checks.

## Production work already performed
- Migration 030 was applied after preflight checks found zero duplicate membership groups, malformed invitation hashes, live pending invitations missing roles, and duplicate pending invitation groups.
- The runtime role lexa_runtime_safe exists but is not yet configured with a usable password, so Render was not cut over to it. The existing lexa_runtime remains a privileged login, although application transactions switch to lexa_app.

## Validation completed in the temporary validation workspace
- Backend suite: 28 passed after installing the missing Starlette test-client dependency httpx2. One upstream deprecation warning remains.
- Frontend checks on Node 24.21.0: npm ci passed; npm audit reported 0 vulnerabilities; typecheck passed; 23 tests passed; production build passed and generated 18 routes.
- Clean-replay database already validated migrations 001–030 with labelled equivalents and a replay-only brands composite-key fix. Migration 031 was then applied to that isolated replay database; its ledger entry is present, RLS enabled and forced on all five remaining auth-surface tables, and the registration DELETE privilege is revoked.
- Isolated role/RLS smoke check passed: self user and active tenant visible in matching context; a different user and pre-tenant registration rows are hidden after clearing registration context; permission catalog and migration ledger remain readable to lexa_app.
- The replay manifest path-integrity script passes for all declared steps.

## Validation still required before phase closure
- Run migration 031 only after the updated API code is deployed, then verify all public tables have RLS enabled/forced or an explicit reviewed exception.
- Re-run the full clean database replay using the corrected manifest. The six exact historical SQL files (010, 011, 023, 024, 025, 026) remain unavailable; equivalents do not prove byte parity.
- Run backend tests and authenticate to verify login, registration, branch/category create/update/delete, and read/write acceptance across modules. Existing live log evidence includes HTTP 500 on branch/category creation before this patch; that acceptance must be repeated after deployment.
- Finish the database safe-role credential cutover using an authorized secret-management method and verify Render readiness.
