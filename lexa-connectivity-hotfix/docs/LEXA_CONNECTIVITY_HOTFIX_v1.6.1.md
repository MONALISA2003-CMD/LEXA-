# LEXA Connectivity + Mobile Hotfix v1.6.1

## What was verified

1. Vercel production deployment is on GitHub `main` commit `8a2471a57758f1f7927aa9b41bb178db4854ac1a` and is `READY`.
2. Neon project `LEXA` / branch `lexa-live` (`br-soft-star-b1dj2m2w`) is reachable and contains the required schema. The `lexa_app` role can see all nine readiness tables.
3. The current root API source contains `/api/v1/auth/dev-session` starting from commit `a9fbcf404f35e94fcc3ffb9a287af2cfed04c3cf`.
4. Commit `2191e5a23a81261c5a643622b40907d3f97fc418` does NOT contain `/api/v1/auth/dev-session` and its Render Blueprint still used `APP_ENV=production` without the open-development environment variables.
5. Therefore, if the live Render service is still on `2191e5...` or older, the current Vercel frontend cannot establish the development workspace session. This is the primary deployment-path failure to verify in Render.

## Hotfix changes

### Mobile sidebar
The LEXA sidebar mark had no size constraint. The source image is much larger than the mobile drawer, so the image was rendered at its intrinsic dimensions and covered the screen. The hotfix explicitly constrains `.lexa-sidebar-mark` and clips horizontal overflow in the drawer.

### Workspace bootstrap
The browser previously waited for `/health` + `/ready` to finish before requesting `/auth/dev-session`. A sleeping Render instance could therefore block workspace bootstrap behind readiness. The hotfix starts the system probes and dev-session bootstrap in parallel.

### Dev-session resilience
The hotfix retries the development session after short delays (`0`, `0.9`, `2.2`, `5` seconds) to tolerate a cold API instance without fabricating or bypassing authentication.

### Network timeout
API fetches now have a bounded 12 second timeout so a sleeping/unreachable upstream does not leave the workspace in an apparently permanent loading state.

## Render verification required

In the Render service that serves `lexa-api`:

- deploy a commit at or after `a9fbcf404f35e94fcc3ffb9a287af2cfed04c3cf`;
- ensure the Blueprint/environment contains:
  - `APP_ENV=development`
  - `LEXA_OPEN_DEV_MODE=true`
  - `LEXA_OPEN_DEV_EMAIL=preview@lexa.local`
  - `LEXA_OPEN_DEV_WORKSPACE_NAME=LEXA Workspace`
  - `LEXA_NEON_BRANCH_ID=br-soft-star-b1dj2m2w`
  - `DATABASE_APP_ROLE=lexa_app`
  - `DATABASE_URL` for the `LEXA` project's `lexa-live` branch
  - `CORS_ORIGINS` containing `https://lexa-green.vercel.app`
- after deployment, verify:
  - `GET /health` -> HTTP 200
  - `GET /ready` -> HTTP 200 with `status: ready`
  - `POST /api/v1/auth/dev-session` -> HTTP 200 and a JSON access token

Do not point Render at the empty Neon `production` branch.

## Vercel verification required

The production Vercel project must have `NEXT_PUBLIC_API_URL` set to the exact HTTPS URL of the current Render API service. The repository `.env.example` contains a stale example value and is not authoritative for the live Vercel environment.

After changing the Render API URL or deployment, redeploy Vercel so the browser bundle/proxy uses the intended environment.
