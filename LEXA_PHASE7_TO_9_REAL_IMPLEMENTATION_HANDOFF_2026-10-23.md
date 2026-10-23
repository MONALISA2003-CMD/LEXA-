# LEXA Phase 7–9 real-application update — 23 October 2026

## Purpose

This is a repository-root source overlay for the existing LEXA application. It changes real `apps/web` and `apps/api` sources and tests. It contains no HTML prototype or standalone mock UI.

## App changes included

- Phase 7 purchasing: supplier, purchase-order, partial receipt, supplier-return/credit, bill, payment/allocation and supplier-ledger workflows retained in the canonical app source. Purchasing SQL uses explicit parameter casts for optional filters to avoid PostgreSQL ambiguous-parameter inference.
- Session/workspace authentication: candidate sign-in path preserves the trusted workspace context checks and associated RLS regression coverage.
- Phase 8 finance: existing receivables/payables, recorded payment, expense lifecycle, manual reconciliation and reporting flows retained; no second payables ledger or external payment initiation added.
- Phase 9: the real Business Insights page now displays a direct answer from the matched saved insight after a supported question. The answer includes the original summary, available metric and comparison, period, source table/row count, refresh provenance, methodology, limitations and link to the matching source screen. Editing the query clears the previous answer; unsupported queries reset the filter instead of leaving an old category selected. Stale or missing data remain explicitly unverified, not fabricated zeros.
- Owner dashboard: overdue supplier bills are shown in the “Things to check today” queue only when the purchasing summary has loaded successfully and reports a positive overdue count. The alert routes to Purchasing.

## Verification performed on this candidate

- Backend: `PYTHONPATH=apps/api python -m pytest -q` — **347 passed, 1 existing Starlette deprecation warning**.
- Frontend contracts: `node --test tests/*.test.mjs` from `apps/web` — **77 passed, 0 failed, 0 skipped**.
- Python compile: `python -m compileall -q apps/api/app apps/api/tests scripts` — passed.
- Migration recovery manifest consistency — passed, but the checker explicitly reports six historical migration equivalents whose semantic replacement validation remains pending.
- `python scripts/check_migration_sources.py --strict` — source disposition reconciliation passed; semantic validation for six replacement equivalents remains pending.
- `python scripts/run_clean_migration_replay.py --plan-only` — passed without opening a database connection or executing SQL.
- TypeScript/TSX syntax transpilation on the changed intelligence page — passed.

## Not yet verified

- `npm ci` did not complete in this environment, and runtime Node is 22.16.0 while the package declares Node 24.x.
- Full TypeScript typecheck and Next.js production build — not passed/verified.
- Authenticated Playwright end-to-end tests against a seeded, isolated staging tenant — not run.
- Real-phone and desktop browser visual acceptance — not run.
- Clean migration replay semantic validation for six approved reconstructed equivalents — still pending.

## Production boundary

This archive is a tested candidate, not production acceptance. No GitHub source change, Render/Vercel deployment, production database write, or Neon change was performed by packaging this file. The migrations are bundled as source; the plan-only command executed no SQL.

The repository ZIP-extractor workflow protects `.github/workflows/**` and will skip that path even if a workflow file is present in the archive. Workflow installation must be verified separately in GitHub after extraction; do not infer CI success from the upload alone.
