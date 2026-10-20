# LEXA Phase 0–3 Increment 3 closure matrix

**Inspection baseline:** `MONALISA2003-CMD/LEXA-` `main` at `8124cca301062eac6ffe59f68d02fc689a3ffae1`, inspected 20 October 2026.  
**Delivery boundary:** candidate code and replay artifacts only; no production migration, role change, service setting, deployment, merge, or live data write was performed.

## What is covered in the candidate

| Area | Candidate coverage | Evidence available | State / unresolved gate |
|---|---|---|---|
| Phase 0 — auth/session and tenant security | Existing auth/session model is retained; current source migrations 028–029 are included in clean replay order. Increment 02 validates active workspace membership server-side and revokes the old session before switching transaction-local tenant context. | Auth source-contract checks; full base checkout Node 24 tests/build; isolated DB role/RLS metadata queries. | **Partial acceptance.** Live role least-privilege rollout, authenticated revocation E2E, and cross-tenant runtime behavior are not proven. Historical SQL gate remains. |
| Phase 0 — health/readiness and deployment wiring | Prior closure artifacts record Render `/health` and `/ready` as healthy; source has `/ready` readiness contract. | `LEXA_Phase0-2_Closure_Report_2026-10-20.md` and prior validation JSON. | Render service health-check configuration still needs approved alignment; no service setting changed. |
| Phase 1 — tenant/business foundation and least privilege | Existing migrations 001–009, 012 and 029 are retained. New setup completion is derived from persisted profile/branch/warehouse/location state, not a duplicate flag. | Clean isolated replay reached schema version 030 using the explicit order file; 030 checks `lexa_app` exists. | Production `lexa_runtime` remains a recorded high-privilege login; no credential or role cutover executed. |
| Phase 2 — product catalogue and runtime constraints | Original available migrations 007, 012–015 and reconstructed equivalent files for gaps 010/011 are documented; payment identity compatibility equivalent included in replay sequence. | Clean replay reached 119 public tables and retained RLS metadata. | Exact historical sources 010 and 011 still unavailable. The strict historical-source checker must stay failed. |
| Phase 2 — purchasing/membership integrity | Original 023 identity/tenant migration remains distinct from reconstructed purchasing 023–026 equivalents. Replay-only 025a reconciles the existing assignment-table shape before reconstructed 026. | Replay of this documented sequence succeeds through 029, then candidate 030. | Exact historical purchasing SQL 023–026 still unavailable; equivalents do not prove original bytes. |
| Phase 2 — migration 021 analytics | Original source bytes remain at `migrations/021_phase5_analytics_foundation.sql`; generator validates its expected Git blob and writes a separate candidate after decoding escaped line breaks and removing pasted tool code. | Prior isolated replay of a decoded candidate succeeded; output is not written over the original path. | Repair candidate requires code review and exact canonical schema comparison before it can replace anything. |
| Phase 3 Increment 01 — business profile and branch setup | Combined installer includes the increment-01 API/UI prerequisite plus profile/branch helpers used by onboarding. | Prior package contract suite. | Hosted-repository branch/commit/PR was not created; do not claim merged or deployed. |
| Phase 3 Increment 02 — workspace context and resumable onboarding | Workspace options/select/context API, active membership validation, old-session revoke ordering, progress-from-records, workspace selector and resumable onboarding page. | 26 Python package tests, 4 Node contract tests, TypeScript fixture check; base checkout Node 24 app typecheck/build/tests passed (23 frontend tests). | Full application overlay typecheck/build, token-refresh browser flow, authenticated workspace-switch browser test, and DB-backed ASGI tests still required. |
| Phase 3 Increment 03 — memberships/invites/branch assignments | Tenant-scoped membership listing/status changes, last-owner serialization guard, deactivation session revocation, branch assignment replacement, one-time invitation create/preview/accept/revoke/resend, token hash only at rest, idempotency and audit/outbox calls; Owner-only membership permissions. | Package tests and isolated DB metadata/orphan checks; candidate migration 030 targets the existing `tenant_invitations` table rather than creating a duplicate table. | No mail provider is configured; administrators copy one-time links. Branch-specific business endpoint enforcement is not comprehensively wired. Authenticated acceptance, expiry/replay concurrency and last-owner concurrency E2E are still open. |
| Release / provenance / parity | SHA-guarded installer, manifest, replay-order JSON, replay-only candidates for the 004/005a/021/025a source-shape gaps, and checksum package. | Clean child Neon branch `br-purple-art-b1horduo`, database `lexa_phase0_3_cleanbridge`: 119 tables, 1,300 columns, 446 indexes, 1,799 constraints, 116 RLS policies, 460 public functions, 36 user triggers; RLS enabled + forced on invite/assignment tables; under `lexa_app`, tenant-A reads saw only A fixtures and cross-tenant inserts were denied; all temporary fixtures were deleted; zero orphan memberships, assignments, invitations. | Canonical live comparison still differs from earlier recorded counts. The final candidate DDL was re-run idempotently, the membership-branch primary key is `PRIMARY KEY (id)`, and the duplicate branch-status indexes were removed. The replay proves the result is executable with labelled equivalents and the two target RLS policies behave under `lexa_app`; it does **not** prove canonical schema parity or exact applied-byte provenance. |

## Six exact historical SQL gaps — stay visible

The package must never install guessed SQL into the six expected historical paths:

- `migrations/010_phase2_catalog_intelligence.sql`
- `migrations/011_phase2_catalog_runtime_constraints.sql`
- `migrations/023_phase4_purchasing_core.sql`
- `migrations/024_phase4_purchasing_security.sql`
- `migrations/025_phase4_purchasing_permissions.sql`
- `migrations/026_phase4_membership_branch_integrity.sql`

Reconstructed equivalents are kept under `migrations/reconstructed/` and identified as equivalents in the existing source-gap manifest. The database migration ledger only records version strings; it cannot certify historical SQL bytes. Owner-held backups could still change this finding, but no authoritative copies were found in inspected archives/accessible repository history.

## Replay-only files are not production migrations

`004_catalog_and_rbac_hardening.replay-equivalent.sql`, `005a_phase0_outbox_contract_reconciliation.replay-only.sql`, and `025a_phase2_membership_branch_contract_reconciliation.replay-only.sql` exist only to let a disposable clean replay bridge the ordering/shape differences between available files. `021_phase5_analytics_foundation.repair-candidate.sql` is a separate repair candidate. None is represented as historical original bytes. Follow `migrations/reconstructed/clean_replay_order.json` only in a disposable test database.

## Final exit conditions before calling Phase 3 accepted

1. Review generated replay candidates, reconstructed equivalents, and the source-gaps manifest; do not close historical recovery by renaming equivalents.
2. Compare clean replay schema against a newly collected, read-only canonical snapshot, resolving outstanding column/index/constraint/function/trigger diffs.
3. Run full Python backend suite on the installed overlay with required services (including Redis integration) and run all app frontend checks on Node 24 *after* overlay installation.
4. Perform authenticated browser/database E2E for multi-workspace switching, session invalidation on membership deactivation, invitation token expiry/replay, last-owner race, tenant crossing, and branch crossing.
5. Wire branch assignment enforcement into every branch-scoped business endpoint and prove denial of unassigned branches; the current increment only manages and surfaces assignment data.
6. Approve the least-privilege runtime-role/connection change separately; do not change live credentials or roles without the explicit production gate.
7. Obtain repository push/PR permissions, review the diff, authorize migration/release, and document rollback. No PR, CI/release branch, or deployment is claimed here.
