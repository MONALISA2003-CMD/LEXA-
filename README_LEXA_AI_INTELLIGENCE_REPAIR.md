# LEXA Phase 1 — Business-grounded assistant source overlay

This ZIP contains changed files at canonical paths for the existing repository's **LEXA ZIP Extractor**. It is not a full source archive and not an installer. It includes `apps/web/package.json`, `apps/api/app/main.py`, and `migrations/` at the ZIP root so the extractor can recognize the source tree. It does not include workflows, API keys or secrets.

## Phase 1 scope

- Exact factual questions about sales/net sales, recorded payments, recorded expenses, gross margin and current stock-health exceptions are answered from LEXA's own tenant-scoped projection data, not inferred by a model.
- Read paths require permission, full authorized branch scope and an appropriate fresh successful analytics refresh; stock-health questions additionally require a fresh stock-health snapshot.
- Answers include the data source, reporting period, latest refresh, status, response latency and a link to the corresponding LEXA screen.
- Missing or stale figures remain unavailable. The assistant does not silently treat absent rows, failed refreshes or missing amounts as zero.
- General advice continues to use the central Gemini/Groq question-only route with the current provider allowlist, short timeout and shared authenticated rate limiter. Only the screened question is sent; saved business summaries and customer data remain excluded. No automatic paid-provider fallback or business writes are added.
- The UI distinguishes locally sourced business figures, general guidance and unverifiable/missing saved data; it does not show model/provider selection to business users.
- Compliance copy and tax setup test contracts are aligned with the current URA/EFRIS language. This does not create a URA connection or self-activate fiscalisation.

## Database state — updated 24 October 2026

Production Neon `lexa-live` (`br-soft-star-b1dj2m2w`) now has migrations `045_intelligence_foundation`, `046_intelligence_documents`, and `047_analytics_forecast_history_backfill` applied. The migration set was applied in order after a prerequisite check and verified after execution. **Do not rerun these migrations.** See `PHASE1_DATABASE_EVIDENCE.md` for the exact checks.

Production now has 134 public tables and RLS enabled and forced on all 134. Seven fresh, successful 56-day refresh windows cover 30 August–24 October 2026 for seven active tenants. Recorded sales, payments, inventory transactions, journal entries and daily/product metrics remain empty, so LEXA correctly cannot produce real demand forecasts from this database yet.

## Deployment/CI truth

The source overlay is **not yet deployed**. Render's LEXA API was last verified live on canonical SHA `d5be996d8cf45c93200351c6a21251c4d3a6c934`. Vercel had a later `READY` deployment on SHA `e44b70d03b9863428b8bb37a07188932a5359380`, but that came from a ZIP uploaded under `source/` rather than a canonical source update. The latest Main Build CI inspected on the canonical `d5be996...` source was red at run `40100560783` (three stale frontend contracts, two stale API expectations). Do not report this overlay or current canonical CI as green before a subsequent extraction, build and deployment are inspected.

## Install

1. Upload this ZIP at the repository root using the existing **LEXA ZIP Extractor**.
2. Confirm it writes changed files under canonical `apps/api/...` and `apps/web/...` paths, not only a nested `source/` folder.
3. Run `LEXA Main Build CI` on the new extractor-generated commit. Require frontend contracts, API tests, Node 24 typecheck and production frontend build to pass.
4. Verify Render and Vercel run the same validated SHA. Test the signed-in assistant using a controlled workspace with seeded synthetic transactions; confirm data source, date window, permissions, tenant/branch isolation, timeout and missing/stale paths.

## Validation performed for this overlay

Python compilation passed for changed API modules/tests. New Node contract tests and provider/URA contract tests passed in focused runs. TypeScript/TSX syntax transpilation had no syntax diagnostics. Pure intent/date/Decimal smoke checks covered factual question routing and ensured missing values do not become zero. The **full canonical API suite, complete Node 24 suite, full typecheck and Next.js production build have not yet been run against this overlay**. The repository CI after extraction remains the release gate.
