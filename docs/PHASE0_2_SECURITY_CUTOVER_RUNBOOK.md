# LEXA Phase 0–2 Security and Release Cutover Runbook

**Status:** Prepared for review; not authorization to mutate production.  
**Scope:** LEXA's Neon database roles/RLS, Render API service settings, GitHub Actions/branch protection and release validation.

## 1. Current verified state

- Canonical Neon branch: `lexa-live` (`br-soft-star-b1dj2m2w`), database `neondb`.
- Production `lexa_runtime` remains connected and overprivileged through Neon-managed role membership. `lexa_runtime_safe` is absent on production and migration 029 is not recorded there.
- On isolated branch `lexa-phase1-security-test-2026-10-19` (`br-red-voice-b16z9b0i`), migration 029 is recorded. Read-only catalog inspection shows `lexa_runtime_safe` is LOGIN/NOINHERIT/NOCREATEDB/NOCREATEROLE/NOREPLICATION/NOBYPASSRLS, not a member of `neon_superuser`, and has SET membership in `lexa_app`. The existing `lexa_runtime` remains elevated on that test branch too; migration 029 intentionally leaves it untouched.
- The isolated safe role has no production secret provisioned by this runbook. The application still needs a deliberately created secret for any credential cutover.
- `permissions`, `registration_requests`, `schema_migrations`, `tenants`, and `users` have RLS disabled/no policies on production. Ten sampled business-engine tables are RLS enabled and forced, but that does not prove all table grants/policies are complete.
- Render's `/ready` endpoint is healthy and reports database/cache `ok`, but service metadata has an empty `healthCheckPath`; the checked-in `render.yaml` specifies `/ready`.
- GitHub `main` is unprotected and required status checks are off. Root CI workflow is absent on active main; the existing ZIP extractor protects `.github/workflows/**`, so a ZIP overlay will not install a root workflow.
- The exact source for `027_release_convergence.sql` is now restored and hash-verified against historical Git blob `e6d9242d7dedb2cbf7b1a71a46fe635b3ab051d8`. Six full migration sources remain missing; strict replay remains blocked.

## 2. Runtime role cutover — controlled procedure

**Do not execute against production until a release window and rollback owner are explicitly approved.**

1. Capture the latest Neon branch identity, migration ledger, roles/memberships, grants and RLS state; verify backup/PITR coverage and the named recovery operator.
2. Review `migrations/029_phase1_runtime_role_least_privilege.sql` and the exact source package. Re-apply/validate it only on a disposable branch first; do not “repair” `lexa_runtime` in place.
3. Assign a unique password to `lexa_runtime_safe` using the authorized Neon role/password workflow. Never put it in Git, a report, chat or a command-line argument. Record only that the secret was provisioned, not its value.
4. In a coordinated Render change, update both `DATABASE_LOGIN_ROLE=lexa_runtime_safe` and `DATABASE_URL` username/password together, retaining the same pooled endpoint, TLS parameters and `DATABASE_APP_ROLE=lexa_app`. Do not update one without the other.
5. Start with a non-production/staging service. Confirm the DB login succeeds, transaction-local switch sets `current_user=lexa_app`, `session_user=lexa_runtime_safe`, and health/readiness works; confirm application role grants work while the login role itself cannot read `public.users`, delete migration history, or bypass RLS.
6. Run authenticated API tests: login, workspace selection, refresh rotation/reuse denial, `/auth/me`, protected read, sign-out/revocation, error paths, tenant boundary, branch boundary and representative read/write transaction against disposable records.
7. In the approved production window, update the credential/role pair and use the normal reviewed deployment path. Observe `/ready`, logs and all acceptance checks before declaring success. Roll back by restoring the last known working pooled connection URL/role pair if safe-role login or user flows fail. Retain the old role until the new connection is verified; plan retirement separately.
8. Once stable, remove elevated legacy credentials only via a separately reviewed operation after confirming no service or manual task still depends on them.

## 3. RLS/grants policy design — do not use a blanket enable switch

For each of the five tables, enumerate every SQL/API/bootstrap/migration call, owner, direct grant, SECURITY DEFINER helper, and expected no-session behavior before drafting a policy:

- `users`: authentication identity lookups require a very narrow pre-tenant path; ordinary queries must not permit cross-tenant enumeration. Prefer specific existing security-definer lookup functions or a separate identity service contract over broad user-table access.
- `tenants`: workspace discovery for a user with zero/one/multiple memberships must not rely on a caller-controlled tenant ID. Check `lexa_list_user_workspaces` and other narrowly scoped lookup functions for grants and tenant binding.
- `permissions`: role/permission dictionaries may contain global reference data, but grant only the operations the application requires; a table being global does not automatically mean any role should write it.
- `registration_requests`: decide whether idempotency keys/hashes and replay payloads are globally scoped or tenant scoped. Explicitly test that an anonymous replay token cannot enumerate or mutate a different registration request. Avoid exposing stored response bodies through a broad list/read route.
- `schema_migrations`: runtime application should not normally need mutation rights. Migration tooling should use a dedicated operator/migration role. If health checks need to query migration state, expose a narrow read-only status path or function rather than broad delete/alter grants.

Before any production RLS change: write table-specific policies, add tests for unauthenticated/no-tenant, tenant A, tenant B, a branch-bound member and an administrator/migration role; validate on an isolated Neon branch; run the complete auth and business test suites; inspect policies/grants after applying; document rollback. Owners and superuser-like roles may bypass RLS, so RLS alone is not a replacement for fixing the elevated login.

## 4. CI and release controls

1. Install the candidate `.github/workflows/lexa-ci.yml` at the root via an authorized reviewed Git change. It uses full-length verified action SHAs, minimal `contents: read`, Node 24, backend tests, migration reconciliation, frontend typecheck/test/build, and a separately opt-in strict migration gate.
2. The workflow should run on ordinary push/PR. A strict migration replay dispatch is intentionally expected to fail until the six original sources are recovered; normal CI remains useful and green for unrelated changes.
3. Enable `main` branch protection/ruleset via repository administration. Require the backend and frontend job checks and the Vercel check where appropriate, disallow force pushes/deletes and require PR review. Do not select required-check names until a real successful Actions run confirms the exact names GitHub publishes.
4. The existing ZIP extractor's `GITHUB_TOKEN` push does not ordinarily trigger a fresh `push` workflow run, and it protects the workflow directory. Change that automation separately to create a PR or to use a reviewed GitHub App/PAT if follow-on checks are required. Do not grant more token permissions without a threat review.
5. Verify the final intended commit SHA against: GitHub CI runs, Vercel production deployment, Render live deployment, source ZIP manifest and smoke report. A green service on a different commit is not proof of this package.

## 5. Render health check and rollback

- The blueprint defines `healthCheckPath: /ready`; the observed live service setting is blank. `/ready` currently returns 200 when database and cache are available.
- Change the hosted setting only during an approved, reviewed release or reconcile through the Blueprint workflow. Verify the setting after the update and ensure failure responses go non-2xx when operation-critical dependencies are down.
- Preserve `/health` as process liveness and `/ready` as dependency readiness; do not conflate the two.
- Keep a one-page rollback record: prior live commit/deploy ID, target commit/zip checksum, DB migration version, environment change references (never values), smoke-test timestamp, rollback trigger, and who can execute rollback.

## 6. Final acceptance before Phase 3

- [ ] Exact six migration sources recovered from authoritative artifacts, or a formal decision scopes only additive/non-schema Phase 3 discovery while replay stays blocked. Do not fabricate source.
- [ ] Root CI is installed and green on the intended source commit with branch protection effective.
- [ ] Node 24 clean install, typecheck, tests and `next build` pass.
- [ ] Authenticated API/browser E2E passes with dedicated non-production credentials.
- [ ] Tenant/branch isolation negative tests pass across at least two disposable tenants and multiple branches.
- [ ] Least-privilege production cutover explicitly approved, applied and observed, or production data/security-changing work remains blocked.
- [ ] Table-specific RLS/grant decisions implemented and tested on an isolated branch before production.
- [ ] Render `/ready` configured and confirmed by the platform.
- [ ] Responsive and keyboard acceptance is recorded at 320, 360, 390, 430, 600, 601, 768, 800 and 1280 CSS px.

No steps in this document have altered canonical production settings, roles, credentials or data.
