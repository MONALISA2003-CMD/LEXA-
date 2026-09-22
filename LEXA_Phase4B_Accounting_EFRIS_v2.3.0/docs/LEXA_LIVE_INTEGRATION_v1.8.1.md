# LEXA Live Integration v1.8.1

## Canonical path

Browser → Next.js `/api/lexa/*` proxy → FastAPI → canonical LEXA Neon PostgreSQL

## Readiness contract

`GET /ready` now verifies:

- canonical project identity
- canonical branch identity
- canonical database name
- Phase 0 schema
- Phase 2 Universal Business Engine schema

The endpoint may return HTTP 200 with `status=not_ready`; the frontend must inspect the payload, retry, and only mark the workspace ready when `status=ready`.

## Browser bootstrap

Development preview bootstrap uses `/api/v1/auth/dev-session`, stores the short-lived access token in session storage, and immediately re-runs readiness. Transient 502/503/504 responses are retried.

## Deployment dependency

The source package is deployment-ready. Live deployment of the frontend/API still depends on access to the connected hosting accounts. No non-LEXA Neon target is used.
