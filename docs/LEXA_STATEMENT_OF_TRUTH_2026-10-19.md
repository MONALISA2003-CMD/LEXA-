> **Historical snapshot — superseded for current gate status by Phase 6 (21 October 2026).** Any statement here that requires recovering the six Phase 3-approved lost SQL files is retained only to describe the state at the time. Their historical recovery gate is permanently closed by `docs/decisions/ADR-DB-001-permanent-replacement-of-lost-migrations.md` and `migrations/migration_dispositions.json`. Do not treat this snapshot as the current release-gate register.

# LEXA — Statement of Truth

**Document status:** Product and implementation direction locked for the next increment  
**Prepared:** 19 October 2026  
**Scope:** LEXA only  
**Purpose:** One authoritative, plain-language statement of what LEXA is, what the current evidence says exists, what has been decided, what remains unverified, and how work must proceed.

---

## 1. Why this document exists

This statement consolidates the LEXA direction discussed and locked in the current planning conversation with the source package's product, architecture, Phase 0, and Phase 1 handoff documents. It is intended to prevent the product from drifting into disconnected modules, placeholder screens presented as finished features, unverified deployment claims, or AI work that outruns operational correctness.

This is a decision and evidence document, not proof that every requirement is already implemented. Claims about current implementation below are explicitly labelled as source-documented or observed. Items described as decisions or targets are not to be mistaken for completed code.

## 2. The product truth

**LEXA is a multi-tenant business operating and intelligence system for the people who run a business.** It is not a public customer portal, storefront, or collection of unrelated dashboards.

Its initial business focus is:

1. Retail and shops.
2. Distribution and wholesale.
3. Businesses operating across multiple branches or locations.

The first product outcome is **complete, dependable daily business operations**. Intelligence must be built into the workspace after the underlying operational workflows and data are trustworthy.

The product promise is:

> **Run the business. Trust the numbers. Know what needs attention.**

The workspace should adapt to the user's role, permissions, and authorized branch scope rather than fragmenting into different products for every role. Typical internal roles include owner, manager, cashier, storekeeper, purchasing, finance, and administrator. The precise capabilities available to each person must be enforced by the server, not only hidden by the UI.

## 3. Product principles that are binding

1. **Operations before intelligence.** Make everyday business journeys reliable before building broad AI capabilities.
2. **One adaptive workspace.** Present relevant work based on role, permissions, branch, and current operational context.
3. **One source of business truth.** Neon PostgreSQL remains the canonical transactional system of record. Do not introduce a second transactional database.
4. **No false zeros.** Failed, forbidden, loading, or unavailable data must never be presented as a legitimate zero or empty business state.
5. **No success without confirmation.** A mutation is successful only after the server confirms it; errors must not imply that an operation definitely failed to save when its outcome is uncertain.
6. **Tenant and branch isolation are foundational.** All protected data and actions must be scoped and enforced server-side, with database RLS as a defence in depth.
7. **Critical changes are traceable.** Important operations need authorization, auditability, idempotency where retries are possible, and consistent transaction boundaries.
8. **Mobile-first, accessible UI.** Daily tasks must remain usable on small screens, with clear focus states, understandable errors, and explicit loading/empty/error/forbidden/success states.
9. **AI is optional for core operations.** Selling, stock movement, payment recording, permissions, and reporting must not depend on a model being available.
10. **Intelligence must be evidence-grounded.** Initial LEXA intelligence is read-only, based on verified business facts, with explanations that can be traced to the underlying data. Controlled actions require later approval gates.
11. **No invented completion claims.** A module is not production verified until its UI, API, database effects, permissions, failure paths, and hosted smoke tests are evidenced.

## 4. What LEXA is not

The initial release is not intended to be:

- A public customer-facing portal or online storefront.
- A collection of independent modules that each invent their own business truth.
- An autonomous AI operator allowed to mutate business records without review.
- A broad set of shallow modules where key workflows remain incomplete.
- A replacement of working backend or database architecture without evidence of a specific defect and a safe migration path.
- A production-ready system merely because Vercel and Render display a green deployment state.

Internal customer records remain necessary for sales, credit, payment allocation, and customer history. That does not make LEXA a customer-facing portal.

## 5. Authoritative architecture and deployment shape

The reviewed source package states the following architecture:

- **Web:** Next.js application in `apps/web`, served by Vercel.
- **API:** FastAPI application in `apps/api`, served by Render.
- **Database:** Neon PostgreSQL project `LEXA`, canonical branch `lexa-live`, database `neondb`.
- **Identity contract:** `/api/v1/auth/me` is the authoritative user/workspace identity contract; cookie-backed refresh and server-side authorization guard protected operations.
- **Database safety:** tenant/user context and row-level security protect tenant-owned data; the restricted `lexa_app` role is intended for application transactions.
- **Operational foundations:** idempotency, audit and outbox patterns, organization/branch/location boundaries, and business transaction primitives support future module workflows.

These are source-documented design and implementation claims. They do not, by themselves, prove the current hosted deployment is using the exact same source or that every hosted flow passes acceptance. Deployment identity must be reconciled against the exact commit and tree before promotion.

## 6. Module boundaries

| Workspace/module | Owns | Must not become |
|---|---|---|
| Command Centre & Reports | Operational attention, summaries, traceable historical views | A separate source of business truth or a screen that turns failed requests into zeroes |
| Products & Catalog | Product identity, SKU/barcode, variants, units, categories, pricing | The stock ledger or an alternative inventory balance store |
| Inventory | Stock movements, balances, adjustments, counts, transfers, location-level stock | A disconnected product catalogue or manually edited stock totals without ledger evidence |
| Sales & Payments | Checkout, completed sales, payment recording, receipts, returns, reconciliation | A single oversized page that mixes unrelated customer administration and finance configuration |
| Customers | Internal customer directory, purchase history, and balances derived from authoritative records | A public portal or manually maintained balance that bypasses payment allocations |
| Purchasing & Suppliers | Supplier identity, purchase orders, approvals, partial receiving, discrepancies, supplier obligations | A simulated workflow without authoritative schema, permission, and ledger support |
| Finance & Compliance | Journals, periods, balances, statements, tax/fiscal integration with actual provider confirmation | A claim of accounting/fiscal completion based only on UI placeholders |
| Administration & Settings | Memberships, roles, permissions, invitations, branches, sessions, workspace preferences | A client-only security boundary |
| Intelligence / Ask LEXA | Read-only investigation and explanation grounded in verified operational facts, later controlled-action preparation | A prerequisite for core operations or an ungrounded model response presented as business fact |

The Business Kernel, tenant isolation, audit/outbox, idempotency, migration discipline, and model gateway are technical foundations, not additional user-facing modules to launch as separate products.

## 7. Workflow order

### P0 — Access and workspace truth

- Sign-in, refresh rotation, logout/revocation, and session restoration.
- Authoritative identity, active membership, role, permission, and branch scope.
- Correct distinction between expired credentials and network/server outage.
- Database/cache readiness that accurately reports required dependencies.

### P1 — The first end-to-end business journey

**Product → stock/location → sale → payment/receipt → accounting/report.**

This must work against real API and database state, not mocks or static UI. The journey must prove correct permissions, tenant/branch isolation, stock effects, payment effects, duplicate/retry behaviour, failure behaviour, and reconciliation between the source records and displayed summaries.

### P2 — Daily operations expansion

- Internal customer accounts and purchase/payment history.
- Purchasing and suppliers, including order approvals, partial receiving, and receiving discrepancies.
- Multi-branch operational controls and transfers.

### P3 — Control depth

- Finance and compliance depth.
- Membership, roles, branch assignments, sessions, and administration.
- Additional reporting and operational policies.

### P4 — Read-only intelligence

- Ask LEXA against verified data.
- Evidence-linked explanations, anomaly investigation, and recommendations.
- Controlled actions only later, through prepare → review/approve → execute with audit trails and idempotency.

Multi-branch data and permission design is foundational from P0; it is not a late-stage add-on.

## 8. Definition of module maturity

Every module must use exactly one of these statuses:

1. **Placeholder** — explanatory, navigational, or static UI; not a complete working workflow.
2. **In progress** — some real paths exist, but important behaviour or acceptance remains incomplete.
3. **Implemented (not production verified)** — source code and local/CI checks exist, but hosted acceptance or full operational verification is missing.
4. **Production verified** — real API/database effects, tenant/branch permissions, failure and retry paths, UI states, and hosted smoke tests have passed and evidence is recorded.

A successful build, a green service indicator, a route that renders, or a migration row alone is not sufficient to label a business module production verified.

## 9. Current evidence snapshot — what the sources support

### 9.1 Source-documented as implemented or present in the handoff

- Phase 0 authentication/RLS hardening source includes an opaque refresh-token hash lookup, `/api/v1/auth/me` identity contract, tenant/user database context, migration 028 checks, and a readiness function intended to verify database and Redis/Valkey.
- Phase 1 UX source includes shared responsive UI components, primary navigation, sign-in improvements, resumable onboarding, centralized API error language, and a responsive Products/Inventory list foundation.
- The web source contains real API clients for catalog, inventory, commerce, analytics, organization, and Business Kernel endpoints.
- Several workspaces remain explicit placeholders in source, including Purchasing, Settings, Administration, and Intelligence; a placeholder is not a working business workflow.
- The source package's Phase 1 report records 104 Python tests passing, one skipped because the offline environment lacked the Redis dependency, and three frontend static contract tests passing. Full npm install/typecheck/build and responsive screenshot review were pending in that report.

### 9.2 Deployment evidence observed in this audit

- Vercel project `lexa` has a latest listed READY production deployment at commit `63a62b4fa8b9a4b95431fa9c6c49888b4057c35c` (`chore: automatically extract LEXA ZIP package [lexa-extractor]`). This confirms deployment metadata status, not business acceptance.
- Render service `LEXA` is configured for repository `MONALISA2003-CMD/LEXA-`, branch `main`, root directory `apps/api`, with auto-deploy enabled. The observed live service setting has a blank `healthCheckPath`, while the reviewed `render.yaml` declares `/ready`.
- Neon project `LEXA` (`wispy-mud-75323042`) has a ready branch named `lexa-live` (`br-soft-star-b1dj2m2w`). This does not establish that all application requests or the latest deployed code are correct.
- GitHub repository metadata and source-file reads are available, but branch creation returned HTTP 403 `Resource not accessible by integration`. An outbound Git clone also failed because DNS/network access was unavailable in this execution environment.

### 9.3 Known blockers that must not be hidden

- Seven historical migration SQL sources are documented as missing: 010, 011, 023 purchasing core, 024 purchasing security, 025 purchasing permissions, 026 membership/branch integrity, and 027 release convergence. Their SQL must not be reconstructed from schema guesses. Strict migration replay remains blocked until exact authoritative source is recovered.
- Credentialed hosted login/refresh/identity/protected-read/logout acceptance was not evidenced in the supplied handoff.
- The Render health-check path and live readiness implementation need reconciliation against the intended source and required cache dependency.
- The current Command Centre source previously coupled seven API calls in one `Promise.all`, so one failure caused unrelated panels to appear unavailable. The first increment addresses this source-level defect with independent per-panel states.
- Responsive screenshot review at 360, 390, 430, 768, and 1280 CSS pixels was pending in the supplied handoff and must be performed before production UX acceptance.
- The Intelligence page is documented in source as a placeholder; no inference router was registered in the reviewed FastAPI source at the time of the prior audit. Do not market it as a live AI service until that gap is closed and tested.

## 10. First implementation increment: Product Convergence and Core Workflow

The first increment is a reliability and vertical-slice increment, not a broad module expansion.

### A. Reconcile source and deployment truth

- Identify the exact commit/tree deployed to Vercel and Render.
- Ensure the reviewed changes are represented by a traceable branch/commit and that both services deploy the intended source.
- Align Render health-check configuration with the readiness contract after confirming the exact live endpoint semantics.
- Keep the canonical Neon project/branch/database; do not create a second business database.

### B. Close foundation gates

- Verify session restore, refresh rotation, `/auth/me`, protected read, logout/revocation with a dedicated test account.
- Verify role and branch scope on server-side reads and writes.
- Verify `/health` is liveness and `/ready` checks all required dependencies with bounded timeouts and sanitized responses.
- Keep strict migration-source verification as a blocker until exact source recovery is complete.

### C. Standardize truthful UI states

- Loading, empty, error, forbidden, validation, and success states are distinct.
- Each dashboard panel fails independently; one analytics or inventory error must not erase successful sales data.
- Do not show zero or “nothing urgent” when the data needed to support that statement did not load.
- Mutations are only described as successful after server confirmation.

### D. Complete one real vertical workflow

- Product identity and pricing.
- Stock/location and ledger effects.
- Sale completion and payment/receipt.
- Accounting/report reconciliation.
- Test success, validation errors, permission denial, retries/duplicates, partial failures, and tenant/branch boundaries.

### E. Verify UX and release evidence

- Review 360, 390, 430, 768, and 1280 CSS pixel widths.
- Run deterministic install, frontend typecheck/tests/build, backend tests, and migration-source integrity checks.
- Run hosted anonymous health/readiness probes and credentialed auth acceptance.
- Record exact commit, deployment IDs, test results, known blockers, and final module maturity statuses.

## 11. Guardrails for implementation

- Work only in the LEXA repository/project and its already-authorized services.
- Do not make production schema changes or reconstruct missing migrations as a shortcut.
- Do not claim a push, deployment, hosted acceptance, visual QA, or production verification without tool evidence.
- Do not silently broaden scope into a new product, public customer portal, or autonomous AI feature.
- Keep implementation in small, reviewable changes and preserve existing business data.
- Prefer repairing existing APIs and workflows over replacing architecture.

## 12. Acceptance criteria for calling increment one complete

The increment is complete only when all of the following are evidenced:

- [ ] Deployed source identity is reconciled and the intended changes are committed to a traceable branch/commit.
- [ ] Frontend install, typecheck, tests, and production build pass on the actual source.
- [ ] Backend tests and normal migration-source checks pass; strict migration replay is either unblocked by exact source recovery or clearly remains a release blocker for affected changes.
- [ ] Login, refresh rotation, `/auth/me`, protected reads, logout, and revoked-session rejection pass against the hosted environment using a dedicated test account.
- [ ] Readiness reflects the actual required database/cache dependencies, and Render's health-check configuration matches the intended readiness path.
- [ ] Command Centre panels report independent truthful states and never convert failed requests into zero/empty states.
- [ ] Product → stock → sale → payment/receipt → accounting/report works against real data with permission, tenant/branch, retry, and reconciliation tests.
- [ ] Responsive review is recorded at 360, 390, 430, 768, and 1280 CSS pixels.
- [ ] Each touched module has a maturity status and evidence trail.

**Current truth:** the first increment is in progress. Source changes and local verification can be prepared from the supplied handoff, but production acceptance is not complete until the access, deployment, migration-source, hosted test, and visual QA gates above have evidence.

## 13. Change control

This document is the current product-direction authority for LEXA. If a future decision changes the product focus, initial outcome, role-adaptive workspace, workflow order, or AI safety boundary, update this document and the roadmap together. Existing code or a historical release note does not override these decisions automatically. If source evidence conflicts with a product decision, document the gap and resolve it explicitly rather than pretending the code already conforms.
