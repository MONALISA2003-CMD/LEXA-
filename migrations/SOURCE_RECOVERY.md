# Migration source recovery notes — updated 15 October 2026

## Recovered source

- Full version: `019_phase4a_customer_credit_allocation`
- Path: `migrations/019_phase4a_customer_credit_allocation.sql`
- Source commit: `d850ce04c8930134f01a63cd65c5d1947a17b17d`
- Source repository: `MONALISA2003-CMD/LEXA-`
- Verified Git blob SHA-1: `caefc2e3b46c5a4bae2ff2592b787d3b4092dd61`
- Verification method: recomputed the Git blob hash from recovered file bytes and matched GitHub's historical file API result.

## Canonical ledger recheck — 15 October 2026

A read-only query against `public.schema_migrations` on Neon project `wispy-mud-75323042`, branch `lexa-live` (`br-soft-star-b1dj2m2w`), database `neondb`, returned the same 27 full version strings as the 13 October snapshot. A separate read-only query confirmed migration 028, the refresh lookup function, `lexa_app` EXECUTE privilege, and a `SECURITY DEFINER` owner with RLS bypass. See `live_ledger_snapshot_2026-10-15.json` for the refreshed ledger evidence and retain the `2026-10-13` snapshot as historical evidence.

## Unresolved historical sources

The following applied full version strings remain absent from the supplied package and inspected Git history:

- `010_phase2_catalog_intelligence`
- `011_phase2_catalog_runtime_constraints`
- `023_phase4_purchasing_core`
- `024_phase4_purchasing_security`
- `025_phase4_purchasing_permissions`
- `026_phase4_membership_branch_integrity`
- `027_release_convergence`

Search of connected repository history and public results did not reveal authoritative copies. Their SQL was not fabricated from live-schema inference. Run `python scripts/check_migration_sources.py`; `--strict` remains blocked until exact source artifacts are recovered and reviewed.

## Dynamic SQL validation

The corrected dynamic Brain RLS policy block in `022_phase6a_brain_foundation.sql` was executed on the existing disposable Neon branch `lexa-convergence-test-2026-10-08` only. A follow-up read of `pg_policies` verified all seven expected Brain policies use a properly quoted empty-string predicate. This validates the corrected dynamic SQL statement; it does not prove a full from-zero replay, because the seven historic SQL gaps remain.

## Deployment evidence — 15 October 2026

- Render `https://lexa-n10e.onrender.com/health`: HTTP 200.
- Render `https://lexa-n10e.onrender.com/ready`: HTTP 200, but the deployed payload still reports only `dependencies.database`; the new Redis/Valkey readiness code is not yet deployed.
- Bodyless POST `https://lexa-n10e.onrender.com/api/v1/auth/refresh`: HTTP 401 on retry after the service warmed, not HTTP 422.
- Bodyless POST `https://lexa-n10e.onrender.com/api/v1/auth/logout` without a cookie: HTTP 200, `{"status":"logged_out"}`.
- Connected Render service `LEXA` still reports a blank live `healthCheckPath`, though this package's `render.yaml` declares `/ready`.

No SQL mutation was made on canonical `lexa-live` during this validation. The connected Render tool does not expose a direct health-check setting update; no production deployment was triggered. Credentialed browser/API acceptance remains pending until a dedicated test account is available. GitHub branch creation was denied with HTTP 403, so this is a ZIP handoff rather than a pushed release.
