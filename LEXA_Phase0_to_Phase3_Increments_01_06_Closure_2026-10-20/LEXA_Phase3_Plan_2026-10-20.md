# LEXA Phase 3 Plan — Business Setup and Workspace Administration

**Plan date:** 20 October 2026 (Africa/Kampala)  
**Basis:** LEXA repository head inspected in Increment 08: `4dac83541badc21800f84e652f0f192c211a612a`  
**Status:** Planning approved in principle; production schema changes and release remain **NO-GO** until the entry gates below are evidenced.

## 1. Phase charter and naming

For this plan, **Phase 3 means Business Setup and Workspace Administration**: making first-time setup, workspace selection, business configuration, memberships, invitations, role/permission administration, branches, warehouses/stock locations, and branch assignments safe, resumable and auditable.

The repository uses “Phase 3” in more than one way: migration `014_phase3_inventory_foundation.sql` is the inventory foundation; an older product/UX roadmap calls another track “Phase 3 — Product catalogue close-out.” Keep those as separate workstreams. Do not mix inventory/catalogue scope into this Phase 3 charter without an explicit versioned scope decision.

## 2. Outcomes

At the end of Phase 3:

1. A new business can register and finish setup without duplicate workspaces or lost progress when requests fail or are retried.
2. Users with zero, one, or multiple workspace memberships get clear, server-validated outcomes. Workspace or branch selection is never treated as authorization merely because the client supplied an ID.
3. Workspace owners/admins can maintain business settings, branches, warehouses/locations, memberships, invitations and role assignments within their authority.
4. Removing a membership, revoking an invitation or changing access takes effect server-side, including relevant session/cache invalidation.
5. Security-sensitive configuration changes are audited, transactional and idempotent where retries are possible.
6. API, database and browser tests demonstrate both allowed behaviour and denied cross-tenant/cross-branch access.
7. The release can be tied to one reviewed immutable commit with passing CI, recorded browser evidence and a tested rollback route.

## 3. Current baseline and blockers

The Phase 2 frontend checks did pass on Node `v24.21.0`: clean `npm ci`, typecheck, 23 frontend contract tests, production build, and four Chromium acceptance tests. Those browser checks covered route rendering, 390/768/1280px overflow, labelled login controls and keyboard focus. They were **not authenticated** and did not prove refresh/revocation, tenant-denial or business-write acceptance.

The historical scan examined 116 ZIP-related commits and 58 archive versions with zero matching copies and zero scan errors for these six missing original SQL sources:

- `010_phase2_catalog_intelligence.sql`
- `011_phase2_catalog_runtime_constraints.sql`
- `023_phase4_purchasing_core.sql`
- `024_phase4_purchasing_security.sql`
- `025_phase4_purchasing_permissions.sql`
- `026_phase4_membership_branch_integrity.sql`

These exact-source gaps must stay marked unresolved until byte-identical authoritative sources are recovered. Reconstructed SQL is not historical source. Also, the checked-in `021_phase5_analytics_foundation.sql` includes malformed escaped newlines and trailing non-SQL text; any repair must use an authorized reviewed change with before/after hashes and provenance.

The first isolated replay reached 119 tables and 116 RLS policies, but it was not schema-equivalent to the canonical clone: 14 fewer columns, 10 fewer indexes, 12 fewer constraints, three fewer public functions and four fewer triggers. Forty-eight common function definition hashes also differed. A compatibility delta was needed because available migration `012` did not create a composite payments key referenced by `016`. Later reconstructed hashes were not yet validated through a fresh clean replay; do not cite the first-pass object counts as parity proof.

GitHub feature-branch creation returned 403. Root CI and branch protection are therefore not installed/proven on the candidate. The Vercel candidate SHA and Render live SHA did not agree at the latest recorded check; Render's hosted `healthCheckPath` was blank although source declares `/ready`. The production `lexa_runtime` login has excessive attributes/membership, and the five exceptional tables (`permissions`, `registration_requests`, `schema_migrations`, `tenants`, `users`) need table-specific privilege designs and negative tests. No production mutation is authorized by this plan.

## 4. Work order and gates

### Gate 0 — Establish a releasable working lane

**Purpose:** avoid building/testing one candidate and releasing another.

- Obtain authorized GitHub branch/PR access. Do not bypass the ZIP extractor’s protection of `.github/workflows/**`; install CI via a reviewed repository change.
- Run the root workflow on the immutable candidate SHA: Node 24 clean install, frontend typecheck/contracts/build, full backend tests with declared dependencies, compile checks, recovery-manifest checker and migration-source check.
- Require named checks on `main`, then verify branch protection/ruleset is actually effective.
- Recover the six exact SQL sources **or** obtain a documented review decision permitting a forward-only replacement plan. If originals remain missing, keep the exact-source gate failing and label the forward chain as a new migration history.
- Review and repair `021` from authoritative bytes or through a provenance-preserving forward repair.
- Re-run current hash-pinned reconstructed migrations from an empty isolated database. Compare columns/defaults, constraints, indexes, RLS policy roles/USING/CHECK, grants, functions and triggers. Classify every delta and test critical behaviour. No production replay.
- Confirm an approved isolated LEXA test/staging target and dedicated disposable accounts/data. No separate Render staging service was found in the last inspection.

**Gate 0 exit:** one reviewed candidate SHA, reproducible CI pass, migration/provenance disposition recorded, current clean replay differences classified, and approved isolated E2E target available. A formal scope exception may permit source-only Phase 3 work while these are open, but it does not authorize schema changes or production cutover.

### Workstream 1 — Read-only contract and data-flow inventory

- Trace registration/login, refresh/logout, `/me`, workspace listing/selection, invitations, membership changes, branch access and all current settings endpoints through API routes, service functions, ORM/raw SQL, grants and frontend callers.
- Inventory existing tables/columns/constraints, the migration ledger, endpoint contracts and current role/permission codes. Distinguish “exists in schema” from “verified correct at runtime.”
- Write an endpoint/access matrix: unauthenticated, authenticated without a selected workspace, workspace member, branch-limited member, owner/admin, migration/operator and cross-tenant attacker.
- Mark every required behaviour as implemented, incomplete, missing or unsafe before adding routes or migrations.

**Deliverables:** reviewed API contract, role-action matrix, onboarding state diagram, per-table data ownership/access map and evidence-backed gap list.

### Workstream 2 — Idempotent, resumable setup

Define the setup lifecycle before implementation. Proposed conceptual states (map to existing schema/API if possible):

`not_started → account/workspace_created → business_profile_completed → first_branch/location_ready → operational_ready`

- Make every step safe under duplicate submit, timeout/retry, browser refresh and interrupted onboarding.
- Use request idempotency where writes can be repeated. A repeated key with a different canonical request hash must be rejected; it must not disclose a prior response payload to another request.
- Keep related user/workspace/default settings/first branch/first location writes transactionally consistent. Define explicit recovery behaviour for partial failure rather than silently creating duplicates.
- Preserve user-entered data across retry, present recoverable failure states and allow a returning user to resume without recreating existing objects.
- Define sensible defaults from business type/currency/time zone only where product policy supports them; do not assume server or browser locale is the business authority.

**Acceptance:** a fresh registration reaches a usable workspace; interrupted setup resumes; duplicate submissions produce one logical result; conflicting idempotency reuse fails safely; failures roll back or leave a documented resumable state.

### Workstream 3 — Workspace context and switching

- **Zero memberships:** show a safe recovery/registration/support state; do not accept a caller-chosen tenant ID as a substitute for membership.
- **One membership:** select the only eligible workspace through the authoritative API response.
- **Multiple memberships:** show a workspace picker with real business names and authorized descriptors, not UUIDs.
- Validate membership and tenant status server-side every time a workspace is selected or refreshed.
- Prompt for branch/location only when the operation requires that context. Branch choice is scoped to branches the member may access.
- On workspace switch, clear tenant-scoped state, cancel stale requests and invalidate client caches before rendering data from the newly selected context. A remembered last workspace is a preference only and must be re-authorized.
- Reject forged tenant IDs, branch IDs and resource IDs in paths, query strings and write bodies.

**Acceptance:** a user with one workspace proceeds correctly; a user with multiple workspaces selects either; invalid/disabled memberships fail safely; switching never flashes or reuses the previous workspace’s data.

### Workstream 4 — Business profile and administration

Implement against reviewed existing contracts first; propose a new schema migration only if the data model truly cannot support the required behaviour.

- Business profile/settings: name, legal/contact/tax fields, supported currency/time zone and any configurable business-date policy, with server-side validation and a visible saved/error state.
- Branches and stock locations: create/read/update/archive according to existing domain policy; preserve tenant-qualified relationships and define what happens to active sessions/transactions when a branch is disabled.
- Warehouses vs. locations: define whether these are separate business concepts in the existing schema before introducing synonyms or duplicated tables.
- Memberships: add/remove members, suspend access, show effective roles and allowed branch scope.
- Invitations: create, accept, expire, revoke and safely resend invitations; hash tokens at rest if compatible with the existing token model; prevent token reuse and cross-tenant acceptance.
- Roles/permissions: use a reviewed permission matrix, default-role map and guarded mutations. Protect the last active owner/administrator and prevent privilege self-escalation.
- Access changes must invalidate or revalidate affected sessions and authorization caches where relevant.

**Acceptance:** each state transition has a clear response, is authorized server-side, is retry-safe, and leaves the data/audit trail consistent.

### Workstream 5 — Security and access-control boundaries

Do not apply blanket RLS to all tables. Implement the reviewed per-table contract:

- `permissions`: global reference data; runtime should normally read only, with writes reserved to migration/operator paths.
- `schema_migrations`: readiness reads only; migration ledger writes belong to the release/operator path.
- `registration_requests`: narrow pre-tenant idempotency/bootstrap access; protect request-hash binding and response replay; do not grant DELETE unless a traced legitimate runtime path requires it.
- `tenants`: tenant creation only through an authorized atomic bootstrap; workspace reads must be membership-backed.
- `users`: narrowly scoped identity lookup and registration, then current-user/membership-scoped access; general lookups must not return password hashes or disclose other users.
- Runtime credentials: design and test a separate least-privilege login that can use `lexa_app` in the intended transaction boundary. Keep credential provisioning and any production role switch as separately approved release work.
- Verify EXECUTE grants, owner, `search_path`, argument provenance and returned fields of any SECURITY DEFINER helper.

**Acceptance:** two controlled tenants and at least two branches prove both allowed access and denied cross-tenant/cross-branch reads and writes. Also test user enumeration, forged selectors, invitation replay, role escalation, last-owner removal and attempts by the runtime principal to write global permissions or migration history.

### Workstream 6 — Auditability and operational safety

- Emit structured audit events for business-profile, branch/location, invitation, membership and permission mutations, including actor, target, outcome, correlation/request ID and safe before/after metadata.
- Do not record passwords, raw invitation tokens, refresh tokens or other secrets.
- Keep mutation, audit write and any outbox event in one transaction where supported.
- Document retry/duplicate handling, access revocation and the operator-only repair path.
- Update readiness only for true runtime requirements. Keep liveness (`/health`) distinct from dependency readiness (`/ready`). Verify the hosted Render control-plane path and reconcile deployment SHAs during the approved release.

### Workstream 7 — UI implementation and accessibility

Implement the user journey end-to-end rather than adding isolated form pages:

1. Registration / resume setup.
2. Business profile and first operational location.
3. Workspace selection for users with multiple memberships.
4. Workspace context bar with current business, branch/location and role where relevant.
5. Business settings and branch/location administration.
6. Member, role and invitation management.
7. Clear empty, loading, save-success, validation, permission-denied and recoverable-failure states.

Required browser matrix: 320, 360, 390, 430, 600, 601, 768, 800 and 1280 CSS px; screenshots and interaction records; no horizontal overflow or hidden primary action. Check keyboard-only signup/login/workspace selection, visible and non-obscured focus, labels/error associations, activation and zoom. Do not claim conformance without the corresponding evidence.

### Workstream 8 — Test and acceptance matrix

**Automated unit/contract:** setup state transitions, canonical request hashes, permission mapping, role/owner invariants, cache invalidation, audit records and error-response contracts.

**Backend/database integration:** successful bootstrap; rollback; partial failure/retry; duplicate/concurrent requests; invitation accept/expire/revoke/replay; membership removal; role denial; disabled workspace/branch; branch assignment; cross-tenant and cross-branch denial; SECURITY DEFINER hardening; RLS/grant inventory; readiness without tenant context.

**Credentialed browser/API E2E in approved isolated LEXA:** registration, login, `/me`, zero/one/multiple workspace outcomes, branch context, refresh rotation and reuse-denial, logout/revocation, user with reduced permissions, owner/admin setting changes, invite lifecycle, representative inventory/sales/accounting read paths and safe test writes, request failures/retries, workspace switching with no stale data, screenshots, keyboard and responsive matrix.

Tests must assert negative paths at the server/database boundary, not only hide buttons in the UI. Use disposable records and clean them up only in the isolated target.

### Workstream 9 — Release and rollback

- Release from one immutable commit SHA only. Bind the CI run, migration/replay evidence, browser artifacts, deployment IDs, health-check setting and artifact manifest to that SHA.
- Verify recoverable backup/PITR evidence and name the rollback owner before any database or credential change.
- Deploy first to approved LEXA staging/preview. Verify `/ready` fails when a required dependency fails, but liveness stays independent.
- Enable branch protection with successful required checks before merge; then verify Vercel and Render source SHAs align.
- Production schema/credential changes require a separate explicit approval, planned window, pre-change snapshot/backup evidence and tested rollback. Never use the runtime login as the migration administrator.

## 5. Phase 3 Definition of Done

Phase 3 is accepted only when all are true:

- [ ] The phase charter and API/access contracts are reviewed; duplicate Phase 3 nomenclature is resolved in project docs.
- [ ] Every setup/workspace/admin workflow above passes its positive and negative acceptance cases.
- [ ] Idempotency, resumability, audit records and transactional rollback are proven.
- [ ] Cross-tenant and branch isolation tests pass for two controlled tenants and multiple branches.
- [ ] All-table grants/RLS/functions/sequences are inventoried and reviewed against the access map; exceptional tables have their designed behavior and tests.
- [ ] The clean migration replay passes or every remaining source/parity gap is handled by a formally approved, hash-pinned forward-migration plan. Reconstructions remain labelled as reconstructions.
- [ ] Node 24 clean install, frontend typecheck/contracts/build and dependency-complete backend suite pass in CI on the exact release SHA.
- [ ] CI required checks and branch protection are effective.
- [ ] Credentialed browser/API acceptance and responsive/keyboard evidence are recorded.
- [ ] Render health-check metadata and Vercel/Render SHA alignment are verified.
- [ ] Backup/rollback evidence and release ownership are recorded.

## 6. Explicit non-goals and safety boundaries

- No production SQL, RLS/grant changes, role/credential changes, deployment triggers or hosted configuration edits during discovery and contract design.
- No rewriting reconstructed SQL under original migration names to make historical source checks pass.
- No broad RLS sweep over global/auth bootstrap tables without a table-specific trust design.
- No inventory-engine rebuild or product-catalogue close-out in this charter; those tracks need their own versioned plan and dependency decisions.
- No release acceptance based solely on green local tests, HTTP 200 public routes, or a READY deployment from another SHA.

## 7. Immediate next actions

1. Resolve authorized GitHub branch/PR access, then install and prove CI on a feature branch.
2. Reconcile the current migration artifacts, repair/recover `021` with provenance, and rerun the current reconstructed chain from a fresh isolated database.
3. Complete the read-only Phase 3 route/schema/access map and review the onboarding state machine and workspace/branch contract.
4. Obtain approved isolated LEXA credentials/data and a test target for authenticated E2E; confirm the current Render health-check control-plane state.
5. Only after the gate review, begin implementation in a reviewed feature branch. Keep production cutover separate.

**Decision:** proceed with non-mutating discovery, contracts, and source-only Phase 3 preparation. Do not start production schema-changing work or cut over credentials until Gate 0 and the relevant per-workstream gates have recorded evidence and approval.
