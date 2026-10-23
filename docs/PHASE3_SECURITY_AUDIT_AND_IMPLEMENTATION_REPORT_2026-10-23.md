# LEXA Phase 3 Security Hardening — Audit & Implementation Report

**Date:** 23 October 2026  
**Scope:** Phase 2 source review, Phase 3 identity/security implementation, Render/Vercel/Neon audit, disposable PostgreSQL migration validation.  
**Production status:** No production deployment, production environment-variable mutation, or production database write was performed.

## Executive summary

Phase 3 introduces account recovery and active-session controls, hardens the API proxy boundary, and aligns the readiness gate with the currently maintained migration chain. The updated candidate was regression-tested locally and migration `044` was applied only on the existing Neon forward-validation branch, not on `lexa-live`.

The most important discovered risk was a production fallback in the deployed GitHub `main` proxy: if its origin environment variable was absent, it could route an unconfigured Preview/Production deployment to the live Render API. The candidate now fails closed when `LEXA_API_URL` is not configured and does not use `NEXT_PUBLIC_API_URL` or a hardcoded production origin.

## Changes implemented in the candidate

### 1. Forgot password and secure password reset

- Added `POST /api/v1/auth/forgot-password` and `POST /api/v1/auth/reset-password`.
- Added Emerald Fusion `/forgot-password` and `/reset-password` screens and a login-page recovery link.
- Reset tokens are cryptographically random, stored only as SHA-256 hashes, expire, and are single-use. Requesting a fresh token invalidates previous unused reset tokens for that user.
- The public request response is generic for existing and unknown accounts. Reset email configuration is checked before account lookup.
- Reset URLs carry the token in a URL fragment, which browsers do not send to the server. The page removes the fragment from the address bar after reading it.
- The initial email adapter uses the Resend HTTPS API. Email delivery occurs after the HTTP response; if delivery fails, the newly issued token is invalidated. Logs avoid printing the token, reset URL, email or provider response body.
- Password reset changes the password and revokes active sessions for the user across workspaces, in one database function call.
- Per-IP and per-email rate limits use Redis. Email addresses are hashed before use in Redis keys. Redis failures fail closed with `503` rather than disabling the limits.

### 2. Active sessions and sign-in security

- Added `GET /api/v1/auth/sessions` and `POST /api/v1/auth/sessions/{session_id}/revoke`.
- The session list is scoped to the authenticated user and current workspace; session revocation cannot affect another user's session. The current session cannot be accidentally revoked from the page; the user signs out normally instead.
- The security page allows users to review active sessions and revoke another session. Settings and search/navigation expose the destination.
- Refresh-cookie deletion now matches the production Secure, HttpOnly and SameSite attributes used when issuing the cookie.

### 3. Vercel-to-Render proxy hardening

- The Next.js proxy uses only server-side `LEXA_API_URL`. An unconfigured Preview/Production deployment responds with `API_ORIGIN_NOT_CONFIGURED` rather than sending requests to the live API by fallback.
- The proxy forwards a Vercel-derived client IP only with the server-side `LEXA_PROXY_SHARED_SECRET`; FastAPI checks the secret using constant-time comparison and parses the address as an IP. Untrusted headers fall back to the direct peer address.
- Production startup now requires a shared secret at least 32 characters long. This is a deliberate fail-closed gate because login/registration/recovery rate limiting otherwise sees the proxy's egress IP and risks applying one shared throttle bucket to many browser users.
- Updated Vercel/Render deployment docs and `.env.example` files to use the server-only origin and secret, and to document required email configuration.

### 4. PostgreSQL migration and readiness

- Added `migrations/044_phase3_password_reset_security.sql` with three restricted `SECURITY DEFINER` functions: `lexa_issue_password_reset`, `lexa_consume_password_reset`, and `lexa_revoke_password_reset`.
- Functions use a fixed `search_path`, validate token-hash and expiry inputs, revoke `PUBLIC` execution, and grant execution to `lexa_app` only. Installation checks ensure the definer owner bypasses forced RLS; the app role itself remains least-privileged and must not bypass RLS.
- The `/ready` gate now requires migrations `041`, `042`, `043`, and `044` in addition to the previously required application migrations. This closes a gap where the live database was further ahead than the health-check migration contract.
- Updated the clean-replay manifest, replay gate and tests. The manifest contains 48 migration inputs.

## Live infrastructure audit

### Vercel

- Project `lexa` on the production target reports its latest listed deployment as `READY` on commit `71b80763d0e42d7c870e1e0bbb14b5bbf7e660a1`.
- Grouped runtime-error query for the prior 24 hours reported no runtime-error clusters. A recent detailed runtime-log query returned no entries for the requested window; this does not prove there are no latent issues outside that query window.
- Environment metadata showed `LEXA_API_URL` and `NEXT_PUBLIC_API_URL` on the Production target, with no `LEXA_PROXY_SHARED_SECRET` listed. Remove the obsolete `NEXT_PUBLIC_API_URL` variable from Vercel when preparing the new release, and configure `LEXA_PROXY_SHARED_SECRET` as a server-only variable before deploying this candidate.

### Render

- The LEXA FastAPI service `srv-dakm8k95efls73egg9a0` reports its latest deployment succeeded on commit `44b59f0615da5106e134a60b589fd0d762c0cd27` at approximately `2026-10-23T07:36:44Z`.
- Render error/warning logs queried for `2026-10-23T07:30Z` to `08:24Z` were empty. This is a bounded observation window, not a guarantee of error-free operation.
- The service remains on the Render Free plan with one configured instance. This is not an adequate capacity commitment for the eventual 10,000–20,000-user target; capacity planning and load tests remain Phase 6 work.
- The available Render service metadata did not expose environment variable values, so whether the shared secret and mail-provider variables already exist in Render could not be verified. Confirm them in the dashboard without exposing their values in logs or chat.

### Neon PostgreSQL

- The production `LEXA` project (`wispy-mud-75323042`), branch `lexa-live` (`br-soft-star-b1dj2m2w`), is PostgreSQL 18 and showed migration history through `043_phase5_journal_currency_guard`. Migration `044` is **not applied to production**.
- Read-only security queries found all 130 public base tables with RLS enabled and forced, and no public base table missing RLS. The `lexa_app` role was non-login, did not have `BYPASSRLS`, and did not have schema `CREATE` privilege.
- Identity tables inspected (`users`, `sessions`, `user_security_tokens`, memberships and security/audit records) had RLS policies. This provides a strong base, but API-level cross-tenant and branch-access tests remain necessary.
- The production `lexa-live` branch currently reports `protected=false`; protect the production branch after checking the team's existing branching policy.

## Real PostgreSQL validation of migration 044

The migration was executed against the existing disposable Neon forward-validation branch `lexa-phase345-forward-validate-20261023` in project `LEXA-PHASE7-REPLAY-20261022`; it was not applied to `lexa-live`.

Verified on that branch:

- Migrations `041`, `042`, `043`, and `044` are recorded.
- All three new functions exist, are `SECURITY DEFINER`, are owned by a role with `BYPASSRLS`, are executable by `lexa_app`, and are not executable by `PUBLIC`.
- `users`, `sessions`, and `user_security_tokens` still have RLS enabled/forced and policies present.
- An isolated synthetic-user SQL test successfully verified that unknown emails do not issue tokens, a valid reset token updates the password hash, a wrong token is rejected, and a second use of a consumed token is rejected. The synthetic test user and token were deleted; a follow-up count confirmed zero leftover synthetic users.
- An invalid-token check returned `false` as expected.

This validated SQL behavior on a test branch. The complete production release still needs a controlled `044` migration rollout and authenticated browser acceptance after environment configuration.

## Verification completed

- Backend suite: **320 passed**, 1 existing Starlette cookie-test deprecation warning.
- Frontend node test suite: **68 passed, 0 failed**.
- Phase verification script: passed, including TypeScript syntax contract across 40 files and workspace-convergence checks.
- Python source compilation: passed.
- Clean migration replay `--plan-only`: **48 inputs present and hashed**, bundle SHA-256 `8be73eaaf3bcf4dd13c24c9ec09b06db35115d2032b3bb946f8da57ade8aec24`. The plan-only check opened no database connection and executed no SQL.
- Next.js production build/typecheck could not be verified in this environment: project configuration expects Node 24 and installed dependency types, while this environment is Node 22 and has no successful dependency installation. Do not treat TypeScript syntax transpilation as a full production build.
- GitHub push/branch creation is not available through the connected integration (previous branch creation returned HTTP 403). No commit or PR was created by this run.

## Required release order

1. Configure a random `LEXA_PROXY_SHARED_SECRET` of at least 32 characters in both Render and Vercel (server-only, same exact value), and remove obsolete `NEXT_PUBLIC_API_URL` from Vercel. Do not send these values through chat or commit them.
2. Configure and verify a Resend API key, verified `EMAIL_FROM`, and trusted HTTPS `PUBLIC_APP_URL` in Render. Until then, password recovery intentionally returns a service-not-configured error.
3. Apply migration `044` to a separate staging branch/database using the approved migration runner, run `/ready`, and repeat token/session/browser tests.
4. Back up and review the production migration plan. Apply `044` to production only in the approved release window, then deploy the API and confirm `/ready`.
5. Deploy the Vercel frontend with its own `LEXA_API_URL` and shared secret. Confirm an unconfigured Preview fails closed rather than connecting to production.
6. Run authenticated browser acceptance for forgot/reset password, token expiry/replay, sign-in after reset, active-session listing/revocation, cross-tenant denial and navigation links.

## Boundaries of this report

No production database changes, production environment edits, GitHub pushes or deployments were performed. The prepared archive is a candidate for review and staging, not a statement that Phase 3 has been released to production.
