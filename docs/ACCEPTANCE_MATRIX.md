# Acceptance matrix — Phase 3 Increments 01–03 deep candidate

| Area | Candidate criterion | Current evidence | Remaining acceptance gate |
|---|---|---|---|
| Workspace selection | Zero, one and multiple membership cases; forged tenant ID denied | Existing login picker inspected; new source uses active-membership function | API integration + browser tests with 0/1/2 tenants, inactive destination and forged UUID |
| Session switching | Old session revoked before tenant GUC changes; new refresh cookie/token bound to chosen tenant | Source-contract test | Two-tenant Postgres transaction/RLS test; refresh rotation and old-token rejection E2E |
| Setup progress | Progress resumes from durable configuration; no stale shadow flag | Unit tests of pure derivation + source contract | Live DB tests for partial records, retries, deactivated configuration and all-step completion |
| Invitation token | Raw token not persisted; hash lookup, expiry and one-time consumption | Source-contract tests + migration review | Live Postgres race/replay/expiry tests; confirm function privileges with real app role |
| Invite email/account binding | Existing user's password verified; new invitee can set password only for invited address | Source inspection | Credentialed E2E for existing/new users, duplicate memberships, disabled user and token guessing limits |
| Invite lifecycle | Create, resend, revoke, replay; resend invalidates previous token | Source-contract tests | Concurrent create/resend/revoke tests and confirmation email delivery strategy (current UI displays a private one-time link; no mail provider connected) |
| Membership status | Tenant-scoped listing/update; session revocation; last active owner protected | Source-contract tests | Isolated Postgres tests under runtime role, concurrency test for two simultaneous owner removals |
| Branch assignment data | Only active same-tenant branch IDs accepted; composite FK prevents cross-tenant pair | Source-contract tests + candidate SQL | Live RLS/constraint tests. Assignment CRUD is not equivalent to effective branch authorization. |
| Migration source | Additive, preflight guards, RLS and role permission seed | Static check only | Blocked pending recovery of historical migrations 010/011/023–026, repair of 021, clean full replay and schema parity |
| Frontend | Workspace selector, resumable onboarding, invitation acceptance and team UI | Node source-contract tests | Node 24 clean install, application `typecheck`, frontend tests/build, real-browser accessibility/responsive E2E |
| Remote delivery | Branch, CI, PR and reviewed acceptance | Not performed | GitHub integration 403 must be resolved; no production deploy until release gates pass |
| Branch-level enforcement | NOT ACCEPTED | Assignment CRUD is implemented; business APIs and database policies are not yet consistently wired to enforce it | Integrate authorization on each branch-scoped route and prove cross-branch denial in Increments 04–05. |
