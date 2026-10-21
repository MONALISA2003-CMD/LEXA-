# LEXA Phase 5 — Increment 02 acceptance matrix

| Gate | Implementation/evidence | State |
|---|---|---|
| Multi-line checkout | Existing Increment 01 cart submits multiple lines through one commerce sale route | Source present; staging E2E pending |
| Partial payment/split tender | Staging test checks a 15,000 sale with 10,000 allocated and 5,000 due | Test authored; not run against database |
| Same-key checkout retry | Staging test replays identical payload and requires same sale ID | Test authored; not run |
| Sale/payment read-after-write | Sale detail now exposes recorded payment allocations and test totals them | Source tests pass; DB verification pending |
| Stock reconciliation | Staging test reads per-variant balance and SALE ledger reference before/after checkout | Test authored; not run |
| Cumulative refund cap | Source locks sale, sums prior recorded refunds, rejects refund above remaining collected balance | Helper tests + source contract pass; transaction E2E pending |
| Returns list branch scope | Active member/branch-assignment predicates added | Source contract passes; cross-branch API test pending |
| Sale detail payment/refund ledger | Response includes payment, return, and refund records after branch authorization | Source contract passes; browser/UI E2E pending |
| Cashier price override denial | Staging spec expects HTTP 403 for price override | Test authored; not run |
| Cashier discount denial | Staging spec expects HTTP 403 for discount | Test authored; not run |
| Manager positive pricing/discount path | Not included in this increment's staging spec | Pending before release |
| Cross-branch sale detail/returns denial | Branch checks are present; explicit test is not in the current staging spec | Pending before release |
| Backend test suite | `PYTHONPATH=. python -m pytest -q tests` | PASS — 19 tests |
| Backend compile | `python -m compileall -q app tests` | PASS |
| Frontend contracts | `node --test tests/*.test.mjs` | PASS — 3 test files |
| Full Node 24 install/typecheck/build | Clean install, typecheck, unit tests, production build | BLOCKED — current runner Node 22.16 and package missing from offline npm cache |
| Playwright E2E | Authenticated QA browser against allowlisted staging host | NOT RUN — requires staging URL and fixture |
| Preview deployment | Frontend/API source SHA, readiness, logs, smoke test and rollback evidence | NOT RUN |
| Production mutation | Production DB/service | NONE |

## Release rule

Increment 02 is a candidate, not release-accepted. Keep the opt-in Playwright writes disabled until a dedicated staging database, host allow-list, QA auth storage state and fixture have been prepared. Do not promote to production before every blocked gate has evidence.
