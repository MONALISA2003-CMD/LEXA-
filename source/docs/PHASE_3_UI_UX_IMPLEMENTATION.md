# LEXA Phase 3 — Catalog, Products & Inventory UI/UX Foundation

## Purpose

Phase 3 establishes the authenticated LEXA workspace shell and moves Products and Inventory out of the previous monolithic dashboard into dedicated operational routes.

## UX contract

- LEXA is a business workspace, not an ERP maze.
- Desktop uses a persistent left navigation rail; mobile uses a compact bottom navigation.
- The top bar provides global business search, Ask LEXA, notifications and account context.
- Pages use consistent heading, context, primary action, filters, table/detail and status patterns.
- Product records describe catalogue-facing items; variants/SKUs carry operational identity.
- Inventory shows authoritative on-hand/available/value state and separates stock from ledger/workflow areas.
- Empty, error, loading, permission and integrity states are explicit rather than hidden.
- The UI never claims a business mutation succeeded without the API/database response.
- Internal Business Engine infrastructure remains invisible to users.

## Implemented routes

- `/products` — searchable product catalogue, product detail, variant creation and product creation.
- `/inventory` — stock balances, ledger, location filtering, inventory integrity status and workflow tabs.

## Shared shell

`apps/web/components/app-shell.tsx` is the first shared authenticated shell. It centralizes:

- workspace identity
- primary/secondary navigation
- responsive mobile navigation
- global search surface
- Ask LEXA entry point
- connection state
- account action

The existing Home experience is preserved during this incremental migration; subsequent phases should migrate remaining modules onto the shared shell rather than recreating navigation per page.

## Validation

- Python suite: 95 passed.
- Existing visible-product contract: PASS.
- Existing frontend hardening contract: PASS.
- Full Next build/typecheck was not claimed from this local sandbox because the base package intentionally has no installed dependency tree; production-equivalent web builds remain a deployment gate.
