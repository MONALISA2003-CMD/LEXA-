# LEXA Open Development Mode — Retired

LEXA no longer ships an open-development workspace session. The former `/api/v1/auth/dev-session` route, browser development bootstrap, and persisted bearer-token flow were removed from the production package.

## Current authentication model

Users enter through `/login` or `/register`. Access tokens remain in browser memory only. Refresh credentials are stored in an HttpOnly, Secure production cookie and rotated by the API.

## Production requirement

Render must run with:

- `APP_ENV=production`
- `LEXA_OPEN_DEV_MODE=false` (kept only as an explicit deployment guard)
- `DATABASE_APP_ROLE=lexa_app`
- `DATABASE_URL` using the Neon pooled endpoint
- explicit production `CORS_ORIGINS`
- `REDIS_URL` configured for rate limiting

The open-development route is intentionally absent from the FastAPI router.
