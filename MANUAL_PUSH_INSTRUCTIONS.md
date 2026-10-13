# LEXA v2.8.0 — manual push

This archive contains the full root-level project tree, not a nested wrapper. Extract it into a **new temporary directory** first and compare with your current GitHub checkout before replacing files. Keep any local-only environment files out of Git.

## Validate

```bash
git diff --check
python -m compileall -q apps/api/app
python -m pip install -e 'apps/api[dev]'
pytest -q
node --test apps/web/tests/visible-product-contract.test.mjs
cd apps/web
npm install --include=dev --no-audit --no-fund
npm run typecheck
npm run build
```

The backend test suite and frontend contract test passed in the packaging environment. The full Next.js production build was not run during packaging, so let CI verify it before promoting to production.

## Push safely

Compare/extract the archive into your existing checkout, inspect `git status --short` and `git diff`, then commit and push. Do not overwrite `.env` files or commit credentials.

```bash
git add apps/api/app/db.py apps/api/app/auth.py apps/api/tests/test_phase1_hardening.py .github/workflows/lexa-ci.yml DEPLOYMENT_FIXES_2026-10-13.md MANUAL_PUSH_INSTRUCTIONS.md
git commit -m "fix: harden Neon pooled connections and release CI"
git push origin main
```

## After push

Confirm GitHub Actions passes, Vercel builds the new SHA, and Render deploys the same SHA. Then check `/health` and `/ready` on Render and test sign-in. If `/ready` remains 503, inspect its JSON diagnostic and Render logs; do not disable readiness checks to force a deploy.

This archive cannot include live secrets and does not claim that cloud deployment has already happened.
