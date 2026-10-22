> **Historical snapshot — superseded for current gate status by Phase 6 (21 October 2026).** Any statement here that requires recovering the six Phase 3-approved lost SQL files is retained only to describe the state at the time. Their historical recovery gate is permanently closed by `docs/decisions/ADR-DB-001-permanent-replacement-of-lost-migrations.md` and `migrations/migration_dispositions.json`. Do not treat this snapshot as the current release-gate register.

# LEXA Phase 1 UX foundation implementation report

**Version:** 2.9.0  
**Date:** 15 October 2026  
**Scope source:** `docs/research/LEXA_PRODUCT_UX_AI_RESEARCH_AND_INCREMENTAL_ROADMAP_2026-10-13.md`, Phase 1 “UX foundation & core sign-in”.

## Summary

Phase 1 source changes are implemented in this package across global styling, navigation, shared UI components, the Products and Inventory list experiences, sign-in, first-workspace setup, the registration contract, and centralized API error copy. Business transaction semantics in the Products and Inventory workflows were not intentionally changed; the primary list display components now share a common responsive data table/card renderer.

## Deliverables

### 1.1 Tokens and typography

- Added CSS tokens for body/supporting type, spacing, focus ring, and raised surfaces.
- Added visible keyboard focus, reduced-motion support, mobile text sizing, and responsive page-heading/layout rules.
- Added safe-area padding for the mobile navigation and top bar.

### 1.2 Navigation

- Primary navigation is Home, Sell, Inventory, and Products, with More exposing the remaining workspaces.
- Added mobile More/menu toggle labels and expanded-state attributes.
- Kept the command-search interaction and mapped readiness labels to `/ready` instead of a hard-coded online label.

### 1.3 Shared UI components

- Added reusable `DataState`, `ResponsiveDataTable`, `MobileRecordCard`, `PageHeader`, `StatusBanner`, `FormField`, and `ConfirmDialog` components.
- Migrated the Products catalogue and Inventory current-stock list to `ResponsiveDataTable` / `MobileRecordCard`.
- Products and Inventory clear list data when a refresh fails rather than presenting previously loaded data as if it were current. Inventory summary metrics render an em dash until the current request succeeds, avoiding false zero values.

### 1.4 Sign-in

- Reworked sign-in layout with explicit field labels, input autocomplete, a show/hide password button, customer-facing error state, workspace selection, and a safe local return path.
- Kept account-help guidance actionable; no dead “forgot password” link was added.

### 1.5 Registration and onboarding

- Added three resumable steps for business details, owner account, and review.
- The browser stores only the non-secret draft and current step in session storage; passwords are not persisted there.
- Added stable idempotency keys for retries and binds idempotency to the full registration request.
- Registration creates the workspace profile, Owner membership, first branch, warehouse, and stock location in the same transaction. It returns the created location IDs and starts sign-in; if automatic sign-in fails after registration succeeds, the user receives an explicit sign-in path.

### 1.6 Error language

- Centralized HTTP status-to-message mapping in `apps/web/lib/api.ts`.
- Added explicit, actionable copy for credential failures, permissions, missing records, conflicts, field validation (422), rate limiting, network failures, and server errors. Server errors advise checking whether the change was saved before retrying.

## Verification evidence

- `bash scripts/verify-phase0.sh`: **104 Python tests passed, 1 skipped**; **3 frontend Node contract tests passed**; utility syntax and migration-source reconciliation passed in normal (non-strict) mode.
- Python compilation of the changed auth route passed.
- TypeScript/TSX source transpilation was checked separately for syntax.
- The strict migration replay gate remains blocked because seven historical SQL source files are still missing. The exact missing files are listed in `migrations/SOURCE_RECOVERY.md`.

## Checks not completed

- A full `npm ci`, `npm run typecheck`, and `npm run build` could not be completed in this container because the npm registry dependency was unavailable and the requested `undici-types` tarball was not cached. GitHub CI is configured to run all three checks on Node 24.
- No visual browser screenshot pass was performed at 360, 390, 430, 768, and 1280 CSS pixels in this environment.
- No credentialed hosted registration/login acceptance was performed. The registration flow has not been exercised against live Render.

## Deployment status and blockers

This report describes a **source implementation handoff**, not a production deployment. GitHub writes previously returned HTTP 403 (`Resource not accessible by integration`), so no branch/PR could be assumed available. No Render deployment, Vercel production promotion, or canonical Neon schema mutation was triggered in this Phase 1 pass. Seven source migrations remain missing from Phase 0; do not replay an incomplete migration chain or invent replacement SQL to close that gate.

## Phase 1 acceptance status

| Gate | Status |
|---|---|
| Shared UX components and responsive primary lists | Implemented; static contract tests pass |
| Sign-in UX and workspace selection | Implemented in source; hosted flow not yet verified |
| Resumable first-workspace setup | Implemented in source; hosted flow not yet verified |
| Central error copy | Implemented; static contract tests pass |
| Python/backend regression suite | 104 passed, 1 skipped |
| Frontend static contract tests | 3 passed |
| Full TypeScript typecheck / Next.js build | Pending dependency install in CI |
| Required viewport screenshot checklist | Pending browser verification |
| Production deployment and credentialed E2E | Not performed |
| Overall production acceptance | **Pending** |
