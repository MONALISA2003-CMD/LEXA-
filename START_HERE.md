# LEXA Phase 1 — Start Here

**Package date:** 24 October 2026  
**Goal:** Add source-grounded, tenant-safe answers to LEXA's business assistant and report source evidence in the UI, while keeping general advice behind the central Gemini/Groq question-only policy.

## Important: backend, database and frontend status

### Production database

Migrations **045**, **046**, and **047** have already been applied to Neon production branch `lexa-live` (`br-soft-star-b1dj2m2w`) in that order. **Do not rerun them.** The live database was verified at 134 public tables, with RLS enabled and forced on all 134. The new intelligence/document tables are empty. The bounded `refresh_analytics_forecast_baselines(1)` was run until it reported no remaining work. Seven fresh 56-day windows now cover 30 August through 24 October 2026, one per active tenant.

The business data itself remains empty: there are still no recorded sales, payments, inventory movements, journal entries, or daily/product analytics metrics. The refresh coverage does **not** imply there is demand data or that forecasts are available. Do not manufacture data or present missing figures as zero.

### Source and deployments

The files in this ZIP are a **canonical-path source overlay**, not a full application archive. Production source changes in this ZIP have not yet been extracted/deployed. At the last audit, Render's API was live on `d5be996d8cf45c93200351c6a21251c4d3a6c934`; Vercel showed a later ready deployment on `e44b70d03b9863428b8bb37a07188932a5359380`, which came from a Phase 0 ZIP upload that was stored under `source/` and did not update the canonical root source files. The latest main-build CI seen for canonical source SHA `d5be996...` was red (`40100560783`). Do not state that this overlay is deployed or the canonical build is green until a new extractor commit, CI and same-SHA hosting deployment are checked.

## Install this overlay

1. Upload this ZIP at the **repository root** of `MONALISA2003-CMD/LEXA-` using the existing **LEXA ZIP Extractor**.
2. Do not put it under `.github/workflows/` and do not unpack it into a new enclosing project folder. The archive contains `apps/`, `migrations/`, and documentation at its root.
3. Verify the extractor generated a commit containing the files at canonical root paths `apps/api/...` and `apps/web/...`, not only under `source/`.
4. Rerun **LEXA Main Build CI** on the resulting SHA. The last known canonical CI failed on three outdated frontend contract checks and two outdated API expectations; this overlay updates their source/test contracts. Wait for all frontend contracts, API tests, typecheck, and production build to pass.
5. Verify Render and Vercel build/deploy that **same validated SHA**. Then test signed-in assistant queries on a non-sensitive workspace with actual seeded test data and confirm answer source mode, response timing, permission denial and unavailable/stale states.

## What Phase 1 adds

- Locally answered exact sales, payments, recorded expenses, gross-margin, and stock-health questions read LEXA's own tenant-scoped analytics projections.
- Full branch authorization and freshness/coverage checks are required before figures are returned.
- Responses include source mode, response time, date range, last refresh and an in-app evidence link.
- Missing, stale, or absent figures produce an explicit unavailable response rather than a fabricated zero.
- General business advice remains routed through the central provider policy. Only the screened question is sent externally; saved business records, tenant IDs, customer data and business figures are not appended to the provider prompt.
- No AI-triggered sales, accounting, stock, payment, tax, or fiscal-document writes are added.

## Validation boundaries

Static checks performed for this overlay include Python compilation, Node test syntax, a focused business-grounding Node contract, TypeScript/TSX syntax transpilation, and local pure-function intent/formatting smoke checks. The **full canonical API suite, full Node 24 contract suite, full TypeScript typecheck, and Next.js production build have not yet been run against this complete overlay**. GitHub CI after canonical extraction remains the authority.
