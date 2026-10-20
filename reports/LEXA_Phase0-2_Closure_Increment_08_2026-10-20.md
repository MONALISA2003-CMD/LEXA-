# LEXA Phase 0–2 Closure Investigation — Increment 08

**Date:** 20 October 2026  
**Repository head inspected:** `4dac83541badc21800f84e652f0f192c211a612a`  
**Release disposition:** **NO-GO for production Phase 3 cutover**  
**Production changes made during this investigation:** None

## Executive result

Phase 0–2 gained a repeatable CI candidate, a hash-checked reconstruction manifest, browser acceptance source, historical-archive scan evidence, and an isolated Neon replay/diff. This is meaningful progress, but it is not a claim that the release gates passed. The six original migration SQL byte streams remain unrecovered. The first reconstructed replay was not schema-equivalent to the observed canonical clone. GitHub write access rejected feature-branch creation, so the workflow has **not** been installed remotely or run as GitHub Actions against a candidate SHA.

## 1. Historical source recovery

The hosted scan examined **116 ZIP-related commits and 58 distinct archive versions** for:

- `010_phase2_catalog_intelligence`
- `011_phase2_catalog_runtime_constraints`
- `023_phase4_purchasing_core`
- `024_phase4_purchasing_security`
- `025_phase4_purchasing_permissions`
- `026_phase4_membership_branch_integrity`

It reported zero hits and zero errors. That closes the archive-scan step for the inspected history but cannot prove no copy exists outside the scanned repository objects. The original `migrations/source_gaps.json` and `scripts/check_migration_sources.py` stay intact. Reconstructed SQL lives only in `migrations/reconstructed/` with a status that explicitly says it is not historical source. The separate `023_phase2_identity_tenancy_authorization_foundation.sql` must not be conflated with missing `023_phase4_purchasing_core.sql`.

### Additional integrity finding

The checked-in `migrations/021_phase5_analytics_foundation.sql` retrieved from GitHub contains 32 literal `\n` sequences after the intended SQL block and extra non-SQL text. Raw SQL replay failed at a backslash. The isolated replay used a separately normalized string and left the checked-in file unchanged. This needs a sourced, reviewed repair commit; do not silently edit the historical bytes or describe them as replay-clean.

## 2. Isolated Neon replay

Only LEXA's isolated Neon branch was used for replay: project `wispy-mud-75323042`, branch `br-crimson-shadow-b1e7n1ce`, database `lexa_phase2_replay_full`. An additional failed-first-pass database (`lexa_phase2_replay`) preserves the initial `016` failure. The canonical database on the isolated clone was inspected read-only; the production branch was not written.

| Catalogue measure | Canonical clone | First-pass replay | Delta |
|---|---:|---:|---:|
| Tables | 119 | 119 | 0 |
| Views | 0 | 0 | 0 |
| RLS policies | 116 | 116 | 0 |
| Columns | 1,305 | 1,291 | -14 |
| Indexes | 433 | 423 | -10 |
| Constraints | 1,804 | 1,792 | -12 |
| Public functions | 458 | 455 | -3 |
| User triggers | 36 | 32 | -4 |

Equal table/policy counts are not semantic parity. The first replay exposed two reproducibility problems:

1. Checked-in `012_phase1_business_kernel.sql` does not create the `(tenant_id,id)` unique key referenced by `016_phase4a_sales_payments_reconciliation.sql`. Exact `016` failed on the isolated empty database until an explicitly labelled replay-only key compatibility delta was added.
2. The raw `021` file is not directly executable due the corruption noted above.

The first-pass schema comparison additionally found audit and transaction-line fields missing from the replay, a different membership-branch assignment shape/default, query indexes and relational constraints missing or different by definition/name, three canonical-only functions, four canonical-only triggers, and 48 changed function definition hashes among common signatures. Some index/constraint differences are name-only or equivalent forms, so the delta needs classified reconciliation rather than blind object copying. The source-evidence JSON preserves the most important column diffs and the exact object counts.

The current local reconstructed-source files have been revised after that initial replay to reflect additional observed catalog evidence. **They have not yet been re-run as a clean replay**, so the diff is evidence from the first pass, not a success claim for the current hashes. `migrations/reconstructed/schema_observation_compatibility.equivalent.sql` is included as a candidate isolated-only delta; it has not been applied in the measured comparison and is not approved for production.

## 3. Test results

The disposable Vercel sandbox checked out SHA `4dac83541badc21800f84e652f0f192c211a612a` and executed the frontend on Node **v24.21.0**, npm **11.19.0**. The new packaged Playwright suite was then run from that same source revision after a sandbox-only install of `@playwright/test@1.64.1` and its Chromium OS dependencies:

- `npm ci --no-audit --no-fund`: pass
- `npm run typecheck`: pass
- `node --test tests/*.test.mjs`: **23 passed, zero failed**
- `npm run build`: pass
- Playwright/Chromium acceptance: **4 passed, zero failed** (the portable test source included in this package was executed; browser dependencies were installed only in the disposable sandbox)
- 16 LEXA preview routes responded HTTP 200 in a real-browser route smoke check.

Browser checks covered route response/rendering, 390/768/1280px horizontal overflow, labelled login inputs, visible keyboard focus and keyboard traversal. They were *not authenticated* and did not validate refresh rotation, server-side revocation, tenant authorization or business writes.

The complete backend suite command was executed in the disposable Node 24 sandbox after installing `apps/api` with its `[dev]` dependencies; `python -m pytest -q tests apps/api/tests` and `python -m compileall -q apps/api/app apps/api/tests scripts` completed with exit code zero. Detailed test-count output could not be exported before that disposable sandbox stopped, so no exact remote Python count is asserted. The packaging workspace separately reports **116 passed, 1 skipped**; that one skip is caused by Redis not being installed in that local workspace, so it is not substituted for the dependency-complete sandbox result. The normal migration provenance checker retains six gaps; strict mode correctly fails. The new hash/separation checker was run locally and passed.

## 4. CI and repository controls

The updated candidate is `.github/workflows/lexa-ci.yml`. It includes a clean dependency install, full canonical backend test paths, Node 24 frontend typecheck/contracts/build, the reconstructed file hash/separation checker, the existing non-strict migration check, and an explicitly opt-in strict historical-source job.

The GitHub connector returned **403 Resource not accessible by integration** on feature-branch creation. `main` was unprotected at inspection. Therefore:

- no branch, commit or pull request was created;
- no CI workflow was installed or run on GitHub Actions;
- no branch protection/status-check rules were enabled;
- no claim is made that the checked candidate is merged or protected.

This CI candidate must go through an authorized GitHub branch/PR workflow; do not paste it into a source ZIP expecting the extractor to overwrite `.github/workflows/`.

## 5. Render/Vercel state

The LEXA Render `/health` and `/ready` endpoints each returned HTTP 200; the readiness payload reported database and cache healthy. That is a current availability check, not release acceptance. The Render metadata reported an empty `healthCheckPath` although source declares `/ready`; confirm the control-plane value before changing it. Only the existing live LEXA Render service was found—no separate LEXA staging service was available. Its auto-deploy setting was left unchanged.

The Vercel READY frontend SHA was `4dac83541badc21800f84e652f0f192c211a612a`; the latest live Render SHA observed was `a1ed64eec79daf3d74456c7b8b854d84f634d6fd`. These are not the same candidate. No Vercel config, deployment, Render setting or production release was changed.

## 6. Security boundaries

The canonical-clone inspection confirmed tenant isolation policies on the catalog tables described by the reconstruction. No blanket RLS rewrite was made, because global permissions, identity bootstrap/registration, migration metadata, tenant records and business tables have different access requirements. Price-unit and currency validation, product family cycle prevention, purchasing security, role mappings and tenant-qualified membership/branch constraints are explicitly represented as reconstructions/compatibility checks, not claimed as historical SQL.

No production SQL writes, production credential changes, role cutover, production deployment trigger or Render/Vercel config change occurred. Directly passing DB credentials into a remote shell was blocked; no workaround was attempted.

## 7. Phase 3 re-entry gates

Phase 3 implementation should stay paused until these gates pass:

1. **History:** recover original bytes for all six SQL sources from an authoritative archive, or obtain a documented approval to treat reconstructions as a new forward migration plan. Never mark reconstructions as recovered originals.
2. **Source integrity:** repair/recover the `021` source through a reviewed repository change; compare expected bytes to authoritative history and preserve hashes.
3. **Replay:** re-run the current hash-pinned equivalent chain from a fresh isolated database, compare columns, data types/defaults, all constraints, index definitions, RLS policy roles/USING/CHECK, grants, functions and triggers. Classify every delta; test critical behavior (tenant denial, price unit/currency, purchasing overlap/permissions, branch membership).
4. **CI:** install the workflow by an authorized GitHub PR, run Node 24 and dependency-complete Python tests on the immutable candidate SHA, and prove the same SHA’s checks pass. Then turn on branch protection and required status checks.
5. **Authenticated acceptance:** obtain approved LEXA staging or a dedicated isolated LEXA test service/account; record login, workspace selection, refresh rotation, logout/revocation, negative tenant reads/writes, representative business workflows, responsive widths and keyboard checks.
6. **Runtime & rollback:** verify Render health-check control-plane configuration, keep runtime role changes out of this stage, and write a rollback plan before any production deployment. Vercel and Render SHA must converge for the release candidate.

### Current decision

**Phase 0–2 discovery, scan, initial replay and frontend smoke tests: completed. Release gates: not complete. Phase 3: not yet approved for implementation against production.**

## Evidence files

- `reports/LEXA_Historical_ZIP_Recovery_Scan_2026-10-20.json`
- `reports/LEXA_Isolated_Schema_Replay_Diff_2026-10-20.json`
- `reports/LEXA_Phase2_Validation_Results_2026-10-20.json`
- `migrations/reconstructed_source_manifest.json`
- `scripts/check_migration_recovery_manifest.py`
