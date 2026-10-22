# LEXA Phase 3 write-path and replay correction — 2026-10-21

## Why this patch exists
Live Render logs recorded HTTP 500 on authenticated `POST /api/v1/organization/branches` and `POST /api/v1/catalog/categories` with SQLAlchemy `Could not refresh instance`. Tenant RLS state was transaction-local and cleared by commit; the next ORM refresh opened a new transaction without restored tenant context.

## Source fix
- Persist request tenant/user IDs in SQLAlchemy `Session.info`.
- Reapply `app.tenant_id` and `app.user_id` in the existing `Session.after_begin` hook for every transaction, using `SET LOCAL` so PgBouncer transaction pooling stays safe.
- Add a regression source-contract test.

## Clean replay issue
The root `migrations/021_phase5_analytics_foundation.sql` in the uploaded source contains literal escaped newline text and trailing non-SQL scripting text. Its valid counterpart is `lexa_v280_src/migrations/021_phase5_analytics_foundation.sql`, which passed isolated replay. Apply that source correction separately before relying on the root migration directory as a replay source.

## Validation and remaining gates
- An isolated empty-database replay ran migrations 001 through 030 successfully using labelled replacements and a replay-only composite unique key for brands before migration 004.
- Production migration 030 was applied after its data preflight counts were zero; forced RLS was verified on `tenant_invitations` and `membership_branch_assignments`.
- Do not declare Phase 3 complete yet. After this patch lands, run the backend test suite and authenticated write acceptance for branch/category create/update/delete, plus write/read flows for the remaining modules.
- `users`, `tenants`, and `registration_requests` remain RLS-disabled until pre-login and registration access moves to approved RLS-safe database functions/roles. Do not enable RLS on those tables before that refactor.
- The safe runtime role is staged but the Render credential cutover is not complete.
