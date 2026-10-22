# LEXA Stage 4 + Stage 5 Reporting and Acceptance Handoff

**Candidate date:** 2026-10-22  
**Status:** Source candidate and assembled archive pass the available automated source-level checks. Full Stage 5 acceptance is **not yet complete** because the clean PostgreSQL replay, Node 24 build/typecheck and authenticated browser journeys have not run in their required environments. No production database or live deployment was changed by this work.

## Stage 4 — Reports people can trust

The agreed design is: Home is a compact business overview with a small finance summary; Finance has the detailed money workflows; Reports contains the deeper visual analysis. All amounts must use the saved business currency, and a missing/failed data request must never be displayed as a zero.

### Implemented in the candidate

- Common date presets: Today, Last 7 days, Last 30 days, This month and Last 90 days, plus manual start/end dates and validation.
- Independent loading/error/empty states for reports. A failing panel does not hide other successful panels; the UI distinguishes unavailable information from a real empty result.
- Sales trend, sales by location, money recorded by payment method, expenses by category, best-selling products, customer outstanding balances, stock value by location and current-stock views.
- Tables with exact values accompany the charts, including a dedicated stock-value-by-location table. Charts retain accessible labels and record links.
- Drill-through links from report rows/charts into date-filtered sales history, payment-method-filtered sales history, product search, customer detail, expense history and stock by location.
- CSV export uses the actual loaded panels, includes a per-section availability row and formula-injection-safe text cells. The export now distinguishes the selected date range from all-date customer balances and current stock snapshots.
- Payment reports describe provider payments as **recorded entries only**. LEXA does not process, transfer, or independently verify funds, and no provider credentials are needed.
- A read-only browser acceptance spec covers reports, common date presets, CSV download, mobile overflow, main module headings, runtime errors and report-to-record links. It requires an explicit allow-listed staging host and QA authentication state.

### Reporting definitions worth preserving

- **Sales after returns** is not the same metric as money received.
- **Money recorded** is the sum of customer payments entered in LEXA, not a bank/mobile-money confirmation.
- **Customer balances** and **stock on hand/value** are current/all-date views unless a report says otherwise; the selected sales date range does not rewrite those snapshots.
- **Stock value** is a stock-cost valuation, not revenue or cash.
- **Profit after product cost** is not full net profit; it does not automatically subtract rent, wages or other operating costs.
- If a report panel fails, export must label it unavailable rather than silently inventing zero values.

## Stage 5 — Acceptance, not just attractive screens

### Implemented in the candidate

- The canonical clean-replay manifest now contains 44 ordered SQL migration inputs through `migrations/040_phase8_finance_workflows.sql`.
- The replay planner verifies each input path and SHA-256 before it can be considered for execution.
- `scripts/run_clean_migration_replay.py --plan-only` is the default and opens no database connection. `--apply` requires explicit opt-in, a loopback database host, a database name explicitly indicating replay/test/CI, and an empty public schema.
- Replay postconditions check tenant Row-Level Security and cross-tenant read/write isolation, the Phase 5 return/accounting routines, Phase 6 stock indexes, Phase 7 supplier ledger schema/grants, and Phase 8 expense correction fields, tenant-safe journal reference, posting routine and reporting metric.
- The evidence checker now requires the Phase 8 postconditions as well as exact migration-input hashes and an immutable source commit.
- The acceptance runner includes opt-in Stage 4 read-only browser checks and separate Stage 5 sales and Stage 7 purchasing staging-write suites. Write journeys remain disabled unless a disposable fixture, authenticated QA state, staging host allow-list and explicit opt-in are provided.
- Automated source-level regression tests cover reports, filters, accessibility contracts, CSV export safety, the migration manifest and replay evidence requirements.

### Verification completed in this environment

- Python backend/test suite: **262 passed** (one existing Starlette deprecation warning).
- Frontend Node contract suite: **53 passed**.
- Python source compilation: passed.
- TypeScript/TSX syntax transpilation: **35 files, 0 syntax errors**.
- Migration plan/hash validation: **44 inputs pass**. Bundle SHA-256: `15555832b8153b52f412937de6f153e96afb1c6f6187a15b487b5e874ed5ae46`.
- Bash syntax validation for `scripts/run_stage4_stage5_acceptance.sh`: passed.
- Packaged ZIP validation: archive CRC passed; the extracted 409-file package re-ran with **262 backend tests passed**, **53 frontend contract tests passed**, and the 44-input migration plan/hash check passed.

### Still blocked / not run

1. **Full frontend typecheck/build:** environment has Node `v22.16.0`, while the app is configured for Node 24; dependency installation (`npm ci`) and the Next.js typecheck/build were not performed here.
2. **Actual PostgreSQL clean replay:** no local PostgreSQL server/`psql` client is available, so the 44-step sequence was validated in plan-only mode, not executed. The replay must run on a new, local/CI disposable database after the required six reconstructed-equivalent historical replacements receive semantic validation. Do not point this runner at Neon or production.
3. **Authenticated browser journeys:** not run because a Node 24 dependency environment, QA authentication state and allow-listed staging environment were not available. The gated suites are included for the appropriate environment.
4. **Live deployment:** this candidate has not been pushed or deployed. The connected GitHub API returned 403 for write operations earlier. Vercel's current public deployment and Render's API deployment need to be aligned to the same canonical source commit.
5. **Live database alignment:** earlier investigation found the inspected live database behind supplier-billing/Phase 8 schema expectations. Do not run migrations against production before the clean replay, migration review, backup/recovery plan and explicit approval.

## Run the acceptance runner

From the source root:

```bash
bash scripts/run_stage4_stage5_acceptance.sh
```

To require every environment-dependent acceptance gate rather than allowing safe skips, set `LEXA_REQUIRE_FULL_ACCEPTANCE=1`. The run will stop if Node 24, disposable PostgreSQL, immutable source SHA, or the opt-in authenticated staging setups are missing.

Never commit Playwright storage state, real `.env` files, provider secrets or production credentials. Browser write journeys must use disposable staging fixtures and isolated test accounts.

## Research basis used for the reporting/acceptance design

Checked against the official guidance on 22 October 2026:

- [Texas Department of Insurance data-visualization guide](https://www.tdi.texas.gov/styleguide/style-guide-for-data-visualization-tools.html) recommends choosing a visual for the user's task, keeping filters and reporting context visible, and pairing charts with exact-value tables and accessible text alternatives. This informed the report layout: line charts for trends, bars for comparisons, clear date ranges, tables and a separate stock-value table.
- [W3C Web Content Accessibility Guidelines (WCAG) 2.2](https://www.w3.org/TR/WCAG22/) is the accessibility reference for visible focus, perceivable contrast, keyboard interaction and understandable labels. Source-level checks cover selected accessibility contracts, but do not establish full WCAG conformance; that still needs browser/manual review.
- [Playwright authentication guidance](https://playwright.dev/docs/auth) warns that saved browser state can contain cookies and headers capable of impersonating an account and should not be committed. The acceptance lanes therefore take authenticated state from local environment configuration and keep staging writes explicitly opt-in.
- [Render monorepo support](https://render.com/docs/monorepo-support) states that a service's root directory controls which repository files are available at build/runtime and affects automatic deploy triggers. [Vercel monorepo guidance](https://vercel.com/docs/monorepos) likewise documents project root/build configuration. These references inform the final requirement to verify that both services build from the same intended canonical source and correct roots before release.

These references inform implementation choices; they do not substitute for the unrun full browser accessibility pass, a clean database replay, or live deployment/source-parity verification.

## Acceptance decision

**Stage 4 is implemented in the source candidate, but Stage 5 is not accepted yet.** Acceptance requires the clean replay (including migration 040) and evidence checker, full Node 24 typecheck/build, authenticated read-only report/module journeys, and the scoped sales and purchasing workflows on staging. Only after this should Phase 8 be considered for sign-off. Phase 9 AI remains on hold; the full release/rollback gate remains Stage/Phase 12.
