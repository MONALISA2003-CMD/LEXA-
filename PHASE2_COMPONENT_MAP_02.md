# LEXA Phase 2 — Shared component map (Increment 02)

## Shared primitives now available

| Component | Responsibility | Migration guard |
|---|---|---|
| `Button` | Consistent hierarchy, sizing, disabled/loading state | Existing `button-*` CSS variants stay supported |
| `Badge` | Compact semantic status labels | Display only; never treated as authorization |
| `Skeleton` | Non-data loading placeholders | Must only render during a real loading state; never imply numeric values |
| `DataState` | Loading, empty, error, forbidden and unavailable states | Failed/forbidden/unavailable are never represented as zero |
| `StatusBanner` | Page-level info/success/warning/error messaging | Success copy must follow server confirmation |
| `PageHeader` | Shared page title, description and context | Navigation/session behavior remains in AppShell |
| `FormField` | Label, hint and validation message structure | Direct controls receive described-by and invalid state; wrapper controls should keep explicit IDs |
| `ConfirmDialog` | Confirm/cancel interaction | Escape/backdrop close are blocked while busy; focus is trapped and restored |
| `ResponsiveDataTable` | Desktop table plus mobile record cards | Callers must explicitly provide loading/error/empty state from real data state |

## Current explicit adoption

- `AppShell`: `PageHeader` continues to render shared page heading and readiness context.
- `login` and `register`: `FormField` and `StatusBanner` are already used for auth and onboarding.
- `products` and `inventory`: `ResponsiveDataTable` already controls desktop/mobile presentation and can display explicit data states.
- `DataState` now uses the shared `Button` for retry actions; `ConfirmDialog` uses the shared `Button` for cancel/confirm actions.
- Products uses `Badge` for catalogue status; the Command Centre uses `Skeleton` only inside explicit loading branches, with a live status label.

## Route rollout order

1. Products and inventory (table, filters, status and detail-panel patterns).
2. Sales and purchasing (transaction entry forms, line editors and approval actions).
3. Customers and accounting (balances, payment and finance states; preserve values, currency and audit semantics).
4. Reports, compliance and intelligence (date filters, evidence/empty states, generated-content provenance).
5. Administration, settings and commerce (permissions, workspace setup and role-sensitive actions).
6. Auth/invite and shell polish, followed by a full responsive/accessibility pass.

## Boundaries

This document inventories the design-system adoption path. It does not certify route completeness or live behavior. Only server-authorized API responses should determine business state; hiding a button is not an authorization boundary. No production changes were made.
