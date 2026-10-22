# LEXA — Phase 8 Finance Implementation Candidate (22 October 2026)

**Implementation status: source candidate with targeted local acceptance; not production-approved.** This package extends the Phase 7 candidate with plain-language finance workflows: customer collections/balances, supplier payables via the existing supplier ledger, expenses, owner-configured payment methods, manual end-of-day checking and finance reporting.

**Payment boundary:** LEXA records a business user's chosen payment method and amount. It does not initiate, transfer, settle or automatically verify money. No payment gateway or payment-provider credentials are included or requested.

- [Phase 8 implementation report](PHASE8_IMPLEMENTATION_REPORT_2026-10-22.md)
- [Phase 8 onwards architecture handoff](LEXA_PHASE8_REVISED_ARCHITECTURE_AND_IMPLEMENTATION_PLAN_2026-10-22.md)

Phase 12 remains the single full production-readiness and launch gate. The report above lists exact test results and the remaining disposable-database, Node 24 build and browser acceptance checks. Historical Phase 7 reports below are retained as baseline evidence and are not Phase 8 completion evidence.

---

# LEXA — Phase 7 Purchasing & Supplier Management (v2.12.0, Increment 03 — 22 October 2026)

**Release decision: NO-GO for production.** This is a full-source repair archive, not a deployment certificate. It fixes two live-log-confirmed backend failure patterns (supplier-payment Pydantic validator override and post-commit ORM refresh 500s), adds regression tests, and records exact backend/database/hosting evidence and blocked gates.

- **Deep audit report:** [`PHASE7_DEEP_AUDIT_ACCEPTANCE_REPORT_2026-10-22.md`](PHASE7_DEEP_AUDIT_ACCEPTANCE_REPORT_2026-10-22.md)
- **Release gate status:** [`PHASE7_INCREMENT_03_RELEASE_GATE_STATUS_2026-10-22.json`](PHASE7_INCREMENT_03_RELEASE_GATE_STATUS_2026-10-22.json)
- **Manual Neon replay evidence:** [`PHASE7_REMOTE_REPLAY_EVIDENCE_2026-10-22.json`](PHASE7_REMOTE_REPLAY_EVIDENCE_2026-10-22.json)
- **Unblock checklist:** [`PHASE7_CI_AND_RELEASE_UNBLOCK_CHECKLIST_2026-10-22.md`](PHASE7_CI_AND_RELEASE_UNBLOCK_CHECKLIST_2026-10-22.md)
- **Increment 03 notes:** [`RELEASE_NOTES_2.12.0_PHASE7_INCREMENT_03.md`](RELEASE_NOTES_2.12.0_PHASE7_INCREMENT_03.md)

## What Increment 03 fixes

Render logs repeatedly emitted a warning that `SupplierPaymentCreate.validate_allocations` overrode an earlier Pydantic validator. The class contained two same-named methods and the surviving validator called `validate_payment_allocations` without importing it. The fix imports the shared validator, keeps one method and adds executable regression tests for valid allocations, duplicate bill allocations and over-allocation. Render also showed `Could not refresh instance` errors for category/branch creation after commit; the affected catalog/organization/RBAC routes no longer issue a redundant post-commit refresh SELECT under transaction-local RLS. A regression contract protects this behavior. These repairs are source-only: current GitHub `main` and Render do not yet contain this source change because GitHub writes returned 403.

## Observed verification

- Backend suite: **211 passed, 1 skipped** (offline environment lacks Redis Python package; CI must run it with Redis and no skip).
- Frontend contracts: **38 passed**.
- Static frontend action/destination audit: **PASS** — 29 files, 153 controls, 35 forms, 33 links.
- Python compileall and strict source reconciliation: **PASS**.
- Plan-only migration check: **43 inputs** and SHA-256 `2d446ba3c0df5903b06ed0dbb92e1c2239f353aa69cc40e80d452ecb78ec1674`.
- Actual remote disposable PostgreSQL replay: 43 ordered SQL inputs executed, migration 039 present in the test DB, 126/126 public tables with forced RLS, all six Phase 7 tables with tenant policies, cross-tenant and branch-scope probes passed. The checksummed `artifacts/phase6-replay-evidence.json` passes the evidence checker for the current baseline SHA and migration bundle. This is manual remote evidence, not CI.
- Vercel `READY` on baseline commit `b920c8719079741ed3c2fb2288de67c7de8a0d37`. Render still live on older `dd4069109d5c94143f5c5e28e758128b90dee55a`.

## Why release remains blocked

The GitHub Actions CI workflow is absent from deployed `main` and the connected GitHub integration denied writes with 403; exact-SHA CI did not run. The API patches are not deployed, authenticated staging E2E has no isolated target/fixture/state, Render health-check path is blank despite `/ready` in `render.yaml`, the canonical `lexa-live` Neon schema remains at 031, and the available Neon snapshot API will not snapshot this non-root app branch. The project has no snapshots/schedule and branch capacity is exhausted; restore readiness remains unproven. **Do not apply migrations 033–039 in production or claim this release green.**

Phase 7 scope follows [`FRESH_NEW_PRODUCT_STRATEGY.md`](FRESH_NEW_PRODUCT_STRATEGY.md), especially supplier terms, PO lifecycle, partial receipts, landed costs, returns, bill matching and supplier balances. The approved historical Phase 3 replacement disposition remains closed; exact historical byte parity is not claimed.

---

## LEXA — background and historical handoffs

# LEXA — v2.9.0 Phase 1 UX Foundation Handoff

LEXA is a real multi-tenant business operating and intelligence system. The canonical business system of record is Neon PostgreSQL project `LEXA`, branch `lexa-live`, database `neondb`.

## Phase 0–2 closure candidate (Increment 06 — 20 October 2026)

**Current decision: Phase 3 schema-changing work remains NO-GO.** The exact `027_release_convergence.sql` source has been recovered and verified against its Git blob; six exact historical migrations still need authoritative recovery. This candidate adds date/proxy/navigation hardening, responsive sign-in refinements, UI/UX research, stronger tests, root CI workflow source and a security/role-cutover runbook. Production roles/settings/data have not been changed.

- **Current closure audit:** [`docs/PHASE0_2_CLOSURE_AUDIT_2026-10-20.md`](docs/PHASE0_2_CLOSURE_AUDIT_2026-10-20.md)
- **UI/UX research:** [`docs/research/LEXA_PHASE0_2_UI_UX_RESEARCH_2026-10-20.md`](docs/research/LEXA_PHASE0_2_UI_UX_RESEARCH_2026-10-20.md)
- **Security/cutover runbook:** [`docs/PHASE0_2_SECURITY_CUTOVER_RUNBOOK.md`](docs/PHASE0_2_SECURITY_CUTOVER_RUNBOOK.md)
- **Migration source lineage:** [`migrations/SOURCE_RECOVERY.md`](migrations/SOURCE_RECOVERY.md)

The hosted platform’s prior green commit is not the same as a clean CI build of this local candidate. GitHub root workflow installation/branch protection, production role/RLS rollout, Render's health-check setting, full Node 24 build and authenticated E2E remain open. Do not treat packaging as deployment or deploy source changes without the approved release procedure.

## Current product direction and first increment

- **Authoritative product direction:** [`docs/LEXA_STATEMENT_OF_TRUTH_2026-10-19.md`](docs/LEXA_STATEMENT_OF_TRUTH_2026-10-19.md)
- **First increment evidence and blockers:** [`docs/LEXA_FIRST_INCREMENT_IMPLEMENTATION_REPORT_2026-10-19.md`](docs/LEXA_FIRST_INCREMENT_IMPLEMENTATION_REPORT_2026-10-19.md)

These documents distinguish locked product decisions from source-documented implementation and hosted acceptance that remains pending. They do not imply a production deployment.

## Production hardening carried forward from v2.5.0

This release repairs the production weaknesses identified during the Phase 1 deep review:

- restricted `lexa_app` PostgreSQL role applied per transaction for PgBouncer-safe RLS
- bounded SQLAlchemy connection pooling and PostgreSQL timeouts
- production fail-closed environment validation
- Redis-backed login and registration rate limiting
- HttpOnly refresh-cookie rotation and memory-only access-token handling in the web app
- removal of the open-development workspace bootstrap from the shipped API and browser
- removal of the user-facing Business Engine route module
- production security response headers and generic 5xx browser responses
- migration `022_phase6a_brain_foundation` added to source convergence
- GitHub CI for backend/frontend contract verification
- direct Neon backup script using the unpooled migration/backup connection

## Phase 0 reliability increment

- Cookie refresh is single-flight, sends an explicit empty JSON body, and is accepted by the API even when the body is omitted.
- Protected business requests restore the session before loading; workspace pages are hidden while session verification is unresolved.
- Failure states no longer present dashboard request failures as zero-valued business metrics.
- Vercel runs the standard `npm run build` from `apps/web`; obsolete technical UI routes were removed.

## Canonical deployment

Vercel serves `apps/web`. Render serves `apps/api`. Neon PostgreSQL is the only authoritative LEXA business database. Do not create a second transactional database.

See `docs/MANUAL_DEPLOY_v2.5.0.md` for the exact manual handoff procedure.

## Phase 0 final auth/RLS increment (v2.8.5)

- Cookie refresh now resolves the session through an opaque-token hash lookup, establishes tenant/user context, and rotates under a row lock.
- `/api/v1/auth/me` is the authoritative identity contract used before the web workspace unlocks.
- Protected database requests establish both tenant and user context for branch-aware RLS.
- Migration 028 hardens empty RLS context and assigns a least-privilege Member role only to active memberships that currently have no role. Apply it only after checking the canonical Neon migration ledger.
- Readiness in this source package verifies migration 028 and its SECURITY DEFINER refresh lookup before reporting healthy.
- Migration 028 was promoted to canonical Neon branch `lexa-live` after explicit approval. The live ledger row, lookup function, `lexa_app` grant, SECURITY DEFINER/RLS owner properties, and safe tenant policy expressions were verified after promotion.
- Render logs confirmed the screenshot path: `/api/v1/auth/refresh` returned 500 because the lookup function was missing before migration 028. The previously failed refresh hash now resolves to one unrevoked, unexpired session through the new function.
- Full browser/API acceptance is still pending. Render’s live `healthCheckPath` is blank while `render.yaml` declares `/ready`, and GitHub `main` still has the older health-readiness check. The Vercel `lexa-green.vercel.app` production deployment and both API-origin variables match the Render API and same commit, but the newly added readiness guard is not yet deployed. No repo write or application deployment was performed here; deploy this reviewed ZIP and verify the live browser/API flow before declaring Phase 0 complete.
- See `LEXA_E2E_FORENSIC_AUDIT_2026-10-13.md` for the full evidence trail and exact acceptance checklist.


## Historical Phase 0 reliability handoff snapshot (15 October 2026)

**This section is a dated historical snapshot. The current Increment 06 source gaps, tests and go/no-go decision are recorded at the top of this README and in `docs/PHASE0_2_CLOSURE_AUDIT_2026-10-20.md`.**

This package includes additional source-side hardening and release gates:

- Corrected the dynamic Brain RLS policy SQL in migration 022 using `format(%I, %L)` and verified the generated policy expressions on a disposable Neon validation branch.
- Added refreshed read-only canonical Neon ledger evidence dated 15 October 2026 and an explicit manifest of unrecovered historical migration SQL sources.
- Added `scripts/check_migration_sources.py`; normal mode ensures all gaps remain documented, while `--strict` fails until the exact migration sources are recovered.
- Corrected deployment documentation to treat `/health` as liveness and `/ready` as dependency-aware database/cache readiness. The readiness check now verifies Redis/Valkey using bounded timeouts.
- Recovered `019_phase4a_customer_credit_allocation.sql` byte-for-byte from historical GitHub commit `d850ce04c8930134f01a63cd65c5d1947a17b17d` (verified Git blob SHA documented in `migrations/SOURCE_RECOVERY.md`).
- Added `scripts/smoke_phase0.py` for public liveness/readiness/bodyless-auth probes and optional credentialed login/refresh/me/protected-read/logout acceptance.
- Added `pytest.ini` to exclude archived package copies from canonical test collection, fixed API test import paths, and separated the strict migration replay gate from ordinary code CI.
- Added `scripts/apply-deletion-manifest.sh` and marked the obsolete unregistered backend Business Engine route module for removal from existing checkouts.
- Added a complete `apps/web/package-lock.json` and changed CI to use `npm ci` for deterministic frontend dependency installation.
- Aligned `render.yaml`'s blueprint service name to the existing Render service `LEXA` so this package does not imply creating a second `lexa-api` service. The blueprint declares `/ready`; the live Render service setting still needs reconciliation.

**This is not a claim that Phase 0 is fully accepted.** Current local checks report 104 passed and 1 skipped (the local offline environment lacks the `redis` dependency); frontend contract tests pass. A disposable-branch SQL check confirms the corrected Brain policy block compiles. On 15 October, live Render `/health` returned 200, `/ready` returned 200 with the older database-only payload, bodyless refresh returned 401 instead of 422 on retry, and anonymous logout returned 200. Seven applied migration SQL sources remain absent from the inspected repository history: 010, 011, 023 purchasing core, 024 purchasing security, 025 purchasing permissions, 026 membership/branch integrity, and 027 release convergence. Their SQL was not reconstructed from schema inference. The strict migration source check intentionally remains blocked until authoritative source files are recovered. GitHub branch creation was denied, so this is a local source package rather than a pushed commit. Live Render still returns the older readiness payload (database only), the live health-check path is blank, and credentialed browser sign-in/refresh/logout acceptance remains pending.


For execution order and dedicated-account smoke acceptance, see `docs/PHASE0_RUNBOOK.md`. The current detailed acceptance status is `docs/PHASE0_IMPLEMENTATION_REPORT.md`.


## Phase 1 UX foundation (15 October 2026)

Version 2.9.0 carries the Phase 1 UX foundation implementation from the product/UX roadmap. It adds responsive shared UI states and table/card components, a four-action primary navigation plus More menu, readiness-linked service copy, a sign-in pass with workspace selection and password reveal, and resumable first-workspace setup that creates branch/warehouse/location defaults transactionally. API error language is centralized and the registration idempotency digest now binds all registration inputs.

The handoff is source-only: the updated build is in the Phase 1 ZIP. On this runner, **104 Python tests and 3 frontend static contract tests passed, with one Python auth-refresh test skipped because the local environment lacks `redis`**. A local frontend dependency install/typecheck/build could not run because the npm registry was unavailable and `undici-types` was not cached; CI is configured to execute `npm ci`, typecheck, tests, and build with Node 24. The five-width visual screenshot checklist and credentialed hosted auth acceptance remain pending.

The Phase 0 blockers remain release blockers: six exact historical migration SQL sources are still missing, hosted production readiness settings still require reconciliation, and GitHub write access returned 403. No production deployment or canonical Neon schema mutation was performed in this pass. See `docs/PHASE1_UX_IMPLEMENTATION_REPORT.md` and `docs/PHASE1_UX_RUNBOOK.md`.

## Phase 1 security and stability candidate (19 October 2026)

This source-only candidate adds a separately provisioned least-privilege database login (`lexa_runtime_safe`), production validation for the expected database login role and TLS/pooler URL, and transaction-local role switching for direct readiness connections. It includes migration `029_phase1_runtime_role_least_privilege.sql`, the regression suite, and a repeatable verification script.

**No production change is implied by this package.** The new role must be provisioned and verified on an isolated Neon branch, given a password through secret management, and only then configured in Render during an explicitly approved release. The old elevated `lexa_runtime` role remains unchanged until a safe cutover and separate decommission plan.

See `docs/PHASE1_SECURITY_STABILITY_RUNBOOK.md` and `docs/PHASE1_SECURITY_STABILITY_REPORT_2026-10-19.md`. Run `bash scripts/verify-phase1.sh` from the repository root. Strict full migration replay remains blocked by six remaining missing historical SQL sources; frontend typecheck/build and credentialed hosted authentication acceptance remain release gates.

## Phase 0–2 closure evidence (2026-10-20)

See [`reports/LEXA_Phase0-2_Closure_Increment_08_2026-10-20.md`](reports/LEXA_Phase0-2_Closure_Increment_08_2026-10-20.md) for the historical ZIP scan, isolated replay results, CI/hosting access blockers and Phase 3 re-entry gates. The six missing SQL sources remain explicitly unresolved; reconstructed equivalents are isolated under `migrations/reconstructed/` and do not satisfy exact source recovery.


## Historical Phase 5 core-hardening candidate (2026-10-21 — superseded)

This section records a previous candidate snapshot only. Its test counts, version, and blocker language are historical and are not the current source of truth. The current candidate is **2.10.0+phase6.increment01**. Read `PHASE6_IMPLEMENTATION_REPORT_2026-10-21.md`, `PHASE6_RELEASE_GATE_STATUS_2026-10-21.json`, and `PHASE6_ENTRY_POLICY.md` for current evidence. In particular, the six Phase 3 source recovery tasks are permanently dispositioned as replacements; they must not be reopened. Clean semantic replay, Node 24 CI, authenticated isolated staging, candidate-specific deployment parity, and approved production migration rollout remain separate release gates.

