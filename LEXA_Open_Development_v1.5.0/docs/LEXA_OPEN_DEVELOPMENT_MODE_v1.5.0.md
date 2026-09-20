# LEXA Open Development Mode v1.5.0

## Purpose

LEXA is temporarily presented as an open workspace so product and engineering work can continue without the authentication screen interrupting module review. This is a development workflow, not a production authentication decision.

## Browser behavior

The browser opens the LEXA workspace directly. When the open development switch is enabled, the web application requests a guarded development session. The returned token is a normal LEXA session token, so tenant context, permissions and PostgreSQL row-level security continue to exercise the real authorization path.

The authentication UI is not rendered during this phase. The underlying register, login and refresh endpoints remain in the API for the later production onboarding pass.

## Safety boundary

The development session endpoint is available only when:

- `LEXA_OPEN_DEV_MODE=true`
- `APP_ENV` is not `production`

The API also verifies the canonical Neon identity before issuing the session:

- project: `LEXA`
- branch: `lexa-live` (`br-soft-star-b1dj2m2w`)
- database: `neondb`

The current development Render configuration therefore uses `APP_ENV=development` and enables `LEXA_OPEN_DEV_MODE`. Before production readiness, that switch must be disabled and the application environment must be changed back to production.

## Preview workspace

The canonical LEXA branch contains one dedicated preview workspace with a small set of neutral sample catalog records. These are ordinary tenant-scoped records and are loaded through the same RLS-protected application paths as real workspace data.

The preview workspace currently includes sample products, variants, a retail price list, a branch, warehouse and location. It is intended for UI/UX review and workflow development only.

## Inventory resilience

Inventory data loading now uses partial success handling. Available areas such as locations can still be reviewed while unfinished stock services are being implemented. The browser does not expose internal service failures.

## Production transition

When LEXA is nearly production-ready:

1. Set `LEXA_OPEN_DEV_MODE=false`.
2. Set `APP_ENV=production`.
3. Set `NEXT_PUBLIC_LEXA_OPEN_MODE=false`.
4. Restore the production onboarding interface.
5. Validate registration, login, workspace selection, session refresh and logout end to end.

No database reset is required for this transition.
