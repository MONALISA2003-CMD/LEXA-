# LEXA v2.8.5 — End-to-end auth readiness / manual push

This archive is a complete root-level project tree. The repository has a ZIP-extractor workflow: pushing this ZIP to the repository root lets the workflow extract the files and consume the root `DELETE.txt` manifest to remove the obsolete frontend-only routes. If you extract locally instead, run `bash scripts/cleanup-obsolete-frontend-routes.sh` and remove `DELETE.txt` before staging; do not commit the deletion manifest itself. Review all changes before pushing. Keep local `.env` files out of Git.

## Validate locally

```bash
git diff --check
python -m pip install -e 'apps/api[dev]'
python -m pytest -q
node --test apps/web/tests/*.test.mjs
cd apps/web
npm install --include=dev --no-audit --no-fund
npm run typecheck
npm run build
```

The backend refresh test verifies cookie-only refresh through the security-definer session lookup. Migration 028 has already been applied and verified on canonical Neon `lexa-live` for this package; do not re-run it unless you first check the live ledger. Do not replay older migrations or reset the database. Frontend contract tests verify preflight session restoration, single-flight refresh, auth-gated UI, no fabricated zero values on request failure, and the standard Vercel build command. Python suite: 97 passed / 1 skipped. Node contract tests: 2 passed. TypeScript syntax parsing: 26 non-declaration TS/TSX files, zero syntax errors. Migration 028 was promoted to the canonical branch after approval and its function/privileges/RLS changes were verified live. The full Next.js production build and authenticated live smoke test must still be confirmed after source rollout; no application deployment is claimed here. See `LEXA_E2E_FORENSIC_AUDIT_2026-10-13.md`.

## Vercel configuration

The intended Vercel Root Directory is `apps/web`; Framework Preset is Next.js. `apps/web/vercel.json` explicitly selects `npm run build`, and the obsolete Business Engine/Kernel frontend route modules have been removed from this package. This means the old command `rm -rf app/business-engine app/kernel && npm run build` is no longer needed.

## Push safely

For a ZIP workflow push, place the ZIP in the repository root and let the existing ZIP-extractor workflow process it. For a local source update, extract to a temporary folder, copy reviewed changes into your checkout, run `bash scripts/cleanup-obsolete-frontend-routes.sh`, remove `DELETE.txt`, inspect `git status --short` and `git diff`, then commit and push. Do not commit credentials or the temporary `DELETE.txt` manifest.

```bash
git add -A
git diff --cached --check
git commit -m "fix: stabilize Phase 0 auth refresh and Vercel build"
git push origin main
```

Render is configured to auto-deploy from `main`. Its service uses `apps/api`; the API changes include tenant-safe refresh lookup, identity verification, RLS context and correlated error logging. Migration 028 is an additive schema/security change and a conservative read-only role backfill; it was already applied to canonical `lexa-live` in this remediation. Check the ledger before any application elsewhere; it does not alter existing Owner/Admin roles or attach accounts to unrelated tenants.


## Phase 0.4 — required deploy order

1. Do not re-run migration 028 blindly: it is already applied to `lexa-live`; query the live ledger first if reconciling another database.
2. Push/extract this reviewed ZIP into the LEXA repository and inspect the diff before accepting it. Render auto-deploys from `main`; Vercel production commit/status must be verified separately.
3. In the actual LEXA Render service settings, set Health Check Path to `/ready` (the service currently reports this setting as blank while `render.yaml` declares `/ready`).
4. Verify `/ready`, login, cookie-backed refresh, `/api/v1/auth/me`, hard reload, protected inventory and dashboard requests, and logout. Check logs by `X-Request-ID` if any request remains 5xx.
5. Never grant Owner to every account. Accounts with no active tenant membership must be invited/attached by a tenant administrator; Phase 0 cannot safely infer their workspace.
