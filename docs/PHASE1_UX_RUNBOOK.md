# Phase 1 UX foundation runbook

## 1. Review the handoff

Use the repository root in this ZIP as the source root. The frontend is `apps/web`; the API is `apps/api`. The current branch is not known to be updated, because GitHub repository writes were denied by the connected integration. Do not assume the production deployment contains these files.

## 2. Local / CI verification

Run from the repository root:

```bash
bash scripts/verify-phase0.sh
```

Then run the full frontend toolchain from `apps/web` in a dependency-equipped Node 24 environment:

```bash
npm ci
npm run typecheck
npm test
npm run build
```

The current container could not retrieve uncached npm dependencies, so the full typecheck/build result must come from CI or another connected Node 24 environment.

## 3. Visual acceptance checklist

Review both `/login` and `/register`, the application navigation, `/products`, and `/inventory` at viewport widths of 360, 390, 430, 768, and 1280 CSS pixels.

- Check that no horizontal page overflow or clipped primary action appears.
- Confirm the bottom navigation respects safe-area insets and that More opens/closes the workspace sidebar.
- Confirm keyboard focus is visible, the password reveal control is announced clearly, and the workspace selector appears when multiple memberships are returned.
- Confirm registration can resume from the stored non-secret draft and the password is absent from session storage.
- Force the catalogue/stock API request to fail and confirm that list/KPI areas show an error/unavailable state instead of stale current values or false zeros.
- Confirm that 422 errors explain a field correction, 401 sign-in errors ask the user to check credentials, and 5xx errors tell the user to verify a record before retrying.

Record screenshots and any defects before sign-off. This checklist has not been marked passed by the source-package checks alone.

## 4. Registration test

Use a dedicated non-production test account and a disposable/test database branch only. Verify the registration transaction creates the tenant, user, business profile, active membership, Owner role assignment, first branch, first warehouse, and first location. Check the returned IDs and that the owner can sign in and load protected workspace data. Do not create a test account in the production tenant and do not print credentials/tokens into logs.

Retry behavior should include both (a) the same request and idempotency key, which must return the original response without making duplicate workspace rows, and (b) reuse of that key with changed request fields, which must return conflict.

## 5. Production handoff boundaries

- Do not deploy by triggering Render `main` while the candidate is only in the ZIP; that would deploy the existing main commit, not this code.
- After the ZIP is reviewed and brought into the intended branch, use GitHub CI to run the backend tests, frontend `npm ci`/typecheck/tests/build, and migration-source check.
- Production acceptance remains blocked by the seven missing exact migration files noted in `migrations/SOURCE_RECOVERY.md`, live Render readiness configuration reconciliation, and credentialed hosted auth E2E.
- Do not mutate the canonical Neon `lexa-live` schema as part of the UX pass.
