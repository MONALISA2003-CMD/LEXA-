# Migration source recovery notes — updated 20 October 2026

## Recovered source

- Full version: `019_phase4a_customer_credit_allocation`
- Path: `migrations/019_phase4a_customer_credit_allocation.sql`
- Source commit: `d850ce04c8930134f01a63cd65c5d1947a17b17d`
- Source repository: `MONALISA2003-CMD/LEXA-`
- Verified Git blob SHA-1: `caefc2e3b46c5a4bae2ff2592b787d3b4092dd61`
- Verification method: recomputed the Git blob hash from recovered file bytes and matched GitHub's historical file API result.

## Recovered source — 027 release convergence (20 October 2026)

- Full version: `027_release_convergence`
- Canonical path: `migrations/027_release_convergence.sql`
- Recovered source path: `lexa_v280_src/migrations/027_release_convergence.sql`
- Source commit: `51355d941eb50e075e3d4f884838a11b6807778b`
- Source repository: `MONALISA2003-CMD/LEXA-`
- Verified Git blob SHA-1: `e6d9242d7dedb2cbf7b1a71a46fe635b3ab051d8`
- Verified SHA-256: `404334dde3e34a80d3176b1ba38347eb1def3cc8793f6b52d3a663cbc05b19cd`
- Source size: `16,980` bytes
- Verification method: recovered file bytes recompute to the GitHub blob SHA-1; SHA-256 is recorded in `source_gaps.json` under `recovered_sources`.
- Scope/caveat: the legacy `lexa_v280_src/migrations/README.md` describes 027 as the additive schema-parity/readiness/analytics convergence point and the 023–026 purchasing entries as historical lineage markers. The live ledger records version names, not source checksums; this validates tracked artifact provenance, but it is not an independent checksum of the SQL originally executed on the database. Do not reapply this source to the live branch as part of source recovery.

## Canonical ledger recheck — 15 October 2026

A read-only query against `public.schema_migrations` on Neon project `wispy-mud-75323042`, branch `lexa-live` (`br-soft-star-b1dj2m2w`), database `neondb`, returned the same 27 full version strings as the 13 October snapshot. A separate read-only query confirmed migration 028, the refresh lookup function, `lexa_app` EXECUTE privilege, and a `SECURITY DEFINER` owner with RLS bypass. See `live_ledger_snapshot_2026-10-15.json` for the refreshed ledger evidence and retain the `2026-10-13` snapshot as historical evidence.

## Unresolved historical sources

Six applied full version strings remain absent from the supplied package and inspected Git history after recovering 027:

- `010_phase2_catalog_intelligence`
- `011_phase2_catalog_runtime_constraints`
- `023_phase4_purchasing_core`
- `024_phase4_purchasing_security`
- `025_phase4_purchasing_permissions`
- `026_phase4_membership_branch_integrity`

Search of connected repository history and public results did not reveal authoritative copies. Their SQL was not fabricated from live-schema inference. Run `python scripts/check_migration_sources.py`; `--strict` remains blocked until the remaining exact source artifacts are recovered and reviewed.

## Dynamic SQL validation

The corrected dynamic Brain RLS policy block in `022_phase6a_brain_foundation.sql` was executed on the existing disposable Neon branch `lexa-convergence-test-2026-10-08` only. A follow-up read of `pg_policies` verified all seven expected Brain policies use a properly quoted empty-string predicate. This validates the corrected dynamic SQL statement; it does not prove a full from-zero replay, because the six remaining historic SQL gaps remain.

## Deployment evidence — 15 October 2026

- Render `https://lexa-n10e.onrender.com/health`: HTTP 200.
- Render `https://lexa-n10e.onrender.com/ready`: HTTP 200, but the deployed payload still reports only `dependencies.database`; the new Redis/Valkey readiness code is not yet deployed.
- Bodyless POST `https://lexa-n10e.onrender.com/api/v1/auth/refresh`: HTTP 401 on retry after the service warmed, not HTTP 422.
- Bodyless POST `https://lexa-n10e.onrender.com/api/v1/auth/logout` without a cookie: HTTP 200, `{"status":"logged_out"}`.
- Connected Render service `LEXA` still reports a blank live `healthCheckPath`, though this package's `render.yaml` declares `/ready`.

No SQL mutation was made on canonical `lexa-live` during this validation. The connected Render tool does not expose a direct health-check setting update; no production deployment was triggered. Credentialed browser/API acceptance remains pending until a dedicated test account is available. GitHub branch creation was denied with HTTP 403, so this is a ZIP handoff rather than a pushed release.


## Canonical ledger recheck — 20 October 2026

A fresh read-only query of `public.schema_migrations` on project `wispy-mud-75323042`, branch `br-soft-star-b1dj2m2w`, database `neondb` returned these relevant rows:

| Full recorded version | Applied timestamp (UTC) | Exact source in current package? |
|---|---|---|
| `010_phase2_catalog_intelligence` | `2026-09-20T20:53:12.510Z` | Missing |
| `011_phase2_catalog_runtime_constraints` | `2026-09-20T21:02:49.364Z` | Missing |
| `023_phase4_purchasing_core` | `2026-10-08T12:37:54.528Z` | Missing |
| `024_phase4_purchasing_security` | `2026-10-08T12:38:45.629Z` | Missing |
| `025_phase4_purchasing_permissions` | `2026-10-08T12:39:27.658Z` | Missing |
| `026_phase4_membership_branch_integrity` | `2026-10-08T12:43:33.086Z` | Missing |
| `027_release_convergence` | `2026-10-08T16:00:40.435Z` | Recovered from tracked Git blob; DB has no source checksum |
| `028_phase0_auth_rls_runtime_hardening` | `2026-10-13T10:42:36.374Z` | Source exists elsewhere in the package lineage |

The current ledger records these versions as applied; the six source files remain unrecovered from exact authoritative artifacts. Do not delete or edit ledger rows to make the repository appear consistent. Do not re-run guessed migrations. The ledger has only `version` and `applied_at`, so none of these rows contains a checksum proving which bytes were executed.

## Expanded recovery searches — 20 October 2026

After recovering 027, each of the six outstanding basenames was searched using (1) all 24 ZIP archives currently available under `/mnt/data`, including additional older archives materialized from the connected File Library, (2) a recursive Library search for standalone `.sql` files (none returned), (3) the recursively enumerated GitHub repository tree and known historical source prefixes, (4) direct GitHub API path history queries for `migrations/<basename>` and `lexa_v280_src/migrations/<basename>`, (5) exact-name GitHub code and commit searches, and (6) exact-name/public developer-web searches. No authoritative copy was found for any of the six. This means no source artifact can be restored from the currently reachable materials; it is not proof that no owner-held backup exists. The strict checker remains intentionally failing until sources are supplied and reviewed.

The live `schema_migrations` table has only `version` and `applied_at` and cannot prove the exact SQL bytes applied. A ledger name or matching live schema is not a substitute for source recovery.
