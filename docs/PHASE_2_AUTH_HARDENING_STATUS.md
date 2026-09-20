# LEXA Workspace Registration Hardening Status

## Scope

This hardening is LEXA-only and targets the development implementation branch before further feature work.

## Fixed

- Workspace registration now creates the `business_profiles` record required by the tenant model.
- Registration is protected by a pre-tenant idempotency record so repeated submissions can safely replay the same response.
- Concurrent use of the same idempotency key is serialized with a row lock.
- Registration request hashes include the request fields but never persist the plaintext password.
- Workspace creation writes a tenant audit record and transactional `workspace.created` outbox event.
- Database integrity conflicts are returned as explicit client/service errors instead of generic 500 responses.
- API responses now expose an `X-Request-ID` for traceability.
- The Vercel proxy forwards the upstream `X-Request-ID`.
- The web client includes the request ID in API error messages.
- The registration client now sends an `Idempotency-Key`.
- Migration `008_workspace_registration_hardening` was applied to `lexa-phase1-dev`.

## Environment requirement still external to this source package

The live Vercel deployment uses a separate FastAPI service. Its secret `DATABASE_URL` is not stored in Git and cannot safely be embedded in this package.

For development validation, the FastAPI service must point to the LEXA `lexa-phase1-dev` Neon branch. LEXA production remains intentionally untouched and currently contains zero application tables.

The service should expose:

- `GET /health` for process liveness
- `GET /ready` for PostgreSQL readiness
- `POST /api/v1/auth/register` for workspace creation

## Verification

- Python source/unit/integration suite: 38 passed.
- Existing visible-product frontend contract: PASS.
- Neon migration 008: applied successfully on `lexa-phase1-dev`.
- Neon registration hardening table: present.
- Production branch: not modified.
- No production data reset, deletion, or seeding performed.

## Deployment gate

Do not promote the development database schema to LEXA production until the live FastAPI service has been verified against the intended development branch, registration succeeds end-to-end, login succeeds, and tenant isolation tests remain green.
