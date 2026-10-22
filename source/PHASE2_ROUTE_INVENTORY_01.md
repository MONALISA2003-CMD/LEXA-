# Phase 2 route and integration inventory — initial pass

Source: `apps/web/app/**` and `apps/web/lib/api.ts` in the uploaded Phase 1 candidate.
This is a filesystem inventory, not a claim that every workflow is fully implemented.

## App routes discovered

| Route | Source file | Phase 2 action |
|---|---|---|
| `/` | `apps/web/app/page.tsx` | Command Centre; audit data states and summary resilience |
| `/sales` | `apps/web/app/sales/page.tsx` | Audit critical sales workflows and mobile actions |
| `/inventory` | `apps/web/app/inventory/page.tsx` | Audit dense tables and mobile fallback |
| `/products` | `apps/web/app/products/page.tsx` | Audit catalog forms, filters and tables |
| `/commerce` | `apps/web/app/commerce/page.tsx` | Inspect shared commerce behavior and route wrappers |
| `/customers` | `apps/web/app/customers/page.tsx` | Audit customer data and forms |
| `/purchasing` | `apps/web/app/purchasing/page.tsx` | Audit purchasing/receiving workflows and maturity |
| `/accounting` | `apps/web/app/accounting/page.tsx` | Audit financial state accuracy and permissions |
| `/reports` | `apps/web/app/reports/page.tsx` | Audit filters, empty/error states and responsive data |
| `/compliance` | `apps/web/app/compliance/page.tsx` | Audit status, access and unfinished workflow indicators |
| `/intelligence` | `apps/web/app/intelligence/page.tsx` | Audit query and insight states without fabricated answers |
| `/administration` | `apps/web/app/administration/page.tsx` | Audit membership and permission-sensitive controls |
| `/settings` | `apps/web/app/settings/page.tsx` | Audit settings maturity and save/error states |
| `/login` | `apps/web/app/login/page.tsx` | Preserve auth behavior; accessibility and responsive review |
| `/register` | `apps/web/app/register/page.tsx` | Preserve auth behavior; validation and responsive review |
| `/invite` | `apps/web/app/invite/page.tsx` | Preserve invitation flow and authorization checks |

Shared layout: `apps/web/app/layout.tsx`.
Shared authenticated shell: `apps/web/components/app-shell.tsx`.
Shared UI primitives: `apps/web/components/ui.tsx`.
API client: `apps/web/lib/api.ts`.

## Initial shell integration contracts

`app-shell.tsx` continues to call `restoreSession()`, `getReadiness()`, and `logout()`; it preserves the sign-in redirect and the existing route mapping for business search. Phase 2 increment 01 changes no API client, backend, database, auth or permission code.

## Audit status

This is a route inventory only. Each route still needs inspection for actual API calls, authorization, mutation outcomes, loading/empty/error/forbidden states, responsive behavior and whether any module is a scaffold or wrapper. Those findings must be recorded before declaring full Phase 2 complete.
