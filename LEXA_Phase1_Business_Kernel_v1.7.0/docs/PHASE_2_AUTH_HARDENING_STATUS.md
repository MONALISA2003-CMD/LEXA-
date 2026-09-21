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
- The registration client now sends an `Idempotency-Key`.
- Login no longer requires users to type a workspace identifier for normal use.
- Accounts with one active workspace enter it automatically.
- Accounts with multiple active workspaces receive a workspace picker.
- Browser-facing errors are translated into business-friendly messages.
- Internal trace identifiers and infrastructure diagnostics are kept out of customer-facing frontend messages.
- Migration `008_workspace_registration_hardening` was applied to `lexa-live`.
- Migration `009_auth_workspace_picker` was applied to `lexa-live`.

## Environment requirement still external to this source package

The live Vercel deployment uses a separate FastAPI service. Its secret `DATABASE_URL` is not stored in Git and cannot safely be embedded in this package.

For development validation, the FastAPI service must point to the LEXA `lexa-live` Neon branch. LEXA production remains intentionally untouched and currently contains zero application tables.

The service should expose the health and readiness checks used by the deployment environment and the authenticated workspace flows.

## Verification

- Python source/unit/integration suite: 42 passed.
- Frontend customer-language contract: PASS.
- TypeScript source transpilation checks: PASS.
- Python compilation: PASS.
- Neon migrations 008 and 009: applied successfully on `lexa-live`.
- Production branch: not modified.
- No production data reset, deletion, or seeding performed.

## Deployment gate

Do not promote the development database schema to LEXA production until the live FastAPI service has been verified against the intended development branch, registration succeeds end-to-end, login succeeds, workspace selection succeeds for multi-workspace accounts, and tenant isolation tests remain green.
