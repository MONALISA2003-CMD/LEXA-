# Stage 1 implementation notes

## Implemented in this candidate

1. **Canonical source/deployment path:** the delivery archive is prepared from repository root, so it overlays `apps/web`, `apps/api` and `migrations`, not a second `LEXA/` directory. The root delete manifest removes the obsolete duplicate wrapper after the canonical source is extracted.
2. **ZIP workflow normalization:** a replacement workflow is included at `docs/stage1/lexa-zip-extract.yml` and mirrored at `.github/workflows/lexa-zip-extract.yml`. It recognizes either root layout or one unambiguous wrapper directory, skips protected workflows during extraction and refuses ambiguous source roots. The existing live workflow protects `.github/workflows`, so this patch needs a direct manual update of the workflow path; ZIP extraction alone cannot install it.
3. **Sign-in and registration:** the current API candidate sets the required email-scoped RLS context before user lookup and the registration key/context before registration-request writes. User context is established before reading active workspaces.
4. **Honest readiness:** `/health` is liveness; `/ready` checks canonical DB identity, dependencies, required application tables, full migration identities and schema columns needed by this release. Public production responses use safe failure codes, never raw SQL, credentials or connection strings.
5. **Workspace setup:** the existing idempotent setup initializer fills missing locations, payment-method defaults and accounting setup without replacing existing configuration. Setup progress now checks six items: business details, main branch, stock room, stock location, payment method and money tracking.
6. **Render health-check source:** `render.yaml` uses `/health` for liveness so schema mismatch does not make Render continually restart a process. `/ready` remains a separate dependency/schema signal. Effective Render settings need verification after the blueprint/source is updated.
7. **Regression coverage:** added Stage 1 canonical-layout tests and readiness contract checks.

## Verification

- Frontend contracts: `node --test apps/web/tests/*.test.mjs` — 51 passed.
- Backend/unit suite: `pytest -q` — 247 passed after adding the four Stage 1 canonical-source tests.
- Python compile: `python -m compileall -q apps/api/app apps/api/tests scripts` — passed.
- `python scripts/check_migration_recovery_manifest.py` — passed.
- `python scripts/check_migration_sources.py --strict` — source reconciliation passed; semantic validation remains pending for six approved reconstructed-equivalent historical migrations.
- `python scripts/run_clean_migration_replay.py --plan-only` — 43 input identities/hashes passed; no DB connection opened and no SQL executed.
- Full TypeScript typecheck: not passed because this environment lacks `@types/node`, `@types/react` and `@types/react-dom`. The app specifies Node 24.x; the available local Node is 22.16.0. Run install/typecheck/build in a clean Node 24 environment before deploy.

## Not performed

- No GitHub commit or branch was created. The connected GitHub integration returned `403 Resource not accessible by integration`.
- No Vercel or Render deployment was triggered.
- No Neon migrations or production data changes were executed.
- No live account or password was changed.

## Next safe actions

1. Restore write-capable GitHub access and directly replace `.github/workflows/lexa-zip-extract.yml` with this package's documented patch.
2. Run pinned Node 24 install/typecheck/build and full disposable PostgreSQL replay + schema/RLS tests in CI.
3. Inspect and approve the migration replay evidence. Only after that should a separately reviewed migration plan be prepared for `lexa-live`.
4. Publish the root-normalized canonical source and confirm Vercel and Render are building the intended commit from `apps/web` and `apps/api`.
5. Verify `/health` (liveness) and `/ready` (full schema readiness) plus sign-in, signup, workspace initialization and authenticated Stage 1 journeys.
