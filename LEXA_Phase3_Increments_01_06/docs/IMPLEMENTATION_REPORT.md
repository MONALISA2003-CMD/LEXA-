# Implementation report — Phase 3 Increments 01–06 candidate

## Delivery composition and provenance

The package targets `MONALISA2003-CMD/LEXA-` pinned to `8124cca301062eac6ffe59f68d02fc689a3ffae1` and combines the Increment 01 business-setup prerequisites with workspace context/onboarding, memberships/invitations, role assignment, core branch authorization, and role/permission administration. It is a source-only overlay. It has not been committed to the hosted repository, merged, deployed, or applied to production.

The installer checks a clean worktree, the exact pinned HEAD, and original Git blob SHA-1s for every replacement. It refuses already-present new paths and generates two explicitly labelled historical SQL replay candidates only after checking the original blobs. An integration exercise used a disposable checkout reconstructed from the pinned-source archive; a copy of the installer was adjusted to that checkout's temporary commit SHA while preserving the original per-file blob guards. It confirmed the staging/copy path, but is not equivalent to testing the installer against the original pinned Git commit in place.

## Implemented behavior

### Business setup, workspace lifecycle and onboarding

The combined overlay supplies business profile and branch setup; active-workspace listing and switching; source-session revocation before context change; active destination checks; derived, resumable setup progress; workspace context and selection screens. Setup progress derives from stored records rather than a shadow completion flag.

### Membership, invitation and session lifecycle

Tenant-scoped member listing, activation/deactivation and branch assignment replacement are provided. Workspace deactivation revokes the user's sessions within that tenant. Last-owner removal is guarded under a shared advisory lock. Invitations use high-entropy one-time tokens, SHA-256 digests at rest, expiry and email binding, with raw tokens omitted from audit/outbox events. Create/resend is the only route that reveals the one-time link; idempotent replay does not re-disclose it. New and existing invitees use different password setup paths.

### Increment 04: role assignment

The role-replacement endpoint requires an active member in the selected workspace, validates every role against that tenant, requires a non-empty effective role set, and allows granting Owner only when the acting membership already has Owner authority. The last-owner invariant is checked under the same per-tenant advisory lock as deactivation. Audit and outbox writes are part of the transaction. The member administration page supplies draft checkboxes and an explicit save operation.

### Increment 05: branch access enforcement

`branch_access.py` resolves active branch assignments from current membership state rather than treating a client-supplied ID as authorization. Core inventory paths filter reads to assigned locations, validate stock mutations against the assigned location, and require both source/destination access for transfers. Tenant-wide inventory rebuild is guarded by full active-branch scope and fails if any active location is not tied to an active branch. Sales/returns, receivables, dashboard/reconciliation and analytics use branch checks or row filters. Workspace-wide finance/compliance and cross-branch analytics operations require every active branch assignment until those data models support safer partitioning.

This represents core-path implementation, not comprehensive proof for every endpoint. A static query-by-query authorization audit, authenticated E2E and negative database tests remain open. This package does not claim every branch-sensitive API is certified.

### Increment 06: role/permission administration

Workspace owners can inspect the permission catalog, create tenant roles and replace a custom role's permissions with validated global permission IDs. Role/permission mutations are tenant-scoped and audited/emitted through the outbox. The built-in Owner permission set is protected. The member screen now supports role creation, custom-role permission editing and member role assignment; it explains that permission changes affect every member holding that role. Security remains enforced on the server.

### Database candidate and history

Migration 030 extends the existing invitation and branch-assignment model, preflights prerequisites and duplicate conditions, enables forced tenant RLS and adds restricted helper functions. The active-workspace SECURITY DEFINER helper now binds its `p_user_id` argument to transaction-local `app.user_id`; the authenticated workspace API establishes that context after validating the live session. The separate login-time lookup remains pre-auth and unchanged. It must not be applied to production until historical source, clean replay, parity and release gates are resolved. The original malformed `021` remains untouched; the package provides a separately labelled repair candidate. The exact historical SQL files 010, 011 and 023–026 were not recovered.

## Render runtime audit follow-up — 2026-10-20

Read-only inspection was performed in Render workspace `My Workspace`, against service `LEXA` (`srv-dakm8k95efls73egg9a0`). The service's latest listed deploy is `dep-dbbgra1srm7s7386q0l0` for commit `a1ed64eec79daf3d74456c7b8b854d84f634d6fd`; its build and deploy events succeeded, and the service is listed as live. `healthCheckPath` is empty, although runtime logs recorded `/ready` and `/health` responses with HTTP 200.

The runtime log query produced a current, reproducible code defect: on 2026-10-20 at 07:01:40 UTC, `GET /api/v1/accounting/journal-entries` returned HTTP 500 when the optional `status` parameter was absent. PostgreSQL raised `AmbiguousParameter: could not determine data type of parameter $2` for `(:s IS NULL OR status=:s)`. The candidate `finance.py` now builds the status predicate only when a non-null value is supplied, leaving tenant filtering parameterized. A source sweep found the same risky nullable `IS NULL` predicate in `/api/v1/compliance/fiscal-documents`; that filter was corrected in the candidate too as a precaution, although no matching runtime failure was found for it. Source-contract regression coverage checks both optional filters and preserves the branch-scope guard.

Earlier commerce-dashboard HTTP 500s traced to `out(row)` assuming a SQLAlchemy row has `_mapping`. The currently inspected source already handles `Mapping` and SQLAlchemy row objects; no equivalent commerce stack was seen after the newest queried runtime deploy. Treat that historical issue as source-corrected but pending a post-release smoke test. The environment running this audit could not resolve the public Render hostname directly, so direct external HTTP probes were inconclusive; runtime logs are the evidence for the successful health responses. No Render service configuration, Git branch, deployment, credential or database was changed. Both optional-filter corrections remain local-only until a reviewed source release is authorized.

## Verification evidence

Latest `bash scripts/validate-package.sh` results: **38 Python tests passed**, Python compilation passed, **8 Node contract tests passed**, and the isolated TypeScript contract fixture passed. The suite includes the updated migration 030 identity-binding contract, authenticated-call ordering checks, member role/permission/branch source contracts and reconstruction-generator checks.

The separate SQL regression `tests/sql/lexa_list_active_user_workspaces_context_test.sql` passed on isolated Neon branch `br-purple-art-b1horduo` / database `lexa_phase0_3_cleanbridge`. It proved that user B cannot enumerate user A’s workspaces by passing A’s UUID and that missing `app.user_id` fails closed. Catalog verification showed `PUBLIC EXECUTE=false` and `lexa_app EXECUTE=true`; a post-run query found zero test tenants, users and memberships. This was an isolated branch write only, not a production change.

A full repository test run on the disposable installed-overlay checkout passed **116 tests with 1 skipped**. The only skip was `apps/api/tests/test_auth_refresh.py` because the `redis` Python dependency was unavailable. Python compilation of the installed API tree passed. The earlier isolated replay reached the expected candidate object counts (119 tables, 1,300 columns, 446 indexes, 1,799 constraints, 116 RLS policies, 460 public functions and 36 user triggers). Selected `lexa_app` RLS checks proved tenant-A reads did not expose tenant-B invitation/assignment fixtures and cross-tenant inserts were rejected; fixtures were deleted. Because the final small changes were reapplied idempotently to an existing replay, these counts do not establish a fresh empty-database replay or canonical schema parity.

The app's Node 24 base checkout passed an earlier clean install, typecheck, 23 frontend tests and production build. A full Node 24 clean install and app build on this expanded overlay were not completed; the separate sandbox stopped before dependencies were verified. The isolated TypeScript fixture and source-contract tests do not substitute for the real frontend build. The Redis-dependent auth-refresh integration is still skipped, and authenticated browser/API E2E has not been run on the overlay.

## Release blockers and remaining acceptance

1. Recover or obtain an approved disposition for exact historical SQL files 010, 011 and 023–026; keep exact-source checks failing until evidence exists. Review 021 repair candidate provenance.
2. Execute a fresh full-history replay from an empty isolated database with the final package, then diff schema objects, RLS, grants, functions and triggers against a current read-only canonical snapshot.
3. Install Redis/required backend services to rerun the skipped auth-refresh integration; run Node 24 app checks after overlay installation.
4. Run authenticated E2E for multi-workspace access, switching and revocation, invite expiry/replay, concurrent owner changes, role escalation, branch access, responsive layouts and keyboard/accessibility.
5. Complete a static route/query/table access audit; verify cross-branch denial on each branch-specific resource and that full-branch gates protect tenant-wide aggregates.
6. Review/approve runtime-role design. The prior production inspection reported overprivileged `lexa_runtime`; no role/credential change was made.
7. Reconcile hosted Vercel/Render source SHAs and health-check metadata only through authorized release work. Resolve GitHub integration permission (previous feature-branch creation returned 403) before remote branch/PR/CI work.

No live database, production role/credential, hosted setting or deployment was changed for this package.
