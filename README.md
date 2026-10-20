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
- Adds a guarded, additive candidate migration for invitation and membership-branch tables, tenant-composite foreign keys, RLS policies, active-workspace and token lookup functions, and owner-only member-management permissions.

## Apply locally

This is a **combined** overlay, not a standalone patch to stack on top of Increment 01. It installs Increment 01’s prerequisites plus Increments 02 and 03 in one guarded operation. From a clean repository root at the exact pinned commit:

```bash
python /path/to/LEXA_Phase3_Increments_02_03/scripts/apply_phase3_increments_02_03.py
```

The script verifies the pinned commit, a clean worktree, exact original source blobs, duplicate anchors and all new-target collisions before staging any files. It then copies the reviewed candidate overrides and applies exact-anchor edits to auth routing, navigation and API helpers. It **refuses** if Increment 01 or 02/03 changes are already present; do not apply it atop another Phase 3 overlay. Review the resulting `git diff` before any tests or SQL.

**Do not run migration 027 yet.** The Phase 0–2 hard blockers remain: original SQL sources 010, 011 and 023–026 are missing, migration 021 needs a provenance-preserving repair, and no fresh full migration replay/parity result exists. This migration is a candidate file only and is intentionally not executed by the apply script.

## Validation currently performed

- Python pure-domain and source-contract suite: run from this package with `python -m pytest -q tests`.
- Python syntax compilation: `python -m compileall -q overrides/apps/api/app`.
- Node source-contract suite: `node --test tests/phase3-increments-02-03.test.mjs`.
- TypeScript UI + appended API-helper contract fixtures (when `tsc` is available): `cd fixtures/typecheck && tsc --noEmit -p tsconfig.json`.

These are package-local checks, not full LEXA dependency-complete tests. Full Node 24 clean install/build, Python suite against the actual repository runtime, Postgres migration/replay, RLS and transaction integration, authenticated browser E2E, token rotation/revocation tests and cross-tenant/cross-branch acceptance have **not** been run for this overlay. Branch assignments are persisted and exposed for administration/context, but branch-specific business endpoints are not yet all wired to enforce them; the package does not claim branch-level authorization acceptance.
