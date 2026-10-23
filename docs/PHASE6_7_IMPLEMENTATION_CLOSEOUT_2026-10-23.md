# LEXA Phase 6 & 7 implementation increment — acceptance overlay

**Prepared:** 23 October 2026  
**Source revision inspected:** `dae8c615b09f555762d12a747e312c95d2b55a29` (GitHub `main`)  
**Disposition:** Implementation overlay; not merged by this session and not release acceptance.

## What the canonical source already contains

Phase 6 inventory intelligence is present in `apps/api/app/routes/inventory.py`, `apps/api/app/inventory_intelligence.py`, `apps/web/app/inventory/page.tsx`, and migrations `036`–`038`: location-specific replenishment policies, deterministic Decimal recommendations, movement-health signals, stock-age analysis, and read-only inventory integrity views. Recommendations are advisory and do not create purchase orders or stock movements.

Phase 7 purchasing is present in `apps/api/app/routes/purchasing.py`, `apps/api/app/purchasing_rules.py`, `apps/web/app/purchasing/page.tsx`, and migration `039`: supplier master data and effective costs, PO status lifecycle, partial receipts, cost variance reasons, landed-cost allocation, supplier returns, bill receipt matching and reviewed exceptions, payment allocation, and an append-only supplier ledger. The current canonical source includes the single `SupplierPaymentCreate.validate_allocations` model validator wired to `validate_payment_allocations`.

## New acceptance safeguards in this overlay

1. Adds a Playwright global setup that refuses write-enabled Phase 6/7 tests unless the target is a plain HTTPS origin, hostname is explicitly allow-listed, target is not a known production host, fixture identifies a disposable staging tenant and reset strategy, separate auth storage state exists, and `/api/lexa/ready` returns a ready staging/test environment with healthy database and cache. It does not print tokens, fixture values, or API body contents.
2. Adds a Phase 6 authenticated inventory acceptance journey: configure/upsert a location/variant policy, confirm idempotent update, re-compute reorder quantity from returned facts, check movement health and age analysis, verify restricted-location denial, and assert recommendation/read calls do not alter inventory balances or ledger IDs.
3. Adds a Phase 7 branch authorization journey: a manager cannot list, read or cancel a draft purchase order outside their assigned branch.
4. Extends the Playwright config and scripts to select these journeys explicitly and disables automatic retry for write-enabled workflows to prevent replaying partially completed fixture mutations.
5. Adds fixture templates and a static safety-contract suite.

## Acceptance commands (run from `apps/web`)

```bash
npm ci --no-audit --no-fund
npm run typecheck
node --test tests/*.test.mjs
npm run build
npm run test:e2e:phase6
npm run test:e2e:phase7
npm run test:e2e:phase7:security
```

Write-enabled E2E commands are gated and will be skipped/blocked until the separate staging host allow-list, staging readiness, QA storage state and disposable fixture are configured. They must never be run against `lexa-green.vercel.app` or `lexa-n10e.onrender.com`.

## Required environment for Phase 6 staging E2E

- `LEXA_BROWSER_BASE_URL` — isolated staging frontend origin, HTTPS only.
- `LEXA_PHASE6_STAGING_HOSTS` — comma-separated hostname allow-list containing only the exact staging hostname.
- `LEXA_PHASE6_ACCEPTANCE_FIXTURE_JSON` — contents based on `docs/PHASE6_STAGING_ACCEPTANCE_FIXTURE.example.json`.
- `LEXA_PHASE6_STORAGE_STATE` — path to the separate Playwright QA storage state file.
- `LEXA_PHASE6_ALLOW_STAGING_WRITES=1` — explicit opt-in, only for the staging job.

Phase 7's existing lifecycle suite uses the corresponding `LEXA_PHASE7_*` variables. The new branch-boundary suite additionally needs a restricted draft order ID on a branch the fixture manager cannot access.

## Workflow and ZIP import warning

This is an **overlay ZIP, not a complete source-tree ZIP**. Do not upload it by itself to the current repository ZIP extractor: that workflow requires both `apps/web/package.json` and `apps/api/app/main.py` at the ZIP root (or under one wrapper), and will skip/delete a standalone overlay. Merge these files into the full source archive/checkout first. The repository's ZIP extractor also intentionally protects `.github/workflows/`; a workflow inside any source ZIP will not activate. A maintainer with workflow write permission must copy `workflow_install_required/.github/workflows/lexa-ci.yml` to repository path `.github/workflows/lexa-ci.yml`, review it, and run CI on the exact resulting SHA. GitHub integration writes returned `403 Resource not accessible by integration`, so this overlay was not pushed or merged here.

## Still required for genuine “fully accepted” status

- Run the full backend test suite with Redis installed and no dependency-driven skip.
- Run `npm ci`, TypeScript typecheck and Next production build under Node 24 on this exact overlay plus the full repository.
- Execute the canonical migration replay against an empty disposable PostgreSQL database, including RLS/forced-RLS/role grant checks and rollback-only cross-tenant read/write probes.
- Run the Phase 6 and Phase 7 authenticated E2E jobs against the separate staging environment with disposable data; save failure/screenshot/trace artifacts while excluding auth state.
- Verify deployed Render and Vercel commit SHAs match; probe API readiness and test the real frontend-to-API route path.
- Complete production backup/restore and rollback readiness and obtain explicit approval before applying any production migrations.

No production Neon branch, backup contents, Render environment variables, Vercel settings or live financial/inventory records are changed by this overlay.


## Live alignment readout from 23 October 2026

- GitHub `main`, Render LEXA deployment metadata, and Vercel production deployment metadata all identify source SHA `dae8c615b09f555762d12a747e312c95d2b55a29`. Render reports the deployment live; Vercel reports READY and its `/api/lexa/ready` endpoint returned HTTP 200 with database/cache healthy. A direct Render readiness probe was not verified in this pass.
- Read-only Neon checks confirmed migrations 036–039 are recorded on the canonical main branch and forced tenant RLS plus one policy each exist on the Phase 6 replenishment table and six Phase 7 supplier finance tables.
- The `lexa_runtime` PostgreSQL role exists with `BYPASSRLS=true`, while `lexa_app` and `lexa_runtime_login_p3` are not bypass roles. Render's secret DB URL/login-role values were not inspected, so the live login identity cannot be certified. Do not approve release until the actual configured login role is verified through owner-controlled secure configuration and the app's runtime tenant read/write probes pass. No role flags or secret settings were changed.
