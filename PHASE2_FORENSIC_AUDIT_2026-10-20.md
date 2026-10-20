# LEXA Phase 2 — Forensic Platform Audit

**Audit date:** 20 October 2026 (UTC)  
**Scope:** LEXA only — GitHub repository `MONALISA2003-CMD/LEXA-`, Vercel project `lexa`, Render service `LEXA`, Neon project `LEXA` / default branch `lexa-live`.  
**Mode:** Read-only inspection of hosted systems. Local source changes and a new source-package candidate are separate from hosted state. No production deployment, GitHub write, Render settings change, Neon SQL mutation, role/password change, or branch change was performed as part of this audit.

## Executive decision

**NO-GO for Phase 3. Phase 2 is not yet release-certified.** Multiple independently confirmed blockers remain: the archive workflow nests the repository under an extra directory so updates do not replace the live root; the newest Vercel build still fails TypeScript; Render is currently serving a backend implementation that returns repeatable HTTP 500 responses; the live database login role has excessive privileges; and historical migration source recovery is incomplete.

A passing `/ready` endpoint proves the API process can access its declared dependencies. It does not prove commerce endpoints, token refresh, tenant isolation, or end-to-end user workflows are healthy.

## Confirmed findings, highest priority first

### P0 — Deployment archive paths do not overlay the configured project root

The previous Phase 2 packager wrote every ZIP entry beneath `LEXA-Phase1-2.9.1/`. The repository's deployment automation extracted those literal entry paths into GitHub. A read-only comparison of the latest commit (`b309ea7ea78a62f654d214ec26c761f2ef38fd0a`) against its parent confirms the modified app files are under `LEXA-Phase1-2.9.1/apps/web/...`, rather than active root paths such as `apps/web/...` and `apps/api/...`.

The hosted services are configured against the root project paths: Vercel builds the Next.js root project, and Render's service root is `apps/api`. The Render live deploy is still on commit `b7da77cda94424326b777d87d7612974e67dceab`, while the GitHub main branch has advanced to `b309ea7...`. Thus a newer source ZIP commit did not update the active service trees. This is why fixes in a nested source folder can coexist with the old TypeScript failure and API exception.

**Local remediation in this candidate:** the package script now writes repository-relative entries directly at ZIP root and checks for required paths. It rejects an enclosing `LEXA-Phase1-2.9.1/` directory. This is a package/source fix only; it has not been deployed or proven by the external ZIP extractor yet.

**Release gate:** unpack into a clean directory; assert `apps/web/app/page.tsx`, `apps/api/app/routes/commerce.py`, `render.yaml`, `.github/workflows/lexa-ci.yml`, and `migrations/README.md` exist at extraction root; then verify the next commit contains changes at these exact active paths.

### P0 — Latest Vercel production-target build is failing

Latest inspected Vercel deployment:
- Deployment: `dpl_HbqTRZgPi5Vm8Rqhfc91B8qG681P`
- Source commit: `b309ea7ea78a62f654d214ec26c761f2ef38fd0a`
- State: `ERROR`
- Error code: `lint_or_type_error`
- Failed command: `npm run build`

Build events report `TS18047` at `app/page.tsx` lines 91 and 93: `dashboard` and `analytics` may be `null`. Values in the Command Centre had a null guard, but their small descriptive text still dereferenced the nullable objects. The static tests in the nested package check that fix; they cannot repair active root source until the archive layout is corrected.

Three recent deployment attempts were reported as errors with the same typecheck failures. The newest commit has a failing Vercel status check. GitHub `main` currently has branch protection disabled and no required status checks, so the known failure does not stop another commit/package from landing on `main`.

**Release gate:** deploy from the corrected root paths; run Node 24.x `npm ci`, `npm run typecheck`, frontend tests, and `npm run build`; require the successful Vercel deployment and checks for the exact same commit before promoting aliases.

### P0 — Render commerce dashboard returns HTTP 500

Live Render logs on the latest service instance show repeated requests to:

`GET /api/v1/commerce/dashboard?business_date=...` → `500 Internal Server Error`

The stack trace reports:

`sqlalchemy.exc.NoSuchColumnError: Could not locate column in row for column '_mapping'`

The source cause is `apps/api/app/routes/commerce.py::out()`, which accesses `row._mapping`. Several call sites use `.mappings().one()` or `.mappings().all()`, which return mapping objects rather than SQLAlchemy `Row` objects. The serializer fails on those mapping objects. This is a code defect, not a database availability issue. The same helper is used across commerce handlers, so the affected surface may be broader than the dashboard; other endpoint failures must be tested after the fix.

Inventory balances and ledger requests were logged as 200 in the same observed window. The API `/health` and `/ready` endpoints returned healthy JSON, including database and cache dependencies. No Render request-log entries were returned through the request-type query; the application log contained the Uvicorn access records.

**Local remediation in this candidate:** `out()` now supports `collections.abc.Mapping` directly and falls back to `row._mapping` for SQLAlchemy `Row`. New regression tests exercise a `.mappings().one()` result, a normal `.one()` row, and Decimal output formatting. These need to pass in local CI and be observed after the corrected backend is deployed.

### P1 — The live Neon login role is not least-privilege

Read-only inspection of Neon `LEXA`, default branch `lexa-live` (`br-soft-star-b1dj2m2w`), database `neondb`, found active pooled connections under `lexa_runtime`. The role currently has `LOGIN`, `CREATEDB`, `CREATEROLE`, `REPLICATION`, and `BYPASSRLS`; it is a member of `neon_superuser` with inherit/set enabled. This role has significantly broader authority than the application should normally need.

Migration `029_phase1_runtime_role_least_privilege` is not recorded in the live migration ledger and the intended `lexa_runtime_safe` role is absent. The checked-in migration source/runbook describe this isolation, but the canonical live branch has not adopted it. This is a security release blocker until a reviewed, approved rollout has been applied and verified against the actual Render connection configuration. Do not fix this by casually changing a role or connection string: the migration and runtime credential transition require a controlled change window, rollback plan, and explicit approval.

### P1 — Seven applied historical migrations lack exact SQL source

The live ledger includes migration versions whose original SQL is absent from the current source package. Tracked gaps include `010`, `011`, `023_phase4_purchasing_core`, `024`, `025`, `026`, and `027_release_convergence`. The source tree tracks these in `migrations/source_gaps.json`; the duplicate numeric `023` prefix also means migration tooling must use full version strings rather than numeric prefixes alone.

This prevents a strict, source-grounded from-zero migration replay. Do not recreate missing historical SQL by guessing from current tables. Recover exact SQL from an authoritative historical Git commit/release artifact, checksum/review it, then run the complete chain on a disposable database/branch. A live schema that currently responds does not prove the repository can reconstruct it.

### P1/P2 — Registration idempotency table has no RLS policy

On `lexa-live`, `public.registration_requests` contains `tenant_id` but row-level security is disabled and there are no policies; it also stores email, request hash, replay response body, and optional user/tenant IDs. This may be an intentional pre-tenant/global idempotency record, but the rationale and threat model are not evident from runtime policy metadata. Review whether the data must be global, scope it safely if appropriate, and add a test proving anonymous registration replay cannot read or modify another request. Treat this as a defense-in-depth concern pending that review, not as proof of an exploitable vulnerability.

### P1 — Render's actual health-check setting differs from source blueprint

Render's hosted service metadata reports `healthCheckPath` as empty. Repository `render.yaml` specifies `/ready`. `/ready` returns `status=ready` with database and cache `ok`, but the platform is not configured to use it for health gating according to the metadata. Correct configuration drift through the normal approved release procedure and confirm the setting after deployment.

### P1 — No GitHub Actions run is recorded for the latest main commit

The checked-in `.github/workflows/lexa-ci.yml` declares a `push` trigger for `main`, with frontend Node 24 install/typecheck/test/build and backend regression jobs. But a read-only query of the GitHub Actions runs API for latest main commit `b309ea7ea78a62f654d214ec26c761f2ef38fd0a` returned `total_count: 0`. In other words, this commit has no recorded CI run; the failing Vercel deployment is the only observed check for it.

The commit was authored/committed by `github-actions[bot]` and describes itself as an automatic ZIP extraction. One plausible cause is that the extraction automation pushes with `GITHUB_TOKEN`, which by default does not trigger downstream workflow runs for `push` events. The credential used by the extractor was not inspected, so that cause is an inference, not confirmed. GitHub documents the suppression behavior in [Triggering a workflow](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).

**Release gate:** identify the extraction bot's auth mechanism; ensure root-source updates invoke the intended CI (e.g. an approved GitHub App/PAT-based event or explicit `workflow_dispatch`); and require evidence of successful CI for the exact ZIP-derived commit. Do not treat the existence of a workflow file as proof that CI ran.

### P2 — Main branch accepts failed checks

The latest commit has a failing Vercel status check; the repository's `main` branch reports `protected=false` with required status checks disabled. For a release with live API and security issues, this is not an acceptable quality gate. Require successful frontend typecheck/build, backend regression tests, migration-source reconciliation, and packaging-layout tests before main is treated as releasable.

## Neon operational findings

Read-only checks confirmed the expected `lexa-live` branch is primary/default and `ready`, the database is `neondb`, all 28 queried core required tables are present, migration 028 is recorded, and `public.lexa_find_session_by_refresh_hash(text)` exists. Its `SECURITY DEFINER` owner has `BYPASSRLS`, `lexa_app` can execute it, PUBLIC cannot, and the function pins `search_path=pg_catalog, public`. Three other enumerated SECURITY DEFINER functions also had pinned search paths and PUBLIC execute was false.

Point-in-time database diagnostics found no query older than five minutes and no held locks. This is a snapshot, not a load or resilience test. The live branch is not marked protected, its allowed-IP list is empty, public connections are not blocked at the project level, and retained history is six hours. Review branch protections, connection exposure, backup/restore and recovery objectives as part of the operational security gate.

The auth-refresh 500s seen in Render logs were on 13 October before migration 028 was applied later that day. They should be treated as historical evidence; no comparable auth-refresh 500 was present in the inspected 13–20 October 500-log result after the later rollout. Still run current sign-in, expiry, rotation, replay, revocation and session-refresh tests against the deployed root source.

## Phase 2 scope still incomplete

Phase 2 cannot be considered complete based only on a shared token layer and a few shared-component adoptions. The following remain release gates:

1. **All routes:** migrate/audit the shared design system across all 16 identified page routes, including Products, Inventory, Sales, Commerce, Customers, Purchasing, Accounting, Reports, Compliance, Intelligence, Administration, Settings, Login, Register, Invite, and the home Command Centre. Confirm the correct empty, loading, permission-denied, validation, stale-data, API-error and success states on each.
2. **Responsive behavior:** browser verify at narrow phone widths (360/390/430), tablet (768), and desktop (1280+); check overflow, side-navigation, tables, dialog positioning, keyboard viewport, safe-area insets and touch sizes.
3. **Accessibility:** keyboard-only navigation; visible focus; focus order and restoration; dialog containment/escape behavior; form labels/errors; live announcements for async states; contrast; reduced motion; screen-reader checks.
4. **Actual frontend build:** Node 24.x clean install, typecheck, frontend tests and production build on root source, not the nested folder; then inspect browser console and requests on a successful deployment.
5. **Backend handler tests:** fix the serializer and add tests for its use across dashboard, customer, payment-channel, sale/payment, reconciliation and other `.mappings()` call sites. Exercise normal Row and RowMapping shapes; verify numeric/Decimal/date/UUID serialization and nullable/empty results.
6. **End-to-end business workflows:** sign-in, workspace selection, token refresh and expiry; product create/edit/lookup; inventory balances/ledger/counts/transfers; sale/payment/return; customer/credit; purchasing; accounting/reconciliation; reporting; permissions/tenant boundary checks. Use disposable/test workspaces and non-destructive test data.
7. **Database source and role:** recover seven exact migration sources, strict clean replay, document duplicate migration prefix handling, and complete the least-privilege application role transition with explicit approval and rollback plan.
8. **Same-commit release evidence:** root ZIP layout, source hash, Git commit, Vercel build, Render deploy, Neon migration version, and smoke-test report must all refer to the intended candidate. A successful service on an older commit is not proof that the new source works.
9. **Monitoring and rollback:** verify `/ready` is configured in Render, add alerts for 5xx bursts, maintain a short post-deploy smoke test and a documented rollback procedure.

## Candidate-local fixes and test intent

This source candidate includes local fixes for the commerce serializer, additional tests for RowMapping/Row output and a stronger Command Centre null-guard regression test. It also corrects the ZIP packager to use repository-root-relative entries and to require the active service/config files in the archive. These changes have **not** been applied to hosted systems in this audit.

## Exact release decision criteria before Phase 3

Do not start Phase 3 until:

- The corrected ZIP is unpacked with no enclosing project directory; root-path contents are inspected.
- Root source passes Node 24 typecheck, all tests and production build.
- The commerce serialization fix and its regression tests are deployed to Render, and the previously failing dashboard plus representative commerce routes return expected non-5xx responses.
- The successful Vercel deployment and live Render deploy use the same intended root source commit; all release checks are green and branch protection prevents failed-check promotion.
- Neon least-privilege rollout is reviewed, explicitly approved, applied and verified; the registered runtime role is not a superuser-like login and tenant boundary tests pass.
- Historical migration source gaps are recovered and strict migration replay succeeds in a disposable environment.
- Responsive, keyboard/accessibility, and E2E smoke checks are recorded against the successful candidate.

**Audit limitation:** no authenticated business-user browser journey or live write workflow was executed, to avoid modifying user data. The findings above distinguish observed logs/configuration/schema from unverified risks and local candidate fixes.

## Local candidate verification (after the audit)

- Frontend static/contract suite: **18 passed, 0 failed** (`node --test tests/*.test.mjs` from `apps/web`).
- Backend regression suite: **112 passed, 1 skipped** (`python -m pytest -q tests apps/api/tests`). The one skip is `apps/api/tests/test_auth_refresh.py`, which requires the Redis package not available in this local environment.
- Focused serializer and Phase 1 runtime-security tests: **8 passed**. The serializer tests cover both SQLAlchemy `RowMapping` and `Row` results and Decimal formatting.
- Python `compileall`/`py_compile` and shell `bash -n` validation: passed.
- Migration-source reconciliation: ran and reported **seven unresolved exact-source gaps**. Strict from-zero replay remains blocked.
- Frontend `npm run typecheck`: attempted but **not passed locally**. Installed `node_modules` does not contain the actual `react`/`next` packages and type declarations; TypeScript reports `TS2307` for those modules followed by JSX-type cascade errors. The available runtime is Node `v22.16.0`, while this project declares `24.x`. A clean install at Node 24 and actual build remain mandatory; static contracts are not a substitute.
- ZIP verification: **220 source files plus the internal manifest**, CRC passed, byte-for-byte and per-file SHA-256 checks passed, required active-root paths present, no `LEXA-Phase1-2.9.1/` enclosing prefix, and no actual secret environment files included. The external manifest's archive SHA-256 matches the ZIP.

These local test results do not change the hosted findings above: no build/deploy or mutation was run against hosted systems in this audit.
