# LEXA Phase 4–6 Completeness Increment 03 — implementation report

**Assessment date:** 21 October 2026  
**Candidate version:** `2.11.0+phase4-6.completeness.increment03`  
**Status:** Local source candidate. Local tests and static source gates pass; Node 24 typecheck/build, live clean replay, authenticated staging E2E, and candidate deployment acceptance remain pending.

## Executive result

This increment implements the next missing product-system pieces from `FRESH_NEW_PRODUCT_STRATEGY.md`, strengthens the actual CI gates, and permanently separates historical SQL disposition from replacement validation. It does **not** declare Phases 4–6 production-accepted based on local tests alone.

### Permanent migration decision

- The six Phase 3 sources in `migrations/migration_dispositions.json` remain `PERMANENTLY_REPLACED`. Historical recovery is closed; the maintained SQL equivalents remain clearly labelled and checksum-controlled. No further routine recovery search is required and this is not a claim that historical bytes were recovered.
- The active source gate `python scripts/check_migration_sources.py --strict` passes source reconciliation and reports semantic replay as a distinct pending gate.
- The current read-only Neon snapshot contains 31 full migration identity strings. Exact current sources `029_phase3_runtime_privilege_surface.sql` and `031_phase3_auth_surface_rls.sql` are present and Git-blob hash-verified. Prefix collisions `023` and `029` are handled by complete identities rather than numeric prefixes.
- QA-only ledger item `032_phase5_return_settlement_reconciliation` is not silently promoted into canonical production replay. It remains an explicit QA discrepancy to reconcile if that QA environment is reused. Migration 021 remains identified as a repair candidate, not original historical recovery.

## Strategy coverage: Phases 4–6

### Phase 4 — consistent, explainable workspaces and reporting

- Reports now use an explicit Apply Period action, validate the selected range, request the business profile currency, and distinguish unavailable data from a confirmed no-records period.
- Customer history and current-stock snapshots are labelled as such rather than represented as historical values for the selected period.
- Product and inventory money displays now use the business-profile currency where available. If that currency is unavailable, monetary values are not silently relabelled as UGX.
- `scripts/audit_frontend_actions.mjs` parses the application TypeScript/TSX source and checks button handler/submit wiring, form submit handlers, and link destinations. Current scan: 29 TypeScript/TSX files; 117 button-like controls, 27 forms, 33 links; no structural issues. This static audit does not replace browser usability or business-flow acceptance.

### Phase 5 — safer commerce returns and settlement

- Return UI supports multiple sale lines in a single return; server logic still validates previously returned quantities and remains authoritative.
- Candidate backend/migration changes preserve refund caps against gross recorded collections less prior completed refunds, reject no-refund/no-credit returns that exceed the open receivable, prorate partial-line discounts/tax, and carry accounting/COGS/fiscal-document links through the return trail.
- The Phase 5 database migrations in the package are forward candidates only. They have not been applied to production in this increment.

### Phase 6 — inventory intelligence

- Replenishment policies are tenant/location/variant scoped and recommendations are deterministic, explainable, and advisory. They do not create purchase orders or stock movements.
- Remaining-stock age analysis exposes 30/60/90-day quantities, unknown-provenance stock, the oldest traceable positive layer, and an explicit reconciliation-gap flag. It uses a documented analytical oldest-first depletion convention; it is not serial/batch tracking and does not change moving-average accounting valuation.
- The new Stock Health view reports on-hand/reserved/available/inbound quantities, gross sales and returns separately for 30/90 days, last completed sale, days since sale, and exception classes for out-of-stock/recent demand, configured minimums, and no-sale periods. It is location/tenant scoped, and no-sale labels are qualified as “no completed sale found” in available history rather than forecasts.
- Migration 037 adds the inventory-ledger age-analysis index. Migration 038 adds four idempotent concurrent indexes supporting movement-health joins. Both remain candidate migrations, not production-applied changes.
- Inventory screens retain explicit error/empty states, request IDs prevent stale Stock Health/age/replenishment responses from replacing newer filters, and UI actions are included in the static control audit.

## Release-gate improvements

- Clean-replay manifest now contains 42 ordered SQL inputs. Current bundle SHA-256: `ca3d402f58650ba4acf9ede4493ec3960b7d546fccb806ee96e02f6e93282864`. `--plan-only` validates path containment and file hashes without opening a database.
- The guarded replay runner only accepts an explicitly opted-in, empty loopback disposable PostgreSQL database. It rejects remote hosts and production-like database names.
- Replay postconditions include RLS enabled and forced on every public table, migration identities, return/accounting routines, policy table/tenant policy, `lexa_app` privilege boundaries, rollback-only runtime cross-tenant probes, the age-analysis index, and four *valid and ready* movement-health indexes.
- `scripts/check_phase6_replay_evidence.py` requires evidence pinned to the exact source commit and current SQL bundle/checksums. The GitHub workflow provisions Redis and disposable pgvector/PostgreSQL, uses Node 24 with `npm ci`, runs typecheck/contracts/build and includes the AST control audit.
- This local environment could not execute the actual replay or Node 24 installation/build. CI must provide that evidence for this exact candidate.

## Local verification

| Check | Result |
|---|---|
| `python -m pytest -q tests apps/api/tests` | **188 passed, 1 skipped, 0 failed**; the only local skip is the Redis-dependent refresh integration test because Redis’s Python package is unavailable in the offline runner |
| `cd apps/web && node --test tests/*.test.mjs` | **33 passed, 0 failed** under local Node 22.16.0 |
| `node scripts/audit_frontend_actions.mjs` | PASS — 29 TS/TSX files parsed; 117 controls, 27 forms, 33 links |
| `python -m compileall -q apps/api/app apps/api/tests tests scripts` | PASS |
| `python scripts/check_migration_recovery_manifest.py` | PASS |
| `python scripts/check_migration_sources.py --strict` | PASS — six historical recovery decisions closed; semantic replacement validation still pending |
| `python scripts/run_clean_migration_replay.py --plan-only` | PASS — 42 inputs verified; no SQL executed |
| Node 24 `npm ci`, `npm run typecheck`, production build | NOT VERIFIED locally; requires CI |
| Actual disposable PostgreSQL clean replay | NOT RUN locally; requires CI |
| Authenticated isolated staging browser E2E | NOT RUN |

## Release and production boundary

- Candidate is a local source package; it has not been committed or deployed by this work. The current healthy baseline SHA is not evidence that this candidate is running.
- No production SQL mutation, deployment, or production migration was performed.
- Migrations 033–038 have not been applied to production.
- Full production acceptance still requires candidate-SHA CI success including Redis integration, Node 24 typecheck/build, actual clean replay and runtime-role probes, authenticated E2E in sanitized isolated staging, same-SHA Render/Vercel readiness checks, and a separately approved production migration/rollback plan.

## Files of record

- `docs/PHASE4_6_STRATEGY_COVERAGE_2026-10-21.md`
- `PHASE4_6_COMPLETENESS_ACCEPTANCE_MATRIX_2026-10-21.md`
- `migrations/migration_dispositions.json`
- `migrations/reconstructed/clean_replay_order.json`
- `PHASE6_RELEASE_GATE_STATUS_2026-10-21.json`

Historical exact-byte recovery for the six Phase 3 files is permanently closed. Semantic correctness, authenticated E2E, cloud build, deployment parity, and the approved rollout remain separate gates.
