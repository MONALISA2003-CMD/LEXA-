# LEXA Phase 3 — Candidate overlay for Increments 01–06

**Repository:** `MONALISA2003-CMD/LEXA-`  
**Pinned source:** `8124cca301062eac6ffe59f68d02fc689a3ffae1`  
**Status:** reviewable source-only candidate. Not merged, committed, deployed, or applied to production.

This is a combined overlay for Phase 3 Increments 01–06, not a patch to stack on top of an earlier Phase 3 overlay. It contains the business-profile/branch prerequisites, workspace switching and resumable onboarding, membership/invitation/branch assignment controls, member role assignment, server-side branch access checks, role/permission administration, source provenance, replay-only aids, contracts and installation guardrails.

## Increment 01 — business setup prerequisites

- Supplies the business-profile/branch API and setup screen required by the later workspace/onboarding flow.
- Supports creating and listing a business profile, branches, warehouses, stock locations and POS terminals with tenant checks and relevant audit/idempotency patterns.
- This increment is included because Increments 02–06 depend on its routes and API types.

## Increment 02 — workspace context and resumable onboarding

- Adds active-membership-backed workspace options and workspace switching. A submitted tenant UUID is a selector, never an authorization claim.
- Revokes the prior session before changing transaction-local tenant context, checks the destination workspace is active, then returns new session credentials.
- Makes login use the active workspace list and rejects inactive destinations.
- Adds workspace context and setup progress derived from persisted profile/branch/warehouse/location records, plus workspace-selection and resume screens.

## Increment 03 — memberships, invitations and branch assignments

- Adds tenant-scoped member listing, activation/deactivation, branch-assignment replacement and invitation create/preview/accept/revoke/resend.
- Deactivation revokes that workspace's sessions. Last-owner protections share an advisory lock across sensitive membership changes.
- Invitation tokens are high entropy, stored as SHA-256 digests, expiry-checked and one-use. Raw links are disclosed only on create/resend; audit/outbox metadata excludes secrets. Existing users prove their password and new invitees bind to the invited email.
- Migration 030 extends the existing invitation/branch-assignment contract rather than creating a parallel invitation table. Production application remains blocked by historical-source and clean-replay gates.

## Increment 04 — member role assignment

- Adds `PUT /api/v1/members/{membership_id}/roles` with tenant-scoped active-membership validation, role ownership checks, at-least-one-role policy and an Owner grant guard.
- The role replacement and member deactivation use the same tenant-level advisory lock when checking the last active Owner.
- Audits role changes and emits a safe outbox event. Team and Access now has role checkbox drafts plus an explicit save action.

## Increment 05 — branch enforcement on core business paths

- Adds shared fail-closed helpers to resolve active branch assignments at request time, validate locations against active branch-linked warehouses, and gate workspace-wide actions.
- Inventory list/detail and mutation flows (balances, ledger, product inventory, adjustments, counts, transfers, rebuild and integrity) now filter by or validate assigned branches. Transfers require access to both endpoints. Workspace-wide rebuilds require full branch access and reject unscoped active locations.
- Sales/returns, receivables, daily dashboard/reconciliation, and branch-aware analytics apply branch access checks or scope filters. Finance/compliance and cross-branch analytics operations are fail-closed behind full-branch access because their current underlying aggregates are workspace-wide.
- This is core route coverage, not a claim that every API/data path has passed a static query audit or authenticated E2E. Legacy locations not tied to an active branch must be repaired using normal reviewed business setup before branch-scoped writes can use them.

## Increment 06 — role and permission administration

- Adds an owner-only role/permission catalog, tenant role creation, and permission replacement for custom roles, using the existing global permission catalog.
- Validates that role and permission IDs belong to their expected scope; logs audit/outbox records for changes; protects the built-in Owner permission set.
- Team and Access now includes role creation and a permission editor; the UI explicitly notes that a role's permission changes apply to every member with that role. The backend remains the authorization boundary.

## Apply to a local checkout

The installer is intentionally strict and source-only. It expects the exact pinned Git commit and a clean worktree, checks exact Git blob SHAs for the replacement targets and refuses collisions at new paths. Review the resulting diff in a disposable feature checkout before running the application test suite.

```bash
python /path/to/LEXA_Phase3_Increments_01_06/scripts/apply_phase3_increments_02_03.py
```

The installer does not run SQL, alter database credentials, create a commit, push a branch, run CI, or deploy. The replay-equivalent 004 and repair-candidate 021 files generated by the installer remain explicitly labelled and do not overwrite historical originals. Do not apply this combined patch to an already modified Phase 3 checkout.

## Validation performed for this candidate

- `bash scripts/validate-package.sh`: **46 Python tests passed**, Python syntax compilation passed, **8 Node source-contract tests passed**, isolated TypeScript UI/API contract fixture typecheck passed.
- A new isolated Neon SQL regression test exercises `lexa_list_active_user_workspaces(uuid)`: user B cannot list user A’s workspaces by passing A’s UUID; blank `app.user_id` returns no workspaces. The catalog also confirms `PUBLIC` cannot execute the helper and `lexa_app` can. Synthetic fixtures were deleted before the test statement completed; a separate post-check found zero residual fixture rows.
- Full repository test run in the disposable installed-overlay checkout: `python -m pytest -q` — **116 passed, 1 skipped**. The skipped test is `apps/api/tests/test_auth_refresh.py`, because the `redis` dependency is not installed in this environment; compileall on the installed API tree passed.
- The installer was exercised in a disposable full-source checkout reconstructed from the pinned-source archive. A copy of the installer had only its expected HEAD value adjusted to the temporary checkout's generated commit SHA; the strict original-file Git blob guards remained unchanged and passed. Seven installed candidate files matched package bytes and the appended role APIs plus both generated replay candidates were verified. This demonstrates staging/copy behavior, not a test of applying directly to the original pinned SHA.
- Earlier isolated Neon candidate replay evidence: 119 tables, 1,300 columns, 446 indexes, 1,799 constraints, 116 RLS policies, 460 public functions and 36 user triggers. Under `lexa_app`, selected invitation and branch-assignment RLS paths blocked cross-tenant reads/writes; the new workspace-list identity-binding SQL regression also passed. Test fixtures were removed, with a separate zero-residual check. This was not a new clean replay using the exact final package from an empty database, nor canonical schema parity signoff.
- The pinned base web application passed Node 24 checks in an earlier disposable run (clean install, typecheck, 23 frontend tests and production build). A full Node 24 install/typecheck/test/build for this expanded overlay was **not completed**: the separate validation sandbox stopped before the dependencies could be verified. Isolated fixture checking is not a substitute for the app build.

## Historical migration replacement fallback

If the six exact original SQL files remain unrecoverable, the package now includes `scripts/replace_missing_migrations.py`. Run it from a **full LEXA checkout**, not this overlay-only directory. First run dry-run mode, inspect the six pinned equivalence sources, then use `--apply` to create clearly labelled canonical-path replacements. The installer verifies source Git blob SHA-1s and SHA-256 output checksums, refuses to overwrite unknown SQL, preserves the original checker, and installs a replacement-aware checker. It does not run SQL.

A review-ready CI workflow candidate is supplied at `release-controls/lexa-ci.yml`. It is deliberately outside `.github/workflows/` because the current repository ZIP extractor protects that directory; it must be installed through a separately authorized, reviewed GitHub change. It runs Python 3.13 tests with Redis, a Node 24 clean frontend install/typecheck/tests/build, and the migration provenance gate. The `LEXA_ALLOW_SQL_REPLACEMENTS` repository variable is an explicit opt-in for path validation with labelled equivalents; it does not certify clean replay or historical byte parity.

The replacement-aware checker keeps the strict historical-byte gate **blocked by default**. Use `--strict --allow-replacements` only to permit a disposable replay with explicit acceptance; it still reports the six sources as replacements rather than recovered historical bytes. Clean replay, schema/RLS/grant parity, and release review are still required. The installer and its tests passed package validation; it has not been run against the connected repository because GitHub branch creation currently returns HTTP 403. See `docs/EXECUTION_REMAINING_WORK_2026-10-20.md` for current platform evidence.

## Render runtime audit follow-up — 2026-10-20

A read-only inspection of the confirmed Render workspace found the LEXA service live on `main` with successful recent build/deploy events. Render's `healthCheckPath` is blank even though logs show `/ready` and `/health` returning HTTP 200. The logs also captured a real HTTP 500 from `GET /api/v1/accounting/journal-entries` when `status` is omitted: PostgreSQL could not infer the type of the nullable second bind parameter in `(:s IS NULL OR status=:s)`. The local candidate replaces that nullable predicate with a parameterized optional filter and adds a regression contract. A source sweep found the same risky predicate in `/api/v1/compliance/fiscal-documents`; that route now uses the same safe optional-filter pattern as a precaution (no corresponding 500 was found in the queried logs). **Neither candidate change is committed, merged, or deployed.** Earlier commerce-dashboard row-mapping 500s are consistent with an older runtime revision; the current source serializer handles both SQLAlchemy `Row` and `RowMapping`, but a post-release request check is still required. See `docs/RENDER_RUNTIME_AUDIT_2026-10-20.md`.

## Remaining acceptance gates

1. Recover the exact original historical SQL bytes for migrations `010`, `011`, and `023`–`026`; keep their reconstructed equivalents clearly labelled. Review the malformed original `021` and its separate repair candidate.
2. Run a brand-new clean isolated replay from an empty database using the exact final replay order; compare canonical schema definitions, grants, policies, functions and triggers.
3. Add Redis/required services and rerun the skipped auth-refresh integration; run app-level Node 24 clean install/typecheck/tests/build after overlay installation.
4. Run authenticated database/API/browser E2E for workspace switching, refresh/revocation, invitations and replay/expiry, last-owner races, role escalation, branch-denial cases, and responsive/keyboard acceptance.
5. Finish the static route/query authorization audit across all branch-sensitive paths and verify all business tables are covered; this package adds broad core-path guards but is not an end-to-end authorization certification.
6. Resolve authorized GitHub branch/PR/CI access. A previous branch-creation call returned 403; no remote branch, PR, CI or release was created.
7. Separately approve any runtime-role, credential, migration, hosted service-setting or production deployment change. No production writes were performed for this candidate.

## Historical source gaps are intentionally unresolved

- `migrations/010_phase2_catalog_intelligence.sql`
- `migrations/011_phase2_catalog_runtime_constraints.sql`
- `migrations/023_phase4_purchasing_core.sql`
- `migrations/024_phase4_purchasing_security.sql`
- `migrations/025_phase4_purchasing_permissions.sql`
- `migrations/026_phase4_membership_branch_integrity.sql`

The equivalents under `migrations/reconstructed/` are not originals. The standalone strict history check must remain failed until authoritative bytes or an explicit approved forward-history decision exist.
