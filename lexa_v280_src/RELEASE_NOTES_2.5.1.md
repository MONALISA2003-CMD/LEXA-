# LEXA 2.5.1 — Production Readiness Repair

- Introduce `lexa_runtime` login role inheriting `lexa_app` least-privilege grants.
- Keep `lexa_app` non-login and retain transaction-local `SET LOCAL ROLE lexa_app`.
- Point Render at the canonical Neon pooled endpoint and canonical LEXA branch.
- Restore production mode and explicit Vercel CORS origin.
- Use `/ready` as the documented deployment readiness gate.
- Log sanitized database readiness exceptions for operational diagnosis.
- Readiness now returns HTTP 503 with Retry-After when the database is unavailable.
- Remove internal Business Engine and Kernel frontend routes from the deployable web tree.
- Pin the web toolchain to exact direct dependency versions and Node 24.x.
- Verification: 95 Python tests, frontend contract tests, TypeScript contract compile, and backend compile all pass.
