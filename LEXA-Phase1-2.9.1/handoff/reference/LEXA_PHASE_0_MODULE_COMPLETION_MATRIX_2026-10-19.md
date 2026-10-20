# LEXA Phase 0 — System Inventory & Module Completion Matrix

**Inspection date:** 19 October 2026  
**Scope:** `MONALISA2003-CMD/LEXA-` only  
**Approach:** Read-only inspection of the current GitHub main branch, connected Neon project/branches/schema, Render service configuration, Vercel project/deployments, and the locally available source snapshot. No production resources were changed.

## Executive summary

LEXA is not an empty project. It has a substantial FastAPI backend, a Next.js frontend, and a populated Neon schema. The primary problem is uneven end-to-end completion: several operational screens call real APIs, while Purchasing, Administration, Settings, and AI Intelligence are explicitly foundation/scaffold pages. Security and reproducible database setup are also release blockers.

### Verified baseline

- GitHub default branch `main` points to `63a62b4fa8b9a4b95431fa9c6c49888b4057c35c` (15 October 2026).
- Frontend snapshot: Next.js 16 / React 19, with 16 `page.tsx` routes and a shared shell/UI layer.
- Backend source inventory: 8 domain route modules plus the kernel router; approximately 151 route decorators including system endpoints. This is a source count, not proof every endpoint passes an end-to-end test.
- Neon canonical project: `wispy-mud-75323042`; branch `lexa-live` (`br-soft-star-b1dj2m2w`); database `neondb`.
- Neon table inventory: 119 public base tables.
- Render `LEXA` service deploys from `main` with automatic deploy-on-commit enabled; live `healthCheckPath` is blank while repository `render.yaml` declares `/ready`.
- Vercel `lexa` latest production deployment was `READY`, from the same GitHub main commit. `READY` is deployment status, not proof of complete user workflows.
- No production database, Render setting, Vercel setting, or GitHub source was modified during Phase 0.

## Module completion matrix

**Status key:** `Active, verify` = real UI/API implementation exists but still needs full acceptance testing; `Partial` = useful real functionality exists but important gaps remain; `Scaffold` = route is mainly explanatory/placeholder content; `Blocked` = a concrete prerequisite prevents reliable release/testing.

| Module / route | Frontend status | Backend status | Database status | Phase 0 finding / acceptance needed | Priority |
|---|---|---|---|---|---|
| Sign-in, registration, invite | Partial | Auth endpoints exist for register/login/me/refresh/logout | Users, tenants, memberships, invitations, sessions, tokens exist | Run credentialed end-to-end auth, refresh rotation, logout, invite and tenant-context tests. The local refresh test is skipped because `redis` is absent from this environment. | P0 |
| Command Centre / dashboard (`/`) | Active, verify | Analytics and operational APIs exist | Analytics, sales, payments, inventory tables exist | Dashboard has independent loading/error states and real-data paths; verify tenant-scoped metrics, empty states and small-screen layout. | P1 |
| Products / catalog (`/products`) | Active, verify | Catalog endpoints cover products, variants, categories, brands, units, prices and barcodes | Matching catalog tables exist | Test create/edit/archive, SKU/barcode uniqueness, pricing and stock links end-to-end. | P1 |
| Inventory (`/inventory`) | Active, verify | Balances, ledger, adjustments, counts, transfers and integrity endpoints exist | Inventory transaction, balance, adjustment, count and transfer tables exist | Validate complete approval/posting/dispatch/receive flows and concurrency/ledger invariants. | P1 |
| Sales / Commerce (`/sales`, `/commerce`) | Active, verify | Sales, payment channels, receivables, reconciliation, returns and customer APIs exist | Sales, payments, allocations, returns, reconciliation and credit tables exist | Verify atomic sale/payment/stock/accounting outcomes, idempotency, returns and day close with test data. | P1 |
| Customers (`/customers`) | Shared workflow; partial | Customer operations are implemented through the shared commerce route/API | Customer profiles/parties/credits exist | Customer page reuses the commerce screen; separate customer-specific UX and lifecycle coverage need review. | P2 |
| Accounting (`/accounting`) | Partial / active | Accounts, periods, trial balance, statements, journals, posting/reversal endpoints exist | Accounts, journals, lines, periods, expenses and mappings exist | Verify balanced postings, period close, reversals, date filters, reconciliation against source transactions. | P1 |
| Tax & EFRIS (`/compliance`) | Partial / active | Tax rates/configuration and fiscal-document APIs exist | Tax and fiscalization tables exist | Configuration/records are present; do not assume a live URA/EFRIS integration is complete. Test provider integration and failure/retry behavior separately. | P2 |
| Reports (`/reports`) | Active, verify | Analytics overview/daily/product/customer/inventory/branch APIs exist | Analytics tables and refresh-run tracking exist | Validate report totals against ledger/source transactions, date ranges, empty states and access boundaries. | P2 |
| Purchasing (`/purchasing`) | **Scaffold** | No dedicated purchasing route module; purchasing-specific end-to-end API coverage is not established | Purchase orders, receipts, returns, lines and supplier tables exist | Replace foundation page with supplier → purchase order → approval → partial/full receipt → inventory/payables → return workflow, based on recovered authoritative schema/migration history. | P1 |
| Administration (`/administration`) | **Scaffold** | Organization and RBAC endpoints exist | Users, roles, permissions, memberships, branch assignments and audit tables exist | Build member/invitation/role/permission/branch assignment UI and test authorization boundaries. | P1 |
| Settings (`/settings`) | **Scaffold** | Some organization/configuration APIs exist | Tenant settings, business profile/configuration and tax configuration exist | Build actual settings forms with validation, permissions, audit behavior and clear save/error states. | P2 |
| AI Intelligence (`/intelligence`) | **Scaffold** | Analytics exists; no completed user-facing AI investigation/action workflow verified | Brain evidence/memory/model-route/recommendation/run/tool tables exist | Treat as planned until evidence-grounded query, authorization, audit, model routing and safe action approvals exist end-to-end. | P2 |
| Shared shell, navigation, responsive UI | Partial | Readiness/session APIs are wired in the shell | No direct schema changes expected | Establish one design system and shared page primitives; standardize loading/error/empty/success states, spacing, typography, responsive navigation and accessibility. | P1 |
| CI, local build and deployment acceptance | **Blocked** | Backend test suite runs locally | Strict from-zero migration replay is blocked | Restore frontend dependency installation/build, Redis test dependency, hosted smoke tests and safe branch-based CI before release. | P0 |

## Security and database blockers

### P0 — Database runtime role is over-privileged

Read-only inspection of Neon role membership found `lexa_runtime` has `LOGIN`, `CREATEROLE`, `CREATEDB`, `REPLICATION`, and `BYPASSRLS`, and can `SET ROLE` to `neon_superuser` through role membership. This undermines the intended application-role boundary even when application transactions switch to `lexa_app`.

**Remediation approach:** design and test a least-privilege runtime role and grants on an isolated/test branch first; validate migration/connection behavior and application flows before considering a separately authorized production change. Do not revoke production grants as part of Phase 0.

### P0 — Five tables lack RLS/policies

The prior read-only catalog audit found 114 of 119 public tables with RLS enabled and forced; these five had RLS off and no policies: `permissions`, `registration_requests`, `schema_migrations`, `tenants`, `users`. Their intended access model must be established before applying protections; avoid a blind blanket change that could break authentication/bootstrap/migration operations.

### P0 — Seven historical migration sources are missing

`python scripts/check_migration_sources.py --strict` fails because these exact applied sources are unavailable in the source package/repository snapshot:

- `010_phase2_catalog_intelligence.sql`
- `011_phase2_catalog_runtime_constraints.sql`
- `023_phase4_purchasing_core.sql`
- `024_phase4_purchasing_security.sql`
- `025_phase4_purchasing_permissions.sql`
- `026_phase4_membership_branch_integrity.sql`
- `027_release_convergence.sql`

There is also a numeric-prefix collision: the source contains `023_phase2_identity_tenancy_authorization_foundation.sql`, while the live ledger records a distinct `023_phase4_purchasing_core` migration. Recover exact historical SQL from an authoritative artifact; do not invent it from the current schema. Until recovered, a reproducible from-zero migration replay is blocked.

### P1 — Render health check mismatch

Render's live service configuration has an empty health-check path; repository `render.yaml` specifies `/ready`. Reconcile this only after a safe deployment/configuration plan, and verify readiness behavior in the target environment.

## Local verification performed

| Check | Result | Notes |
|---|---|---|
| Python test suite | **104 passed, 1 skipped** | Skip: `redis` dependency missing for `apps/api/tests/test_auth_refresh.py`. |
| Frontend contract tests | **4 passed** | `npm test` / Node test runner; these are contract tests, not full browser E2E. |
| TypeScript typecheck | **Failed / environment incomplete** | `@types/node`, `@types/react`, and `@types/react-dom` folders are present but empty/incomplete; TypeScript cannot find the definitions. |
| Next.js production build | **Failed / environment incomplete** | `next: not found` in the current incomplete `node_modules`. |
| Strict migration-source check | **Failed / known blocker** | Seven authoritative migration files are missing. |
| Credentialed hosted workflow E2E | **Not run** | No dedicated test account was available for safe authenticated hosted acceptance. |
| Visual browser/screenshot QA | **Not run** | Build dependencies are incomplete; source review alone cannot certify visual quality. |

The local working folder is an extracted source snapshot, not a Git checkout (`.git` is absent). Prior branch-creation attempt through the connected GitHub integration returned HTTP 403. Since Render auto-deploys `main`, do not push implementation changes directly to `main`. Establish a writable feature branch or deliver an explicitly reviewed patch before code implementation.

## Ordered work after Phase 0

1. **Phase 1 — Security and stability:** runtime-role least privilege, RLS gaps, missing migration recovery, auth/readiness tests, dependency-complete local build and branch-only workflow.
2. **Phase 2 — Frontend design system:** rebuild the whole application consistently; start with shell/navigation, typography/spacing/color tokens, shared tables/forms/dialogs, then apply across all routes.
3. **Phase 3 — Business setup:** profile, workspace, branches, warehouses, locations, users, invitations and permissions.
4. **Phase 4 — Operational modules:** catalog, inventory, sales/POS, purchasing and customer lifecycle, with transactional tests.
5. **Phase 5 — Accounting:** journal integrity, posting/reversal, periods and reconciliation.
6. **Phase 6 — Analytics and intelligence:** reconcile reports to source transactions; build evidence-grounded intelligence only after permissions and audit controls are verified.
7. **Phase 7 — Full acceptance and release:** automated integration/E2E, responsive visual checks, migration replay, backups/recovery, performance, and release evidence.

## Acceptance rule

A module is not “complete” because a route exists or a page looks finished. It must have: (1) a usable responsive UI, (2) real backend behavior with validation and authorization, (3) correct database constraints/tenant isolation, and (4) automated workflow tests plus an explicit acceptance result.
