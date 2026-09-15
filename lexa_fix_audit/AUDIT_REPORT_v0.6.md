# LEXA Deployment Integration v0.6 — Audit Report

## Scope

This package hardens the Vercel ↔ Render runtime boundary without embedding production secrets.

## Changes

- Added `/` API identity endpoint.
- Kept `/health` as a dependency-independent liveness probe.
- Added `/api/health` compatibility alias.
- Added `/ready` and `/api/ready` readiness probes that verify PostgreSQL without exposing connection details.
- Standardized frontend API access through `apps/web/lib/api.ts`.
- Frontend health check uses the public `NEXT_PUBLIC_API_URL` only.
- Kept PostgreSQL connectivity on psycopg 3.
- Added test bootstrap so repository-root pytest works consistently.
- Added runtime endpoint tests.

## Verification

- Python compilation: PASS
- Python tests: PASS (21 tests)
- Reserved SQLAlchemy metadata audit: PASS
- psycopg2 reference audit: PASS
- Production secret scan: PASS
- Render configuration audit: PASS
- ZIP structure/integrity audit: PASS

The local environment in this execution session did not have the Next.js CLI installed, so a local Next.js build could not be repeated here. The previously supplied Vercel build log showed the production Next.js build completing successfully.

## Required deployment variables

### Render API

- `DATABASE_URL` — real Neon connection string
- `REDIS_URL` — Render Key Value/Valkey connection URL
- `JWT_SECRET` — production secret stored only in Render
- `CORS_ORIGINS` — Vercel production origin
- fixed non-secret runtime variables remain defined in `render.yaml`

### Vercel

- `NEXT_PUBLIC_API_URL` — public Render API URL

## Safety

No production Neon database mutation, reset, destructive migration, or credential insertion is performed by this package.
