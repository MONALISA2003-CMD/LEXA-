# Phase 3 final closeout and runtime cutover — 2026-10-21

## Final acceptance result

The Phase 3 production acceptance gates requested for this closeout have passed after the runtime database login cutover. The six canonical historical SQL sources listed below remain formally declared lost and replaced with labelled equivalents; their original-byte parity is not claimed.

## Production database and security

- Production schema ledger records migrations `030_phase3_workspace_memberships` and `031_phase3_auth_surface_rls`.
- Final live audit checked all 119 public base tables: every table has Row-Level Security enabled and forced; the disabled and enabled-but-not-forced inventories are both empty.
- `lexa_app` has no DELETE privilege on `registration_requests`.
- Created `lexa_runtime_login_p3` with `LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS`, and granted membership in `lexa_app` for explicit `SET LOCAL ROLE lexa_app`.
- Connected as the new login and verified that after switching to `lexa_app`, users, tenants, and registration requests are hidden without the relevant transaction-local context; permissions and the migration ledger remain readable.
- Updated Render's `DATABASE_URL` to the Neon pooled endpoint with TLS required and username matching `DATABASE_LOGIN_ROLE=lexa_runtime_login_p3`. The deployment is live on commit `3b2edd639d2828ad371c2176376e4016f2992439`, deployment `dep-dbc7nnd9fdbs73c5a760`.
- Readiness after the cutover returned HTTP 200 with production status `ready`, database `ok`, and cache `ok`. Neon `pg_stat_activity` showed active pooled connections using the new least-privilege login.
- Rotated the legacy `lexa_runtime` password after the new login was live. Its old connection string is no longer valid. The Render application uses the new login.

## Authenticated live end-to-end acceptance after cutover

Tested through the deployed LEXA frontend and API against a clearly labelled QA workspace:

- Registration completed and produced a workspace with active Owner membership; the browser showed `Session active`.
- `/api/v1/auth/refresh` returned HTTP 200 and `/api/v1/auth/me` returned HTTP 200 with the QA owner/workspace identity matching.
- Branch create returned HTTP 200; subsequent branch list returned HTTP 200 and contained the new branch.
- Category create returned HTTP 201; subsequent category list showed it. Update returned HTTP 200 and the updated name was visible. Delete returned HTTP 200, changed the record to `INACTIVE`, and the record was absent from the active category list.
- Inventory UI acceptance had also previously created and verified QA warehouse/location records with the forced-RLS migration applied.
- The final QA browser session was signed out. Database verification showed no active session for that QA owner. No sales, invoices, payments, products, inventory quantities, or stock transactions were created.

## Build and test evidence from this source line

- Backend: 28 tests passed in the validation workspace, with one upstream deprecation warning.
- Frontend on Node 24.21.0: clean `npm ci`, `npm audit --audit-level=high` (0 vulnerabilities), typecheck, 23 tests passed, and production build passed with 18 routes.
- The replay manifest has 35 declared steps with no missing referenced paths.
- Source changes include the transaction-local tenant-context restoration, registration/login pre-tenant scoping, migration 031, source-contract tests, and the updated default runtime login name.

## Declared historical source gaps — substitutes retained

The exact historical sources remain unavailable and are not represented as byte-recovered originals:

- `migrations/010_phase2_catalog_intelligence.sql`
- `migrations/011_phase2_catalog_runtime_constraints.sql`
- `migrations/023_phase4_purchasing_core.sql`
- `migrations/024_phase4_purchasing_security.sql`
- `migrations/025_phase4_purchasing_permissions.sql`
- `migrations/026_phase4_membership_branch_integrity.sql`

They are declared lost per the project decision and represented in the replay manifest by labelled equivalents/compatibility steps. A successful equivalent replay is evidence of compatibility, not proof of canonical byte parity. The replay manifest remains disposable/test-only and must never be executed as a production runner.
