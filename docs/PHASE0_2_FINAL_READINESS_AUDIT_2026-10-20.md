# LEXA Phase 0–2 Final Readiness Audit

**Audit date:** 20 October 2026 (Africa/Kampala)  
**Scope:** LEXA only — existing Vercel web app, Render API, Neon PostgreSQL, source repository, Phase 0 reliability/authentication, Phase 1 security/UX foundation, and Phase 2 frontend system/reliability.  
**Mode:** Read-only inspection of hosted resources; local source/test work only. No production deploy, Render settings change, Git push/merge, Neon SQL write, credential change, or role cutover was performed.

## Executive decision

**Phase 0–2 are not yet fully release-accepted. Do not begin Phase 3 schema-changing work yet.** The latest deployed application is healthy at the platform/probe level and the current commit includes the prior frontend null-guard and SQLAlchemy `RowMapping` fixes. But green hosting status is not the same as authenticated end-to-end acceptance or security sign-off.

The most important remaining blockers are:

1. The production Neon login `lexa_runtime` still has elevated Neon role membership; the safe login `lexa_runtime_safe` does not exist on `lexa-live`, and migration 029 is not applied there.
2. Five public tables have RLS disabled and no policies (`permissions`, `registration_requests`, `schema_migrations`, `tenants`, `users`). Their intentional global/bootstrap access patterns must be documented and secured/tested deliberately; do not enable RLS blindly.
3. Seven exact historical migration SQL sources are still missing. Strict replay remains blocked. Repository path history and the available ZIP artifacts did not recover them.
4. GitHub Actions CI is not running on the latest commit. The current green commit status is Vercel only. The workflow file is nested under `LEXA-Phase1-2.9.1/.github/workflows/` while the active root `.github/workflows/` is protected by the ZIP extractor. `main` is not protected and has no required status checks.
5. Hosted credentialed authentication and tenant-scoped business acceptance have not been run with a dedicated test account.
6. The current local runner lacks full frontend dependencies and runs Node 22 rather than required Node 24; local TypeScript typecheck fails with missing `react`/`next` modules. The latest Vercel deployment is READY, but this local candidate still needs a reproducible CI run and visual responsive acceptance.
7. Phase 2 route inventory shows shared primitives are not directly adopted consistently across all application routes; the whole-app UI/responsive acceptance matrix is not signed off.

## 1. Current hosted evidence

### Same deployed source commit

- **GitHub `main`:** `2cbfda1b24864d7cc03ad2cbb3972639545fe28d` (`chore: automatically extract LEXA ZIP package [lexa-extractor]`).
- **Vercel:** deployment `dpl_FnFNF8mB4PxJPvGUvwyHFHagYEpL`, production target `READY`, serving alias `lexa-green.vercel.app`.
- **Render:** latest live deployment `dep-dbbfa06k1f9s73bplsg0`, same commit `2cbfda1b24864d7cc03ad2cbb3972639545fe28d`, service `LEXA` (`srv-dakm8k95efls73egg9a0`), API origin `https://lexa-n10e.onrender.com`.

### Read-only HTTP probes

| Probe | Result | Interpretation |
|---|---|---|
| `https://lexa-green.vercel.app/` | HTTP 200 | Frontend route is served |
| `https://lexa-green.vercel.app/login` | HTTP 200 | Login page is served |
| `https://lexa-n10e.onrender.com/health` | HTTP 200 | Process liveness is healthy |
| `https://lexa-n10e.onrender.com/ready` | HTTP 200; `database=ok`, `cache=ok` | API reports database and cache dependencies ready |
| `https://lexa-green.vercel.app/api/lexa/health` | HTTP 200, API health JSON | Next.js API proxy reaches Render |
| Anonymous `GET /api/v1/commerce/dashboard?business_date=2026-10-20` | HTTP 401 | Auth boundary responds; not a proof of authenticated dashboard success |
| Anonymous `GET /api/v1/inventory/balances?limit=1` | HTTP 401 | Auth boundary responds; not a proof of authenticated inventory success |
| Render app error logs from 04:59–05:15 UTC after latest deployment | No error/warning rows returned | Good short-window signal only; not a sustained monitoring guarantee |

The previously observed commerce dashboard 500s occurred before the latest deployment. The active source now serializes both SQLAlchemy `Row` and `RowMapping` values safely. The current anonymous request does not execute the protected query, so the authenticated dashboard path must still be tested using a dedicated test account.

### Platform controls still drift

- Render service metadata still reports `healthCheckPath` as blank, although `render.yaml` declares `/ready`. The live `/ready` endpoint is healthy, but the control-plane health-check setting has not been reconciled.
- GitHub combined status for the latest commit has a passing `Vercel` context only. GitHub Actions workflow runs for that SHA are empty.
- Repository `main` is unprotected; required status checks are disabled.
- The root ZIP extractor explicitly skips `.github/workflows/**`, so the nested CI workflow is not installed into the active root workflow directory by normal ZIP extraction. This is a source/automation defect, not a Vercel build failure.

## 2. Phase-by-phase acceptance matrix

### Phase 0 — platform, auth, readiness, and migration safety

| Requirement | Status | Evidence / remaining action |
|---|---|---|
| Existing canonical service topology retained | **Pass** | Existing Vercel `lexa`, Render `LEXA`, Neon project `LEXA` and `lexa-live` branch remain in use; no extra production service/database created. |
| API liveness and dependency readiness | **Partial pass** | `/health` and `/ready` return 200; readiness lists database and cache as `ok`. Render's configured health-check field remains blank. |
| Frontend-to-API routing | **Probe pass** | Frontend API proxy health endpoint returns Render API health JSON. Protected business endpoints still need authenticated acceptance. |
| Refresh-session lookup contract | **Previously verified / recheck in E2E** | Migration 028 and `lexa_find_session_by_refresh_hash(text)` are present; security-definer functions have pinned `search_path`, app execute grants and no PUBLIC execute. Credentialed refresh rotation/revocation is not re-tested in this pass. |
| Authenticated login → refresh rotation → `/auth/me` → protected read → logout/revocation | **Blocked** | Must run `scripts/smoke_phase0.py` with a dedicated non-production test account and retain sanitized output. |
| Strict from-zero migration replay | **Blocked** | Seven exact applied migration sources remain missing. Never synthesize them or replay partial history against production. |
| `/ready` and cache failure behavior | **Partial** | Healthy-path probe passes. Dependency-down/failure behavior needs controlled non-production validation. |

### Phase 1 — security and UX foundation

| Requirement | Status | Evidence / remaining action |
|---|---|---|
| Production DB role is least privilege | **P0 blocker** | `lexa_runtime` remains elevated through `neon_superuser` membership; `lexa_runtime_safe` absent on `lexa-live`; migration 029 not applied to live. |
| Safe role tested on isolated branch | **Pass on test branch only** | Existing runbook records successful validation on `lexa-phase1-security-test-2026-10-19`; no production cutover is implied. |
| Tenant/RLS boundaries | **Partial / security review required** | Phase 2 business-engine tables are RLS enabled and forced. Five public tables have RLS off and no policies; review their data flows, grants, and bootstrap requirements. |
| Security-definer functions | **Read-only checks pass** | Four observed public security-definer functions are owned by `neondb_owner`, pin `search_path=pg_catalog, public`, grant execution to `lexa_app`, and do not grant PUBLIC execute. |
| Registration idempotency and global registration data | **Review required** | `registration_requests` has `tenant_id` but no RLS/policies; it stores registration/replay data. Confirm the intended global idempotency design and direct grants, then test. |
| Auth error handling/session safeguards | **Source tests pass; hosted E2E pending** | Current source has regression coverage; complete credentialed hosted acceptance and negative cases. |

### Phase 2 — frontend design system and reliability

| Requirement | Status | Evidence / remaining action |
|---|---|---|
| Root source paths match deployment roots | **Pass for active app source** | Current root `apps/web/...` and `apps/api/...` contain the frontend null guards and backend serializer fix; Vercel and Render deploy the same commit. The old nested copy remains and must not be treated as canonical. |
| Shared shell/design tokens/primitives | **Partial** | Foundation exists, but route inventory shows several pages do not directly adopt shared UI primitives; complete route-by-route audit and consistent loading/empty/error/forbidden/pending/success states. |
| API-backed data, no fake-zero error state | **Improved; acceptance incomplete** | Dashboard now distinguishes unavailable/error/loading data. Verify each route with real API success, empty data, 401, 403, validation, 5xx and network failures. |
| Frontend tests | **Pass locally** | `node --test apps/web/tests/*.test.mjs`: 18 passed, 0 failed. |
| Backend tests | **Pass with one skip** | `python -m pytest -q tests apps/api/tests`: 112 passed, 1 skipped because `redis` is not installed locally. Run in CI with declared dependencies to execute the skipped test. |
| Python/shell syntax | **Pass** | Compilation and syntax checks passed in prior Phase 2 verification. |
| Full local frontend typecheck/build | **Not verified locally** | Local `node_modules` is empty; runner is Node 22.16.0, not Node 24. `npm run typecheck` fails with missing React/Next modules. Run `npm ci`, typecheck, tests and build in a real Node 24 CI environment. Latest Vercel deployment is READY. |
| Responsive visual acceptance at 360/390/430/768/1280 CSS px | **Open** | Desktop/mobile page captures exist, but no complete measured, reviewed five-width screenshot matrix is signed off. Do not infer responsiveness from desktop HTTP 200. |
| Accessibility and keyboard/focus review | **Partial** | Source has shared accessibility foundations/tests; complete route-level keyboard, focus, dialog, form, contrast, screen-reader state and mobile navigation checks. |
| Whole-app authenticated workflow test | **Blocked** | No dedicated hosted account acceptance has been recorded. |

## 3. Database findings confirmed during this audit

### Elevated runtime login — P0

Read-only SQL against `lexa-live` confirmed:

- `lexa_runtime` exists and has elevated privileges through Neon-managed role membership.
- `lexa_runtime_safe` does not exist on this branch.
- `029_phase1_runtime_role_least_privilege` is not in the live migration ledger.

Do not revoke or alter the current role as a quick fix. Follow `docs/PHASE1_SECURITY_STABILITY_RUNBOOK.md`: backup/recovery plan, isolated branch validation, create/set the new login password through approved secret handling, deploy with the matching `DATABASE_LOGIN_ROLE` and pooled URL, verify authenticated flows, and only then plan retirement of the old login. This needs explicit production authorization.

### RLS off on five public tables — P0 security review

Read-only catalog inspection confirmed no RLS and no policies on:

- `permissions`
- `registration_requests`
- `schema_migrations`
- `tenants`
- `users`

This is a concrete defense-in-depth concern, but the correct policy differs by table. `schema_migrations` and `permissions` may need tightly scoped operational access; `tenants`/`users` and registration bootstrap flows need deliberate tenant and lifecycle semantics. Map all API/SQL call paths and grants, design policy tests, validate on an isolated branch, and only then plan an approved production migration. Do not toggle RLS blindly.

### Phase 2 tables

The ten Universal Business Engine tables checked during this audit have RLS enabled and forced. Each has at least one policy; `transaction_status_history` has two. This is positive evidence for that subsystem, not proof every table or query is correctly tenant-isolated.

### Missing migration source history

The source manifest still identifies these seven missing exact SQL files:

- `010_phase2_catalog_intelligence.sql`
- `011_phase2_catalog_runtime_constraints.sql`
- `023_phase4_purchasing_core.sql`
- `024_phase4_purchasing_security.sql`
- `025_phase4_purchasing_permissions.sql`
- `026_phase4_membership_branch_integrity.sql`
- `027_release_convergence.sql`

Queries against the inspected GitHub path history returned no commits for those paths, and available source ZIPs did not contain the files. This does not prove no other owner-held backup exists; request authoritative release artifacts or backup source. Preserve the full migration version names because numeric prefix `023` collides. Keep `python scripts/check_migration_sources.py --strict` blocked until exact bytes are recovered and reviewed.

## 4. Source and test verification recorded for this candidate

- Frontend contract tests: **18 passed** (`node --test apps/web/tests/*.test.mjs`).
- Backend suite: **112 passed, 1 skipped** (`python -m pytest -q tests apps/api/tests`); skip reason: missing local `redis` dependency.
- Local TypeScript typecheck: **not passed** because the runner's `apps/web/node_modules` is empty and cannot resolve `react` or `next`; this is an environment/dependency-install blocker, not evidence of a specific application typing regression.
- Runtime environment is Node `v22.16.0`, while `apps/web/package.json` requires Node `24.x`.
- Latest production Vercel build: **READY** on commit `2cbfda1...`; no claim that the local source ZIP was independently built in a clean Node 24 environment.
- Migration source check: normal mode documents seven gaps; strict replay remains blocked.
- No real credentialed business mutation was attempted against production.

## 5. Research notes from official platform documentation

- GitHub documents that commits pushed by workflows using `GITHUB_TOKEN` do not trigger new workflow runs for ordinary `push` events; this is consistent with, but does not alone prove, why the ZIP extractor's own commit has no subsequent CI run. A manual `workflow_dispatch` can run the CI workflow, but the root workflow must first be installed at the correct path. Source: https://docs.github.com/en/actions/concepts/security/github_token
- Render documents that HTTP health checks are configured through the service settings or `healthCheckPath` in a Blueprint, and accept `2xx`/`3xx` responses. This supports reconciling the live blank setting with `render.yaml`. Source: https://render.com/docs/health-checks
- Neon recommends reserving `neon_superuser`-equivalent roles for administration and using explicit least-privilege database roles for application access. Source: https://neon.com/docs/manage/database-access and https://neon.com/docs/manage/roles
- PostgreSQL documents that `BYPASSRLS` bypasses row-level security and that role attributes/membership must be reviewed as part of access control. Source: https://www.postgresql.org/docs/17/role-attributes.html

## 6. Required gates before Phase 3

### Gate A — source/CI control

- [ ] Install `.github/workflows/lexa-ci.yml` at the active repository root through an authorized reviewed GitHub change; do not rely on ZIP extraction to install it while the extractor protects workflow paths.
- [ ] Ensure it runs on the same root source layout and includes Python dependencies, frontend `npm ci`, typecheck, frontend tests, production build, migration-source reconciliation and security regression tests.
- [ ] Trigger and observe a real Actions run on the exact candidate commit; confirm backend and frontend jobs pass.
- [ ] Protect `main` and require the intended CI checks. Do not use Vercel `success` alone as the complete release gate.
- [ ] Remove or clearly quarantine the stale `LEXA-Phase1-2.9.1/` duplicate so it cannot be mistaken for active source.

### Gate B — database security and migration provenance

- [ ] Recover the seven exact missing SQL sources from authoritative artifacts; verify source bytes and full migration identities.
- [ ] Complete a table-by-table RLS/grant review for `permissions`, `registration_requests`, `schema_migrations`, `tenants`, and `users` on an isolated branch; test anonymous, logged-in, cross-tenant, bootstrap, admin, and migration paths.
- [ ] Execute the least-privilege role migration on an isolated branch and verify role membership, `SET ROLE lexa_app`, absence of direct sensitive-table access, and login behavior.
- [ ] Prepare backup, rollback, secret rotation and explicit approval plan before any production role/schema cutover.

### Gate C — hosted end-to-end acceptance

- [ ] Use a dedicated non-production account and run `scripts/smoke_phase0.py` against the intended hosted API.
- [ ] Verify login, refresh cookie creation and rotation, `/auth/me`, workspace selection, protected product/catalog/inventory/dashboard reads, logout, revoked-refresh rejection and access-token rejection after logout.
- [ ] Verify tenant and branch isolation using two controlled tenants/branches; include forbidden-action tests and last-admin/owner safeguards.
- [ ] In a disposable workspace, test an idempotent business write end-to-end and confirm the UI reflects the persisted result. Do not use a production workspace for test writes.
- [ ] Confirm no new 5xx in relevant logs and that `/ready` fails safely when a critical dependency is unavailable.

### Gate D — Phase 2 UI and build acceptance

- [ ] Run clean `npm ci --no-audit --no-fund`, `npm run typecheck`, `npm test`, and `npm run build` under Node 24.
- [ ] Audit all 15 route pages and shared layouts; ensure consistent design primitives and honest loading, empty, error, forbidden, pending and success states.
- [ ] Capture/review at 360, 390, 430, 768 and 1280 CSS px; check overflow, clipped actions, mobile nav, tables/forms, touch targets, keyboard/focus, contrast and screen-reader announcements.
- [ ] Test frontend API proxy, auth/session restore, workspace context, branch context, error handling and browser console for every critical flow.

### Gate E — platform configuration and release proof

- [ ] Reconcile the live Render health-check field with `/ready` or document an approved alternative; verify the resulting service metadata after the setting change.
- [ ] Keep the same source commit in the release record for GitHub CI, Vercel and Render.
- [ ] Keep production deployment, Neon mutations, runtime-role credential cutover and live health-check setting changes behind explicit approval.

## Final recommendation

**Phase 3 status: NOT READY for schema-changing implementation.** It is reasonable to begin a non-mutating Phase 3 discovery/specification pass—mapping existing business profile, workspace, branch, warehouse, membership, invitation and permission contracts—but defer migrations and production changes until Gates A–C are satisfied. Phase 2 should not be declared complete until Gate D is evidenced, and production readiness should not be declared until Gate E is reconciled.
