# LEXA Phase 5 Increment 03 — Handoff

This full-source ZIP is based on the latest uploaded GitHub revision `779f8fe5dc704411b9abab371a29311e7dbc844a` and adds the Phase 5 Increment 03 refund/return/accounting/analytics changes. The new source is not yet committed or deployed.

## Apply

Use the existing approved GitHub ZIP extractor to upload `LEXA_PHASE5_INCREMENT_03_FULL_SOURCE_2026-10-21.zip`. Do not deploy from a different/unreviewed revision. Once extraction yields its commit, record that exact SHA and verify both Vercel and Render target it.

## Validate

```sh
# Backend (from repository root)
export PYTHONPATH="$PWD/apps/api"
export DATABASE_URL='postgresql://test:test@localhost/test'
export REDIS_URL='redis://localhost:6379/0'
export JWT_SECRET='test-secret-at-least-32-characters-long'
export APP_ENV='test'
export DATABASE_APP_ROLE='lexa_app'
export DATABASE_LOGIN_ROLE='lexa_runtime_login_p3'
python3 -m compileall -q apps/api/app apps/api/tests
python3 -m pytest -q apps/api/tests

# Frontend
cd apps/web
npm ci
npm run typecheck
npm test
npm run build
npm run test:e2e:phase5
```

Run all frontend commands in Node 24.x. `npm run test:e2e:phase5` intentionally requires an explicit safe staging host, a staging fixture and `LEXA_PHASE5_ALLOW_STAGING_WRITES=1`; supply isolated cashier/manager storage states. Never set the browser host to production for this mutating suite.

## Database migrations in this increment

- `033_phase5_refund_settlement_consistency.sql`: payment/refund/customer-credit totals, refund-row refresh trigger, analytics `amount_due` correctness.
- `034_phase5_return_accounting_journals.sql`: customer store-credit liability mapping, return settlement journal, returned-stock COGS journal, optional EFRIS credit note.
- `035_phase5_none_return_receivable_guard.sql`: no-refund return cannot credit AR beyond the open receivable.

These were installed and schema/function-checked on Neon QA branch `br-young-base-b1mi15fs`, not on production. The QA branch inherits parent data and is not a sanitized staging target. Review and validate the SQL with a clean isolated replay before production promotion.

## Known constraints

- Current live baseline is green on the same SHA `779f8fe5dc704411b9abab371a29311e7dbc844a`: browser-side fetch returned HTTP 200 for Render `/health` and `/ready`, and Vercel-owned fetch returned HTTP 200 for its same-origin readiness proxy. An intermittent raw scraper 503/challenge was followed by successful direct checks.
- New Increment 03 source is not part of that deployed baseline yet.
- Local tests: 66 backend passed, 1 Redis-dependent test skipped; 27 frontend contracts passed under Node 22.16.0. Node 24 clean install/typecheck/build and authenticated staging E2E remain open.
- The connected GitHub integration previously returned 403 for write requests. No claim is made that local files have been committed.
- Historical migration source parity remains false. In particular, the repaired `021_phase5_analytics_foundation.sql` is labelled a repair candidate; a previous Neon QA ledger records `032_phase5_return_settlement_reconciliation`, but that SQL source is missing from this repository.
