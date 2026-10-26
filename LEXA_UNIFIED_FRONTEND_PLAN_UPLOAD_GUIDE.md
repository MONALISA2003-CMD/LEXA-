# LEXA Unified Frontend Plan — Upload & Verification Guide

## Package

Upload **`LEXA_UNIFIED_FRONTEND_PLAN_IMPLEMENTATION_2026-10-26.zip` itself** to the **root** of `MONALISA2003-CMD/LEXA-` on `main`. Do not extract it, rename its contents or nest it in a folder. The existing `.github/workflows/lexa-zip-extract.yml` requires a recognisable source tree containing `apps/web/package.json`, `apps/api/app/main.py` and `migrations/`; the package includes unchanged current copies of those marker files solely for that detector.

## Expected safe path

1. Upload the ZIP to the repository root.
2. Open GitHub Actions and follow **LEXA ZIP Extractor**.
3. Confirm its log lists `apps/web/app/lexa-brand-authority.css`, the updated frontend tests and `docs/LEXA_UNIFIED_FRONTEND_BRAND_AND_WORKFLOW_SYSTEM.md` as extracted canonical paths, followed by a new `[lexa-extractor]` source commit.
4. Confirm **LEXA Main Build CI** passes on the extractor commit SHA. Do not rely on the ZIP upload commit's green check alone.
5. In Vercel, confirm the production deployment SHA equals that extractor source commit. Open `https://lexa-green.vercel.app/` and verify the master artwork in desktop navigation/authentication, the master wordmark in the mobile header, blue primary actions, dashboard KPI/chart treatments and several operational modules at mobile and desktop widths.
6. If the visuals still appear unchanged after a matching READY deployment, hard-refresh the browser and check that the HTML references the current CSS chunk; do not declare success until visible assets and styles match the deployed commit.

## Scope/safety

This is a frontend-only CSS/contract-test/documentation overlay. `apps/api/app/main.py`, `apps/web/package.json` and `migrations/001_phase1_foundation.sql` are unchanged current markers for ZIP recognition. No database migration, production data write, provider integration, payment processing, EFRIS call or backend logic change is intended.

The package intentionally does not pretend unsupported serial/batch tracking is active. The current web API exposes no serial/batch records or operations, so those workflows require a backend contract first. Likewise, this package styles the report period controls that exist today; it does not implement all requested date presets or financial-year semantics.

## Local verification commands (CI runs them in the repository)

From `apps/web` in a Node 24 environment:

```bash
npm ci --no-audit --no-fund
npm test
npm run typecheck
npm run build
```

These commands and manual visual checks are still required after extraction. Static stylesheet checks and ZIP integrity do not replace full CI or browser verification.
