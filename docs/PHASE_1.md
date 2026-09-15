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

## Still pending before Phase 1 can be called complete
- Run the migrations and full integration suite against a real PostgreSQL instance.
- Add explicit RLS integration tests proving tenant A cannot read/write tenant B rows.
- Add Alembic environment/revision integration and migration CI checks.
- Add richer user/membership management APIs and session/device management endpoints.
- Add audit/outbox service boundaries for critical writes.
- Continue into Catalog foundation after the identity/organization boundary is verified.
