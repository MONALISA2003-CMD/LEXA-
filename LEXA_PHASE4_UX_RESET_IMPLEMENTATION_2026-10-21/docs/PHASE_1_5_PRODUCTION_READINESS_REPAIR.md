# LEXA Production Readiness Repair — Phase 1.5

## Runtime database identity

LEXA keeps `lexa_app` as a `NOLOGIN` PostgreSQL role containing the application's least-privilege grants.

Render authenticates with the separate `lexa_runtime` login role, which is a member of `lexa_app`. Application transactions then use `SET LOCAL ROLE lexa_app` so the effective database privileges remain bounded and transaction-local.

The runtime must point to the canonical Neon pooled endpoint for the `lexa-live` branch. Do not introduce a second database or a Render-managed PostgreSQL instance.

## Readiness

`/ready` is the deployment readiness gate. It verifies the canonical Neon database identity and required schema. Production responses remain sanitized; database exceptions are written to application logs for diagnosis without exposing credentials to callers.

## Web source cleanup

Internal Business Engine and Kernel frontend routes are not product routes and are removed from the production web tree. They remain technical infrastructure only where required by backend workflows.

## Reproducible web dependencies

The web package pins its direct dependencies to exact versions and uses Node 24.x. The direct web dependencies are pinned to exact versions. A committed lockfile should be added once GitHub write access is restored; the current Vercel build has been verified against the pinned versions.
