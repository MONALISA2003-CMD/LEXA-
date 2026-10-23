# LEXA Kubernetes deployment template

These manifests are real deployment configuration for the existing web/API source, but they are **not ready to apply as-is**. They use placeholder immutable image tags and expect externally managed secrets, an ingress/controller and a supported Kubernetes cluster.

## Required before applying

1. Build and scan `apps/api/Dockerfile` and `apps/web/Dockerfile` from their corresponding app directories; publish images to an owner-controlled registry and replace both `REPLACE_WITH_RELEASE_TAG` placeholders with the same reviewed release version. Do not use `latest` for a production rollout.
2. Provision a staging cluster with the Kubernetes metrics API enabled for HPA, plus a configured ingress/controller and TLS certificate for the chosen domain.
3. Create `lexa-api-secrets` in namespace `lexa-system` through the cluster's secret manager. Required keys are `database-url` (Neon pooled TLS URL using `lexa_runtime_login_p3`), `redis-url`, `jwt-secret` (at least 32 random characters), and `lexa-proxy-shared-secret` (at least 32 random characters). Never commit the secret values to Git.
4. Confirm that the target Neon branch has the expected migrations and application-role permissions. These manifests never run migrations.
5. Verify database connection budgets before raising the initial replica count. The starter config caps each API process at three pooled/overflow connections and HPA at four API replicas; include the background worker and any other consumers in the total.
6. Point external ingress traffic at `lexa-web:3000`. The API stays internal behind the `lexa-api:8000` ClusterIP service.

## What is included

- API deployment with two initial replicas, readiness/liveness/startup probes, rolling updates, non-root execution, conservative DB pooling, resource limits, a disruption budget and bounded CPU-based HPA.
- Web deployment with two replicas, health probes, non-root execution, an explicit writable Next.js cache volume, resource limits and bounded HPA.
- Separate analytics queue worker deployment. The API pods use `ANALYTICS_REFRESH_WORKER_ENABLED=false` and the worker runs `python -m app.workers.analytics_outbox`.
- ClusterIP services and namespace/configuration through Kustomize.

The worker separation is configured only for Kubernetes. Do not disable the currently embedded Render worker until a replacement is deployed and verified there.

## Staged rollout

Run `kubectl kustomize deploy/kubernetes/base` and schema/policy checks first, then deploy to disposable staging. Verify all readiness probes, at least two serving API pods, request distribution, analytics queue progress, tenant/RLS isolation, pod termination during active requests, rollback and a representative concurrent load test. Do not migrate the production Vercel/Render/Neon setup until all gates pass and the owner explicitly approves the hosting change.
