# Phase 4 — UX Reset and Dashboard Foundation

**Date:** 21 October 2026  
**Implementation package:** LEXA Phase 4 foundation (source-only)  
**Primary file:** `FRESH_NEW_PRODUCT_STRATEGY.md`

## Scope implemented in this package

1. Reworked the Command Centre information hierarchy to emphasize key business questions and next actions.
2. Added selectable **7-day, 30-day and 90-day** analytics ranges through the existing analytics API.
3. Added a dependency-free SVG chart comparing **net sales** and **payments collected**, sourced from actual daily analytics records.
4. Made missing dates appear as gaps rather than inventing zero-valued transactions; added a daily data table as an accessible alternative.
5. Added a tenant-scoped `/analytics/products/summary` API that aggregates product metrics across the selected date range before ranking; the existing daily product endpoint remains unchanged for detail reports. The dashboard displays net sales and gross-margin value separately.
6. Preserved independent load/error states so failure in product metrics does not hide valid stock or commerce data.
7. Added mobile responsive styling, visible focus, larger range controls, reduced-motion handling and chart labels.
8. Added source-contract tests for the date ranges, data provenance, accessible table and responsive chart surface.
9. Carried forward the supplied Phase 3 transaction-local tenant-context source correction and least-privilege runtime-login default in the reconstructed package.
10. Added product-strategy and Phase 4 acceptance documentation.

## Screen-by-screen audit register

This is the Phase 4 implementation/audit checklist for the preserved source snapshot. It is **not** a claim that each route was already exercised in a live browser during this build.

| Screen / route | Required UX standard | Acceptance evidence required |
|---|---|---|
| Public landing `/` when signed out | Clear product promise, concise feature explanation, accessible navigation, responsive layout | Visual mobile/desktop review; all links work |
| Login `/login` | Clear field labels, password visibility control, specific errors, keyboard/touch operation | Valid login, invalid credentials, expired/revoked session, refresh behavior |
| Registration `/register` | Field validation and clear setup next step; no silent duplicate submission | Happy path, validation failures, duplicate registration, mobile layout |
| Workspace `/workspace` | Show only active authorized workspaces; clear active selection | Switching verifies server membership, refresh token/session behavior and revocation |
| Onboarding `/onboarding` | Save progress and explain incomplete prerequisites; no ambiguous next action | Resume, create/update profile, create branch and stock location, reload after each step |
| Command Centre `/` signed in | Real KPIs, period selection, clear sales-vs-cash distinction, actionable exceptions | API-source reconciliation; each panel failure isolated; 7/30/90 ranges; narrow viewport; chart table |
| Sales `/sales` | Fast search, obvious checkout total, safe payment state, return/refund traceability | Authenticated create/read sale, payment status, idempotent replay, return/refund path |
| Commerce `/commerce` | Transaction and payment state readable; no confusing status actions | Create/read/change supported records; permissions and error paths |
| Products `/products` | Searchable catalog, concise variant/price/stock info, validated create/edit forms | Product/variant/barcode CRUD and duplicate-key tests; all visible controls covered |
| Inventory `/inventory` | Location-scoped balance, movement ledger, stocktake, transfer and adjustment workflows | Movement-level reconciliation, branch denial, transfer endpoint access, stale/duplicate write checks |
| Purchasing `/purchasing` | Supplier context, PO statuses, partial receiving and clear stock effect | PO lifecycle from draft through receipt and supplier balance, including repeated receipt protection |
| Customers `/customers` | Search, customer history, outstanding balance and accessible edit/create flows | Customer CRUD, credit allocation, return adjustments and permissions |
| Accounting `/accounting` | Honest account/period/entry state, debit-credit clarity and reconciliation links | Journal balance rules, period closure, query optional filters, reports to source records |
| Reports `/reports` | Defined filters, metric glossary, export action feedback and drill-through | KPI definition and source reconciliation per report; empty/error/access-denied states |
| Intelligence `/intelligence` | Recommendations explain sources/period/limits and never imply certainty without evidence | Historical backtest, error bounds and human approval before material writes |
| Compliance `/compliance` | Show fiscal status, error reason and retry guidance; protect credentials | Mock/sandbox integration, duplicate handling, provider down/timeout, audit log, current applicability review |
| Administration `/administration` | Business profile and settings are editable with permission-aware states | Save/cancel, validation, audit trail and restricted-role acceptance |
| Team and Access `/administration/members` | Explain roles, branch scope, invitations and save behavior | Cross-tenant and branch authorization tests, invitation expiry/replay, last-owner race checks |
| Settings `/settings` | Safe, discoverable preferences with clear save feedback | Persist/reload, input validation, role protection and keyboard acceptance |

## KPI glossary and guardrails

| Display | Meaning to the user | Guardrail |
|---|---|---|
| Today's sales | Completed sales for the current business date | Not equivalent to cash collected or profit |
| Collected today | Recorded payments for the current business date | Pending payment requests do not count as collected funds |
| Net sales | Analytics total for selected period, applying the server's return treatment | Period and currency visible; must reconcile to analytics source |
| Inventory value | Sum of the available stock valuation rows | Document cost vs retail valuation basis before publishing a formal finance report |
| Top products | Sum of each variant's returned daily product metrics over the selected period | Ranked by net sales; gross-margin value shown separately; results respect API limit |
| Gross-margin value | Net sales minus cost of goods sold under the analytics source contract | Not net profit; no claim that all product records are returned by a limited endpoint |
| Open receivables | Current outstanding customer balances from commerce dashboard | Do not duplicate payments or ignore approved returns/credits |
| Stock exceptions | Out-of-stock/low-stock rows and draft adjustments returned by the inventory API | Exceptions are partial if any source endpoint failed |

## Design system rules for the next screens

- Use the established LEXA brand tokens and shared primitives rather than introducing a second, disconnected UI library.
- Keep a consistent page-header pattern, panel header, action row, status badges, field labels, inline errors and save feedback.
- Prefer one primary action per screen and use explicit action wording (`Create sale`, `Save changes`, `Receive stock`, `Approve adjustment`).
- Use table/list views for dense business records; use charts only to reveal trends or comparisons, always with labels and an accessible data alternative.
- Target at least 44 CSS px for frequent mobile actions where practical; keep all applicable targets and spacing consistent with WCAG 2.2 SC 2.5.8.
- Treat loading, no records, API failure, forbidden and incomplete results as distinct states. Never disguise failure as an empty list or zero KPI.
- Keep keyboard focus visible, respect reduced-motion preferences, and do not use colour as the only status cue.
- Confirm destructive/financial actions; disable duplicate submission while a request is pending; show the resulting record/status after a successful action.

## Validation performed / pending

### Implemented by source change

- The new dashboard uses existing API functions; no database migration or new business-table write is introduced.
- Analytics range fetches use selected explicit start/end dates.
- The chart's SVG is labelled, and an expandable data table lists actual daily metrics.
- Product and analytics requests have separate loading/error state handling; range-level product ranking aggregates before applying its limit.
- Source-contract tests cover periods, source calls, aggregated product ranking, accessibility, missing-date handling and responsive/reduced-motion styles.

### Must still be run against the final canonical checkout

1. Apply/reconcile this work against the latest final Phase 3 handoff and GitHub `main`; the preserved archive used here is an earlier pinned snapshot plus supplied source overlays.
2. Run clean Node 24 `npm ci`, `npm run typecheck`, `npm test`, and `npm run build`.
3. Run full API tests with required dependencies, then authenticated E2E on the deployed frontend/backend.
4. Validate dashboard totals against database/API responses using at least: no data, sales only, credit sale, return/refund, delayed payment, mixed currency, branch-scoped account and analytics source error cases.
5. Test the dashboard on narrow Android widths, 200% zoom, keyboard-only navigation and a screen reader; inspect actual tap targets.
6. Check chart lines against dates containing gaps and negative net sales.
7. Do not deploy from this reconstructed archive without reconciling its source history with the current production/main source.

## Release decision

**Phase 4 foundation implementation:** source changes and test contracts included.  
**Phase 4 UX gate:** not declared fully passed until the remaining route-by-route browser audit and canonical source reconciliation above are recorded.  
**Database changes:** none introduced by this Phase 4 work.  
**Deployment/GitHub write:** not performed by this source package.
