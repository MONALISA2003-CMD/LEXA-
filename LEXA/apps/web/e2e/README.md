# LEXA real-browser acceptance suite

These Playwright tests are a portable version of the Chromium checks run during the 2026-10-20 Phase 2 investigation. The recorded execution passed four tests in an isolated Vercel sandbox on Node 24.21.0. The checks cover static route responses, narrow/mobile/tablet/desktop overflow, labelled login controls and keyboard focus; they are **not authenticated E2E tests** and do not prove session rotation, logout revocation, API authorization or tenant isolation.

`@playwright/test` was installed only in the disposable validation sandbox. This delivery intentionally does not modify the checked-in package manifest/lockfile for that dependency because this local environment could not reach the npm registry (`EAI_AGAIN registry.npmjs.org`). Regenerate `apps/web/package-lock.json` using the authorized Node 24 build environment before adding `npm run test:e2e` to required CI:

```sh
cd apps/web
npm install --save-dev @playwright/test@1.64.1
npx playwright install --with-deps chromium
npm run test:e2e
```

To test a staging/preview host rather than the local production server:

```sh
LEXA_BROWSER_BASE_URL=https://<approved-LEXA-preview-host> npx playwright test
```

Use `LEXA_BROWSER_BASE_URL` (not `LEKA_BROWSER_BASE_URL`) when running; the latter spelling in the example above is intentionally corrected here for copy/paste safety.
