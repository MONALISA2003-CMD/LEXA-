# Phase 5 Increment 02 — checkout-integrity hardening

This is a **repo-relative overlay**, not a full repository archive. Apply it to the current reviewed LEXA source after reconciling the commerce files with the exact accepted Phase 3 handoff. It does not include secrets or environment files.

## Contents

- Refund-balance helper and unit/source-contract tests.
- Branch-scoped returns list and payment/return/refund ledger detail fields.
- Responsive payment/refund presentation in the existing sale detail panel.
- Opt-in Playwright staging acceptance spec.
- Implementation report, acceptance matrix, and a sample fixture below.

## Local tests

From `apps/api`:

```bash
PYTHONPATH=. python -m pytest -q tests
python -m compileall -q app tests
```

From `apps/web`:

```bash
node --test tests/*.test.mjs
```

These do not replace a clean Node 24 installation, full typecheck, production build, database integration test, or authenticated browser acceptance.

## Safety requirements for the opt-in browser test

The new `e2e/phase5-sales-acceptance.spec.ts` creates a sale and a return. It deliberately skips unless all these are present:

- `LEXA_BROWSER_BASE_URL` points to a dedicated non-production staging deployment.
- `LEXA_PHASE5_STAGING_HOSTS` contains the exact staging hostname.
- `LEXA_PHASE5_ACCEPTANCE_FIXTURE_JSON` contains a fixture whose `environment` is exactly `staging`.
- `LEXA_PHASE5_STORAGE_STATE` or `LEXA_PHASE4_STORAGE_STATE` points to a non-production cashier session.
- `LEXA_PHASE5_ALLOW_STAGING_WRITES=1` explicitly enables writes.

Never put production cookies, bearer tokens, customer data, or credentials in the fixture or commit them to the repository. The fixture IDs must all refer to disposable staging records.

Example fixture: `PHASE5_STAGING_ACCEPTANCE_FIXTURE.example.json`.

## Known limitations before release

The Playwright spec is authored but has not been executed in this environment. Manager positive permission tests, explicit cross-branch denial tests, full Node 24 typecheck/build, preview deployment, and a complete authenticated staging run remain mandatory release gates. No production database or deployment was changed by this overlay.

For manager checks, provide `LEXA_PHASE5_MANAGER_STORAGE_STATE` as a separate manager QA session. The positive permission test posts one additional test sale using a price override plus a discount, so ensure the selected stock variant has enough stock. To run cross-branch denial coverage, extend the fixture with `cross_branch_sale_id` from a branch the manager is not assigned to; `cross_branch_sale_line_id` and `cross_branch_return_id` are optional seeded IDs used for return/list leakage assertions. These writes and reads must remain in the disposable staging workspace. Keep these values within the disposable staging workspace.
