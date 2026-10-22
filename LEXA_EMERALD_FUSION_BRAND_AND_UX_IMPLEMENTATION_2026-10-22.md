# LEXA Emerald Fusion — Brand and UX Implementation

**Date:** 22 October 2026  
**Status:** Implemented in the source candidate; not yet published to the live site.

## Brand direction

LEXA now uses **Emerald Fusion**: a fresh, confident palette intended to make the product more recognizable while preserving readability for finance and daily operations.

| Use | Colour | Hex |
|---|---|---|
| Primary brand | Emerald | `#10B981` |
| Supporting brand | Teal | `#13B8B0` |
| Interactive accent and chart series | Electric blue | `#496CFF` |
| Positive highlight / progress | Sunshine | `#FFC857` |
| Headings and dark surfaces | Deep navy | `#13233F` |
| Page background | Cool pale grey | `#F5F8FC` |

### Logo

The new logo is a vector mark: a rounded gradient tile with a clear check/forward motion and a small sunshine accent, paired with a strong LEXA wordmark. It represents clear action, confidence and progress. SVG is the primary scalable artwork; PNG assets are regenerated from the vector source.

Assets in `apps/web/public/`:

- `lexa-mark.svg` — icon mark used by the app shell and favicon.
- `lexa-logo.svg` — dark wordmark for light surfaces.
- `lexa-logo-light.svg` — white wordmark for dark surfaces.
- `lexa-icon-32.png`, `lexa-icon-180.png`, `lexa-icon.png` — browser and app icons.
- `lexa-logo.png`, `lexa-logo-light.png`, `lexa-wordmark.png` — transparent full-logo PNGs.

## Interface changes

- Replaced character-based navigation glyphs with a consistent set of line icons.
- Kept the eight main business areas together: Home, Sales, Stock, Products, Customers, Purchases, Finance and Reports. Business details, setup, team access, tax/receipts and settings remain grouped under Business settings / More.
- Improved the mobile bottom navigation with larger touch targets, a clearer selected state, safe-area spacing and a floating, high-contrast surface.
- Applied Emerald Fusion consistently across navigation selection, buttons, chart series, cards, focus states, setup guidance, authentication accents and product-performance bars.
- Increased mobile content readability, made the dashboard/report layouts stack cleanly, and reduced cramped multi-column layouts on phones.
- Added a clear setup-first state in the application shell. When required business locations are missing, LEXA explains what to do and opens the setup flow instead of mounting every data-heavy page and showing unrelated permission/error cards.
- Made the setup checklist use everyday business language: **Business details**, **Main branch**, **Stock room**, and **Where stock is kept**.
- Simplified visible wording across Sales, Products, Stock, Finance, Purchasing, Reports and setup. User-facing copy avoids database, API, schema, RLS and other implementation terminology.
- Changed the currency-not-set message to **“Business currency not set”** and explicitly labelled product codes so that internal abbreviations are not presented as business language.
- Kept the existing data-source relationships intact. The change does not introduce a second stock, customer-balance, supplier-balance or accounting ledger.

## Dashboard and report behaviour

The candidate retains the existing sales trend and product-performance charts and restyles them using the new palette. Mobile chart/report layouts use a single-column flow, and the screen displays a guided setup state until the business has the required location records. Missing figures are not fabricated as zeroes.

## Payment and privacy boundary

LEXA continues to **record** amounts and the business-selected method (for example, Cash, MTN Line 1, Airtel Line 1 or Stanbic). The new design does not connect to payment gateways or introduce payment credentials.

## Verification

- Frontend contract tests: **51 passed**.
- Backend tests: **125 passed** (one existing Starlette cookie deprecation warning).
- TypeScript/TSX transpilation: **34 files checked, 0 syntax errors**.
- `npm run typecheck`: **blocked by the current environment** because the Node and React type definition packages are unavailable (`TS2688` for `node`, `react` and `react-dom`).
- A full Next.js build / local rendered browser review could not run because the installed `apps/web/node_modules` is incomplete; the `next` executable is absent.

## Live publication and remaining blockers

This package contains the implementation candidate. It has **not** been deployed to `https://lexa-green.vercel.app/`. The connected GitHub write action was previously rejected with `403 Resource not accessible by integration`, so local source changes cannot be represented as live changes until the repository/deployment write path is restored.

The previously observed live database also lagged behind the candidate schema and lacked the supplier billing/ledger structures introduced by migration 039. Migration 039 and Phase 8 migration 040 are included in the source tree but have **not** been applied to production. The existing live error screen will therefore not disappear merely by downloading these files; the updated source must be published and migrations run against the proper environment. Keep the consolidated release-wide production gate in Phase 12, as planned.

## Acceptance criteria before moving to Phase 9

1. Publish this exact source candidate to the connected project and confirm deployment parity.
2. Run migrations 039 and 040 against the intended non-production database, check fresh and existing-workspace setup, and verify supplier bill/payment and finance flows.
3. Complete an authenticated mobile-width walkthrough through Home → Sales/payment recording → Stock → Purchases/receiving → Supplier bills/balances → Finance → Reports.
4. Confirm the app presents setup guidance rather than a wall of 403/empty-data messages, and that real backend faults are translated into understandable user language.
5. Resolve or document full typecheck/build and authenticated journey coverage before the Phase 8 acceptance decision. The final consolidated production/recovery gate remains Phase 12.
