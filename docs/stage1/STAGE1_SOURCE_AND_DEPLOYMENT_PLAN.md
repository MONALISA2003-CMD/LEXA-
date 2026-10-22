# LEXA Stage 1 — Canonical Source, Access and Deployment Foundation

Date: 22 October 2026

## Goal

Have one authoritative application source, working sign-in and first-run setup, a backend that reports its real schema readiness, and deployment configuration that points to that source. Do not begin Phase 9 until Phase 8 acceptance passes.

## Confirmed cause of the stale frontend

Vercel's production deployment is marked READY but uses the root `apps/web` project. The root styles still use the older blue/navy palette. The newer version exists under `LEXA/apps/web`. The repository's ZIP extractor copied ZIP paths literally; archives whose files start with `LEXA/` therefore created a second nested app instead of updating the canonical root.

## Canonical repository layout

Keep these as the only operational source locations:

- `apps/web/` — Next.js frontend
- `apps/api/` — FastAPI backend
- `migrations/` — canonical database migrations and source-recovery manifest
- `scripts/` — checks and disposable-replay runner
- root `render.yaml`, lock/config files, tests and documentation

The duplicate `LEXA/` source tree is removed by the package's `DELETE.txt` after canonical files are overlaid. The replacement extractor is supplied at `docs/stage1/lexa-zip-extract.yml` and also placed at `.github/workflows/lexa-zip-extract.yml` in this candidate. The current GitHub workflow explicitly protects `.github/workflows` from ZIP extraction, so the workflow file must be updated directly through a write-enabled GitHub connection or the GitHub web UI before relying on the corrected normalization behavior.

## Sign-in and business setup

- Authenticate only after setting the email-scoped pre-login RLS context.
- Set the authenticated user context before reading their workspace list.
- Set registration context, email and idempotency key before writing a registration request.
- First-run setup is idempotent and creates the main branch, stock room, stock location, owner branch access, accounting defaults and the default Cash payment method where missing.
- Setup progress has six steps: Business details, Main branch, Stock room, Where stock is kept, Payment method and Money tracking.
- LEXA records payment methods and amounts. No gateway connection or payment credential is introduced.

## Readiness semantics

- `/health` is liveness only and is the Render health-check path in `render.yaml`.
- `/ready` is full dependency and application-schema readiness. It must not return a healthy status while required migrations/tables/columns are missing.
- The health response may show a safe, plain-language failure code to the UI. It must never expose connection strings, passwords, tokens or SQL details.
- `healthCheckPath` currently shows blank in Render service metadata. The `render.yaml` change does not itself change the live service until the Blueprint/configuration is applied. Check the service's effective settings after the corrected source is deployed.

## Database migration safety

The `lexa-live` branch (`br-soft-star-b1dj2m2w`) currently has migration ledger identities through 031. Current application source expects the supplier billing/ledger structures from 039 and Phase 8 additions from 040. Migration 032 is documented as QA-branch-only and must remain excluded unless a reviewed forward migration adopts its changes.

Before any shared/production migration:

1. Run `python scripts/check_migration_recovery_manifest.py`.
2. Run `python scripts/check_migration_sources.py --strict`.
3. Run `python scripts/run_clean_migration_replay.py --plan-only` to verify the exact inputs/hashes without connecting to a database.
4. Run a full replay only against the disposable PostgreSQL CI service using the repository workflow's explicit disposable-database guard.
5. Review table/function/trigger/RLS/role assertions and required migration identities against the replay evidence.
6. Only then prepare a separately reviewed forward migration plan for `lexa-live`. Never point the replay runner at Neon and never use `--apply` against production.

Current checks report source reconciliation PASS, a 43-input plan PASS, and semantic replacement validation still pending for the six approved reconstructed-equivalent historical sources. That is a known acceptance condition, not permission to migrate production now.

## Deployment order

1. Directly install the corrected `.github/workflows/lexa-zip-extract.yml` (the extractor cannot update its own protected workflow from a ZIP).
2. Publish this canonical-root candidate as a reviewable source change, not by nesting it in another directory.
3. Verify the Vercel project root is `apps/web`, Node is 24.x, and the deployed source commit includes root `apps/web` files from this candidate.
4. Verify Render root directory is `apps/api`, its deployed commit matches the intended repository state, and `/health` and `/ready` have distinct behavior.
5. Ensure API environment references the intended Neon project `wispy-mud-75323042`, branch `br-soft-star-b1dj2m2w` (`lexa-live`), database `neondb`; never print environment values or expose secrets.
6. Complete the schema/replay gate before enabling new API expectations against a shared database.
7. Run authenticated checks: existing-account sign-in, new registration, existing-workspace initialization, payment-method seeding, owner branch access, session refresh, and `/ready` acceptance. Follow with module journey testing for Phase 8.

## Acceptance criteria

- One canonical app tree exists at the repository root; no duplicate `LEXA/apps/web` or `LEXA/apps/api` remains after extraction.
- A canonical source change triggers Vercel and Render builds from the intended directories.
- Both deployments identify the same intended commit/source version.
- Existing-account sign-in and new registration work through the real RLS path.
- An incomplete business receives a guided setup flow, not a misleading permission error or a dashboard of unrelated failures.
- Owner setup creates the missing locations and access assignment, accounting defaults and Cash method idempotently.
- `/health` reports liveness; `/ready` accurately reports missing schema and returns ready only when required schema/dependencies are present.
- Targeted tests and disposable replay pass before any shared database migration.
- Phase 9 remains blocked until Phase 8 end-to-end journeys pass.

## Current limitation

The connected GitHub integration currently returns `403 Resource not accessible by integration` for branch creation, so this local candidate cannot yet be published by the connected tool. No production data was changed, no Neon migrations were applied, and no deployment was triggered as part of this Stage 1 work.
