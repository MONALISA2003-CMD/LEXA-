# LEXA Whole-Product Brand System — Upload Guide

## What this package does

This ZIP is an overlay for the canonical `apps/web` frontend. It establishes the supplied master LEXA identity through the shared shell, global design tokens, dashboard cards, line and comparison charts, table/form states, CSS-module screens and mobile layouts. It also fixes the stale brand assertion that made the latest `LEXA Main Build CI` fail at `tests/phase8-foundation-polish.test.mjs`.

The package is deliberately frontend-only. It does not alter database records, migrations, authentication logic or the business API.

## Upload steps

1. Download this ZIP and upload the ZIP file itself to the repository root of `MONALISA2003-CMD/LEXA-` on branch `main` (do not extract it locally first).
2. Open **Actions → LEXA ZIP Extractor** and inspect its log. The extractor should recognise the canonical `apps/web/package.json`, `apps/api/app/main.py` and `migrations/` markers, extract the overlay, and commit the updated files.
3. Inspect the automatically dispatched **LEXA Main Build CI** run. It must pass API contracts, web `npm test`, TypeScript, production build, and compose config.
4. In Vercel, wait for the deployment whose commit SHA matches the extractor's new source commit. The upload-only commit may deploy unchanged source; it is not the final deployment.
5. Verify `https://lexa-green.vercel.app/` and `/login`. Check the sidebar/header mark, KPI cards, the sales/collections chart, report bars, table scroll behaviour and bottom navigation at desktop and phone widths.

## Important

A Vercel deployment showing `READY` is not enough by itself. The frontend CI must be green and the live page must show the master logo and updated interface. Do not change production database or backend settings for this frontend update.
