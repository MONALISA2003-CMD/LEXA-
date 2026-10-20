# LEXA Phase 3 Closure — Execution Status (20 October 2026)

## Delivered in this candidate bundle

- The Phase 3 Increment 01–06 source overrides remain available for review and guarded application: workspace setup, workspace switching/resumable onboarding, invitations and membership lifecycle, role assignment, branch enforcement, and owner-managed role/permission administration.
- The API finance override avoids PostgreSQL's ambiguous nullable `$2` parameter by adding the optional journal-entry and fiscal-document status predicate only when a status is supplied. A source-contract regression covers both endpoints. This correction is **not deployed**.
- The isolated Neon workspace-options SQL regression was re-run on `br-purple-art-b1horduo` / `lexa_phase0_3_cleanbridge`. It completed without an exception and guards against user B listing user A's workspace by passing A's UUID, and against a missing transaction-local `app.user_id`. Test fixtures were cleaned by the same SQL block.
- Added a fail-closed historical-source fallback installer. It verifies the six available equivalent files against pinned Git blob SHA-1s, creates clearly labelled replacement files only when canonical paths are absent, preserves an unknown existing file, writes SHA-256 provenance, moves entries from “missing path” to “replacement present / historic bytes still unrecovered” in `source_gaps.json`, and switches the path checker to a replacement-aware implementation while preserving the old checker bytes under `.migration-source-audit/`.
- The replacement-aware checker fails its strict historical-source gate by default while any replacement remains. `--strict --allow-replacements` is a deliberate, explicit path-coverage exception for a **disposable clean replay only**; its output continues to state that the historic bytes have not been recovered.

## Validation rerun

| Check | Result | Boundary |
|---|---:|---|
| Candidate Python tests | **46 passed** | Bundle/unit/contract tests, including six tests for the new replacement installer/checker flow |
| Node source-contract tests | **8 passed** | Node v22.16.0; no real browser started |
| Candidate API/script compile | **Passed** | `python -m compileall -q overrides/apps/api/app scripts` |
| TypeScript fixture typecheck | **Passed** | Isolated declaration-stub fixture only, not the complete Next.js dependency graph |
| Neon workspace identity SQL regression | **Passed** | Isolated replay branch only; no production SQL write |
| Node 24 clean install + full app build | **Not run** | This runner has Node v22.16.0, not Node 24, and outbound DNS resolution failed for GitHub/npm |
| Redis-backed auth refresh integration | **Not run** | Redis is unavailable in this runner; the previously recorded full source-checkout run had 116 passed and 1 skipped |
| Fresh empty-database replay + canonical schema parity | **Not signed off** | Existing branch had already been replayed; a fresh exact final candidate replay is still needed |
| Authenticated hosted E2E / real-browser responsive acceptance | **Not run** | No confirmed dedicated test-account credentials/session were available in this execution |

## Connected infrastructure observations

### GitHub

- Repository: `MONALISA2003-CMD/LEXA-`; default branch `main` at inspected commit `ee729a193ff3cc8ce7f0d414a2798cd62bb73129`.
- The root active workflow directory still exposes only `lexa-zip-extract.yml`; the combined status for the inspected current commit had a passing Vercel context but no backend/frontend GitHub Actions checks.
- Feature-branch creation returned HTTP 403 (`Resource not accessible by integration`). No source branch, PR, CI dispatch, or remote commit was created. Therefore the candidate remains local/downloadable rather than merged source.

### Render

- Service `LEXA` (`srv-dakm8k95efls73egg9a0`) on `https://lexa-n10e.onrender.com`, repository `MONALISA2003-CMD/LEXA-`, branch `main`, root `apps/api`.
- Latest observed live deploy: `dep-dbbgra1srm7s7386q0l0`, source SHA `a1ed64eec79daf3d74456c7b8b854d84f634d6fd`; build and deploy events succeeded.
- The current Render service metadata still has an empty `healthCheckPath` although log evidence showed `/ready` and `/health` returning HTTP 200.
- A real log record at `2026-10-20T07:01:40Z` shows `GET /api/v1/accounting/journal-entries` returned HTTP 500 when the optional `status` query value was absent. The candidate correction is staged only in the overlay. `/api/v1/compliance/fiscal-documents` has the same risky predicate shape and received a preventive source correction, but no correlated 500 was found for that route.
- A separate 5xx status-code query returned no rows; this does **not** override the specific journal-entry error record found by endpoint/text query.

### Vercel

- Project `lexa` (`prj_QicfCnse8LU6hnq4ik9liHc289VW`), Node version configured as `24.x`.
- Latest observed production deployment was `READY` for commit `ee729a193ff3cc8ce7f0d414a2798cd62bb73129`; no runtime error clusters were reported in the last 24 hours.
- Vercel is not on the local candidate overlay as a separately built/tested release candidate. The latest READY state is not proof of Phase 3 acceptance.

### Neon

- Project `LEXA` (`wispy-mud-75323042`), live/default branch `lexa-live` (`br-soft-star-b1dj2m2w`) is `ready`.
- Read-only catalog inspection: 119 public base tables, 114 with both RLS enabled and forced, and 5 with RLS disabled: `permissions`, `registration_requests`, `schema_migrations`, `tenants`, `users`.
- `lexa_runtime` on `lexa-live` still has `CREATEDB`, `CREATEROLE`, `REPLICATION`, `BYPASSRLS`, membership in `neon_superuser`, and membership in `lexa_app`. `lexa_runtime_safe` does not exist on this branch.
- This package does not change production roles, credentials, RLS, grants, or live schema. A safe-role cutover needs a tested login secret and a matching Render pooled `DATABASE_URL`/login-role configuration; those cannot be safely swapped by this local package or the currently available Render tools.

## Historical source replacement disposition

The six exact historical files were not recovered from inspectable Git path history or the scanned archives. The repository does contain separately labelled equivalents at these locations:

- `migrations/reconstructed/010_phase2_catalog_intelligence.equivalent.sql`
- `migrations/reconstructed/011_phase2_catalog_runtime_constraints.equivalent.sql`
- `migrations/reconstructed/023_phase4_purchasing_core.equivalent.sql`
- `migrations/reconstructed/024_phase4_purchasing_security.equivalent.sql`
- `migrations/reconstructed/025_phase4_purchasing_permissions.equivalent.sql`
- `migrations/reconstructed/026_phase4_membership_branch_integrity.equivalent.sql`

Run the replacement installer from a full LEXA checkout, not from this overlay-only directory:

```bash
python /path/to/LEXA_Phase3_Increments_01_06/scripts/replace_missing_migrations.py --source-root /path/to/LEXA-checkout
python /path/to/LEXA_Phase3_Increments_01_06/scripts/replace_missing_migrations.py --source-root /path/to/LEXA-checkout --apply
python scripts/check_migration_sources.py --strict
```

The normal strict command is expected to **fail** while labelled replacements are present. Only after review, on a disposable clean database, use `python scripts/check_migration_sources.py --strict --allow-replacements` alongside the replacement manifest, replay results, and schema/grants/RLS parity evidence. This command does not certify replacement SQL as the historically applied bytes. The script is included and unit-tested in this package; it has **not** been applied to the live repository because GitHub branch creation is forbidden by the active integration.

## Release disposition

**NO-GO for Phase 4 / production green certification.** Remaining blockers: remote write permission to install a reviewed branch/PR and CI; deployment of the Render source fix plus `/ready` health-check configuration; reviewed staging-to-production least-privilege database-role cutover and table-by-table RLS/grants work; accepted replacement-vs-historical migration decision plus a fresh empty replay and canonical schema parity; Node 24 dependency-complete build; Redis auth-refresh integration; and authenticated two-tenant/two-branch E2E plus browser acceptance. No production migration, role change, environment edit, or deployment was performed in this pass.
