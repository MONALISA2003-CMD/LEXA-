# LEXA Phase 1 database evidence

**Checked:** 24 October 2026. **Scope:** read-only production audit and non-production replay validation.

## Production: `lexa-live`

- Neon project: `wispy-mud-75323042`
- Branch: `br-soft-star-b1dj2m2w`
- Public base tables: 130
- Tables with RLS enabled: 130
- Tables with FORCE ROW LEVEL SECURITY: 130
- Latest recorded migration: `044_phase3_password_reset_security`
- Migration versions `045_intelligence_foundation`, `046_intelligence_documents`, and `047_analytics_forecast_history_backfill`: absent from the production ledger
- Tenant count: 7
- Sales, payments, inventory transactions, journal entries, analytics refresh runs, daily business metric rows, and product metric rows: all 0
- EFRIS configuration rows: 2
- Fiscal document rows: 0

No production writes or schema changes were made.

## Non-production replay: `lexa-phase3-security-replay-20261021`

- Neon project: `wispy-mud-75323042`
- Branch: `br-dark-breeze-b1mgcaxj`
- Applied migrations 029 variants, 030, 031 and 033–044 using source SQL in per-migration transactions. Migration 038's concurrent index statements were run individually outside a transaction.
- Final public base tables: 134
- RLS enabled and forced: 134 / 134
- All 130 production table names are present, plus `intelligence_jobs`, `intelligence_runs`, `intelligence_documents`, and `intelligence_document_reviews`.
- Latest migration entries include 045–047. Two recent successful 56-day refresh runs covered 30 August 2026 through 24 October 2026 for two active test tenants. `refresh_analytics_forecast_baselines(1)` returned `processed_count=0, failed_count=0` on the final check because no tenant needed a new window.
- Daily business and product-daily metrics both remained empty. Window coverage is not equivalent to demand history or forecast readiness.

## Release interpretation

This is not proof of a clean chronological replay from an empty database. The replay branch originally had the intelligence migrations before the missing earlier migrations were reconciled, and the Neon project currently rejects new branch creation due its branch limit. Use a newly available disposable branch for a complete ordered replay before any production migration rollout.
