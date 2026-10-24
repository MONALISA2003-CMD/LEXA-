# LEXA implementation and release plan

## Phase 1 — Business-grounded assistant

The source overlay answers supported factual questions from LEXA's saved metrics, with tenant/branch authorization, freshness checks, explicit provenance, response timing and evidence links. General advice remains on the central privacy/policy route; model calls do not receive saved business records and cannot perform writes.

## Phase 2 — Cross-module transaction acceptance (implemented, validation pending)

This bundle adds a tenant- and branch-scoped, read-only sale evidence endpoint plus a staging-only browser acceptance scenario. The scenario checks one completed sale across catalog, inventory ledger and weighted-average cost, revenue/tax and COGS journals, partial payment/receivable, idempotent receivable settlement, audit/outbox metadata, and refreshed daily insight metrics. It retries a sale using the same idempotency key and asserts no duplicate sale is created.

Phase 2 uses existing business tables and requires **no new database migration**. The browser scenario is skipped by default; writes are permitted only after explicit staging hostname allow-list, HTTPS, a pre-provisioned disposable fixture, dedicated QA storage state, and a ready staging API/database/cache check. The test never creates or deletes a tenant and must not be pointed at production. See `PHASE2_STAGING_ACCEPTANCE.md` for fixture fields and execution gates.

Additional return/refund caps and role-based denials remain covered by the repository's existing Phase 5 acceptance suite. Phase 2's authenticated staging journey itself has not run without the staging fixture and QA session.

## Phase 3 — Uganda tax calculations and manual-only compliance

Do not build paid URA EFRIS, mobile-money, or payment-gateway integrations. LEXA only records payment method/amount/reference as business records; it never collects or transfers funds, polls provider status, or stores provider credentials. Official fiscal documents are obtained through URA separately and can be added as manual, unverified references in LEXA. The fiscalise endpoint is blocked and the EFRIS config endpoint rejects system-to-system mode.

Local Python/Decimal calculators cover VAT (18% inclusive/exclusive with an owner-selected applicable rule), the October 2026 presumptive-tax bands, resident and non-resident monthly PAYE schedules, and conditional withholding estimates. The server resolves saved effective-dated tax rules at checkout. A standard-rate VAT default is activated only after an owner confirms legal applicability and selects the correct inclusive/exclusive price treatment. Zero-rated and exempt supplies must not be conflated. The October URA FAQ (UGX 300m threshold) and Government of Uganda VAT page (UGX 250m) disagree; LEXA surfaces the conflict and does not infer VAT registration from turnover. See `PHASE3_URA_AND_MOBILE_MONEY_INTEGRATION_GATES.md` for official sources and safeguards.

## Phase 4 — Better grounded intelligence

Expand the fixed read-only query catalogue to authorized customer balances and supplier obligations after currency, scope, freshness and permission contracts are tested. Add deterministic daily-brief evidence links and safe explanation of inventory age/replenishment. Do not add arbitrary SQL, external data sharing, model-generated transactions or automatic purchasing.

## Cross-cutting exit criteria

- The full API suite, Node 24 contract suite, TypeScript typecheck and Next.js production build pass on the **same exact commit**.
- Authenticated staging end-to-end acceptance passes against a disposable tenant; relevant branch/role denials also pass.
- Ordered clean migration replay, forced RLS verification and tenant/branch negative tests pass.
- Staging frontend and API are deployed on one SHA; deployment is not inferred from source extraction or a successful Vercel preview alone.
- Production changes only after migration review, backup/rollback readiness and explicit release approval.

## CI failure follow-up

The previously inspected failed run (`40100560783`, old SHA `d5be996d8cf45c93200351c6a21251c4d3a6c934`) had three frontend copy-contract failures and two stale API expectations. The current canonical `main` source contains corrections for those expectations, but a fresh successful CI on the resulting source SHA was not verified during preparation of this bundle. Upload this archive at repository root through LEXA ZIP Extractor, verify the extractor-generated commit changed canonical `apps/` paths, and confirm the triggered `LEXA Main Build CI` is green before calling the workflows fixed.
