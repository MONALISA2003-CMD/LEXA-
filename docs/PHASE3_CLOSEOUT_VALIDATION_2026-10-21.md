# LEXA Phase 3 closeout audit — 21 October 2026

## Source and handoff
- GitHub repository: `MONALISA2003-CMD/LEXA-`.
- Source baseline: `87a303aa75e6b9df3ff2d64fb6f9f1feabd82aae` (the current main commit after the ZIP extractor ran).
- This handoff includes uncommitted local source fixes and security migration 029. The code fixes in this ZIP are **not yet committed to GitHub main**; uploading the ZIP through the repository's existing extractor is the handoff path.
- The six original migration SQL sources were declared lost by the project owner. Six checksum-pinned equivalents are installed at canonical migration paths and clearly marked `ACCEPTED REPLACEMENT — ORIGINAL HISTORICAL SOURCE LOST; NOT BYTE-IDENTICAL`. The original historical bytes are not claimed to have been recovered.

## Checks that passed
- Frontend on Node `v24.14.1`: `npm ci` passed; `npm audit` reported 0 vulnerabilities; `npm run typecheck` passed; `npm test` passed (23 tests, 0 failures); `npm run build` passed and generated 18 routes.
- Backend under Python `3.13.16`: `python -m compileall` passed; full test command `pytest -q tests apps/api/tests` passed (141 passed, 1 deprecation warning).
- Migration source checker: 28 live migration identities, 22 canonical source files, 6 accepted replacements with SHA-256 verified, 0 unresolved canonical source paths. Full identity strings are preserved for the two distinct `023_*` migrations.
- Replacement manifest checker passed.
- Vercel production deployment from `87a303aa75e6b9df3ff2d64fb6f9f1feabd82aae` was `READY`; no Vercel runtime error clusters were reported for the preceding 24 hours.
- Render service deployed the current GitHub commit and is live. `GET /health` returned HTTP 200. After setting `DATABASE_APP_ROLE=lexa_app` and correcting the read-only migration-ledger policy, `GET /ready` returned HTTP 200 with database and cache `ok`. An unauthenticated call to `/api/v1/accounting/journal-entries` returned the expected 401.
- Production Neon migration `029_phase3_runtime_privilege_surface` was applied and recorded in `schema_migrations`. `permissions` and `schema_migrations` now have forced RLS; `lexa_app` can read both but cannot write either. Effective-role verification showed no superuser, BYPASSRLS, CREATEDB, CREATEROLE or REPLICATION attributes for `lexa_app`.

## Fixes included in this handoff
- `apps/api/app/routes/finance.py`: optional status predicates are added only when `status` is provided for journal entries and fiscal documents. This removes the ambiguous PostgreSQL parameter pattern `(:s IS NULL OR status=:s)`.
- `migrations/016_phase4a_sales_payments_reconciliation.sql`: adds an idempotent composite unique index prerequisite for the tenant-scoped payments foreign key that failed in the first clean replay attempt.
- `migrations/029_phase3_runtime_privilege_surface.sql`: source for the production security changes already applied to Neon.
- Updated migration-source checkers, source-loss acceptance record, current live-ledger snapshot, and focused regression tests.

## Gates still open — do not declare Phase 3 complete yet
1. **Clean database replay is not yet passed.** The first fresh replay failed at migration 016 because `payments(tenant_id,id)` did not have a unique constraint at that point in the migration sequence. An idempotent prerequisite was added, but the complete replay was not successfully rerun afterward. This is a release blocker.
2. **Authenticated end-to-end and real-browser acceptance are not complete.** No authorized production test account/token was available for authenticated module-by-module create/read/update flows. The public unauthenticated 401 test is not a substitute.
3. **The finance route fix is in this ZIP, not in the deployed GitHub source yet.** Re-run CI and deploy after the package is integrated; then test both affected routes against Neon with authentication.
4. **Production database login credential still has elevated inherited membership.** `lexa_runtime` remains a member of `neon_superuser`; the connected SQL role could not revoke that membership. App transactions now switch to `lexa_app`, but this does not remove the escalation capability of the login credential itself.
5. **Three tables remain RLS-disabled:** `users`, `tenants`, `registration_requests`. They serve pre-authentication and registration flows; policy design and authenticated regression tests are required before enabling RLS safely.
6. **Schema parity sign-off is pending.** Source path/checksum validation is not proof that all reconstructed migration effects match live schema/data transformations.

## Production safety notes
- No data rows were intentionally edited by the security migration. It changed role access/policies and inserted the migration ledger row.
- A temporary Neon replay branch and disposable replay databases were used for investigation; the initial replay did not complete.
- Phase 4 remains blocked until the replay, authenticated end-to-end, source integration/deployment, and remaining credential-security gates pass.
