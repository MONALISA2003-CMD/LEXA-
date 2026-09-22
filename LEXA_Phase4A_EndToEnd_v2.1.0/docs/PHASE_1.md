# LEXA Phase 1 — Foundation

## Slice 3 implemented

This slice extends the Phase 1 foundation without resetting or deleting existing data.

### Identity and sessions
- Persisted `sessions` with hashed refresh tokens, expiry and revocation.
- Optional persisted `devices` associated with tenant/user.
- Access tokens carry a session ID and authenticated requests reject revoked sessions.
- Refresh token rotation is implemented.
- Logout revokes the refresh-token session.

### RBAC
- Tenant-scoped role listing and creation.
- Permission listing.
- Membership-to-role assignment with tenant ownership checks.
- Permission dependency for protected organization/RBAC routes.
- New tenant registration creates an initial `Owner` role and assigns it to the registering membership.

### Organization
- Profile read/create with duplicate protection.
- Branch list/create.
- Warehouse list/create with tenant branch validation.
- Location list/create with tenant warehouse validation.
- POS terminal list/create with tenant branch validation.
- Response schemas avoid exposing arbitrary ORM fields.

### Tenant isolation hardening
- Authenticated requests validate active membership and persisted session.
- Tenant context is set before tenant-scoped queries.
- Composite tenant foreign keys are added for branch/warehouse/location/POS relationships where cross-tenant references are a risk.
- RLS is enabled for devices and sessions as well as the existing tenant-owned tables.

## Neon Phase 1 implementation status

The LEXA Neon development branch now contains the Phase 1 database/security foundation, including forced RLS, the restricted `lexa_app` role, audit protection, idempotency records, transactional outbox, and event-consumption records. See `docs/PHASE_1_NEON_STATUS.md` for the exact branch and verification record.

## Still pending before Phase 1 is production-ready
- Run the application itself against the LEXA development branch in a connected integration environment.
- Add Alembic environment/revision integration and migration CI checks.
- Add richer user/membership management APIs and session/device management endpoints.
- Add audit/outbox service boundaries for critical writes.
- Review and execute the controlled production migration procedure.
- Continue into Catalog/Inventory hardening only after the foundation gate is accepted.
