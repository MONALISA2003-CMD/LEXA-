# LEXA Phase 5 acceptance matrix — increments 01–02

Latest status is documented in `PHASE5_INCREMENT_02_ACCEPTANCE_MATRIX.md`. This matrix preserves the sales cockpit requirements from Increment 01 while tracking the additional checkout-integrity work.

| Gate | Evidence | State |
|---|---|---|
| Multi-item checkout and filtered sales history | Frontend/source-contract test | PASS — source contract only |
| Server-owned sale posting and payment allocation | Existing commerce transaction path; staging acceptance test authored | Staging verification pending |
| Stable idempotency retry | Same-key replay check encoded in Playwright staging spec | Test authored, not run |
| Partial payment / split tender | 15,000 sale / 10,000 collected fixture with 5,000 due | Test authored, not run |
| Sale detail payment/return/refund ledger | API detail response and UI display changes | Source contract passes; database E2E pending |
| Cumulative refunds do not exceed total amount collected | Locked sale, prior recorded refund sum, remaining balance helper | Unit/source tests pass; concurrent DB E2E pending |
| Return list branch scope | Active membership and active assigned branch filters | Source contract passes; cross-branch E2E pending |
| Cashier cannot override price / discount | Explicit 403 expectations in staging suite | Test authored, not run |
| Manager positive override/discount permissions | No authenticated positive-role run in this increment | Pending |
| Cross-branch detail and returns denial | Server-side scope exists; explicit tests still required | Pending |
| Backend tests | `PYTHONPATH=. python -m pytest -q tests` | PASS — 19 tests |
| Backend compile | `python -m compileall -q app tests` | PASS |
| Frontend source contracts | `node --test tests/*.test.mjs` | PASS — 3 test files |
| TypeScript syntax scan | Four changed `.ts`/`.tsx` files transpiled for syntax | PASS — 0 syntax diagnostics; not a full typecheck |
| Clean Node 24 install, full typecheck, production build | Must run on exact proposed source tree | BLOCKED in current runner (Node 22.16 and unavailable offline package) |
| Authenticated staging E2E | Seeded non-production records, explicit host allow-list, QA storage state | NOT RUN |
| Preview deployment and rollback evidence | Frontend/API from one source SHA plus smoke checks | NOT RUN |
| Production mutation | No live sales, payments, returns, stock changes or deployment | NONE |

## Release decision

**Candidate only — not release-accepted.** Staging writes must remain disabled until a dedicated staging host, disposable fixture records and non-production authentication state are in place. Promote only after all pending gates have evidence.
