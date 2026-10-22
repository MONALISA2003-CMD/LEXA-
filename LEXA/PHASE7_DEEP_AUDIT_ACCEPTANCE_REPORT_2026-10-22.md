# LEXA Phase 7 — deep implementation, runtime and release-gate audit

**Date:** 22 October 2026  
**Decision:** **NO-GO for production**  
**GitHub baseline inspected:** [`b920c8719079741ed3c2fb2288de67c7de8a0d37`](https://github.com/MONALISA2003-CMD/LEXA-/commit/b920c8719079741ed3c2fb2288de67c7de8a0d37)  
**Repair package:** `2.12.0+phase7.increment03` (source-only archive)

## 1. Product strategy fit

The supplied `FRESH_NEW_PRODUCT_STRATEGY.md` says Phase 7 is Purchasing and Supplier Management: supplier terms, purchase-order state, partial receiving, stock increases, landed/other costs, returns and supplier balances. The current candidate source contains these workspaces and the server-side finance/stock workflow. It preserves the policy that purchases are advisory/user-approved, not auto-executed, and uses tenant/branch scope and idempotent operations. The implementation audit found an actual runtime validator defect in the supplier-payment model; Increment 03 fixes it in source, but it is not yet in the currently deployed SHA.

## 2. Root cause of delayed backend/database release

The delay is not one slow build. It is four separate gates which were conflated:

1. **CI cannot run against the exact commit:** `.github/workflows/lexa-ci.yml` is absent from the current GitHub `main` tree. The only recent workflow observed was the ZIP extractor. The GitHub connection returned 403 `Resource not accessible by integration` for a new branch and for adding the missing workflow. Therefore there is no full CI workflow result for exact SHA `b920...`.
2. **Frontend/backend are deployed at different SHAs:** Vercel is `READY` at `b920c871...`; Render is still live at `dd406910...`. A successful frontend build does not deploy the Python API or apply PostgreSQL migrations.
3. **Canonical DB schema is behind the source:** Render points to Neon project `wispy-mud-75323042`, branch `lexa-live`, DB `neondb`. Read-only queries found 31 migration records through 031, no records 033–039 and none of the six Phase 7 supplier-finance tables. Migration 039 is intentionally not applied while backup/restore and release gates are open.
4. **Backup/staging resources are constrained:** Neon has no recorded automatic snapshot schedule or project snapshots; snapshot creation is disallowed on the `lexa-live` non-root branch, and a new validation branch is currently rejected by the project's branch limit. The existing Render workspace already uses its one Free Redis instance, and creation of a second Free Redis was rejected. Authenticated E2E needs a real isolated staging target and fixture; it was not run.

## 3. Runtime bug reproduced from Render logs and fixed in this archive

Render logs repeatedly recorded a Pydantic warning at `apps/api/app/routes/purchasing.py:231` that `validate_allocations` overrides an earlier model validator. Source inspection found two methods with the same name in `SupplierPaymentCreate`. Python overwrote the earlier method; the surviving method attempted to call `validate_payment_allocations`, which was not imported. A supplier-payment request could therefore enter a runtime validation error path rather than reliably reject duplicate allocations or allocations that exceed the payment total.

Increment 03 imports the shared `validate_payment_allocations` rule, keeps one Pydantic model validator, and adds direct model regression tests for normal currency normalization, valid allocations, duplicate bill IDs and over-allocation. A second runtime pattern was reproduced from Render logs: `db.commit()` followed by `db.refresh()` failed in transaction-local RLS contexts, causing 500s after branch/category writes had already committed. Those affected catalog/organization/RBAC paths now return the already-flushed ORM state or precomputed idempotency response without a post-commit SELECT; this aligns with the configured `expire_on_commit=False` session. A regression contract checks that the unsafe refresh pattern does not reappear. Backend suite is now 211 passed/1 skipped. The fixes are in the archive only: GitHub writes were denied and Render still serves the old commit, so this should not be described as fixed in production until a new exact-SHA API deploy is observed.

Render logs from 21 October also contain prior HTTP 500s while creating branches/categories (`sqlalchemy.exc.InvalidRequestError: Could not refresh instance`). The latest observed app log shows `/ready` returning 200, but these historic failures mean the same-commit authenticated smoke tests are still required after the next candidate deploy. A Pydantic warning is a hard reason not to call the currently live supplier-payment path release-accepted.

## 4. Verification results

### Local source checks

| Check | Observed result |
|---|---|
| Backend tests | 211 passed, 1 skipped; skip is Redis auth-refresh because the local offline image has no `redis` Python package |
| Frontend contracts | 38 passed |
| Frontend action audit | Passed: 29 TS/TSX files, 153 button-like controls, 35 forms, 33 links |
| Python compilation | Passed |
| Strict migration source reconciliation + evidence-backed semantic validation | Passed with an evidence JSON and SHA-256 sidecar bound to the current 43-input migration bundle and baseline source SHA; historical exact-byte parity is intentionally not claimed |
| 43-input plan-only replay/hash check | Passed; bundle SHA-256 `2d446ba3c0df5903b06ed0dbb92e1c2239f353aa69cc40e80d452ecb78ec1674` |
| Node 24 clean `npm ci`, typecheck/build of Increment 03 | Not run locally: Node 24 absent; npm registry/DNS unavailable. Vercel build success above is for SHA `b920...`, before the Increment 03 API fix |

### Actual disposable PostgreSQL execution (manual remote evidence)

I executed the 43 ordered SQL files against isolated Neon project `LEXA-PHASE7-REPLAY-20261022`, branch `phase7-clean-replay`, database `lexa_replay_ci`. This was an actual SQL replay, separate from the plan-only script. Verification reported 33 migration-ledger rows including `039_phase7_supplier_ledger_landed_costs`; 126 public tables, 126 enabled/forced RLS, and zero RLS gaps. All six Phase 7 supplier-finance tables had forced RLS and tenant policies. The required Phase 6/7 indexes were present/valid, Phase 7 columns and four return/accounting routines were present, and the least-privilege grants were checked. Cross-tenant bill reads showed no other-tenant rows, cross-tenant writes were denied by RLS, and a Cashier member saw only its assigned branch. The replay compute was suspended after testing.

This is manual remote evidence; the evidence file and sidecar pass `scripts/check_phase6_replay_evidence.py --expected-commit b920...` and `scripts/check_migration_sources.py --require-semantic-validation`, but it is not a GitHub Actions artifact. The CI workflow must still run on the exact commit; do not portray the remote hand-run as a successful GitHub workflow.

## 5. Render and Vercel review

### Vercel

- Latest observed production-target deployment: `dpl_EAd6M7k5R4KZGhKjd91XjgKjnzYV`, status `READY`, source SHA `b920c8719079741ed3c2fb2288de67c7de8a0d37`.
- Build log recorded completed TypeScript checking and 21 generated static pages.
- Aggregate runtime-error search returned no clusters in the 24-hour window. Detailed log lookup for 24 hours was rejected because the connected account's plan retention does not include that window. This is a telemetry limitation, not proof there were no requests/log records.
- Production environment has `LEXA_API_URL` and `NEXT_PUBLIC_API_URL` keys, but their values are stored encrypted and did not resolve to inspectable URLs in the connected metadata; do not claim their runtime destination is validated.
- The current Vercel deployment does not include the Increment 03 backend code, so the supplier-payment validator issue remains live on the prior Render API.

### Render

- API service: `srv-dakm8k95efls73egg9a0`, URL `https://lexa-n10e.onrender.com`, current live deploy `dep-dbchjh0473hc73ahsm40` on older SHA `dd4069109d5c94143f5c5e28e758128b90dee55a`.
- The live service configuration has an empty `healthCheckPath`; the repository's `render.yaml` specifies `/ready`. Runtime logs show `/ready` responded 200. Configure `/ready` in Render Settings or sync the approved Blueprint and verify the setting after deploy.
- The repeated Pydantic duplicate-validator warning needs to disappear after the corrected source is deployed.
- Exact backend/frontend SHA parity is **FAIL** until Render deploys the same approved SHA as Vercel.

## 6. Neon production/canonical schema and backup review

- Canonical project: `wispy-mud-75323042`; the Render settings reference `lexa-live` branch `br-soft-star-b1dj2m2w`, DB `neondb`.
- Read-only live audit: 31 migration ledger rows through `031_phase3_auth_surface_rls`; migration 039 absent; 0/6 Phase 7 supplier-finance tables present.
- A query against the separate root branch named `production` failed because it has no `public.schema_migrations`; that error is not a migration ledger, and its state is not inferred from it.
- Snapshot schedule query returned an empty list and project snapshot listing returned empty.
- Direct snapshot call to `lexa-live` was rejected with `not allowed to snapshot non-root branch`. Creating another branch was rejected with `branches limit exceeded`. The project reports history retention 21,600 seconds (six hours). No deletion of historical validation branches and no plan upgrade were performed.

**Fastest safe backup path:** use an owner-controlled secure runner to `pg_dump` the actual `lexa-live` database using the correct DATABASE_URL, encrypt the dump outside this project, create a checksum, and restore it to a genuinely separate disposable database. Then run schema/row-count/application smoke assertions and record the restore time. Do not treat a snapshot of the `production` root branch as a backup of `lexa-live`. This backup/restore operation could not be executed by the available connected tools and remains a release blocker.

## 7. Migration 039, rollout and rollback

Migration 039 is forward/additive at a high level, but it includes data backfills, constraints, indexes, permissions/RLS and migration ledger writes. Its locks/duration have only been demonstrated on empty disposable data, not on representative live data. No `down` migration or point-in-time restore was tested. Therefore do not apply 033–039 to canonical production. Before the approved window:

1. verify an encrypted `pg_dump` and successful restore of the actual `lexa-live` source;
2. reconcile the migration ledger/schema and review each 033–039 change, lock impact, constraint validation, grants/RLS and row counts;
3. run exact-SHA CI with Redis and disposable PostgreSQL replay and retain evidence;
4. deploy the corrected API to an isolated Render candidate, configure health `/ready`, pair it with an isolated Vercel preview, and pass authenticated E2E with a throwaway tenant;
5. capture a rollback plan: revert app to a compatible version if necessary, stop traffic, preserve audit evidence, and use a tested forward-fix or restore from the verified dump; do not assume a destructive schema rollback is safe;
6. obtain explicit production approval and a maintenance window before any production migration.

## 8. Release decision

**NO-GO.** The implementation bug is fixed in Increment 03 source and local regression-tested, and Vercel's previous exact SHA is healthy. However, GitHub write access denied installing/running the full CI; the Increment 03 API fix is not committed or deployed; Render/Vercel SHAs differ; authenticated isolated staging E2E was not run; and backup/restore is not demonstrated. No production database mutation, migration or deployment was made by this audit.

The approved six-file Phase 3 SQL replacement disposition remains permanent. Exact historical byte recovery is not being reopened.
