# LEXA Render runtime audit — 2026-10-20

## Scope and safety

Read-only inspection of Render workspace **My Workspace**. No service settings, deployments, source branches, credentials, or databases were changed. Findings below are from Render's service metadata, deploy history, application logs, and metrics; a direct HTTP probe from the audit execution environment was blocked by local DNS resolution failure, so it is not used as evidence of service availability.

## Service/deploy status

- Service: `LEXA` (`srv-dakm8k95efls73egg9a0`), URL `https://lexa-n10e.onrender.com`.
- Source: `MONALISA2003-CMD/LEXA-`, branch `main`, root directory `apps/api`, Python/Uvicorn, Frankfurt region, Free plan; auto-deploy is enabled.
- Latest listed deploy: `dep-dbbgra1srm7s7386q0l0`, commit `a1ed64eec79daf3d74456c7b8b854d84f634d6fd`; build ended successfully at `2026-10-20T06:44:18Z`, deploy ended successfully at `2026-10-20T06:45:11Z`; Render reports deploy status `live`.
- `healthCheckPath` is empty. Application logs recorded `GET /ready` with HTTP 200 at `2026-10-20T07:01:36Z`, and `/health` with HTTP 200 at `2026-10-20T06:58:31Z`. Set the configured health path to `/ready` only through the approved service-configuration/release process; no setting change was made during this audit.
- No `server_failed` event appeared in the recent event page, and recent build/deploy events succeeded. These signals do not establish application-level correctness.

## Confirmed runtime defect and candidate correction

At `2026-10-20T07:01:40.546Z`, the logs show an unhandled exception in `apps/api/app/routes/finance.py` inside `journal_entries`. The failing request was:

`GET /api/v1/accounting/journal-entries`

It returned HTTP 500. The query uses `FROM journal_entries WHERE tenant_id=:t AND (:s IS NULL OR status=:s)` with `s=None`. PostgreSQL raised `psycopg.errors.AmbiguousParameter: could not determine data type of parameter $2`. The optional parameter has a null-test predicate without a type inference path accepted by the deployed query plan.

The source-only candidate changes this to build the tenant-scoped query first and append `AND status=:s` only if `status is not None`, keeping the value parameterized. A source sweep also found the same risky predicate in `/api/v1/compliance/fiscal-documents`; the candidate now applies the same conditional `AND status=:s` parameterized filter there as a precaution, although no runtime failure trace for that route was returned. Python source-contract tests cover both optional filters and verify the journal-entry branch guard remains in place. Latest package validation: **46 Python tests passed**, **8 Node contract tests passed**, Python compileall and the isolated TypeScript fixture check passed. This correction has **not** been pushed, merged, or deployed, so the production endpoint remains unverified/failing for the omitted-status case until a reviewed release.

## Historical commerce-dashboard exception

Earlier logs (2026-10-15 and 2026-10-20 04:38–04:39Z) show `GET /api/v1/commerce/dashboard` returning HTTP 500. The exception came from `out(row)` trying to access `row._mapping` on a SQLAlchemy `RowMapping`, raising `AttributeError: Could not locate column in row for column '_mapping'`. The currently inspected GitHub/default-branch source and candidate serializer support both `Mapping` and `Row._mapping`; no later occurrence of the same stack was returned by the queried recent log set. Treat this as a previous runtime defect whose source fix is present, pending a post-release authenticated smoke test of the dashboard.

## Other observations and limitations

- The latest runtime log query included successful responses for `/ready`, `/health`, `/api/v1/accounting/accounts`, `/api/v1/accounting/balance-sheet`, inventory reads, authentication refresh, and other API calls.
- The filtered Render request-log query returned no 5xx entries, but the failed endpoint responses were plainly present as application-log stack traces and final `500 Internal Server Error` lines. Application logs, not the request-log filter, supplied the defect evidence.
- Process shutdown/startup messages were observed on the Free plan. No failure event was recorded in the recent event page; this alone is not enough to diagnose an outage or classify those cycles as errors.
- Metrics included memory around 104–108 MB and low observed CPU points; Render HTTP request count/latency metrics were empty in this query, so no performance conclusion is drawn.
- Direct external probes for `/`, `/ready`, `/health`, and `/openapi.json` from the audit environment failed before HTTP because DNS resolution was unavailable there. Do not interpret that as Render being down.
- The Render fix, health-check path, broader authenticated API/browser acceptance, and complete release readiness remain open. This source-only package does not certify Phase 3 or Phase 4 readiness.
