# LEXA Phase 5 acceptance matrix — Increment 01

| Gate | Required evidence | Current state |
|---|---|---|
| Multi-line checkout UI | Add/edit/remove several lines; calculate display subtotal | Implemented; source tests pass |
| Server-owned sale posting | One request posts all lines, stock changes, accounting and payments atomically | Existing route reused; integration E2E pending |
| Checkout retry safety | Identical payload retry uses stable idempotency key | Implemented and source-tested; live retry test pending |
| Payment allocation checks | No overpayment; partial amount requires customer; no accidental zero-payment walk-in sale | Client validation added; API remains authoritative; integration test pending |
| Price override boundary | Cashier uses catalogue price; authorized pricing role can override | API guard implemented; DB role test pending |
| Discount boundary | Discounts require `sales.manage` | API guard implemented; DB role test pending |
| Sales history search/date/status/branch | Bound filters, pagination, authenticated member's branch scope | Implemented and source-tested; API DB test pending |
| Sale detail authorization | Branch-level read check on sale detail endpoint | Implemented and source-tested; cross-branch API test pending |
| Receipt print view | Item values/totals readable and printable | Implemented; browser/printer check pending |
| Currency awareness | Amounts/payment channel use workspace currency | Implemented; multi-currency integration test pending |
| Frontend contract suite | `node --test apps/web/tests/*.test.mjs` | PASS — 25/25 |
| Backend suite | `python -m pytest -q apps/api/tests` | PASS — 31; 1 optional auth-refresh test skipped |
| Python compile | `python -m compileall -q apps/api/app apps/api/tests` | PASS |
| TypeScript syntax | Transpile syntax scan across `.ts`/`.tsx` | PASS — 33 files; zero syntax diagnostics |
| Full Node 24 install/typecheck/build | Clean install, `typecheck`, tests, Next production build | BLOCKED — install stalled; only Node 22.16 available |
| Authenticated browser E2E | Cashier/manager price and discount, multi-line payment, read-after-write | NOT RUN |
| Preview verification | Frontend/API deployed from one SHA; smoke checks and rollback path | NOT RUN |
| Production data changes | None during this increment | CONFIRMED — none performed |

## Release rule

Do not promote this increment based solely on source-contract tests. The blocked gates above must pass against a reviewable source revision before Phase 5 increment 01 is release-accepted.
