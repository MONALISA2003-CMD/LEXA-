# LEXA v2.8.1 — frontend build repair / manual push

This archive contains the full root-level project tree, not a nested wrapper. Extract it into a **new temporary directory** first and compare with your current GitHub checkout before replacing files. Keep any local-only environment files out of Git.

## Validate

```bash
git diff --check
bash scripts/cleanup-obsolete-frontend-routes.sh
python -m compileall -q apps/api/app
python -m pip install -e 'apps/api[dev]'
pytest -q
node --test apps/web/tests/visible-product-contract.test.mjs
cd apps/web
npm install --include=dev --no-audit --no-fund
npm run typecheck
npm run build
```

The backend suite (96 tests), Python compilation, frontend visible/hardening contract, and TypeScript/TSX syntax gate passed after the frontend repair. The dependency-backed Next.js production build was not run because `npm install` timed out in this environment, so require CI/Vercel to confirm it before promoting to production.

## Required Vercel frontend setting

After pushing, open Vercel → Project Settings → Build and Deployment. Confirm **Root Directory** is `apps/web` and Framework Preset is **Next.js**. The failing file path `./app/invite/page.tsx` is relative to that frontend root; do not create a root-level `app/invite` or add a fake API export. Before pushing, run `bash scripts/cleanup-obsolete-frontend-routes.sh` from the repository root, inspect and commit its deletion of the obsolete frontend-only Business Engine/Kernel routes and generated `tsconfig.tsbuildinfo`, then set Build Command to `npm run build` or the auto-detected Next.js build. Until that cleanup lands, the current scoped cleanup command `rm -rf app/business-engine app/kernel && npm run build` may be kept temporarily.

The invitation page now explains that invitation acceptance is unavailable because this repository's FastAPI API does not define an invitation endpoint. Re-enable the form only after a real backend endpoint and its authorization/password semantics are implemented and tested. Ensure `NEXT_PUBLIC_API_URL` and `LEXA_API_URL` in Vercel/Render are set to the exact currently deployed Render API origin; examples in historical notes use inconsistent hostnames and must not be copied blindly.

## Push safely

Compare/extract the archive into your existing checkout, inspect `git status --short` and `git diff`, then commit and push. Do not overwrite `.env` files or commit credentials.

```bash
git add .gitignore apps/web/app/invite/page.tsx apps/web/tests/visible-product-contract.test.mjs apps/web/README.md apps/web/app/business-engine apps/web/app/kernel apps/web/tsconfig.tsbuildinfo scripts/cleanup-obsolete-frontend-routes.sh scripts/verify-phase3.sh docs/DEPLOYMENT_RENDER_VERCEL.md docs/MANUAL_DEPLOY_v2.5.0.md DEPLOYMENT_FIXES_2026-10-13.md MANUAL_PUSH_INSTRUCTIONS.md LEXA_PACKAGE_MANIFEST.json RELEASE_NOTES_2.8.1_FRONTEND_BUILD_REPAIR.md README.md RELEASE.txt
git commit -m "fix: repair invite route and document Vercel build settings"
git push origin main
```

## After push

Confirm GitHub Actions passes, Vercel builds the new SHA, and Render deploys the same SHA. Then check `/health` and `/ready` on Render and test sign-in. If `/ready` remains 503, inspect its JSON diagnostic and Render logs; do not disable readiness checks to force a deploy.

This archive cannot include live secrets and does not claim that cloud deployment has already happened.
