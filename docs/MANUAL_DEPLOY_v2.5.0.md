# LEXA v2.5.0 — Manual deployment

This package is the manual handoff because GitHub write access is currently unavailable to the connected integration.

## Canonical database

Use only:

- Neon project: `LEXA`
- project id: `wispy-mud-75323042`
- branch: `lexa-live`
- branch id: `br-soft-star-b1dj2m2w`
- database: `neondb`

Do not point LEXA at the legacy `production` branch.

## Render API

Service: `lexa-api`

Deploy from repository root with `apps/api` as the service root.

Set these non-secret environment values before the first production deploy:

```text
APP_ENV=production
DATABASE_APP_ROLE=lexa_app
LEXA_NEON_PROJECT_ID=wispy-mud-75323042
LEXA_NEON_BRANCH_ID=br-soft-star-b1dj2m2w
JWT_ISSUER=lexa
JWT_AUDIENCE=lexa-web
ACCESS_TOKEN_MINUTES=30
REFRESH_TOKEN_DAYS=30
```

Set these secret values from the existing LEXA/Render/Neon configuration:

```text
DATABASE_URL=<Neon pooled connection string>
DATABASE_URL_UNPOOLED=<Neon direct connection string>
REDIS_URL=<existing Render Redis/Key Value connection>
JWT_SECRET=<random secret of at least 32 characters>
CORS_ORIGINS=<exact Vercel production origin(s), comma-separated>
```

The application must use the pooled `DATABASE_URL` for normal API traffic. `DATABASE_URL_UNPOOLED` is reserved for migrations and direct backup operations.

Render health check should be `/health`.

Do not create a Render Postgres database. Neon PostgreSQL remains the only LEXA business system of record.

## Vercel web

Import the `MONALISA2003-CMD/LEXA-` repository manually.

Set the Vercel Root Directory to:

```text
apps/web
```

Use the Next.js framework defaults and the package's existing build scripts.

Set:

```text
NEXT_PUBLIC_API_URL=https://lexa-n10.onrender.com
LEXA_API_URL=https://lexa-n10.onrender.com
```

The browser talks to the Next.js same-origin proxy. Refresh credentials remain in an HttpOnly cookie; access tokens remain memory-only.

## Migration source of truth

The package includes migrations through `022_phase6a_brain_foundation` so a fresh environment can reproduce the current live schema family.

The 022 migration was reconstructed from the verified canonical Neon schema during the hardening review; it should be applied through the normal migration process, not pasted into an ad-hoc SQL console.

## Backup

The current Neon free plan does not allow an automatic snapshot schedule for `lexa-live`. Run:

```bash
export DATABASE_URL_UNPOOLED='...direct Neon URL...'
./scripts/backup-neon.sh
```

Store the resulting dump outside the application working tree after creation.

## Verification gate

Run from the repository root before deployment:

```bash
pytest -q
python -m compileall -q apps/api/app
tsc -p tsconfig.contract.json --noEmit
node --test apps/web/tests/visible-product-contract.test.mjs
```

Expected current result: all Python tests pass, backend compilation passes, frontend contract tests pass.

## Important source cleanup

The user-facing Business Engine route module has been removed. Its underlying transaction/workflow database schema remains because commerce, inventory and accounting depend on that authoritative transaction layer.

The old open-development browser session has also been removed. Production sign-in is through `/login` and `/register`.
