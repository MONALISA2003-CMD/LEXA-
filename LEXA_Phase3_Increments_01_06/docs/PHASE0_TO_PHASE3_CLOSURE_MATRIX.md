# LEXA Phase 0–3 closure matrix — Phase 3 Increments 01–06 candidate

**Pinned source:** `8124cca301062eac6ffe59f68d02fc689a3ffae1`  
**Delivery state:** candidate only; no hosted branch/PR, migration, production write or deployment.

## Phase 0–3 coverage and current acceptance state

| Phase/workstream | Candidate coverage | Latest evidence | State / remaining gate |
|---|---|---|---|
| Phase 0 — auth/session and tenant security | Existing auth/session model retained; active workspace options; switching revokes old session before tenant GUC change; tenant invitation/assignment RLS remains forced; workspace-list helper binds argument to authenticated `app.user_id`. | Package suite 38 Python + 8 Node; isolated identity-binding SQL regression; selected isolated `lexa_app` RLS test. | Partial. Historical source gaps, least-privilege runtime role, full grants/RLS and authenticated E2E not signed off. |
| Phase 1 — tenant/membership foundation | Uses tenant/membership/role/session schema and additive mappings/migration candidate. | Installer source guards and isolated schema metadata. | Partial. Exact history and clean replay/parity gates remain open. |
| Phase 2 — contracts, CI and source recovery | Hash-guarded installer, explicit migration candidates, manifests, tests. | Installer smoke integration in disposable source tree; installed-overlay full repo pytest passed 116 with 1 Redis-dependent skip; strict original-source gap list remains. | Partial. Hosted CI/branch protection unavailable; Node 24 app build and Redis integration remain open. |
| Phase 3 Increment 01 — business profile/branch prerequisites | Profile and branch/warehouse/location/POS API/UI prerequisite. | Static contract tests and installer source guards. | Candidate implemented; DB transaction/idempotency/accessibility tests remain. |
| Phase 3 Increment 02 — workspace switching/onboarding | Workspace options/context/select; old-session revoke; destination state validation; derived setup progress; UI routes/navigation. | Source-contract tests and workspace-domain unit tests. | Source candidate implemented; authenticated E2E and stale-cache/revocation tests remain. |
| Phase 3 Increment 03 — members/invitations/branches | Activation/deactivation, session revoke, owner guard, invitation lifecycle, branch assignment UI/data. | Source contracts and selected isolated RLS behavior. | Source candidate implemented; accept/replay/expiry race, last-owner race, session and browser tests remain. |
| Phase 3 Increment 04 — member role assignment | Tenant-scoped role replacement, active-membership check, Owner grant guard, shared lock, audit/outbox; explicit role picker save UI. | Additional Python/Node contract tests; backend compilation. | Source candidate implemented; authenticated permission/race tests remain. |
| Phase 3 Increment 05 — branch authorization | Core inventory/sales/returns path gates; branch-filtered inventory and analytics reads; full-branch gates for workspace-wide finance/analytics/rebuilds. | Source checks enforce helper imports and route guards. | Core route coverage implemented, not accepted as complete; static query audit and authenticated negative E2E remain. |
| Phase 3 Increment 06 — role and permission admin | Owner-only catalog, role creation, custom-role permission replacement, Owner role protected; UI for role/permission editing. | Source contracts, package type fixture, backend compile. | Source candidate implemented; API/browser E2E and permission catalog/seed parity remain. |
| Artifact reproducibility | Pinned Git SHA, exact blob guards, safe staging, replay-candidate generation, source hashes/checksums. | Package validator plus disposable installer integration. | Reviewable. Must apply against actual exact base checkout and review diff before merge. |

## Test and replay evidence

Latest package validation passes 38 Python tests, Python compilation, 8 Node source-contract tests and the isolated TypeScript UI/API fixture check. The new isolated Neon SQL regression proved the workspace-list SECURITY DEFINER function is bound to `app.user_id`; it denied a cross-user query and returned no rows when that context was blank. The post-check found no residual test fixtures. An earlier isolated Neon candidate replay reached 119 tables, 1,300 columns, 446 indexes, 1,799 constraints, 116 policies, 460 public functions and 36 user triggers; selected cross-tenant invitation/assignment RLS attempts were denied. These are selected isolated checks, not current canonical schema parity.

A disposable installer integration test applied the candidate overlay to a temporary source checkout reconstructed from the pinned source archive. The test copy's expected HEAD hash was changed to the temporary generated commit for this smoke test only, while original source-file Git blob guards remained unchanged. This demonstrates the installer copy/stage path but does not replace an apply test on the exact original Git clone.

Full Node 24 application clean install/typecheck/tests/build against the expanded overlay did not complete because the sandbox stopped before dependency verification. An earlier Node 24 run passed on the pinned **base only**, so it must not be presented as overlay validation. The Redis-dependent auth-refresh integration and authenticated app/browser E2E remain open.

## Render runtime follow-up — 2026-10-20

The confirmed Render workspace reports LEXA live with recent successful build/deploy events, but its health-check path is blank. Runtime logs show `/ready` and `/health` succeeding, an older commerce-dashboard mapping 500 whose source fix is now present, and a later 500 from `/api/v1/accounting/journal-entries` when the optional `status` parameter is omitted. The candidate now appends `AND status=:s` only when a status is supplied. The same safe optional-filter pattern was applied to `/api/v1/compliance/fiscal-documents` as a precaution; regression contracts cover both. These source fixes are not deployed; post-release smoke coverage and health-check configuration are still gated.

## Six unresolved original SQL gaps

- `migrations/010_phase2_catalog_intelligence.sql`
- `migrations/011_phase2_catalog_runtime_constraints.sql`
- `migrations/023_phase4_purchasing_core.sql`
- `migrations/024_phase4_purchasing_security.sql`
- `migrations/025_phase4_purchasing_permissions.sql`
- `migrations/026_phase4_membership_branch_integrity.sql`

Do not rename reconstructed equivalents to make the strict source checker pass. Original `migrations/021_phase5_analytics_foundation.sql` remains byte-preserved; its repair candidate is separate and requires review.

## Exit gates before Phase 3 can be called accepted

1. Recover/review historical SQL, review 021 repair candidate and approve a clear forward-history decision if originals stay unavailable.
2. Run fresh empty-database migration replay using exact final bundle; compare columns/defaults/constraints/indexes, functions/triggers, grants and RLS policies with the canonical snapshot.
3. Install Redis to rerun the skipped auth-refresh test; run Node 24 clean install/typecheck/tests/build after overlay installation.
4. Run authenticated API/database/browser tests for workspace switch/revocation, invitation replay/expiry, last-owner races, role escalation, branch crossing, business writes and UI keyboard/responsive matrix.
5. Complete a query-by-query route/table authorization audit; this candidate adds core route guards but is not comprehensive security acceptance.
6. Resolve GitHub branch/PR/CI access and require CI/branch protection on an immutable commit.
7. Reconcile Vercel/Render SHA and readiness metadata; confirm backup/PITR and rollback; approve runtime role and production operations separately.

**Safety:** no production DB, role/credential, service configuration, hosted repository branch, release or deployment was changed by this candidate.
