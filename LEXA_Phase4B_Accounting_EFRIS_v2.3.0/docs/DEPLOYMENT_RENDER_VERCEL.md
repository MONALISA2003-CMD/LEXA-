# LEXA Render + Vercel deployment

## Architecture

- Vercel: `apps/web` Next.js frontend
- Render Web Service: `apps/api` FastAPI API
- Neon: PostgreSQL source of truth
- Render Key Value/Valkey: Redis-compatible cache/queue

Do not create a second business database on Render when Neon is the selected PostgreSQL service.

## Render API service

Use the repository root as the Render Blueprint location. `render.yaml` sets:

- Runtime: Python
- Root Directory: `apps/api`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health Check: `/health`

Set the secret values listed in the deployment runbook. `sync: false` variables must be entered in Render and are not stored in Git. For the hardened development deployment, set `DATABASE_APP_ROLE=lexa_app` only after the target LEXA Neon branch has the `lexa_app` role and grants.

## Vercel

Create a Next.js project from the same repository:

- Root Directory: `apps/web`
- Framework Preset: Next.js
- Build Command: auto-detected (`next build`)
- Install Command: auto-detected
- Output Directory: auto-detected

Set `NEXT_PUBLIC_API_URL` to the exact HTTPS URL of the Render API, for example:

`https://lexa-api.onrender.com`

After the Vercel URL is known, put that URL in the Render API's `CORS_ORIGINS`. If more than one browser origin is required, separate them with commas.

## Deployment order

1. Create/connect the Render API service.
2. Add the Render environment variables.
3. Create Render Key Value and set `REDIS_URL` to its connection URL.
4. Set `DATABASE_URL` to the production Neon connection string using the `postgresql+psycopg://` scheme.
5. Deploy and confirm `/health` returns HTTP 200. Then confirm `/ready` reports both database connectivity and the LEXA schema as ready. A reachable but schema-empty Neon branch is intentionally reported as not ready.
6. Create the Vercel project with Root Directory `apps/web`.
7. Set `NEXT_PUBLIC_API_URL` to the Render API URL and deploy.
8. Add the Vercel production URL to Render `CORS_ORIGINS` and redeploy the API.
9. Confirm the Vercel home page reports the API as online.

## Important security rule

Never commit production `DATABASE_URL`, `REDIS_URL`, or `JWT_SECRET`. The source specification requires production secrets to stay out of source control and ordinary developer environment files.

## Runtime probes

- Liveness: `GET /health`
- Compatibility alias: `GET /api/health`
- Readiness: `GET /ready`
- Compatibility readiness alias: `GET /api/ready`

`/health` is intentionally dependency-independent so Render can determine whether the process is alive. `/ready` verifies PostgreSQL and Redis/Valkey without exposing connection details.


## Canonical LEXA Neon branch

The permanent populated branch for LEXA is `lexa-live` (`br-soft-star-b1dj2m2w`) in Neon project `LEXA` (`wispy-mud-75323042`). It is non-expiring and is the project default branch. The API readiness check verifies `current_setting('neon.branch_id', true)` against this canonical branch id before reporting the database ready.

The Render service must use a Neon connection string for this branch. A connection string for the empty legacy `production` branch will intentionally remain unready.
