# LEXA Phase 5 — Auth runtime repair handoff

This overlay repairs the import failure that prevented the latest GitHub `main` revision (`d228e6467894857aeeb632a189d10680179404db`) from starting on Render.

## Apply

Apply the overlay to the reviewed full-source candidate that matches the Phase 5 Increment 02 ZIP. It contains repository-relative paths, not a replacement repository. The patch files are:

- `apps/api/app/auth.py` — shared refresh-cookie helper.
- `apps/api/app/routes/auth.py` — imports/uses the shared helper instead of a duplicated local implementation.
- `apps/api/tests/test_phase1_hardening.py` — expects cookie hardening in the shared auth module.
- `apps/api/tests/test_shared_refresh_cookie.py` — regression coverage for helper definition, cookie attributes, and shared imports.

## Verification run here

```sh
export PYTHONPATH="$PWD/apps/api"
export DATABASE_URL='postgresql://test:test@localhost/test'
export REDIS_URL='redis://localhost:6379/0'
export JWT_SECRET='test-secret-at-least-32-characters-long'
export APP_ENV='test'
export DATABASE_APP_ROLE='lexa_app'
export DATABASE_LOGIN_ROLE='lexa_runtime_login_p3'
python3 -m compileall -q apps/api/app apps/api/tests
python3 -m pytest -q apps/api/tests
node --test apps/web/tests/*.test.mjs
```

Recorded result: **43 backend tests passed, 1 skipped** because `redis` is not installed in this offline runner; **25 frontend contract tests passed** under Node 22.16.0. The deployed Vercel project is configured for Node 24.x and its production build/typecheck passed, but this runner could not run a clean local Node 24 `npm ci`.

## Release constraints

The GitHub app connection returned HTTP 403 for branch creation and direct file update, so these files have not been committed. Render must not be considered fixed until a new reviewed commit deploys and is live. Do not run the authored Phase 5 Playwright checkout/refund tests against the production API. Use a separate staging API, sanitized non-production DB, dedicated QA users and an explicit staging host allow-list.
