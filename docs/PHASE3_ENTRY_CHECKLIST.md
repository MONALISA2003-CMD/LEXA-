# LEXA Phase 3 Entry Checklist

This is the go/no-go checklist for Phase 3 (business setup and workspace configuration). The authoritative current status is `docs/PHASE0_2_CLOSURE_AUDIT_2026-10-20.md`; older readiness audits are historical snapshots.

## Phase 3 goal

Implement reliable business/workspace setup and ongoing administration using existing, verified contracts: business profile/settings; tenant/workspace context; memberships, invitations, roles and permissions; branches, warehouses, stock locations; user-to-branch assignments; resumable onboarding; explicit scope when users have multiple workspaces/branches; and audit trails for configuration mutations.

## Go/no-go gates

- [ ] Root GitHub Actions CI exists, runs on the active source paths, and has a green run on the exact release commit.
- [ ] `main` requires the CI checks; the Vercel deployment check is not the only required status.
- [ ] The six remaining missing exact migration sources—010, 011, `023_phase4_purchasing_core`, 024, 025, and 026—are recovered and reviewed, or a formal migration-provenance plan is approved that keeps strict replay blocked and explicitly scopes any allowed non-schema work. `027_release_convergence.sql` has been recovered from tracked historical Git source with blob/checksum verification; the database ledger itself has no executed-SQL checksum, so this is artifact-provenance evidence, not a DB-side checksum.
- [ ] The elevated `lexa_runtime` production login has an approved, tested least-privilege cutover plan. Do not change credentials or roles without approval.
- [ ] RLS and grants for `permissions`, `registration_requests`, `schema_migrations`, `tenants`, and `users` have documented intended access and tests on an isolated branch.
- [ ] Credentialed hosted auth and workspace selection acceptance passes using a dedicated non-production account.
- [ ] Tenant isolation and branch isolation are tested across two controlled tenants/branches; unauthorized access is denied server-side.
- [ ] Node 24 clean install, typecheck, frontend tests, and production build pass.
- [ ] Phase 2 five-width responsive and accessibility review is recorded.
- [ ] Render health-check configuration and deployed source commit are reconciled in the release record.

## Phase 3 design/implementation sequence once gates permit

1. Inventory current schema, migration ledger, backend route contracts, frontend callers, and authorization checks. Do not assume a route or table is correct merely because it exists.
2. Define the authoritative onboarding state machine and transactional defaults; make retry/resume safe and idempotent.
3. Define workspace/tenant selection behavior for zero, one, or multiple memberships.
4. Define branch/warehouse/location assignments and server-side scope enforcement for each endpoint.
5. Define invitation lifecycle, membership changes, role/permission policy, session revocation, and last-admin/owner protection.
6. Add audit events for profile, branch, location, membership, invitation, and permission mutations.
7. Add integration tests for new workspace setup, resume after partial failure, duplicate retries, invitation accept/expire/revoke, membership removal, role denial, cross-tenant and cross-branch denial, and transaction rollback.
8. Only add schema migrations after source history review, isolated-branch validation, backup/recovery plan, and explicit approval.
9. Complete UI/API/database E2E in a disposable workspace and record the exact source commit plus test evidence.
