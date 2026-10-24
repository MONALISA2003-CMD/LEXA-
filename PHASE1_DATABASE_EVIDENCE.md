# LEXA Phase 1 — Production database evidence

**Checked:** 24 October 2026.  
**Production project:** Neon `wispy-mud-75323042`  
**Production branch:** `lexa-live` (`br-soft-star-b1dj2m2w`)  
**Database:** `neondb`

## Additive migrations already applied

Following a read-only preflight, the exact canonical migrations were applied in order, each in its own transaction:

1. `045_intelligence_foundation`
2. `046_intelligence_documents`
3. `047_analytics_forecast_history_backfill`

The preflight verified the required tenants, branches, users, permissions, role-permission map, schema ledger, `lexa_app`, `lexa_can_access_branch(uuid)`, `refresh_analytics(uuid,date,date)`, and `lexa_business_date(timestamptz,uuid)` objects. Before applying, migrations 045–047 and their main tables/function were absent. After applying, all three migration versions were present and `refresh_analytics_forecast_baselines(integer)` was callable.

**Do not rerun these migrations.** Deployment of the source overlay is a separate step. Keep the migration ledger and schema aligned, and do not add a new migration merely to repeat these changes.

## Post-migration schema and access checks

- Public base tables: **134**.
- Tables with RLS enabled: **134 / 134**.
- Tables with `FORCE ROW LEVEL SECURITY`: **134 / 134**.
- Added tables: `intelligence_jobs`, `intelligence_runs`, `intelligence_documents`, `intelligence_document_reviews`.
- All four new tables contained **0 rows** immediately after migration.
- Tenant/branch policies were found for the intelligence job/run and document/review tables. Document policies target `lexa_app`; the policy predicates enforce tenant and branch scope.

## Analytics refresh proof

`SELECT * FROM public.refresh_analytics_forecast_baselines(1)` was invoked in a bounded batch loop. Calls reported `processed_count=1, failed_count=0` until the final call returned `processed_count=0, failed_count=0`.

Read-only verification then found **7 successful, fresh complete 56-day windows for 7 active tenants**, from **30 August 2026** through **24 October 2026**, each completed within the configured 72-hour freshness window.

## Business data is still empty

Verified post-refresh counts remain zero for sales, payments, inventory transactions, journal entries, daily business metrics, and product daily metrics. Fiscal-document records are also zero. The seven coverage runs prove date-window refresh coverage only; they do not create sales history, cash activity or forecastable demand.

No sales, payments, inventory movements, journal entries or fiscal documents were inserted or modified by this work. The only production database writes were the three additive schema migrations and their ledger rows, plus the bounded analytics refresh-run/projection process.

## Release boundary

This is direct production migration evidence. It is not a clean chronological replay from an empty database and is not a substitute for CI or an authenticated smoke test. The current source overlay remains uncommitted/un-deployed at the point this report was generated. A canonical extractor commit, green Main Build CI, TypeScript/Next.js build, same-SHA Render/Vercel deployment and authenticated assistant verification remain required.
