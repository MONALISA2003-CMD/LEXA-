# LEXA sign-in and workspace registration incident — forensic report

**Incident date:** 22 October 2026 (Africa/Kampala)
**Status:** Root causes confirmed in source and database policy. A surgical source hotfix is prepared and locally tested, but it is **not deployed** because the connected GitHub integration rejects writes with HTTP 403.
**Scope:** Authentication and first-run workspace registration only. No account, password, business records, database policies, or production schema were changed.

## Executive summary

Two different omissions in the deployed backend's transaction-local PostgreSQL security context explain the symptoms:

1. **Sign-in returns 401 for a valid active account.** The deployed `POST /api/v1/auth/login` route reads `users` before setting `app.pre_tenant_access='login'` and `app.pre_tenant_email`. Because `users` has forced row-level security (RLS), the runtime role sees zero matching user rows without that scoped context. After that is corrected, the same route must set `app.user_id` before calling `public.lexa_list_active_user_workspaces(uuid)`; the function explicitly filters results to the current `app.user_id`. The deployed route omitted both steps. The frontend converts the backend's generic 401 into “The email or password doesn't match an account,” disguising the RLS failure as a password error.

2. **New workspace creation returns 503.** The deployed registration route inserts into `registration_requests` without first setting the exact pre-tenant context and idempotency key demanded by that table's forced-RLS policy. The live Render trace records `psycopg.errors.InsufficientPrivilege: new row violates row-level security policy for table "registration_requests"` at the first insert. The route catches that database exception and returns 503. This is not evidence that Redis rate limiting failed; the logged exception identifies the database policy failure.

## Observed evidence

### Account and membership state

A read-only query on the `lexa-live` Neon branch (`neondb`) found one account matching the email shown in the user's screenshot. The account is active and has one active membership in an active workspace (“Amaal”). The password hash is in the expected Argon2id format. No password was viewed, changed, reset, or exposed.

The current live `lexa-live` schema is at `031_phase3_auth_surface_rls`; the `users` and `registration_requests` tables have RLS enabled and forced.

### Controlled RLS-context proof

Using the actual `lexa_app` database role and transaction-local settings only (read-only statements):

- Reading the account without the pre-tenant login context returned **0** rows.
- Setting `app.pre_tenant_access='login'` and the matching email made exactly **1** row visible.
- Setting `app.user_id` to that active user's ID made the user's own row visible and made `lexa_list_active_user_workspaces()` return **1** workspace.

This proves the login route is inconsistent with the database's RLS contract. No persistent settings or account records were modified by the test.

### Registration RLS policy

The live policy on `registration_requests`, `lexa_registration_requests_pretenant`, requires both:

- `app.pre_tenant_access = 'registration'`
- `idempotency_key = app.registration_key`

The same condition is applied to reads/writes. The deployed route's first `INSERT` did not establish those settings.

### Deployment/source relationship

- Vercel frontend: project `lexa`, host includes `lexa-green.vercel.app`; current deployment commit observed as `04f9022a75c09458114ad7498c54da6d86d3a7c7`.
- Render API: `https://lexa-n10e.onrender.com`, service root directory `apps/api`; current live deployment commit observed as `311c9b73e42042956abc148cc7e40a80c93c5035`.
- Render logs showed repeated `POST /api/v1/auth/login` 401 responses and a workspace registration 503. The Vercel same-origin proxy is forwarding requests to the Render API, so the frontend can reach the API; the confirmed failures occur inside the backend's sign-in/registration flow.
- The existing `source/apps/api/app/routes/auth.py` contains a login-context repair but is outside Render's configured root directory, and its registration flow still needed the missing registration context. The hotfix package deliberately places the fixed file at the repository root path `apps/api/app/routes/auth.py`.

## Fix included in the hotfix package

### Login flow

1. Normalize the submitted email.
2. Establish an email-scoped transaction-local pre-tenant login context before querying `users`.
3. Verify the password as before; incorrect credentials still fail closed.
4. Set `app.user_id` and clear the pre-tenant login context before looking up active workspaces.
5. If a correct-password account has no active workspace, return an explicit `NO_ACTIVE_WORKSPACE` response instead of a misleading generic password failure.
6. Do not relax RLS or expose account rows globally.

### Registration flow

1. Generate/validate the idempotency key as before.
2. Before the first `registration_requests` read/write, set `app.pre_tenant_access='registration'`, the normalized email, and the exact `app.registration_key` using transaction-local `set_config(..., true)`.
3. Keep this tightly scoped context through the idempotency record's update and commit.
4. Once the new user and tenant IDs exist, set both `app.tenant_id` and `app.user_id` before tenant-owned inserts.
5. Keep the existing rate limit, idempotency protection, rollback behavior, error reporting, password hashing, and forced RLS policies. No bypass policy is added.

## Local verification

Commands executed under `/mnt/data/lexa_phase8_work/source/apps/api`:

```bash
APP_ENV=development \
DATABASE_URL='postgresql+psycopg://test:test@127.0.0.1/test' \
REDIS_URL='redis://127.0.0.1:6379/0' \
JWT_SECRET='test-only-jwt-secret-for-login-context-contract' \
PYTHONPATH=. python -m pytest -q \
  tests/test_auth_login_workspace_context.py \
  tests/test_auth_refresh.py \
  tests/test_phase1_runtime_security.py
```

Result: **13 passed, 1 warning**. Python `compileall` also passed across the candidate source.

The new/updated regression tests cover login RLS-context ordering, workspace lookup context, wrong-password behavior, the email/key registration context, and the requirement that registration establishes context before the first idempotency insert.

These are focused local/unit checks—not a full live login E2E run. A real sign-in cannot be confirmed until the corrected API file is published and deployed.

## Deployment blocker and safe next step

A GitHub branch-creation attempt for an incident hotfix was rejected with `403 Resource not accessible by integration`. The write was not retried. No GitHub commit, Render deployment, Vercel deployment, or database policy change was made during this investigation.

After repository write access is restored, overlay the `apps/api/` paths from this package onto the **repository root** (not under the nested `source/` directory), run the focused tests in CI, and publish the correction to the `main` branch used by Render. Render has automatic deploys enabled for `main`; confirm its exact deployed commit and then exercise both sign-in and new workspace registration with a test account. Do not weaken RLS, manually set a user's password without an approved recovery path, or change the production policies to accommodate the buggy route.

## User safety / privacy

- Do not ask the user to paste their password, one-time codes, mobile-money PINs, or session cookies.
- Do not reset the user's password as a substitute for fixing the authorization-context defect.
- Avoid repeated sign-in and registration attempts until the hotfix is deployed; the current code can continue to return misleading errors.
- Production database and business data remained unchanged during this investigation.
