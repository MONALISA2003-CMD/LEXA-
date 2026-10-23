# LEXA Phase 2 — request and database timing

## What this increment changes

- API responses retain `X-Request-ID` and now expose an `api` metric plus aggregate `db` cursor-execution time and query count when at least one SQL statement ran.
- Slow HTTP requests (default 500 ms) include route path, method, status, request ID, aggregate database execution time, statement count, and count of slow statements.
- Slow SQL statements (default 250 ms) include only request ID, operation category, elapsed time, and the `executemany` flag. The SQL text, table names, bind values, request body, query string, and business/tenant data are deliberately omitted.
- `LEXA_SLOW_REQUEST_MS` is bounded to 100–10,000 ms. `LEXA_SLOW_SQL_MS` is bounded to 50–10,000 ms. Invalid values fall back to safe defaults.
- The home dashboard has one keyed analytics refresh effect. It waits for the dashboard business date and currency to settle, avoids repeated calls for the same refresh/period/date/currency, and reloads analytics when the user refreshes or changes the reporting period.

## How to interpret timings

`api;dur` is the complete application middleware duration. `db;dur` is the **sum** of SQLAlchemy cursor-execution durations recorded during that request; it is not a wall-clock span and can be larger than elapsed request time if work ever overlaps. The DB metric does not by itself measure connection-pool checkout wait, row materialization, result serialization, network transit, CDN/edge time, or client rendering. A slow API duration with a small `db` duration narrows the investigation; it does not prove a specific cause.

Use `X-Request-ID` to join the browser/network request to API and slow-query log entries. Normal requests do not emit a per-request warning. Slow thresholds are adjustable through environment configuration without changing business behaviour.

## Safety and scope

No business SQL, migration, Neon setting, production secret, hosting plan, or production environment was changed. Timing listeners are attached to the existing SQLAlchemy engine and do not issue extra SQL. No shared cache was added, and no tenant-scoped business response is cached. All dashboard panels, navigation destinations, and business actions remain in place.

## Local validation for this candidate

- Python: `PYTHONPATH=apps/api python -m pytest -q tests apps/api/tests` — **363 passed**.
- Python compilation: `python -m compileall -q apps/api/app apps/api/tests tests scripts` — passed.
- Frontend contracts: `node --test apps/web/tests/*.test.mjs` — **77 passed**.
- Docker builds and cluster validation were unavailable locally because Docker/Kubernetes tooling is absent.
- The web dependency installation did not complete within the available run window. The environment has Node 22, while `apps/web/package.json` and CI require Node 24, so a Node 24 typecheck and production build are still required in CI.
- Live route percentiles, authenticated staging flows, and concurrent load tests remain open. These timings create the evidence needed for the next, workload-specific optimization; no latency improvement is claimed without before/after measurements.
