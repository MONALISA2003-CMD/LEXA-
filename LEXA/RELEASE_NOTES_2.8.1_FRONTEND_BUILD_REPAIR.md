# LEXA v2.8.1 — Frontend Build Repair

## Vercel blocker fixed

The production build failed because `apps/web/app/invite/page.tsx` imported `acceptInvitation`, which was not exported by `apps/web/lib/api.ts`. Repository inspection confirmed the current FastAPI source also has no invitation-acceptance endpoint or invitation model. Adding a speculative API wrapper would make the page compile but fail in production.

The invite route now shows an explicit, customer-safe unavailable state with a sign-in path. Invitation acceptance should be restored only after its backend contract, authorization, token expiry, password rules and tests exist.

## Deployment settings

- Vercel Root Directory: `apps/web`
- Framework: Next.js
- Build command: `npm run build` (or auto-detected `next build`) once legacy technical routes are deleted from source; keep the existing scoped cleanup command temporarily if `app/business-engine` and `app/kernel` still remain.
- Install command: auto-detected from `apps/web/package.json`
- API origin: set `NEXT_PUBLIC_API_URL` and `LEXA_API_URL` to the exact live Render service URL; historical project notes contain different example hostnames.

The Vercel log path `./app/invite/page.tsx` is relative to `apps/web`. A cleanup script removes the obsolete `apps/web/app/business-engine` and `apps/web/app/kernel` user-facing route modules (the backend infrastructure remains intact) plus the generated TypeScript build cache. After reviewing and committing those deletions, use the standard Next.js build command.

## Validation

- Python suite: 96 passed
- Backend Python compilation: passed
- Frontend visible-product/hardening contract: passed after edits
- Frontend TS/TSX syntax gate: expanded from 25 to 26 source files
- Full npm install and Next.js typecheck/build: not verified locally because `npm install` timed out in this environment. Vercel must confirm the dependency-backed production build after the repaired source is pushed.

No database schema, data, credentials or backend invitation behavior was changed.
