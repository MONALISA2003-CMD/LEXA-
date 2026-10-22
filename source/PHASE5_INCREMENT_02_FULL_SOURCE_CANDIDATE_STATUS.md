# LEXA Phase 5 Increment 02 — Full-source candidate status

This is a **full project source candidate**, packaged repository-root relative from a preserved Phase 4 UX reset source archive plus Phase 5 Increment 01 and Increment 02 overlays. It is **not verified byte-for-byte against the owner-accepted Phase 3 final-cutover ZIP or the current GitHub `main`**, so reconcile source before replacing a canonical checkout.

## Verified locally

- Backend suite: 41 passed, 1 skipped. The skipped test requires Redis for auth-refresh integration.
- Frontend source-contract suite: 25 passed.
- TypeScript/TSX syntax scan: 34 implementation/config files, zero syntax diagnostics; this is not a typecheck.
- Production database changes: none. Deployment: none.

## Must pass before release

1. Reconcile the source against the accepted Phase 3 final-cutover snapshot and resolve every conflicting file.
2. On Node 24, run clean `npm ci`, `npm run typecheck`, `npm test`, and `npm run build`.
3. Run the explicit opt-in Playwright suite against a dedicated staging deployment with disposable seeded data and distinct cashier/manager sessions.
4. Prove manager-positive price/discount behaviour, cross-branch denial, checkout/payment reconciliation, stock ledger consistency, and cumulative refund denial.
5. Deploy frontend/API from one reviewed SHA to preview, verify readiness/logs, and record a rollback target before considering production.

The downloadable ZIP contains source and test artifacts; it does not configure secrets, create a deployment, or perform database writes. See `docs/PHASE5_INCREMENT_02_README.md` and `docs/PHASE5_INCREMENT_02_IMPLEMENTATION_REPORT_2026-10-21.md`.
