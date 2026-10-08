# LEXA v2.7.0 — Phase 3 UI/UX Foundation

## Added

- Shared authenticated LEXA application shell.
- Desktop sidebar and mobile bottom navigation.
- Workspace context, global search surface and Ask LEXA entry point.
- Dedicated Products workspace.
- Dedicated Inventory workspace.
- Product catalogue/detail/variant workflows.
- Inventory stock and ledger views with location filtering and integrity state.
- Responsive design tokens/components for panels, tables, forms, status and empty states.

## Architectural rules preserved

- Neon PostgreSQL remains the sole business system of record.
- Existing API contracts are reused; UI does not implement business arithmetic or authoritative inventory logic.
- Idempotency remains API-side for mutations.
- Business Engine remains internal infrastructure and is not exposed in navigation.

## Verification

- 95 Python tests passed.
- Existing visible product contract passed.
- Existing frontend hardening contract passed.
- Production deployment is not claimed from this package because GitHub write access remains blocked by the integration.
