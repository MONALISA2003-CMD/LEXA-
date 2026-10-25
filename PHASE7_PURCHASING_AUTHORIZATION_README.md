# LEXA Phase 7 — Purchasing, Authorization and Reconciliation

**Prepared against GitHub `main`:** `1a430ba1b6f3d82eddfa7e52d6379b514d4ccdf1` (25 October 2026)

This is a root-relative overlay for LEXA's existing ZIP Extractor. Upload the ZIP at the repository root while `main` is selected. Do not unpack it manually on your phone. The extractor will put each file at the matching repository path and start the configured GitHub workflow.

## What this increment adds

### Purchase authorization
- Tenant-scoped, currency-specific approval limits per role.
- Approval fails closed when a non-Owner/non-Administrator approver has no configured limit for the order's currency or the order exceeds the strictest applicable role limit.
- Owner/Administrator are explicit override roles; a reason is required above the highest configured limit.
- The approval limit is enforced both in the API workflow and in a PostgreSQL trigger. Policy changes are audited and use forced tenant RLS.

### Supplier-return reversals
- Posted supplier returns can be reversed only once, with an idempotency key and a required reason.
- Reversal posts compensating positive stock-ledger movements, an append-only supplier-ledger debit and a reversing journal against the original posted return journal. It does not delete or rewrite the historical return records.
- A missing original supplier credit, source receipt, or source stock-ledger movement stops the reversal instead of silently changing only one ledger.

### Supplier/accounting reconciliation
- Adds a read-only purchasing reconciliation endpoint and workspace page.
- Compares stock balances to the inventory ledger; checks that posted receipts and supplier-ledger entries have journals; checks posted journals balance; compares supplier subledger to accounts payable/advances; and compares purchase inventory cost movements to inventory journal value by currency.
- It fails closed for users without full branch visibility and does not net different currencies or repair records automatically.

### Database and accounting
- Adds forward-only migration `048_phase7_approval_limits_reversals_accounting.sql` and adds migrations 047 and 048 to the disposable clean-replay sequence in `migrations/reconstructed/clean_replay_order.json`.
- Establishes accounting mappings for goods-received-not-invoiced, landed-cost clearing, purchases clearing, supplier advances and cost variances. Trigger-only `SECURITY DEFINER` helpers explicitly revoke default `PUBLIC` and runtime-role execute privileges.
- Adds receipt and supplier-ledger posting triggers to create balanced journals in the same transaction, plus safe backfill of existing posted purchasing records.
- The API readiness endpoint fails closed until migration 048, forced RLS/policy, approval guard and accounting triggers are present.

### Acceptance coverage
- Pure Decimal approval-limit rules and source-level safety contracts.
- Playwright acceptance for over-limit/within-limit approval, partial payment allocations across bills, supplier-return reversal and post-workflow reconciliation.
- All write-enabled browser tests are skipped by default. They require an explicitly allow-listed HTTPS staging host, a throwaway tenant/fixture, authenticated QA state, and the corresponding `LEXA_PHASE7_*_ALLOW_STAGING_WRITES=1` opt-in. Production hosts are blocked.

## Checks run on this ZIP's source files

- Python compilation: PASS.
- Phase 7 approval-limit and reversal contract tests: **15 passed**, including the trigger-helper execute-privilege contract.
- Phase 7 frontend approval/reversal contracts: **4 passed**.
- TypeScript/TSX syntax transpilation: **7 files, zero syntax diagnostics**. This is not a substitute for the complete Next.js typecheck/build.
- Replay-order JSON parse: PASS — 52 unique inputs, with 047 and 048 last. This verifies the manifest structure only; no PostgreSQL SQL replay was executed.

## Release boundary — read before deployment

This ZIP has not been committed by this handoff and no hosted CI run has tested this new overlay yet. The existing `main` green CI run is a baseline, not proof that this increment is green. After upload, verify the new GitHub Actions run on the resulting commit. The complete repository `npm test`, `npm run typecheck`, `npm run build`, and API suite must pass there.

Migration 048 has **not** been applied to any database by this handoff. It is a forward-only database change and its posted-record backfill and accounting triggers require an actual reviewed disposable PostgreSQL replay, a confirmed backup/restore path, and explicit production approval before production application. The replay plan now includes migrations 047 and 048, but the existing CI workflow does not execute that replay automatically. The read-only readiness gate intentionally reports not-ready until the required schema is installed; do not declare the deployed API ready before that migration is applied and verified.

The authenticated browser acceptance tests have not been executed against a real isolated staging fixture in this handoff. Their fixture setup and write switches are intentionally not included as live credentials.
