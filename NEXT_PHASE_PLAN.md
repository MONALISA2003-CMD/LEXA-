# LEXA next-phase plan after Phase 1

## Phase 1: Business-grounded assistant (this overlay)

- Local read-only answers for initial sales, payments, expense, gross-margin and stock-risk questions.
- Provenance, freshness, source links, response latency, tenant/branch authorization and no false zeros.
- External providers receive only screened general guidance questions. No model-driven business writes.

## Phase 2: Cross-module transaction acceptance

Create an authenticated synthetic staging journey proving one completed sale connects to stock movement and cost, payment/receivable allocation, revenue/tax journal, COGS/inventory journal, audit/outbox and refreshed insights. Include retries and duplicate idempotency keys, partial returns, credit and refund allocation, permission denial, and rollback cases. No production fixture data.

## Phase 3: Uganda integrations

Review the actual URA onboarding and accredited connector requirements, then test EFRIS in URA's approved test process before any production fiscalisation. Preserve real FDN, verification code, QR and authoritative acceptance/rejection evidence. Separately define a verified mobile-money/bank integration with webhook signatures, idempotency and ledger reconciliation. Recorded payments must never be presented as provider-confirmed.

## Phase 4: Better grounded intelligence

Expand the fixed read-only business query catalogue to authorized customer balances and supplier obligations after currency, scope, freshness and permission contracts are tested. Add deterministic daily-brief evidence links and safe explanation of inventory age/replenishment. Do not add arbitrary SQL, external data sharing, model-generated transactions or automatic purchasing.

## Cross-cutting exit criteria

- Full CI green on the exact source SHA.
- Node 24 typecheck and production build pass.
- Ordered clean migration replay, forced RLS verification and tenant/branch negative tests pass.
- Staging frontend and API deployed on one SHA.
- Read-only/provider privacy tests and authenticated E2E pass.
- Production migrations happen only after migration review, backup/rollback readiness and explicit release approval.
