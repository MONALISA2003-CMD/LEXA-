# LEXA 2.6.0 — Phase 2 Identity, Tenancy & Authorization

This release advances LEXA into the multi-user, multi-tenant authorization foundation.

### Included

- Tenant settings model and API.
- Capability-based default role templates.
- Membership lifecycle endpoints with last-Owner protection.
- Branch assignment API and database-enforced branch scope.
- Hashed, expiring tenant invitation tokens and invitation acceptance.
- Current-user and session management APIs.
- Administration and invitation-acceptance web surfaces.
- Forced RLS on new identity-control tables plus assignment-aware policies on branch-bearing business tables.
- Phase 2 contract tests and verification script.

### Important deployment note

GitHub write access is currently blocked by the integration with HTTP 403 (`Resource not accessible by integration`). This package therefore remains a manual GitHub deployment artifact. Do not apply migration 023 directly to the production Neon branch until the source package has been deployed and the Phase 1.5 Render readiness blocker has been cleared.

### Security note

Invitation and security tokens are stored hashed. The administration page displays a newly created invitation token once so an operator can hand it to the invitee while email dispatch is not yet enabled; it must be treated as a credential and not logged or persisted by the browser.
