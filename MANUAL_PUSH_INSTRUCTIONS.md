# LEXA v2.8.4 — Phase 0 final authentication/RLS hardening / manual push

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

The backend refresh test verifies cookie-only refresh through the security-definer session lookup. The additive migration 028 must be reviewed and applied to the canonical Neon branch before the backend is deployed; do not replay older migrations or reset the database. Frontend contract tests verify preflight session restoration, single-flight refresh, auth-gated UI, no fabricated zero values on request failure, and the standard Vercel build command. Python suite: 10 passed / 1 skipped. Node contract tests: 2 passed. TypeScript syntax parsing: 27 files, zero syntax errors. The full Next.js production build must be confirmed by Vercel after you push; no production deployment is claimed here.

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

Render is configured to auto-deploy from `main`. Its service uses `apps/api`; the API changes include tenant-safe refresh lookup, identity verification, RLS context and correlated error logging. Migration 028 is an additive schema/security change and a conservative read-only role backfill. Apply only migration 028 after verifying the live ledger; it does not alter existing Owner/Admin roles or attach accounts to unrelated tenants.


## Phase 0.4 — required deploy order

1. Inspect the live Neon `schema_migrations` ledger and confirm migration 028 has not already been applied.
2. Apply only `migrations/028_phase0_auth_rls_runtime_hardening.sql` to the canonical `lexa-live` branch. It creates the refresh lookup function, hardens empty RLS context handling, and adds a least-privilege Member role only for active memberships with no role.
3. Deploy the API code to Render, then deploy the web app to Vercel.
4. Verify `/ready`, login, cookie-backed refresh, `/api/v1/auth/me`, hard reload, protected inventory and dashboard requests, and logout. Check logs by `X-Request-ID` if any request remains 5xx.
5. Never grant Owner to every account. Accounts with no active tenant membership must be invited/attached by a tenant administrator; Phase 0 cannot safely infer their workspace.
