# LEXA Phase 3 — Increment 01 Acceptance Matrix

This matrix is deliberately separate from the fast source/handler tests. Run against a disposable Neon branch and a non-production web deployment after the source patch is reviewed. Never run tenant-mutating scenarios against production data.

## API/database acceptance

| Scenario | Expected result | Evidence to capture |
|---|---|---|
| Create business profile with valid key | 201; one profile, one audit row and one outbox event | request/response, DB query result, request key redacted or test-only |
| Retry exact profile-create request/key | Stable replay; no duplicate row/event | same response resource ID and unchanged counts |
| Reuse profile key with different body | 409; no extra mutation | status/body and unchanged DB counts |
| Update profile with partial patch | 200; only sent fields change | before/after rows, audit and outbox rows |
| Empty profile/branch patch | 422; no writes | response and unchanged audit/event counts |
| Create/update branch | 201/200; audit/event in transaction | response plus database evidence |
| Cross-tenant branch ID on PATCH | 404; no field disclosure or write | tenant A request for tenant B ID and unchanged rows |
| Cross-tenant branch-to-warehouse assignment | 400; no warehouse row | tenant IDs, response and unchanged rows |
| Cross-tenant warehouse-to-location assignment | 400; no location row | tenant IDs, response and unchanged rows |
| Missing idempotency header on mutation | 422; no write | response and unchanged DB counts |
| Forced transaction failure during create/update | All business, idempotency, audit and outbox changes roll back | DB query after injected fault |
| Same key concurrent requests | One committed mutation; deterministic replay or safe conflict | repeated concurrent run plus DB counts |

Test with two test tenants and at least two branches. Verify requests under one context cannot read or mutate the other tenant's resources. Also inspect actual grants/RLS as the application role; ORM filtering is not a substitute for database policy checks.

## Frontend acceptance

| Scenario | Expected result |
|---|---|
| Profile absent | Setup prompt and create profile form appear; no claim that setup is complete |
| Profile read fails | Clear error; writes disabled until all configuration datasets can be loaded |
| Create profile then refresh | Saved profile is fetched from the API and shown |
| Update a profile field | Changes persist after reload; no duplicate create action |
| Create/edit branch | API-backed row appears after reload; duplicate-code conflict is readable |
| Warehouse association | Selector only offers branches returned for current workspace |
| Add location | Selector only offers warehouses returned for current workspace |
| API returns 403/409/503 | Helpful error shown and entered data remains available for retry |
| Keyboard-only navigation | All controls reachable; visible focus, labels and live status messages work |
| Mobile/responsive widths | 360, 390, 768, 1024 and 1440 px without horizontal overflow or clipped forms |

## Release gate

Record the exact candidate SHA, Node version, clean-install output, backend test count, frontend typecheck/test/build results, Postgres/RLS results, browser test report, Render health path and deployed SHA, Vercel deployed SHA, backup/PITR evidence, and rollback owner. Do not ship if a required check is missing or if production schema/role gates remain unapproved.
