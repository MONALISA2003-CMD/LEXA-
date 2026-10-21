# LEXA --- Continuation Handoff for Phase 2 and Beyond

**Prepared:** 20 October 2026\
**Purpose:** Give a new LLM/engineering agent enough product direction,
repository context, implementation history, safety boundaries, known
blockers, and ordered next steps to continue LEXA from Phase 2 onward
without losing decisions or repeating prior investigation.

> **Current truth:** Phase 1 has a prepared, tested source ZIP, but it
> has not been pushed to GitHub or deployed. Production was not changed.
> Continue from the Phase 1 ZIP as the current working candidate, not
> from an assumption that it is already live.

## 1. Start here --- canonical handoff artifacts

Use these artifacts as the first sources of truth:

1.  **Phase 1 complete source candidate:**\
    `LEXA_Phase1_Security_Stability_2.9.1_FULL_SOURCE_2026-10-19.zip`\
    SHA-256:
    `80dc30df29010e527675596d489e030bd5f044920fb4d6ce123e7aa45b6698bc`
2.  **Product/implementation direction:**
    `LEXA_STATEMENT_OF_TRUTH_2026-10-19.md` (summarized in this handoff;
    retain its binding principles).
3.  **Module inventory:**
    `LEXA_PHASE_0_MODULE_COMPLETION_MATRIX_2026-10-19.md`.
4.  **Infrastructure status:**
    `LEXA_INFRASTRUCTURE_STATUS_2026-10-19.md`.
5.  **Security evidence:** `LEXA_SECURITY_AUDIT_2026-10-19.md` and
    `LEXA_SECURITY_AUDIT_UPDATE_2026-10-19.md`.
6.  **Deep-dive evidence:** `LEXA_DEEP_DIVE_2026-10-19.md`.
7.  Inside the Phase 1 ZIP, read first:
    -   `PHASE1_ZIP_README.md`
    -   `docs/PHASE1_SECURITY_STABILITY_REPORT_2026-10-19.md`
    -   `docs/PHASE1_SECURITY_STABILITY_RUNBOOK.md`
    -   `FIRST_INCREMENT_HANDOFF.md`
    -   `LEXA_PACKAGE_MANIFEST.json`

The Phase 1 ZIP is a full source handoff artifact. Its previously
supplied download URL in ChatGPT was:
`sandbox:/mnt/data/LEXA_Phase1_Security_Stability_2.9.1_FULL_SOURCE_2026-10-19.zip`

If the artifact is not present in the new agent's environment, ask the
user to attach it. Do not infer or fabricate a sandbox path.

## 2. Product mission and non-negotiable direction

**LEXA is a multi-tenant business operating and intelligence system for
the people who run a business.** Initial focus:

1.  Retail and shops.
2.  Distribution and wholesale.
3.  Multi-branch / multi-location businesses.

Product promise: **"Run the business. Trust the numbers. Know what needs
attention."**

The primary goal is dependable daily operations first. Intelligence
comes after the operational data, permissions, and workflows are
trustworthy. LEXA should be one adaptive workspace that responds to the
user's role, permissions, tenant, and authorized branch/location
scope---not a disconnected collection of apps.

### Binding product principles

-   **Operations before intelligence.** Finish real daily workflows
    before broad AI functionality.
-   **One adaptive workspace.** Roles can include owner, manager,
    cashier, storekeeper, purchasing, finance, and administrator. UI
    adaptation is useful, but the server must enforce permissions.
-   **One transactional source of truth.** Neon PostgreSQL is canonical.
    Do not introduce a second transactional database.
-   **Never invent zeroes.** Failed, forbidden, unavailable, or
    still-loading data must not be shown as zero or an empty business
    state.
-   **Never claim success prematurely.** A mutation is successful only
    after server confirmation. If a timeout leaves outcome uncertain,
    communicate uncertainty and provide safe retry/reconciliation
    behavior.
-   **Tenant and branch isolation are foundational.** Server-side
    authorization plus database RLS; never rely on hidden UI controls.
-   **Critical operations are auditable and retry-safe.** Use consistent
    transaction boundaries, audit records, idempotency for retryable
    writes, and outbox patterns where appropriate.
-   **Mobile-first and accessible.** Clear
    loading/empty/error/forbidden/validation/success states,
    keyboard/focus behavior, readable contrast, responsive navigation,
    and usable small-screen workflows.
-   **Core operations must not depend on AI.** Selling, stock movement,
    payment recording, permissions, and reporting continue to work if
    models are unavailable.
-   **Intelligence must be evidence-grounded and initially read-only.**
    Explanations should point back to verified facts. Any future
    controlled action must use prepare → review/approve → execute, with
    audit and idempotency.
-   **No invented completion claims.** A route, green deployment,
    successful build, or migration ledger row does not establish
    production readiness.

### LEXA is not

-   A public customer portal or online storefront.
-   A set of unrelated dashboards with separate sources of business
    truth.
-   An autonomous AI agent allowed to mutate business records without
    approval.
-   A broad but shallow module catalogue that leaves core journeys
    incomplete.
-   A replacement of working backend/database architecture without a
    proven defect and safe migration path.

Internal customer records remain needed for sales, credit, payment
allocation, and history; this does not make LEXA a customer-facing
portal.

## 3. Architecture and infrastructure baseline

These are the latest known identifiers from the 19--20 October 2026
audit. Reconfirm live state before taking action; they are context, not
proof that deployments currently run a particular source tree.

  --------------------------------------------------------------------------------
  Layer                               Known resource / contract
  ----------------------------------- --------------------------------------------
  GitHub                              `MONALISA2003-CMD/LEXA-`, default branch
                                      `main`

  Latest known `main` commit          `63a62b4fa8b9a4b95431fa9c6c49888b4057c35c`
                                      (15 Oct 2026)

  Web                                 Next.js 16 / React 19 in `apps/web`; Vercel
                                      project `lexa`; known domain
                                      `https://lexa-green.vercel.app`

  API                                 FastAPI in `apps/api`; Render service
                                      `LEXA`, ID `srv-dakm8k95efls73egg9a0`; URL
                                      `https://lexa-n10e.onrender.com`; root
                                      directory `apps/api`

  Database                            Neon project `LEXA`, project ID
                                      `wispy-mud-75323042`; canonical branch
                                      `lexa-live`, branch ID
                                      `br-soft-star-b1dj2m2w`; database `neondb`

  Identity contract                   `/api/v1/auth/me` is authoritative for
                                      current user/workspace identity

  Liveness/readiness                  `/health` is intended for process liveness;
                                      `/ready` checks required dependencies
                                      (database and Redis-compatible cache)

  Intended app DB role                `lexa_app` is the restricted transaction
                                      role; connection login must not be
                                      overprivileged

  Branch/deploy discipline            Render auto-deploys `main`; do not push work
                                      directly to `main`
  --------------------------------------------------------------------------------

GitHub feature-branch creation previously failed with
`403 Resource not accessible by integration`. Do not work around this by
pushing to `main`. Use a newly authorized feature branch, a reviewed
patch, or a source ZIP until write access is confirmed.

## 4. What Phase 1 actually delivered --- and did not deliver

The Phase 1 ZIP is a **source candidate**, not a production release.

### Source changes in the candidate

-   `apps/api/app/db.py`: shared `apply_application_role(...)` helper
    validates role identifiers and applies `SET LOCAL ROLE`; SQLAlchemy
    session hook uses it.
-   `apps/api/app/health.py`: direct readiness database connection
    applies the restricted application role before readiness/catalog
    queries.
-   `apps/api/app/config.py`: adds `DATABASE_LOGIN_ROLE` (default
    `lexa_runtime`) and production validation for role identifier,
    pooled Neon hostname, TLS mode, and URL username consistency.
-   `.env.example` and `render.yaml`: declare `DATABASE_LOGIN_ROLE`.
-   New `migrations/029_phase1_runtime_role_least_privilege.sql`:
    creates `lexa_runtime_safe` with constrained attributes, avoids
    modifying the old `lexa_runtime`, grants it controlled
    `SET ROLE lexa_app` capability, removes direct grants defensively,
    verifies key conditions, and records the migration.
-   New tests: `apps/api/tests/test_phase1_runtime_security.py`.
-   New verifier: `scripts/verify-phase1.sh`.
-   Deployment audit test updated to require `DATABASE_LOGIN_ROLE`.
-   Runbook, report, release notes, ZIP readme, checksum, and manifest
    updated to candidate 2.9.1.
-   The Phase 1 working source includes the dashboard resilience change:
    panels have independent loading/success/error states instead of one
    failed request blanking all panels.

### Test evidence from the Phase 1 working candidate

`bash scripts/verify-phase1.sh` passed: - Python tests: **109 passed, 1
skipped**. - Frontend static contract tests: **4/4 passed**. - Five new
Phase 1 runtime security tests passed. - Python/shell syntax checks
passed. - Migration-source reconciliation correctly identified seven
unavailable historical SQL sources.

`bash scripts/verify-phase3.sh` also passed its source-level checks: -
109 passed, 1 skipped. - Frontend contract checks passed. - TypeScript
syntax transpilation for 27 TS/TSX files passed using a global
compiler. - UI presence checks passed.

Important limitations: - The skipped test requires `redis`, which was
missing in the local environment. - Full `npm ci` did not complete
because the offline environment lacked `undici-types@6.21.0` and
registry DNS was unavailable. Therefore full frontend typecheck and
Next.js production build are **not verified**. Run them with Node 24 and
complete dependencies. - The source migration checker remains blocked in
strict mode by seven missing historical migration files. - The candidate
was not pushed, merged, or deployed. - No production
database/schema/role, Render setting, Render deployment, or Vercel
deployment was changed.

### Isolated Neon test branch evidence

An isolated branch was created for testing:
`lexa-phase1-security-test-2026-10-19`, branch ID
`br-red-voice-b16z9b0i`, under project `wispy-mud-75323042`. Production
branch remained untouched.

On the isolated branch, the Phase 1 SQL was tested and
`lexa_runtime_safe` had constrained attributes: LOGIN, NOINHERIT,
NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS; not a member of
`neon_superuser`; can `SET ROLE lexa_app`; and no direct sensitive-table
privileges. The restricted app role could access the protected data it
needed while the login role itself could not directly read
`public.users` or delete `public.schema_migrations`.

The safe role has **no password yet**. It must be given a unique secret
by an authorized operator using the documented Neon SQL editor/secret
workflow before any approved runtime cutover. The existing
`lexa_runtime` was not modified. Never paste production credentials into
code, logs, chat, or the repository.

## 5. Critical open blockers and risks

### P0 --- Runtime database login is overprivileged in production

The production `lexa_runtime` login was observed with `BYPASSRLS`,
`CREATEROLE`, `CREATEDB`, `REPLICATION`, and membership allowing
`SET ROLE neon_superuser`; it also inherited broad read/write
capabilities. Normal ORM transactions switch to `lexa_app`, but that
does not neutralize the powerful login membership chain for arbitrary
SQL, and direct engine connections were a concern addressed in the Phase
1 source candidate.

**Direction:** keep the safe-role approach test-first. Do not
alter/revoke the production role, change production credentials, or cut
over Render without explicit user authorization and a reviewed rollback
plan. Create/set the safe-role password through an authorized secret
workflow; verify app login, health/readiness, grants, role switching,
and rollback on a test environment first.

### P0 --- Seven historical migrations are missing

Strict source replay cannot be treated as complete until the exact
authoritative source bytes are recovered for:

-   `010_phase2_catalog_intelligence.sql`
-   `011_phase2_catalog_runtime_constraints.sql`
-   `023_phase4_purchasing_core.sql`
-   `024_phase4_purchasing_security.sql`
-   `025_phase4_purchasing_permissions.sql`
-   `026_phase4_membership_branch_integrity.sql`
-   `027_release_convergence.sql`

There is a numeric-prefix collision: the source tree has a different
`023_phase2_identity_tenancy_authorization_foundation.sql`, while the
database ledger lists a separate `023_phase4_purchasing_core`. Do not
reconstruct or "fill in" missing migrations from the live schema. Search
authoritative Git history, release artifacts, backup source packages, or
owner-provided originals and verify exact contents.

### P0 --- Five public tables have RLS disabled / no policies

Observed in the prior audit: `permissions`, `registration_requests`,
`schema_migrations`, `tenants`, `users`. This is a review finding, not
permission to flip RLS blindly. These tables support permission lookup,
registration/bootstrap, migration readiness, tenant resolution, and
authentication. First map every access path, direct grant, owner, and
bootstrap need; design per-table protections and test login/registration
and migration tooling before changing anything.

### P1 --- Render readiness setting mismatch

Repository `render.yaml` specifies `/ready`, while the live Render
service metadata had blank `healthCheckPath`. Reconcile only through a
reviewed, authorized release plan. Confirm `/health` and `/ready`
semantics, required cache variables, bounded timeouts, sanitized error
payloads, and dependency failure behavior.

### P1 --- No hosted credentialed acceptance evidence

A dedicated non-production test account was not available in the prior
audit. The following remain unverified against a hosted target: login,
refresh rotation, `/auth/me`, protected read, logout, revoked refresh
rejection, access-token behavior, tenant/branch scope, and error
behavior under service/cache failure.

### P1 --- Frontend build and responsive review incomplete

Run Node 24, complete `npm ci`, `npm run typecheck`, `npm test`, and
`npm run build`. Do visual/responsive checks at **360, 390, 430, 768,
and 1280 CSS px**. Static contract tests and syntax transpilation are
not substitutes.

## 6. Phase 2 and later roadmap --- continue in this order

The numbered implementation phases below are the engineering roadmap.
They are distinct from product workflow stages P0--P4 described later.

### Phase 2 --- Frontend design system and full-app UX redesign

**Objective:** replace the inconsistent/weak current UI with a coherent,
high-quality, responsive interface across the entire app without faking
feature completeness or breaking API behavior.

Order: 1. Audit every route, shared layout, navigation component,
component primitive, API client, and current UI state. 2. Define design
tokens: color, type scale, spacing, radius, elevation, borders, focus
rings, responsive breakpoints, and motion policy. 3. Standardize shared
primitives: app shell, responsive navigation/sidebar, page header,
breadcrumbs, cards, tables/data grids, filters, search, pagination, form
fields, select/date controls, dialogs/drawers, toasts/alerts,
confirmation flows, status badges, skeletons, empty/error/forbidden
states. 4. Apply the shared system to all existing routes, not only the
dashboard. Ensure desktop and mobile navigation work and
branch/workspace context is clear. 5. Redesign tables and dense
operational screens for small screens: compact card/list fallback where
needed, safe horizontal overflow only where appropriate, touch targets,
readable labels, and no clipped actions. 6. Standardize API state
handling: loading, successful empty, successful populated, recoverable
error, forbidden, validation error, pending mutation, confirmed success,
and unknown outcome. 7. Keep accessible keyboard/focus behavior,
semantic headings, contrast, form labels, and screen-reader-friendly
status changes. 8. Do not replace real API calls with static/mock data
to make screens look complete. Mark scaffolds as scaffolds until their
workflow exists. 9. Capture and review screenshots at 360, 390, 430,
768, and 1280 px and fix visual regressions. 10. Run Node 24 dependency
install, typecheck, tests, and production build; add visual/smoke tests
where practical.

**Phase 2 acceptance:** every route uses consistent shared primitives;
mobile navigation and critical workflows remain usable; no false-zero
state; accessibility/responsive review recorded; typecheck/tests/build
pass; no production deployment without explicit approval.

### Phase 3 --- Business setup and workspace configuration

Build a real first-run setup and ongoing administration foundation: -
Business/workspace profile and settings. - Tenant/workspace context,
membership, invitations, roles, permissions. - Branches, warehouses,
stock locations, and user-to-branch assignments. - Clear
onboarding/resume behavior and validation. - Safe defaults and explicit
scope when a user has multiple branches. - Audit important membership,
permission, and configuration mutations. - Enforce every operation
server-side; UI hiding is not authorization. - Test tenant isolation,
branch isolation, forbidden actions, invitation lifecycle, membership
removal, session revocation, and last-admin/owner protections.

Do not assume existing APIs/schema are correct merely because they
exist. Inspect and reuse existing API and database contracts; only
introduce migrations after reviewing source history and a rollback path.

### Phase 4 --- Operational modules and end-to-end commerce

This phase must turn existing partial modules and scaffold screens into
real workflows, not merely add routes.

#### Catalog / products

-   Product identity, SKU/barcode uniqueness, categories, brands, units,
    variants, prices.
-   Product create/edit/archive validation and permission checks.
-   Explicit link between product/variant and stock-tracked item.
-   No inventory balance stored as a manually edited duplicate of the
    ledger.

#### Inventory

-   Location-level stock and authoritative movement ledger.
-   Adjustments, counts, transfers, dispatch/receive, approvals, and
    integrity checks.
-   Concurrency handling, idempotency, audit trail, and invariants for
    negative/overdrawn stock according to business rules.
-   Validate stock balance against movement ledger.

#### Sales / POS / payments

-   Checkout and completed sale, line pricing/tax rules, payment
    recording, receipts.
-   Atomic or explicitly coordinated stock, sale, payment, and
    accounting effects.
-   Duplicate/retry safety and clear handling of uncertain outcomes.
-   Returns/refunds and day-close/reconciliation where supported by the
    existing business model.
-   Test cashier vs manager permissions and branch restrictions.

#### Customers (internal business records only)

-   Customer directory, history, credit/balance derived from
    authoritative sales and payment allocations.
-   No manually maintained balance that can drift from source records.
-   No public customer portal as part of this scope.

#### Purchasing / suppliers

-   This is a scaffold in the reviewed source. Build supplier → purchase
    order → approval → partial/full receipt → discrepancy handling →
    stock/payables effect → return.
-   First recover and reconcile authoritative migration history and
    existing tables/APIs.
-   Existing purchase-order/receipt/supplier tables in the schema are
    not proof that the workflow is implemented.
-   Include permissions, idempotency, audit trail, partial failures, and
    reconciliation.

**Core vertical-slice target:** Product → stock/location → sale →
payment/receipt → accounting/report, exercised against real API/database
state with tenant/branch, permission, retry, error, and reconciliation
tests.

### Phase 5 --- Accounting and financial integrity

-   Verify chart of accounts, journals/lines, posting, reversal,
    periods, trial balance, statements, expenses, and mappings.
-   Enforce balanced journals and valid period state transitions.
-   Keep source transactions linked to accounting effects.
-   Validate date/time zones, rounding, currency precision, tax
    behavior, reversal semantics, and idempotency.
-   Reconcile sales, payment allocations, inventory valuation/COGS where
    implemented, payables, and report totals to source records.
-   Protect period close, backdated writes, reversals, and privileged
    accounting actions with server-side authorization and audit.
-   Do not claim accounting or fiscal compliance complete from the
    presence of tables or UI.

### Phase 6 --- Analytics and evidence-grounded intelligence

First reconcile conventional reports; only then implement Ask LEXA.

#### Reports and analytics

-   Compare dashboard/report totals against authoritative source
    transactions and ledger records.
-   Validate filters, date ranges, branch/tenant scoping, empty states,
    cache freshness, and refresh failure behavior.
-   Failed data fetches must be visibly unavailable, not zero.
-   Reports should be reproducible and explain their source/aggregation
    rules.

#### Ask LEXA / Intelligence

-   Current source was assessed as a scaffold; no complete user-facing
    AI investigation/action flow was verified.
-   Start with read-only questions over verified, authorized business
    facts.
-   Require grounded retrieval/query plans, tenant/branch permission
    checks, source evidence/provenance, safe limits, auditability, and
    sanitized errors.
-   Clearly separate facts, calculations, inferences, and
    recommendations.
-   Use a model gateway/provider abstraction with timeouts, budgets,
    redaction, logging controls, and graceful unavailability.
-   Core operations must never depend on AI availability.
-   Do not add autonomous mutations. Any later action capability must
    use prepare → review/approve → execute, server authorization,
    idempotency, and immutable audit evidence.
-   Do not market a live AI service until its actual route, auth, data
    grounding, failure paths, and hosted acceptance are demonstrated.

### Phase 7 --- Full acceptance, resilience, and release

-   Restore safe branch-based CI/review and exact source-to-deployment
    traceability.
-   Complete full frontend install/typecheck/test/build and backend
    tests with all expected test dependencies installed.
-   Recover all seven historical migration sources and verify from-zero
    migration replay; if exact recovery is impossible, keep the
    limitation explicit and define an approved alternative evidence
    strategy rather than inventing SQL.
-   Test migrations on disposable/isolated Neon branches,
    backup/restore, and rollback procedures.
-   Run hosted anonymous liveness/readiness checks and credentialed
    acceptance with a dedicated non-production account.
-   Run end-to-end workflows for roles, tenants, branches, retries,
    duplicate submissions, permissions, partial failures, and
    reconciliation.
-   Review responsiveness/accessibility at 360, 390, 430, 768, and 1280
    px.
-   Run performance/security checks appropriate to changed paths;
    inspect logs for secret leakage and ensure errors are sanitized.
-   Produce a release evidence report with exact commit, source tree,
    test commands/results, migration status, target deployment IDs,
    smoke results, known blockers, and module maturity.
-   Deploy/promote only after explicit user authorization.

## 7. Product workflow priority (cross-cutting)

The product stages are separate from the engineering phase numbers:

-   **P0 --- Access and workspace truth:** sign-in, refresh rotation,
    logout/revocation, session restore, authoritative identity, active
    membership, role/permission/branch scope, and accurate DB/cache
    readiness.
-   **P1 --- First end-to-end business journey:** Product →
    stock/location → sale → payment/receipt → accounting/report. Prove
    real effects, tenant/branch isolation, retries, failures, and
    reconciliation.
-   **P2 --- Daily operations expansion:** internal customer
    accounts/history, purchasing/suppliers including partial
    receiving/discrepancies, multi-branch controls and transfers.
-   **P3 --- Control depth:** finance/compliance depth,
    administration/membership/roles/branch assignments/sessions, and
    advanced operational reporting.
-   **P4 --- Read-only intelligence:** Ask LEXA grounded in verified
    facts, evidence-linked explanations, anomaly investigation,
    recommendations; controlled actions only later through approval
    gates.

Multi-branch and permission boundaries are foundational from the start,
not a late feature.

## 8. Current module maturity snapshot

These labels are based on the 19 October source audit, not a fresh code
audit. Re-check the ZIP before editing and update this table when
evidence changes.

  -----------------------------------------------------------------------------------------
  Module                    Known status at handoff Required direction
  ------------------------- ----------------------- ---------------------------------------
  Sign-in / registration /  Partial; auth endpoints Hosted acceptance for login, refresh
  invite                    exist                   rotation, `/auth/me`, protected read,
                                                    logout/revocation, invitations, and
                                                    tenant context

  Command Centre            Active, verify; Phase 1 Validate metrics, truthful states,
                            candidate adds          branch scope, mobile layout
                            independent panel       
                            states                  

  Products/catalog          Active, verify          CRUD/archive, uniqueness, pricing,
                                                    variants, barcodes, stock link

  Inventory                 Active, verify          Ledger/balance consistency,
                                                    adjustment/count/transfer workflows,
                                                    concurrency

  Sales/commerce/payments   Active, verify          Atomic effects, idempotency,
                                                    returns/refunds, receipts,
                                                    reconciliation

  Customers                 Partial/shared commerce Dedicated lifecycle UX; balances
                            workflow                derived from source transactions

  Accounting                Partial/active          Balanced postings, reversals, periods,
                                                    source reconciliation

  Tax/compliance/EFRIS      Partial/active          Provider integration and failure/retry
                                                    behavior unverified; do not overclaim

  Reports                   Active, verify          Reconcile report totals, date filters,
                                                    access scope, failed/empty distinction

  Purchasing                Scaffold                Complete
                                                    supplier-to-receipt-to-stock/payables
                                                    workflow using authoritative schema

  Administration            Scaffold                Membership, invitation, roles,
                                                    permissions, branches, audit, server
                                                    enforcement

  Settings                  Scaffold                Real validated forms, authorization,
                                                    audit and truthful save states

  Intelligence / Ask LEXA   Scaffold                Read-only evidence-grounded workflow
                                                    first; no autonomous mutation

  Shared shell / responsive Partial                 Phase 2 design system and whole-app
  design                                            redesign

  CI / build / migration    Blocked/incomplete      Restore Node 24 build, Redis test
  replay / hosted                                   dependency, branch workflow, migration
  acceptance                                        sources, hosted tests
  -----------------------------------------------------------------------------------------

Every module must use exactly one maturity label: 1. **Placeholder** ---
static/navigational/explanatory UI only. 2. **In progress** --- some
real paths exist, but important behavior or acceptance is incomplete. 3.
**Implemented (not production verified)** --- source and local/CI checks
exist, hosted acceptance missing. 4. **Production verified** --- real
API/database effects, tenant/branch permissions, failure/retry paths, UI
states, and hosted smoke tests passed with evidence.

A route existing is not a maturity status.

## 9. Security and engineering guardrails

### Database and migration safety

-   Do not run destructive SQL or schema changes against canonical Neon
    `lexa-live` without explicit approval.
-   Never reconstruct the seven missing historical migrations from
    schema guesses.
-   Test schema/role/grant changes on isolated branches first; retain
    before/after evidence and rollback steps.
-   Never blanket-enable RLS on `permissions`, `registration_requests`,
    `schema_migrations`, `tenants`, or `users` without tracing
    bootstrap/login/migration flows and proving compatibility.
-   Keep migration tooling privileges separate from application runtime
    privileges.
-   Do not put passwords or API credentials into source, ZIPs, logs,
    markdown, or chat.

### Production/deployment safety

-   **No production changes without explicit user authorization.** This
    includes DB grants/roles/migrations, Render
    environment/settings/deployments, Vercel production deploys, and
    changes to GitHub `main`.
-   Work locally, on feature branches, previews, or isolated test
    branches first.
-   Since Render auto-deploys `main`, never push implementation work
    directly to `main`.
-   Do not claim something was pushed, merged, deployed, or production
    verified unless the connected tool reports that exact action/result.
-   Prefer a small reviewable change over architecture replacement.

### Code quality and UI truth

-   Preserve existing APIs and domain boundaries unless evidence shows a
    defect.
-   Keep request validation, auth checks, tenant/branch scope, DB
    constraints, transaction boundaries, idempotency, and audit
    semantics aligned.
-   Avoid broad refactors mixed with workflow changes.
-   No mock/static data to disguise incomplete integrations.
-   For mutations with unknown outcomes after network failure, offer
    safe refresh/reconciliation rather than falsely saying "failed" or
    "saved".
-   Add regression tests for each defect and document the acceptance
    proof.

## 10. Immediate next steps for the continuing agent

Do this sequence; do not jump straight into building new modules:

1.  **Obtain and inspect the Phase 1 ZIP.** Verify checksum, extract to
    a clean working directory, read the Phase 1 report/runbook/README,
    inspect git metadata (the ZIP is not necessarily a Git checkout),
    and inventory all routes, API clients, shared components, scripts,
    and migrations.
2.  **Establish a trustworthy baseline.** Run
    `bash scripts/verify-phase1.sh`; record actual output. Confirm
    current working tree and ensure no stale `node_modules` or caches
    obscure results.
3.  **Close cheap environment gates.** Use Node 24 and
    network/cache-enabled CI to run `npm ci`, `npm run typecheck`,
    `npm test`, `npm run build`; install the Python test dependency
    `redis` in the correct test environment and rerun backend tests. Do
    not equate syntax transpilation with a full build.
4.  **Set up safe change control.** Re-check GitHub permissions. If
    branch write remains blocked, do not attempt `main`; prepare a clean
    patch/ZIP for authorized review.
5.  **Start Phase 2 with a source-grounded UI audit.** Enumerate all
    routes and classify each current screen as real workflow, partial,
    or scaffold. Map shared components and API state patterns before
    redesign. Then implement the design system incrementally and apply
    it consistently.
6.  **Maintain an acceptance matrix.** For every touched route, record
    UI state coverage, endpoint(s), permissions, tenant/branch scope, DB
    effects, idempotency, automated tests, visual sizes checked, and
    maturity label.
7.  **Track the P0/P1 blockers in parallel without production
    mutation.** Recover exact migration files from authoritative
    history/artifacts; prepare safe runtime-role cutover plan; plan
    hosted auth tests; document Render readiness mismatch. Do not let
    these be silently marked complete just because Phase 2 UI work
    advances.
8.  **Produce a full updated source ZIP** after meaningful increments,
    with release notes, exact checksum, tests/results, changed-file
    summary, known blockers, and runbook. Never supply only a partial
    patch if the user requests the complete source package.
9.  **Ask for explicit approval before any production mutation.** If
    approval is absent, remain in local/test/preparation mode.

## 11. Release gates that must remain visible

-   [ ] Full Node 24 install, frontend typecheck, frontend tests,
    production build.
-   [ ] Python test suite passes with Redis test dependency installed;
    explain any remaining skip.
-   [ ] Exact historical migration sources recovered and strict source
    replay passes, or a clearly approved and documented alternative
    exists.
-   [ ] Safe runtime login configured with a unique secret and tested;
    production cutover only after explicit approval.
-   [ ] Five RLS-disabled tables have a documented per-table access
    model and tested remediation decision.
-   [ ] Render `/ready` setting and live behavior reconciled.
-   [ ] Hosted auth/session acceptance passes using a dedicated
    non-production account.
-   [ ] Core vertical workflow passes end-to-end and reconciles to
    accounting/report source records.
-   [ ] Responsive/accessibility review recorded at 360/390/430/768/1280
    px.
-   [ ] Exact commit and deployment identity reconciled; no
    direct-to-main shortcut.
-   [ ] Every touched module has an evidence-backed maturity label.
-   [ ] User has explicitly authorized any production deployment/change.

## 12. Reporting style expected from the next agent

At each handoff, report: - What changed (file paths and purpose). - What
tests were run and exact pass/fail/skip results. - What was not tested
and why. - Whether changes are only local, on a branch, in preview, or
production. - Current blockers and risks. - Exact output ZIP filename,
byte size, SHA-256, and download link when generated. - Next recommended
action.

Be precise. Say "source implemented, hosted acceptance pending" rather
than "complete" when that is the evidence. Distinguish source-derived
facts, observed infrastructure state, and recommendations/inferences.

## 13. Final instruction to the next LLM

Continue LEXA from **Phase 2 upward**, honoring the product mission and
phase order above. Phase 2 is a whole-app frontend
design-system/redesign effort, but it must preserve real behavior and
truthful data states. Later phases must deliver working business setup,
operational workflows, accounting integrity, evidence-grounded
analytics/intelligence, and full release acceptance---not just
attractive screens or scaffolds.

Keep all work local/test/branch-only until the user explicitly
authorizes production changes. Never fabricate missing migrations, test
results, deployment state, business data, or feature completion.
