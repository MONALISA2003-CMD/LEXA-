# LEXA Phase 3 — Increment 01 Implementation Report

**Date:** 20 October 2026  
**Scope:** Business Setup and Workspace Administration  
**Candidate base commit:** `f48e201fc8c4ed0a9ff1551c0b99451a7eb500dd`

## Delivery state

The source patch and tests are prepared as a version-pinned overlay. They have **not** been written to GitHub: a branch-create attempt against `MONALISA2003-CMD/LEXA-` returned `403 Resource not accessible by integration`. No commit, branch, pull request, CI run, branch-protection update, deploy, hosted configuration change, or database write was performed. The package provides a guarded local apply path for a clean checkout at the verified candidate base.

## Implemented source slice

### API

- `POST /api/v1/organization/profile`: validates and normalizes business identity input; enforces an idempotency key; returns 409 for duplicate profiles or conflicting reuse of a key; emits a `BusinessProfileCreated` outbox event and audit log in the same transaction.
- `PATCH /api/v1/organization/profile`: updates only explicitly supplied fields, rejects empty/null patches, and emits `BusinessProfileUpdated` plus an audit record transactionally.
- `POST /api/v1/organization/branches`: enforces an idempotency key, maps integrity conflicts to 409, and records `BranchCreated` plus an audit event.
- `PATCH /api/v1/organization/branches/{branch_id}`: constrains lookup to the caller's tenant, rejects empty/null patches, and records `BranchUpdated` plus audit data.
- Warehouse and location creates now map `CatalogValidation` failures cleanly and roll back before returning cross-tenant parent-reference errors. POS-terminal creation uses the same idempotency/audit/outbox pattern and validates its branch within the current tenant.
- Mutating configuration routes require `Idempotency-Key` (the current web client already sends this for warehouse/location create and the added helpers send it for profile/branch mutations).

### Frontend

The Administration route is no longer a “planned depth” placeholder. It loads the profile, branches, warehouses, and locations with `Promise.allSettled`; offers profile create/update, branch create/update, warehouse creation, and location creation; displays status/error messages; uses labelled inputs and browser validation; and disables mutations while data is loading or partially unavailable.

### Non-goals in this increment

This is not full Phase 3. Invitations remain explicitly disabled. There is no member/invitation lifecycle, role-permission administration UI, branch-user assignment flow, last-owner protection, or session/device controls in this increment. No schema migration is added.

## Evidence recorded in this workspace

| Check | Result | Scope/limitation |
|---|---:|---|
| Python route compile | PASS | Candidate API module syntax only |
| Python source-contract tests | 5/5 PASS | Checks tenant filters, required idempotency, audit/outbox contracts and route surface |
| Python handler-unit tests | 11/11 PASS | Candidate route logic exercised against a fake SQLAlchemy session and lightweight fixture models/helpers; **not** PostgreSQL integration |
| Node administration/client contract tests | 4/4 PASS | UI/API source contract checks |
| TypeScript fixture typecheck | PASS | Strict check against narrow React/API declaration stubs, not the full Next.js app type environment |
| TypeScript syntax transpilation | PASS | Candidate admin page and helper-transform fixture |
| API-helper patcher fixture | PASS | Exact-anchor transformation adds profile/branch helpers once on the pinned source shape |
| Apply-script shell syntax | PASS | `bash -n` |

Current available Node runtime in this execution workspace is Node `v22.16.0`; the repository declares Node `24.x`. Consequently the full Node 24 clean install, complete application typecheck/test suite and Next production build for this **new candidate overlay** have not been run here. Use `scripts/validate-phase3-increment01.sh` on a pinned checkout with Node 24.

## Unchanged gates / remaining risks

- Remote GitHub write integration is blocked; no source commit/PR exists yet.
- Exact historic migration sources 010, 011, `023_phase4_purchasing_core`, 024, 025, and 026 remain unresolved. `021_phase5_analytics_foundation.sql` still needs a provenance-preserving source repair and fresh full replay/diff.
- Production least-privilege runtime role cutover and table-specific access validation remain open.
- No live Postgres/RLS/transaction rollback test, dedicated-account hosted login, invitation-flow E2E, or cross-tenant/cross-branch two-workspace browser acceptance has been run for this candidate.
- Render/Vercel release SHA parity and branch protection must be verified at a reviewed release candidate SHA; this patch was not deployed.

## Recommended next execution step

Apply the overlay only to a clean checkout matching all pinned guards, review the diff, run the Node 24 full validation script, then run isolated-Postgres tests and credentialed browser acceptance from `PHASE3_INCREMENT_01_ACCEPTANCE_MATRIX.md`. Keep production schema and role cutover blocked until existing Phase 0–2 gates are evidenced and individually cleared.
