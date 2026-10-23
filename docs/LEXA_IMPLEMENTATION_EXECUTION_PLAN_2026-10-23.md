# LEXA performance, resilience and scale-up implementation plan

**Working rule:** retain every existing dashboard and business workflow. The target is to make the existing product faster and more dependable, not to reduce its feature set. Product billing/subscriptions remain the final implementation phase.

## Execution order

### Gate 0 — Establish the baseline and protect production

- Record the source commit, live frontend/API deploys, current service plans and available request metrics before edits.
- Use a non-production change branch and CI before merge; main is connected to automatic deployments.
- Do not write to the authoritative Neon business database, apply migrations to it, change production secrets, alter paid plans, or trigger a production deployment as part of this work.
- Record P50/P95/P99 for warm and cold requests, including the API health/readiness paths and normal authenticated business pages. Separate browser-to-edge duration from API processing duration.

### Phase 1 — Observability and reproducible containers (started in this candidate)

- Emit an API `Server-Timing` header, preserve `X-Request-ID`, and log slow requests using safe metadata only (method, route path, status, duration and request ID; never query values or request bodies).
- Forward the API timing header through the Next.js same-origin proxy.
- Provide Dockerfiles for the existing FastAPI/Python service and Next.js service, with non-root runtime users and health checks.
- Provide a Compose stack for local Postgres, Redis, API, web and a separate analytics worker. Local Compose does not auto-apply database migrations; this avoids accidental changes to an unknown database.
- Add and run helper/contract tests. CI must run against Node 24 and the declared Python test dependencies before release.

**Acceptance:** timing header and request ID can be correlated in browser/network tools and service logs; helper tests pass; Python source compiles; container images build; Compose health checks pass after the disposable local database is prepared; no existing dashboard route/component is deleted.

### Phase 2 — Find and remove measured bottlenecks

- Measure first, then optimize specific slow API endpoints, SQL plans, serialization work, startup work and unnecessary duplicate requests.
- Keep existing dashboards and all their data. Use parallel reads, progressive rendering and request de-duplication where evidence shows a gain, without hiding or deleting modules.
- Add tenant-safe caching only for suitable read-only/reference data, with explicit invalidation and authorization before data access. Do not cache sensitive tenant responses in a shared global cache.
- Tune connection pools against the actual Neon connection/pooler budget; total capacity is per process multiplied by API/worker replicas.
- Run representative concurrent load against disposable staging, not production.

**Acceptance:** measured before/after latency is published by route and percentile; no tenant leakage; no regression in business calculations or action controls; error rate and database-pool wait do not worsen.

### Phase 3 — Recovery and workload isolation

- Maintain distinct liveness and readiness semantics: liveness indicates the process can run; readiness checks the dependencies required to serve traffic.
- Add bounded connection, request and provider timeouts, retry only safe/idempotent operations, and test shutdown/rollbacks.
- Run the durable analytics refresh worker separately when the target deployment supports it. Do not disable the existing embedded worker in Render until a replacement worker is live and verified; otherwise analytics refresh jobs may stall.
- Keep transactions, audit records, tenant isolation and permission checks in the deterministic application path.

**Acceptance:** a dependency interruption returns a safe response; the app recovers without data loss or duplicate financial/stock actions; background queue processing is demonstrated before its old runner is disabled.

### Phase 4 — Load balancing, Docker and Kubernetes

- Verify web/API instances are stateless enough to scale and that session, idempotency, queue and file state are externalized or durable.
- Publish versioned, immutable container images and deploy at least two API replicas behind a Kubernetes Service; use readiness probes so unready pods receive no traffic.
- Start with conservative database pool settings and a bounded replica maximum. Raise limits only after Neon pool capacity and load-test results support it.
- Use a separate worker deployment, resource requests/limits, graceful shutdown, disruption budgets and horizontal pod autoscaling. Supply secrets through the cluster secret manager rather than Git.
- Keep Render as the current live API host until a separate Kubernetes environment is provisioned, tested and approved. Render itself is not the Kubernetes cluster.

**Acceptance:** two-pod traffic distribution confirmed; pod restart and rolling deployment do not interrupt accepted requests or lose queued work; autoscaling/rollback exercised in staging; live data source is unchanged.

### Phase 5 — Python intelligence and governed AI

- Implement one server-side provider interface rather than scattering provider-specific calls through business routes.
- Providers are optional adapters, with explicit per-tenant allow-list, role check, data classification, privacy and retention rule, rate limit, cost budget, audit metadata and timeout.
- Keep paid providers (including Gemini/OpenAI where configured) and approved free/limited providers as separate policy choices. Do not promise a free endpoint will be unlimited or production-grade.
- Fail closed for disallowed data/provider combinations. Fall back to deterministic business rules when AI is unavailable.
- Require human review for accounting journals, refunds, stock adjustments, payment allocation and other high-impact actions; AI may explain or recommend but must not silently commit those transactions.

**Acceptance:** provider failure does not block core sales/stock/finance workflows; tenant context and authorization are enforced before provider calls; all AI outputs are marked as suggestions and auditable without retaining unnecessary prompts.

### Final phase — LEXA product billing and subscriptions

Only after the core app, business workflows, performance, tenant isolation, recovery and scale tests are accepted:

- implement plans, entitlements, trial/activation states, subscription changes, invoices, payment webhooks, retry/dunning rules and owner/admin billing views;
- add idempotency, reconciliation and audit logs for subscription/payment events;
- test payment-provider failure, duplicate webhooks, renewal, cancellation, upgrades/downgrades and tenant entitlement enforcement in sandbox/staging;
- release behind an explicit rollout gate.

No product billing/subscription implementation is included in Phase 1.

## Current candidate status

- Implemented in the local candidate: API duration helper, `Server-Timing` header, safe slow-request/5xx logs, proxy timing passthrough, API/web Dockerfiles, extended Compose stack, Kubernetes base manifests, plan and initial tests.
- Verified here: 7 performance helper/contract tests passed; Python compileall passed; Compose and Kubernetes YAML parse successfully.
- Not verified here: Docker builds, full backend/frontend suites under their pinned CI runtimes, clean migration replay, staging authenticated browser workflows, live performance delta or multi-instance load balancing.
- Not pushed or deployed: the connected GitHub integration returned HTTP 403 when a feature branch was requested. No Render, Vercel or Neon production state has been changed.
- The GitHub Actions workflow currently exists under `.github/workflows/.github/workflows/lexa-ci.yml`; it needs to be added at `.github/workflows/lexa-ci.yml`. The automatic ZIP extractor protects `.github/workflows`, so this path correction requires a direct repository edit; it cannot be achieved by uploading an ordinary source overlay ZIP.

## Important current-hosting limitation

The existing Render API is on a Free plan. Free-service suspension after inactivity can still create a slow first request regardless of in-app code. The candidate measures application response time and establishes the container/scale path, but it does not disable Render suspension, change a hosting plan, create a Kubernetes cluster, or deploy additional instances.
