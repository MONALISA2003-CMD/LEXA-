# LEXA v2.8.2 — Phase 0 reliability repair

## Session and authentication reliability

- Protected API calls now restore the cookie-backed session before fetching tenant-scoped business data.
- Concurrent session restorations and 401 recoveries share a single refresh request to avoid racing rotating refresh tokens.
- Browser refresh requests send an explicit empty JSON object, and FastAPI also accepts a cookie-only refresh with no body.
- Authenticated workspace content is gated until session verification completes. Transient verification errors offer retry, and the sidebar no longer claims the service is online when the session is unverified.
- Sign-out navigates to the login page even when the API is temporarily unavailable.

## Vercel production build

- `apps/web/vercel.json` pins the standard `npm run build` command over the obsolete Vercel dashboard shell command.
- Obsolete Business Engine and Kernel frontend routes are removed from `apps/web`; backend infrastructure is untouched.
- Added session/build contract regression tests and a backend test for cookie-only session refresh.

## Safety / deployment boundaries

- No live database schema or records were modified.
- No production secrets or environment variables were changed.
- The full Next.js build must still pass in Vercel after the new ZIP is pushed; this package records source-level fixes and local test results only.
