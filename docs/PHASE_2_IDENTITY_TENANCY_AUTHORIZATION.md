# LEXA Phase 2 — Identity, Tenancy & Authorization

## Objective

Establish production-safe multi-user, multi-tenant identity and authorization boundaries without creating a second authoritative database or weakening PostgreSQL row-level security.

## Implemented in 2.6.0

- Tenant settings for timezone, locale, business type, industry and fiscal-year start month.
- Membership branch assignments with tenant+membership and tenant+branch composite foreign-key integrity.
- Invitation records with hashed, time-limited tokens and explicit tenant role binding.
- Security-token storage for email verification and password-reset workflows, protected by user context.
- Capability permissions for tenant administration, invitation, membership lifecycle, session management, branch assignment and security controls.
- Standard tenant role templates: Owner, Administrator, Manager, Finance / Accounting, Sales, Inventory, Staff / Operator and Read-only.
- Current-session inspection and per-user session revocation.
- Invitation acceptance creates or activates a tenant membership and binds the invited role. Existing accounts must prove the current password.
- Request context carries both `app.tenant_id` and `app.user_id`; an optional `X-LEXA-Branch-ID` can be validated against membership branch assignments.
- Direct PostgreSQL branch visibility is assignment-aware. Owner, Administrator and Manager remain tenant-wide; operational roles can be narrowed to assigned branches.
- Administration, invitation-acceptance and Settings web surfaces.

## Database safety

Migration `023_phase2_identity_tenancy_authorization_foundation.sql` is additive and contains no reset, destructive rewrite, or data wipe. New tables are forced-RLS protected. Existing branch-aware policies are replaced only to add authorization scope while preserving tenant isolation.

The runtime login identity remains `lexa_runtime` and uses `SET LOCAL ROLE lexa_app` for application queries. The `lexa_app` role remains non-login.

## Deferred boundary

Email verification and password-reset delivery require the notification/email dispatch slice. Phase 2 creates the token data model and keeps token handling server-side; token delivery is not exposed as a secret in production responses. MFA/device policy expansion remains a later security hardening increment.

## Validation

- 101 repository tests pass.
- Backend compile passes.
- Frontend contract tests pass.
- The Phase 2 migration schema slice was executed on a disposable Neon branch.
- RLS behavior was exercised on the disposable branch: an assigned operational member saw only its assigned branch; cross-tenant rows remained invisible.
- Production Neon `lexa-live` was not modified by this validation step.

## Exit gate

Phase 2 is source-complete for this increment but not production-live until the migration and source package are manually deployed to the GitHub `main` branch, Render readiness is green, and the live authentication/tenant-isolation smoke suite is re-run.
