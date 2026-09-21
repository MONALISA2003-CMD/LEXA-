# LEXA Connectivity Diagnostic + Mobile Hotfix v1.6.2

## Apply
1. Replace `apps/api/app/health.py` with the included file.
2. Replace or merge the `.lexa-sidebar-mark` rule from `apps/web/app/globals.css`.
3. Commit to the LEXA repository `main`.
4. Redeploy Render `lexa-api` and Vercel.

## Phase 1 verification
Open `https://<render-host>/ready`. In development mode, a non-canonical database response now includes `expected` and `actual` database/Neon identity.
The canonical expected branch is `br-soft-star-b1dj2m2w`, database `neondb`, project `wispy-mud-75323042`.

## Security
The diagnostic is disabled in production and never returns credentials or a database connection string.
