# LEXA Stage 1 — Foundation Implementation Report

**Status: source candidate prepared and locally verified; live publication is blocked.**

Date: 22 October 2026

## Executive result

Stage 1 has been implemented in a canonical-root source candidate. The candidate includes the source/deployment path correction, a safe ZIP workflow replacement, login and registration RLS-context fixes, first-time business setup improvements, schema-aware readiness checks, and regression tests. It does **not** claim the production site or shared database has been fixed: the GitHub integration returned 403 when creating a branch, and the current schema migration set has not passed a full disposable PostgreSQL replay.

## Confirmed root causes

### 1. The updated frontend is stored under the wrong path

Vercel production deployment `dpl_6hLpYuEuSsEsV4NE5LmieVnnq5Du` was `READY` at commit `dd8fe8f60310831ef80809fe2e517ae80bafd0b2`. The live alias `lexa-green.vercel.app` still exposed the older blue/navy styles from the root `apps/web/app/globals.css`. The newer Emerald Fusion frontend was nested under `LEXA/apps/web`, while the Vercel project was serving the canonical root application.

### 2. The ZIP workflow caused the source duplication

`.github/workflows/lexa-zip-extract.yml` previously copied ZIP members exactly as written. When a source package contained `LEXA/apps/web/...` and `LEXA/apps/api/...`, extraction produced a duplicate tree instead of updating `apps/web` and `apps/api`.

### 3. The API deployment and application schema were out of sync

Render service `srv-dakm8k95efls73egg9a0` is configured with root directory `apps/api`, branch `main`, and its last observed live deployment used commit `99d76473549eb44c33dcff9670e6218cf42a9c60`, older than the latest Vercel deployment. Render logs recorded missing `public.supplier_bills` and a missing `suppliers.supplier_party_id` column. The active Neon application branch `lexa-live` (`br-soft-star-b1dj2m2w`) had ledger identities through 031 in the prior read-only check, while the current API expects migrations 033–040. Migration 032 is documented as QA-only and remains excluded.

### 4. Sign-in and setup failures need accurate context and guidance

The candidate already has the login and registration RLS context fix. Workspace setup now derives completion from saved records and checks six requirements instead of letting the owner reach a nominally complete dashboard without payment and money-tracking setup. The owner should see a guided setup path rather than an inaccurate permission message.

## Implemented in this candidate

- Canonical source paths stay at `apps/web`, `apps/api`, and `migrations`.
- `DELETE.txt` removes the obsolete duplicate `LEXA/` wrapper after canonical paths are overlaid.
- A corrected ZIP extractor recognizes a canonical-root bundle or one unique wrapper directory, normalizes the wrapper, blocks ambiguous archives, protects workflow files during extraction, and prevents a wrapper-only delete entry from collapsing to a repository-root deletion.
- The corrected extractor is included at `docs/stage1/lexa-zip-extract.yml` and mirrored at `.github/workflows/lexa-zip-extract.yml`. **Important:** the existing remote workflow deliberately protects `.github/workflows`, so a ZIP cannot update its own workflow. That file must be directly installed through a write-capable GitHub connection or the GitHub web UI.
- `/health` is the liveness route; `/ready` checks canonical database identity, required dependencies, required application tables, migration identities 033–040, and release-critical columns. Production responses use safe failure codes rather than exposing SQL details or credentials.
- `render.yaml` uses `/health` for the Render liveness check. This is a source setting; the current effective Render metadata must be checked after the source is published/synced.
- Login and registration set the pre-login RLS context before accessing protected records; authenticated user context is set before active-workspace resolution.
- Workspace setup is idempotent and fills missing first-run defaults without replacing existing records. It checks: Business details, Main branch, Stock room, Where stock is kept, Payment method, Money tracking.
- Stage 1 canonical layout contract tests were added.

## Verification completed

| Check | Result |
|---|---|
| Backend Python test suite | **247 passed**, one Starlette deprecation warning |
| Frontend contract suite | **51 passed** |
| Python compilation | Passed |
| Migration source disposition/hash manifest | Passed |
| Strict migration source reconciliation | Passed; semantic validation remains pending for six approved reconstructed-equivalent historical sources |
| Migration plan-only | Passed; 43 migration inputs/hashes enumerated, no database connection opened and no SQL executed |
| ZIP path normalization | Synthetic tests passed for both root-layout and `LEXA/`-wrapper ZIPs |
| Archive structure | Verified canonical `apps/web`, `apps/api`, `migrations/040...`, setup docs, workflow patch and wrapper deletion manifest; no nested `LEXA/apps/web/package.json`; no `.env` file included |
| TypeScript full typecheck | **Not passed**: environment is Node `v22.16.0`, but the app declares Node `24.x`; `@types/node`, `@types/react`, and `@types/react-dom` are missing |
| Full Next.js build | Not run to completion; the environment lacks the required local Next.js/dependency install and matching Node runtime |
| Clean PostgreSQL semantic migration replay | **Pending**; plan-only is not replay evidence |
| Authenticated browser/mobile journeys | Pending; live sign-in is currently a blocker |

## Database migration safety

No migration was applied to Neon. The candidate's `/ready` will signal that the application schema is incomplete while required release migrations are absent; this is intentionally more accurate than claiming the service is ready. Before updating a shared DB:

1. Install dependencies in a clean Node 24 and pinned Python environment.
2. Run the complete source/recovery checks.
3. Run the exact current migration bundle through the repository's disposable PostgreSQL CI replay with the explicit disposable-database guard.
4. Validate schema, functions, triggers, RLS policies, runtime-role privileges and required source identities.
5. Have the results reviewed, then prepare a separate forward-migration plan for `lexa-live`.
6. Do not include migration 032 unless a reviewed forward migration formally adopts its QA-only behavior.

## Publication blocker

Attempted to create the review branch `stage1/canonical-source-foundation-2026-10-22` from the current repository commit. GitHub responded:

`403 Resource not accessible by integration`

Therefore no branch, commit or pull request could be created through the connected integration. No Vercel deployment, Render deployment, remote environment change, production database mutation, account reset or secret change was performed.

## Deployment sequence once write access is restored

1. Directly install the workflow patch at `.github/workflows/lexa-zip-extract.yml` (the current workflow protects this path).
2. Upload/publish the canonical-root Stage 1 source package as a reviewable source change, not as nested `LEXA/` source.
3. Confirm Vercel's root is `apps/web`, Node is 24.x, and the production source commit includes the new root-level Emerald Fusion styles and app shell.
4. Confirm Render's root is `apps/api`, deploy commit aligns to the approved source, and its health check is `/health`; verify `/ready` accurately reports the actual database schema.
5. Complete the disposable replay and review before enabling the current API against any shared DB that lacks required tables/migrations.
6. Run sign-in, registration, session refresh, existing-workspace initialization, payment-method/account default seeding, owner branch access and guided setup against a safe test workspace.
7. Run Phase 8 journeys across sales, stock, recorded payment methods, customer balances, purchasing, supplier bills, expenses and finance reports. Phase 9 remains blocked until Phase 8 is accepted.

## Artifacts

- `LEXA_STAGE1_CANONICAL_SOURCE_CANDIDATE_2026-10-22.zip` — source candidate rooted at the correct repository paths.
- `LEXA_STAGE1_ZIP_EXTRACT_WORKFLOW_PATCH_2026-10-22.yml` — direct replacement workflow, because the current extractor cannot update its own protected workflow path from a ZIP.
- `LEXA_STAGE1_CANONICAL_SOURCE_CANDIDATE_2026-10-22.zip.sha256` — source archive checksum.
