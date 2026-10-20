# LEXA Phase 3 — Deep Candidate for Increments 01–03

**Repository:** `MONALISA2003-CMD/LEXA-`  
**Pinned base:** `8124cca301062eac6ffe59f68d02fc689a3ffae1`  
**Delivery state:** source-only candidate overlay; not merged, committed, deployed, or applied to a live database. The package includes the required Increment 01 business-profile/branch UI and API files so all changes can be applied atomically once to the exact pinned base.

## Increment 02 — workspace context and resumable onboarding

- Adds a verified active-workspace listing and workspace switch endpoint. A requested tenant UUID is treated only as a selector; the server verifies membership through a narrowly-returned database function before issuing a fresh session.
- Revokes the previous session while the old tenant's transaction-local RLS context is still set, before changing tenant context. The new workspace must still be active.
- Hardens login to use the active-workspace list and fail closed when a requested workspace is suspended.
- Adds a workspace context read containing current membership and server-resolved branches, plus an onboarding-progress API and resume screen.
- Setup state is derived from persisted business-profile/branch/warehouse/location records, avoiding a second, potentially stale `setup_completed` flag.
- Adds a workspace selector page and reachable navigation from the existing application shell.

## Increment 03 — memberships, invitations and branch assignments

- Adds tenant-scoped membership listing, activation/deactivation and branch assignment replacement.
- Deactivation revokes the target user's sessions in the workspace. The API refuses to deactivate the last active workspace owner.
- Adds invitation create, preview, accept, revoke and resend flows. Tokens are high-entropy, stored only as SHA-256 digests, expiry-checked, one-use, and not written to audit/outbox events. New links keep the token in the URL fragment, and preview sends it in a POST body rather than a query string. A raw link is shown only in the creation/resend response; an idempotent replay returns no token and prompts a fresh resend.
- Acceptance binds to the invited email. Existing users must prove their password; new invitees must set a password. Membership, role assignment, optional branch assignments, invitation consumption, new session, audit and outbox event are committed together.
- Adds role/branch management UI and replaces the disabled invitation placeholder with a real invitation acceptance flow.
- Adds migration 030 to extend the existing migration-023 `tenant_invitations` and `membership_branch_assignments` tables, preserve composite tenant keys/RLS, add the branch-invitation/status contract and pending-invite uniqueness, and register active-workspace/invitation lookup functions plus Owner-only member permissions.

## Apply locally

This is a **combined** overlay, not a standalone patch to stack on top of Increment 01. It installs Increment 01’s prerequisites plus Increments 02 and 03 in one guarded operation. From a clean repository root at the exact pinned commit:

```bash
python /path/to/LEXA_Phase3_Increments_02_03/scripts/apply_phase3_increments_02_03.py
```

The script verifies the pinned commit, a clean worktree, exact original source blobs, duplicate anchors and all new-target collisions before staging any files. It then copies the reviewed candidate overrides and applies exact-anchor edits to auth routing, navigation and API helpers. It **refuses** if Increment 01 or 02/03 changes are already present; do not apply it atop another Phase 3 overlay. Review the resulting `git diff` before any tests or SQL.

**Do not run migration 030 in production yet.** An isolated Neon database was replayed through 030 using a documented sequence of labelled equivalents and replay-only reconciliation steps. The corrected 025a/030 primary-key/index DDL was then reapplied idempotently and the resulting state has 119 tables, 1,300 columns, 446 indexes, 1,799 constraints, 116 RLS policies, 460 public functions and 36 user triggers. That validates the resulting isolated schema and selected RLS behavior, but is not a brand-new replay of the final package from an empty database and is not proof of exact source-byte parity with the canonical live database. The exact historical SQL originals 010, 011 and 023–026 remain unavailable; `021` is retained byte-for-byte and a separate repair candidate is supplied. Production migration, DB role changes, authenticated E2E and schema-parity signoff remain blocked.

## Validation currently performed

- Package Python suite: `python -m pytest -q tests` — **26 passed** (includes replay-candidate generator regression guards).
- Python syntax compilation: `python -m compileall -q overrides/apps/api/app scripts` — passed.
- Node source-contract suite: `node --test tests/phase3-increments-02-03.test.mjs` — **4 passed**.
- TypeScript UI/API-helper fixture: `(cd fixtures/typecheck && npx --no-install tsc --noEmit -p tsconfig.json)` — passed.
- Pinned base checkout on Node 24: `npm ci`, `npm run typecheck`, `npm test` (**23/23**) and `npm run build` all passed. This was the baseline checkout, not the overlay installed into the application.
- Isolated Neon replay: 119 tables, 1,300 columns, 446 indexes, 1,799 constraints, 116 RLS policies, 460 public functions and 36 user triggers. Under `lexa_app`, tenant-A reads saw only tenant-A invitation/assignment fixtures; attempted tenant-B inserts were denied by RLS. Temporary fixtures were deleted.

Authenticated browser E2E, full dependency-complete Python tests against the overlay, full app Node 24 build/tests on the overlay, refresh-token/revocation flows, invitation expiry/replay concurrency, last-owner concurrency and effective branch-level endpoint authorization remain **unproven**. Branch assignments are persisted and exposed for administration/context, but branch-specific business endpoints are not yet all wired to enforce them; the package does not claim branch-level authorization acceptance.
