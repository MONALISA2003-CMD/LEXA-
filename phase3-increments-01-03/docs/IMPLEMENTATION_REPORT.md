# Implementation report — Phase 3 Increments 01–03 deep candidate

## Delivery composition

This package includes Increment 01 business-profile/branch route and administration-page overlays because the Increment 02 resumable onboarding depends on those edits. The installer therefore applies the required 01 prerequisites plus Increments 02 and 03 as one combined overlay against a clean checkout pinned to the exact inspected `main` head. It refuses duplicate application and rejects dirty trees.

## Source evidence and baseline

The source overlay targets `MONALISA2003-CMD/LEXA-` at `8124cca301062eac6ffe59f68d02fc689a3ffae1` (the inspected `main` head on 20 October 2026). Existing source already implements a login 409 response for multiple workspaces and the login page already displays those choices. This patch extends that flow instead of duplicating it. Existing ORM models cover tenants, users, memberships, roles, sessions, branches, warehouses and locations; the inspected model set did not include invitation or membership-branch tables. The overlay supplies additive mappings and a candidate migration.

## Implemented behavior

### Workspace lifecycle

`GET /api/v1/workspace/options` enumerates active membership-backed workspace options. `POST /api/v1/workspace/select` validates the requested tenant against that authoritative list, checks the source session and user, revokes the old session before changing the transaction-local tenant RLS context, verifies that the destination tenant is active, then issues a new session/access token and refresh cookie. The login path is patched to use the active-workspace list and reject suspended destinations.

`GET /api/v1/workspace/context` returns current workspace and membership details plus branch-assignment context. `GET /api/v1/workspace/setup/progress` derives the required setup checklist from persisted profile, branch, warehouse and location records. `POST /api/v1/workspace/setup/complete` verifies required records and returns a derived completion status; it deliberately does not write a duplicated completion flag.

### Members and invitations

Members can be listed, activated/deactivated and assigned an explicit set of active branches within the current tenant. Deactivation revokes that user's sessions for the workspace. Removing the only active owner is rejected. Invitation creation checks the role and all branch IDs against the current tenant, refuses manager-to-owner escalation, uses an idempotency key, and generates a one-time random bearer token. Only its SHA-256 digest is saved; audit/outbox payloads contain no bearer token. New links use a URL fragment, and preview submits the token in a POST body; the invite page strips the fragment from browser history after reading it. An idempotency replay does not return a stored secret. Resend invalidates the previous invitation and creates a new token. Acceptance is bound to the invitation email and role/branch scope, rejects expired/replayed tokens, verifies existing account passwords, and creates a membership and session transactionally.

### Candidate database migration

`migrations/030_phase3_workspace_memberships.sql` extends the existing migration-023 `tenant_invitations` and `membership_branch_assignments` tables, adds branch/status fields and pending-invite uniqueness, maintains forced tenant RLS, adds restricted SECURITY DEFINER lookup functions, and grants `members.read`/`members.manage` only to existing Owner roles. It fails early if prerequisite tables or duplicate memberships are found. It is **not approved to run yet** because the Phase 0–2 migration-history and parity gates are still unresolved.

## Verification evidence

The package tests exercise the pure progress/token helpers, source-contract invariants and replay-candidate generator safeguards. Final package validation: **26 Python tests passed**, Python compilation passed, **4 Node tests passed**, and TypeScript fixture checking passed. The pinned base checkout also passed Node 24 install/typecheck, 23/23 frontend tests and production build; those frontend checks were not run after installing this source overlay. The final validation record is `VALIDATION_RESULTS.json`.

## Not yet verified / go-live blockers

1. An isolated Neon branch database reached migration 030 using explicitly labelled equivalents for the six unrecoverable sources, the decoded 021 repair shape, and explicit 004/005a/025a compatibility steps. After correcting the replay-only PK/index handling, the candidate 025a/030 DDL was reapplied idempotently: `membership_branch_assignments` now has `PRIMARY KEY (id)` and only one `(tenant_id, branch_id, status)` index. Final snapshot: 119 tables, 1,300 columns, 446 indexes, 1,799 constraints, 116 RLS policies, 460 public functions, 36 user triggers. Both Phase 3 tables have enabled + forced RLS and a tenant predicate; helper ACL/search_path was inspected. A two-tenant transaction under `lexa_app` confirmed per-tenant reads and rejected cross-tenant invitation/assignment inserts; temporary fixtures were removed. This is isolated SQL/RLS behavior evidence, not full authenticated app E2E or canonical parity signoff.
2. Exact historical migrations 010, 011 and 023–026 remain unrecoverable. A provenance-labelled clean replay bundle has been constructed and reached 030, but equivalences are not original bytes; 021 remains malformed in its original path and the repaired candidate must be reviewed before repository application.
3. The production `lexa_runtime` role remains overprivileged and `lexa_runtime_safe` was absent in the last recorded inspection. No role change was attempted.
4. No authenticated browser E2E has proven invite expiry/replay, multi-workspace switching, membership removal session invalidation, last-owner protection or cross-tenant/cross-branch denial. The isolated DB replay verifies metadata/RLS flags and zero orphan checks, not the full ASGI request/data-plane behavior.
5. This increment persists branch assignments and exposes them in workspace context. Every branch-scoped business endpoint must still be wired to enforce assignments before calling Phase 3 fully accepted; tenant-scoped CRUD alone is not proof of branch isolation.
6. The real app's Node 24 clean install, dependency-complete frontend typecheck/build/tests and backend test suite have not been run on this overlay.
7. GitHub branch/PR write permission remains unavailable (prior branch creation attempt returned 403). No remote branch, commit, pull request, CI, deployment or hosted setting was changed.
