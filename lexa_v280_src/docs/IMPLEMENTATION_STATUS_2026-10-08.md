# LEXA v2.8.0 implementation status — 2026-10-08

## Implemented

The release-convergence repair was implemented in the source tree and applied to the canonical Neon production branch.

- Next.js `/invite` now wraps `useSearchParams()` behind `Suspense`.
- The invitation client contract exists and the FastAPI `/api/v1/auth/accept-invitation` route is implemented.
- Malformed/legacy password hashes fail closed as invalid credentials instead of producing HTTP 500.
- Global request exceptions are logged with request ID, method, path and exception type while the response remains sanitized.
- `/ready` now requires canonical Neon identity, the complete required operational schema/migration contract, and Redis availability.
- Migration 021 source corruption was repaired; inventory velocity is sale-only.
- Migration 022 dynamic RLS policy SQL was repaired.
- Migration 027 provides additive release convergence for supplier/purchasing schema parity and tenant-local business dates.
- Canonical Neon production now contains the identity foundation and `027_release_convergence`.
- Production privilege and RLS probes pass for the `lexa_app` role.
- 102 repository tests pass.

## Verified live

- Neon database: `neondb` on `br-soft-star-b1dj2m2w`.
- Required readiness tables: 56/56 present.
- Migration ledger contains identity 023, historical purchasing 023–026, and 027 convergence.
- `lexa_list_user_workspaces`, `lexa_get_invitation_by_token`, and `lexa_can_access_branch` exist and are executable by `lexa_app`.
- Render Key Value resource `lexa-redis` is available.
- Current Render LEXA deployment for commit `0338f3d...` built and deployed successfully; `GET /` has been observed returning 200.

## Still blocked by integration permissions

The connected GitHub integration rejects repository writes with HTTP 403, so the patched source cannot be committed to `main` from this session.

The connected Vercel integration rejects production deployment creation with HTTP 403, so the fixed frontend cannot be promoted from this session. The existing production alias remains on the last known-good deployment.

The current Render toolset exposes environment-variable mutation but does not expose an existing web-service `healthCheckPath` mutation or a shell/SSH deploy operation. Therefore the Render service cannot be switched from the empty dashboard health check to `/ready`, nor can the patched backend be redeployed from this session.

## Required final promotion

Once the GitHub/Vercel/Render connections permit writes, deploy this exact source tree/commit, then verify:

1. Vercel production deployment state = READY.
2. `/`, `/login`, `/invite` and the same-origin API proxy are reachable.
3. Render `healthCheckPath` = `/ready`.
4. `/health` and `/api/health` return liveness OK.
5. `/ready` and `/api/ready` return readiness OK with DB + Redis both OK.
6. Authentication returns 401 for invalid/malformed credentials rather than 500.
7. Invitation acceptance creates/activates the membership, assigns the invitation role, and marks the token accepted.
8. A post-deploy error log window contains no uncaught application exceptions.
