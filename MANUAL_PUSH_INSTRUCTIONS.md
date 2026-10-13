# LEXA v2.8.2 — Phase 0 reliability repair / manual push

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

The new backend test verifies that an HttpOnly-cookie refresh request without a JSON body succeeds (it is skipped in this local sandbox because the API dependency stack is not installed). Frontend contract tests verify preflight session restoration, single-flight refresh, auth-gated UI, no fabricated zero values on request failure, and the standard Vercel build command. Python suite: 96 passed / 1 skipped. Node contract tests: 2 passed. TypeScript syntax parsing: 26 files, zero syntax errors. The full Next.js production build must be confirmed by Vercel after you push; no production deployment is claimed here.

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

Render is configured to auto-deploy from `main`. Its service uses `apps/api`; the only API change in this increment makes cookie-based refresh accept an optional body. No database schema or data changes are included.
