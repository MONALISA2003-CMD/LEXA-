# LEXA Master Brand and Whole-Product UI System

**Status:** Implementation overlay prepared for the canonical `apps/web` source.  
**Brand source of truth:** supplied LEXA master artwork with multicolour geometric wordmark and gold descriptor.  
**Scope:** shared application shell, authentication, all operation modules, dashboards, charts, tables, forms, responsive layouts, empty/error/loading states.

## 1. Brand authority

The master LEXA artwork defines the logo, tone, and visual direction. The old green checkmark treatment must not compete with it as a separate brand. Derivatives are limited to (1) full master artwork, (2) horizontal wordmark, and (3) compact `L` mark derived from the source image. Preserve proportions. Do not recolour or stretch the master asset.

## 2. Token contract

| Token | Value | Intended meaning |
|---|---|---|
| Midnight navy | `#010D27` | Structural frame, sidebar, authentication brand surface |
| Blue | `#075FE8` | Primary actions, navigation, net-sales series, links |
| Cyan | `#01B9BB` | Secondary interaction and collected-payments series |
| Green | `#00B77D` / `#087F5B` | Positive outcomes and completed states |
| Gold | `#E1C140` | Signature accent, selected highlights, caution emphasis |
| Red | `#E91D3A` | Critical errors and destructive actions |
| Canvas | `#F5F8FC` | Neutral workspace background |
| Surface | `#FFFFFF` | Cards, forms, reports and dense data regions |
| Border | `#DFE7F0` | Quiet grouping and table boundaries |

The logo is intentionally multicolour. The UI is not: use one primary action colour and reserve the remaining palette for its agreed meaning. Keep financial numbers on high-contrast solid surfaces.

## 3. Whole-app coverage map

- **Application frame:** sidebar, top bar, mobile brand lockup, global navigation, workspace selection, global search, quick navigation and focus states.
- **Authentication:** sign-in, registration, onboarding, invitation acceptance, forgot/reset password, sessions and security.
- **Daily operations:** Home, Sales, Checkout/Closing, Inventory, Products, Customers, Purchasing, approval limits and purchasing reconciliation.
- **Money and analysis:** Finance/Accounting, Reports, Daily overview, Sales forecast and Intelligence.
- **Collaboration and records:** Business Assistant, Team Chat, Documents, Tax/official receipts, Business administration, Members/roles, Workspace and Settings.
- **Nested workflows:** every route inherits the same tokens, table/form/button/state rules; CSS-module screens receive explicit brand treatments.

## 4. Dashboard and chart rules

- Prioritise business-day KPIs and actionable exceptions before secondary detail. Keep periods and business dates visible.
- A KPI is a card with a clear label, legible tabular-number value, short meaning/context, and an accurate loading/error state. Never substitute unavailable data with zero.
- Use the existing API-sourced time-series for net sales (blue) and payments collected (cyan). Preserve the gap between sales and receipts; they are not interchangeable measures.
- Use a restrained grid, visible labels, a short legend, responsive sizing and an expandable daily figures table. Missing dates remain gaps, not zeros.
- Use horizontal bars for ranked product, expense, payment, customer-balance, location and branch comparisons. Label the measure and use separate consistent colours by chart meaning; avoid decorative rainbow fills inside one series.
- Keep chart details horizontally scrollable when a comparison table cannot fit on a narrow screen. Do not rely on colour alone; include a legend, labels and data table.

## 5. Layout and interaction rules

- Use a neutral canvas, white surfaces, consistent border, radius, shadow and spacing.
- Use consistent page title, eyebrow, explanatory copy, primary action and section heading hierarchy.
- Keep forms and tables aligned across modules. Use visible focus rings, 44px comfortable touch targets where practical, safe-area padding and no horizontal page overflow.
- On phones, the four main home KPIs become a 2×2 arrangement where content fits; very narrow screens fall back to one column. Analytical grids stack and charts retain readable labels.
- Respect `prefers-reduced-motion`. Loading, error, empty and permission states must remain distinct and explain the next safe action.
- Keep existing auth, tenant/branch access, API contracts, money logic and records unchanged. This is a frontend presentation overlay only.

## 6. Research principles incorporated

- [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/): contrast, visible focus, non-text contrast, target size and unobscured focus considerations.
- [U.S. Web Design System — Data visualizations](https://designsystem.digital.gov/components/data-visualizations/): simple familiar chart types, restrained concepts, accessible descriptions and careful colour use.
- [Michelin Design System — Dashboard principles](https://designsystem.michelin.com/data-visualization/design-guidelines/principles-of-a-dashboard): clear titles/labels, consistent backgrounds, white chart surfaces, meaningful chart choice and predictable visual hierarchy.
- [Nielsen Norman Group — Data Tables: Four Major User Tasks](https://www.nngroup.com/articles/data-tables/): support finding records, comparing data, inspecting/editing a row and taking record actions.

## 7. Changed source files in this overlay

- `apps/web/app/layout.tsx` — preserves SVG mark in metadata and sets the master brand description/metadata.
- `apps/web/app/lexa-brand-authority.css` — expands the shared design system across global and CSS-module UI, responsive dashboards and charts.
- `apps/web/tests/phase8-foundation-polish.test.mjs` — updates old brand assertions to the new master brand and keeps the existing navigation/workflow assertions.
- `apps/web/tests/phase11-master-brand-dashboard.test.mjs` — new contract checks for assets, tokens, chart semantics, module coverage and responsive/accessibility states.
- `apps/web/public/*` — reuses the official master assets already extracted into `main`.

The archive also includes exact unmodified marker files at `apps/web/package.json`, `apps/api/app/main.py`, and `migrations/001_phase1_foundation.sql` so the repository's ZIP extraction workflow recognises it. Those markers are not functional changes.

## 8. Verification boundary

This package can be inspected and contract-checked as an overlay. After upload, GitHub Actions must run the whole frontend test suite, TypeScript check and Next.js production build; Vercel then needs a visual check at the canonical production URL on desktop and a mobile viewport. Do not call production visually verified until that review is complete.
