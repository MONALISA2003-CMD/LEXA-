# LEXA — Unified Frontend Brand, Module and Workflow System

**Date:** 26 October 2026  
**Product:** LEXA AI — business operations and intelligence for Ugandan retail, wholesale, distribution and multi-branch SMEs.  
**Authority:** The supplied LEXA master logo — multicolour geometric wordmark on midnight navy, with the gold descriptor `SALES · INVENTORY · BUSINESS MANAGEMENT`.

## Implementation boundary

This package is a frontend source overlay for the existing Next.js/React/TypeScript application. It standardises the shared visual system across existing routes and specialised CSS-module screens. It does **not** alter the FastAPI services, PostgreSQL schema, business records, authentication/permission enforcement, payment integrations or tax submission integrations. Existing route logic and API contracts remain authoritative. A visual state must never claim an operation succeeded when the underlying service has not confirmed it.

## Brand authority

- **Midnight navy `#010D27`:** structural surfaces and primary brand framing.
- **Blue `#075FE8`:** primary actions, navigation, links and sales/analysis series.
- **Cyan `#01B9BB`:** secondary information and selected analysis details.
- **Green `#00B77D` / deep green `#087F5B`:** positive operational outcomes and healthy states, not every primary button.
- **Gold `#E1C140`:** signature highlights, attention/balance cues and selected emphasis.
- **Red `#E91D3A`:** errors, destructive actions and critical exceptions.
- White/cool-neutral surfaces preserve readability for financial data, tables and forms.

The master JPG is used for high-visibility identity surfaces. The horizontal wordmark is used in the mobile header. The compact logo mark is appropriate for favicons/app-icon contexts only. Do not stretch, recolour or substitute the old checkmark icon for the master logo.

## Capability gaps deliberately not faked by the visual overlay

The current browser API (`apps/web/lib/api.ts`) does not expose serial-number or batch/lot entities or calls, and the current Products/Inventory pages do not expose those tracking workflows. The frontend should not present serialized-unit selection, serial duplicate prevention, batch expiry/FEFO, warranty, or serial return-inspection as operational until a backend API contract supports them. The existing variant API does expose inventory tracking and fractional-quantity settings; other stock workflows already present include balances, movements, ageing, transfers, stock counts, adjustments and replenishment.

The Reports screen currently exposes a subset of the target reporting presets (today, last 7 days, last 30 days, this month, last 90 days and custom dates). The full plan's shared preset set, previous-equivalent-period comparisons and financial-year-aware dates are functional date-engine work, not something CSS alone can add. This package applies the brand, responsive layout and chart/table visual contract to the existing preset controls; it does not claim the missing date-engine behavior has been implemented.

## Shared application system

The brand CSS provides global tokens and shared treatments for shell/navigation, page headings, working surfaces, buttons, forms, search and filters, tables, status labels, notices, empty states, keyboard focus, touch targets, reduced motion, and mobile safe areas. CSS-module styles for Team Chat/AI, Documents, Daily Brief and Forecast screens are aligned to the same tokens without replacing their underlying page logic.

## Frontend module map

| Product area | Existing frontend route(s) | Visual and interaction emphasis |
|---|---|---|
| Business Command Centre | `/` | Six dashboard areas: sales, inventory, finance, customers, purchasing, alerts/actions. Metric hierarchy, context, and drill-down navigation. |
| Product catalogue | `/products` | Clear product identity, SKU/variant attributes, prices, barcodes and status tables. |
| Inventory | `/inventory` | Stock ledger-related workflows, locations, counts, transfers, adjustments, serial/batch context; explicit available/attention states. |
| Sales / POS / receipt journey | `/sales`, `/commerce` | Fast item and customer selection, cart/totals, reported payment records, confirmation, receipt lookup, returns. Primary actions are blue, positive saved states are green. |
| Customers | `/customers` | Customer identity, purchase/payment history, receivable balance, credit and follow-up context. |
| Suppliers / purchasing | `/purchasing` | Orders, approvals, receipts, supplier bills, returns and balance/payment allocation states. |
| Finance / accounting | `/accounting` | Ledger/accounting summaries, expenses, receivables/payables, payment records, reconciliation and drill-down. |
| Reports / analytics | `/reports` | Period presets, comparisons, source traceability, readable charts, visible data alternatives, explicit currency/scope/freshness. |
| Daily overview / forecasting | `/daily-brief`, `/demand-forecast` | Clear summaries, forecast uncertainty and honest empty/stale state treatment. |
| Intelligence / AI | `/intelligence`, `/ai-assistant` | Source-grounded, read-only explanation surfaces, clear evidence/context, privacy and processing states. |
| Documents / compliance | `/documents`, `/compliance` | File selection/review, manual fiscal references, clear distinction between uploaded records and externally verified documents. |
| Team collaboration | `/team-chat` | Consistent chat panel/message/composer hierarchy and mobile behaviour. |
| Business/admin/security | `/administration`, `/administration/members`, `/settings`, `/settings/security`, `/workspace` | Setup, membership and role states, account protections, predictable forms, explicit action feedback. |
| Authentication/onboarding | `/login`, `/register`, `/onboarding`, `/forgot-password`, `/reset-password`, `/invite` where present | Master brand, readable forms, accessible focus, recovery and error states. |

## Dashboard and chart contract

- Keep sales revenue separate from payments recorded/collected. A later payment must not create another sale.
- Use a line chart for time series and bars for categorical comparisons, with distinct, consistent series styling (blue solid sales; teal dashed payment series where both appear).
- Provide an accessible chart label/description and a tabular data alternative. The underlying chart must use saved API figures; no invented sample values are added to live dashboards.
- Keep missing dates blank rather than drawing them as zero activity. Do not silently convert unknown money/currency to UGX.
- Dashboard KPIs and date controls must be responsive and readable on narrow Android screens; charts use one-column layouts at tablet/mobile widths, with horizontal scrolling for dense data tables only where needed.
- All period/filter controls keep their semantics from the existing shared date/report implementation. This CSS overlay does not alter transaction dates, accounting bases, time-zone rules or report queries.

## Workflow/status contract

- Product catalogue identifies items; inventory movements remain the source of stock history.
- Sales, payment, reconciliation and fiscal-document statuses are separate and must keep explicit text labels; colour only reinforces the label.
- Purchase orders are not receipts; bills must not imply stock was received twice; payment-method labels are records, not payment processing.
- Receivables/payables are shown from authoritative saved records and allocations, not invented balances.
- LEXA's internal receipt is not represented as an official EFRIS fiscal receipt. Tax/official-document screens must not suggest an external submission or verification happened when it did not.
- AI surfaces stay read-only and source-grounded. Styling does not grant access or replace server permission checks.

## Accessibility, mobile and low-bandwidth rules

This implementation emphasises visible keyboard focus, consistent repeated navigation, compact/mobile layouts, touch-friendly navigation, `prefers-reduced-motion`, semantic chart labels and data tables, and readable status labels. It is aligned with principles in [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) and the [U.S. Web Design System data visualisation guidance](https://designsystem.digital.gov/components/data-visualizations/), especially distinguishable series, plain-language context and a non-visual alternative to charts.

## Verification level

The source package includes a regression contract for the canonical assets, module route coverage, responsive breakpoints, shared table/form/status treatments and chart data alternative. ZIP integrity and static CSS/test syntax checks are a pre-upload gate only. GitHub full CI, TypeScript, Next.js production build, mobile/browser inspection, and deployed SHA/URL verification must pass after the source overlay is extracted and committed. No production readiness claim follows from CSS tests alone.
