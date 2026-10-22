# LEXA 2.14.0 — Connected Sales & Operations Implementation Handoff

**Date:** 22 October 2026  
**Source candidate:** `2.14.0+connected-sales-chat.candidate.20261022`  
**Release status:** source candidate only; not deployed or database-accepted.

## What was implemented

### 1. Sales, pricing and tax integrity

- The server resolves the applicable tax rule by tenant, product/category/default scope and selected business date. Client-posted tax rates are not trusted as the source of truth.
- Checkout preview handles exclusive and inclusive tax and applies the line discount before tax. Existing sales retain their recorded tax snapshot rather than changing when a rate changes later.
- Price-list changes and line discounts are checked against server-side permissions. Hiding an input in the browser is only a user-experience affordance, not authorization.
- Sales and returns retain a business date. Journal posting and period-based reporting should follow that date rather than a machine's current date.

### 2. Inventory and accounting links

A completed sale is expected to preserve this relationship:

`Sale + lines → stock movement at recorded cost → payment allocations/receivable → revenue/tax journal → COGS/inventory journal → audit/outbox → analytics refresh → optional fiscal document queue`.

- COGS now recognizes the lower-case `sale` reference type written by checkout.
- Sale stock issues capture the inventory ledger's cost instead of zero, so stock value and gross margin are not silently overstated.
- Returns remain compensating transactions; they do not erase or mutate the original posted sale. Existing source flow includes partial return proration, refund caps, customer credit and reversal journals.
- Migration 041 includes the sale business date and aligned posting/report/analytics functions. It has not been executed or replayed against PostgreSQL in this package run.

### 3. Analytics refresh

- Migration 041 creates a durable queue coalesced by tenant and business date, a bounded retry/dead-letter lifecycle, `FOR UPDATE SKIP LOCKED` worker processing and forced RLS.
- The API lifespan starts a bounded poller in production configuration. It idles safely before the queue routine exists and does not require a second paid worker service.
- Dashboard analytics refresh should not perform expensive global aggregation inside each checkout transaction. Before release, verify retry behavior, idempotency, queue age, worker privileges and operator visibility using actual PostgreSQL.

### 4. Internal Team Chat

- Responsive Team Chat workspace for desktop, tablet and phone.
- Tenant-scoped threads with optional branch scope, RBAC read/send checks, branch authorization, idempotent message send, message pagination and read/unread state.
- Messages are limited to 4,000 characters and append-only for the ordinary runtime role. Audits/outbox contain event metadata rather than message bodies.
- Migration 042 creates the chat/conversation/read-state tables, tenant constraints, forced RLS, scoped policies, indexes, grants and permissions.
- This is internal operational chat, not AI chat. File uploads, presence, push notifications, external WhatsApp/SMS/email delivery and retention/legal-hold workflows are not claimed as completed.

### 5. EFRIS safety boundary

- The ordinary LEXA setup page cannot simply declare the taxpayer registered and active. System-to-system status must come from a genuine approved adapter/verification flow.
- No FDN, official receipt number, verification code or QR is generated locally.
- Credit-note fiscalization is queued only when the source sale has an accepted fiscal invoice from the actual authority workflow.
- Actual URA API connectivity remains blocked on official system-to-system onboarding, API specifications, certificate/signature requirements, registered taxpayer/device details, credentials and the URA test environment.

### 6. Hosting/readiness

- Database pool size/overflow/timeout/recycle values are configurable and hard bounded per API process.
- Scale target: 5,000 registered/active user accounts is not the same as 5,000 concurrent users. A proposed first load acceptance is 250 concurrent users, then separately review higher traffic.
- No 5,000-user capacity claim is made before testing Vercel request patterns, Render API instance size/concurrency, aggregate connection pool budget, Neon compute/pooled connections, Redis/rate limits, queue lag, and p95/p99 latency.
- Candidate must be run through the guarded 46-input disposable database replay, RLS/cross-tenant probes, Node 24 clean install/typecheck/build, authenticated staging journeys, load tests and backup/restore drill.

## Local verification

| Check | Result |
|---|---:|
| Backend Python tests | **279 passed, 0 failed** |
| Frontend contract tests | **57 passed, 0 failed** |
| Python compileall | **Pass** |
| TypeScript/TSX syntax transpilation | **36 files, 0 syntax errors** (global TS 5.8.3; syntax only) |
| Migration input plan | **46 inputs; hash plan passed** |
| SQL execution in this run | **None** |
| Full Node 24 Next.js build | Not run; available environment is Node 22 and offline dependency installation is incomplete |
| Authenticated browser E2E | Not run |
| Production DB/deployment changes | **None** |

Migration bundle SHA-256 (plan-only): `8d1e7f77051550258fc6784526d48fb6899b0cb3deaade1bd896380c4e2a9957`.

## Integrations: implemented vs. not yet connected

| Integration | Current state | Next required step |
|---|---|---|
| URA EFRIS | Fiscal document records/queue and guarded workflow; no live transmission claim | Complete URA onboarding and approved API adapter, then test with URA sandbox/certificates |
| Mobile money/bank | LEXA records the selected method and amount; no automated transfer/settlement verification | Select provider(s), use approved API/webhook signature verification, idempotent callbacks and settlement reconciliation |
| Accounting packages | LEXA double-entry journal/account mapping foundation exists; connectors are not claimed live | Build reconciled exports/imports for agreed provider and map accounts/periods explicitly |
| WhatsApp/email/SMS | Not externally connected by this candidate | Choose official provider, consent/delivery policy and outbox-backed connector |
| POS/e-commerce imports | No provider-specific live connector claimed | Agree supported systems and build idempotent import contracts and reconciliation reports |
| AI | Deliberately deferred | First accept commerce, accounting, security, EFRIS, chat and scale fundamentals |

## Release blockers that must remain visible

1. Live `lexa-live` was read-only audited at migration 031; the source candidate now includes 041 and 042 but also depends on pending supplier/Phase 8 schema in 033–040. Never run a clean replay on live business data.
2. The actual SQL chain through 042 has not been applied to an isolated PostgreSQL database in this package session. Plan/hash validation is not semantic SQL validation.
3. Full Next.js TypeScript validation/build under the configured Node 24 runtime has not run. Global TypeScript syntax transpilation is not equivalent.
4. No authenticated browser E2E, backup restore test, or load/capacity test was completed.
5. Candidate source has not been pushed or deployed. A previous GitHub connector write returned HTTP 403; no live database or hosting changes were made.

**Rollout rule:** keep this as a candidate until the team reviews the diff, validates on disposable PostgreSQL + staging, restores a tested backup plan, proves tenant isolation, completes EFRIS onboarding where applicable, and confirms a new successful Vercel build and Render deployment on the exact same approved source revision.
