# Phase 5 Acceptance Matrix — Core Hardening Candidate

Date: 2026-10-21. This matrix supersedes the earlier Increment 03-only acceptance snapshot.

| Area | Current evidence | Status |
|---|---|---|
| Refund ceiling / repeat refund safety | Backend rules and route contracts; 170 backend tests passed | Local candidate pass |
| Partial-return discount/tax proration | Backend tests and request path | Local candidate pass |
| Duplicate sale-line protection | Pydantic line validator + regression tests | Local candidate pass |
| Original sale inventory cost on returns | Immutable sale inventory movements queried; original unit-cost helper tested | Local candidate pass |
| Non-stock item return handling | No stock-ledger write for non-stock variant; regression contract | Local candidate pass |
| Missing source inventory movement | Fail-closed conflict for still-stock-tracked variant | Local candidate pass |
| Return settlement journal / COGS reversal | Migration 034 applied and DDL/functions checked on QA branch | QA DDL pass; production not applied |
| Customer-credit liability mapping | Migration 034 QA validation | QA DDL pass; production not applied |
| EFRIS credit note integration | Migration function paths validated on QA branch | QA DDL pass; production not applied |
| No-refund / open receivable guard | Route and migration 035 | Local/QA pass; production not applied |
| Backend tests | 170 passed, 0 failed, 1 skip due local missing `redis` dependency | Partial local pass; CI must run skip-free |
| Frontend contracts | 27 passed under Node 22.16.0 | Pass for contracts only |
| Node 24 clean install/typecheck/build | Registry access failed (`EAI_AGAIN`) locally | Open; require CI on upload SHA |
| Authenticated Playwright business flow | No sanitized, isolated staging host/fixtures available | Open; production deliberately not used |
| Render/Vercel deployed revision | Latest observed deploys both reference `a6acc0eb53660ea938a314640bf28283ae2a98a8` | Same-SHA baseline parity pass; candidate not deployed |
| Production migrations 033–035 | Not applied to production | Open; require review/approval |
| Exact historical migration bytes | Six originals missing; migration-032 source gap also documented | Provenance gate open; substitutes not misrepresented as originals |
| Phase 6 | Contract documentation and separate gate policy committed inside candidate package | Non-destructive implementation unblocked; production/destructive integration remains gated |

## Exit criteria for Phase 5 release acceptance

1. Upload candidate to GitHub and capture exact resulting SHA.
2. CI for that SHA passes complete backend tests (including Redis integration) and Node 24 `npm ci`, typecheck, contracts, and production build.
3. Render and Vercel deploy exactly that SHA and both pass readiness checks.
4. Disposable clean replay and authenticated staging Playwright acceptance pass with deterministic fixtures.
5. Production migration rollout for 033–035 is reviewed, approved, and executed with a documented rollback plan.
6. Historical provenance gaps remain explicitly disclosed unless original bytes are recovered; forward release must carry approved semantic replacement/replay evidence instead of asserting false byte parity.
