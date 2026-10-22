# LEXA sales integrity and 5,000-user readiness

**Status:** implementation candidate; not production acceptance. This document is specific to LEXA.

## Canonical sale workflow

A completed sale should be one database transaction that creates the business transaction and saved line facts, resolves tenant tax configuration for the selected business date, records inventory movements at the stock ledger's current average cost, allocates recorded payments, creates a receivable for any balance, posts the sale and cost-of-goods journals, records an audit trail and durable outbox events, and queues fiscalization only when an approved connector is verifiably active. Repeated client requests must use the same idempotency key and payload. Failed steps roll the transaction back; later corrections are compensating returns/credit notes, not edits to posted financial facts.

## Implemented in this candidate

- Sales checkout resolves the server-side effective-dated product/category/default tax rule; the browser's rate is not authoritative.
- Checkout product data includes the tax mode and effective rate for the selected business date, and the cart preview adds exclusive tax or extracts inclusive tax rather than assuming every price is tax-exclusive.
- Sales and returns persist a business date. Accounting journal posting and reports should use that recorded date, not the host's current date or completion timestamp.
- COGS posting recognizes the lower-case `sale` reference type currently written by checkout. Product gross margin is calculated excluding output tax and including tax reversal on returns.
- EFRIS status is not self-declared in the ordinary setup UI. Selecting system-to-system mode leaves registration pending until the genuine approved adapter completes verification. Queueing a document is not treated as URA acceptance.
- Database pool size/overflow/timeout/recycle limits are environment-configurable and hard bounded per process.

## Team collaboration

The source candidate includes an internal Team Chat for staff coordination, scoped by tenant and optional branch. Messages are permission-gated, saved through an idempotent API, limited to 4,000 characters, append-only under the runtime role, audited, and represented in outbox metadata without placing message bodies in the event payload. Conversation membership/presence, file uploads, push notifications and external messaging are not claimed as implemented; those need separate product/security decisions and staging acceptance.

## External integrations

### URA EFRIS

Complete the real adapter only after URA system-to-system onboarding provides the approved endpoint specification, taxpayer/device registration flow, certificate/signing approach, credentials and test environment. The adapter must use timeouts, idempotency/request hashes, retries with backoff, immutable request/response evidence, FDN/verification code/QR storage, and explicit `PENDING`, `SUBMITTED`, `ACCEPTED`, `REJECTED`, `FAILED`, and void/credit-note states. Never create an FDN, verification code or QR code locally. A credit note is queued only when the source sale has an invoice accepted by URA; its metadata links the source sale and accepted fiscal-document record. It preserves the audit trail.

### Payment and accounting providers

Provider-verified mobile-money or bank collections require a provider's supported API credentials and webhook verification. A typed payment-method record is not evidence that money settled. Store provider transaction IDs only after validating signatures and verify callbacks idempotently; reconcile provider settlements with LEXA's payment ledger. Accounting package exports must be generated from posted journal entries, map accounts explicitly, and be reconcilable back to source sale/payment identifiers.

### CRM, messaging and commerce

Future connectors may include official WhatsApp Business messaging, email/SMS, e-commerce/POS imports, and accounting exports. They should subscribe to versioned outbox events, never issue duplicate sales on retries, and obey consent, tenant access and delivery status rules. Avoid storing tokens in ordinary integration tables or exposing provider secrets in the UI. AI remains out of scope until operational correctness is accepted.

## Scale plan: 5,000 named users vs concurrent workload

5,000 registered accounts is different from 5,000 simultaneous requests. Set an explicit target before capacity acceptance—for example 5,000 active user accounts and a load profile covering 250 concurrent users, followed by a separately approved higher-concurrency test if needed. The current one-instance Render Free service and current live schema drift are not proof of this capacity.

- Use Neon pooled connections (`-pooler` host with TLS) and keep the sum of pool sizes across all API workers below the database's connection budget. Tune `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `DATABASE_POOL_TIMEOUT_SECONDS`, and `DATABASE_POOL_RECYCLE_SECONDS` using measured load, not guesswork.
- Keep tenant scope derived from the validated session, and test row-level security, branch scoping, permission denial and cache-key tenant isolation with two synthetic tenants on every release.
- Load test read-heavy dashboards, product search, paginated sales history, concurrent checkout for the same SKU, idempotent checkout retry, returns, purchasing and report export. Capture p50/p95/p99 latency, error rate, database CPU/connection waits, lock waits, Redis failures, queue age and EFRIS backlog.
- Use bounded requests, search length/row limits, pagination, indexes aligned to tenant + business date + status, statement/lock timeouts, request IDs and structured redacted logs.
- Outbox-driven analytics now uses a durable tenant/date queue, a five-second coalescing window, `FOR UPDATE SKIP LOCKED`, bounded retries and dead-letter status. The LEXA API lifespan includes a bounded poller that is activated in production and idles safely until migration 041 exists, avoiding a separately billed worker process. Do not run expensive aggregate refresh work synchronously in a sale transaction. Operator-facing queue inspection/replay is still a release acceptance item.
- Confirm Render paid instance/concurrency needs, Neon compute/pool settings, backups/point-in-time restore and recovery objectives only after the staging load test.

## Release gate

Do not deploy the new route/migration candidate to the current live database until the canonical migration chain through 042 has been reconciled and validated on a disposable PostgreSQL replay, then migrations 041 and 042 are tested in order. The live `lexa-live` migration ledger was observed at 031 on 22 October 2026; supplier and Phase 8 schemas required by current source were missing. Never run a clean replay against live business data. Require a successful Node 24 Next.js build, API tests, migration replay, tenant-isolation tests, authenticated browser workflows, backup/recovery verification, load testing and staging smoke tests before production rollout.
