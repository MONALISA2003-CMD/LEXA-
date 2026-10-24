# LEXA Intelligence — remaining acceptance work

**Review date:** 24 October 2026  
**Repository:** `MONALISA2003-CMD/LEXA-`  
**Observed ZIP-upload commit:** `1fd4ee081bf45be6c78e330e52851d8a33bb4667`  
**Target upload branch:** `main`

## Source status

The earlier ZIP upload was visible as an archive on `main`; the connected file API did not find the unpacked intelligence source paths in the inspected commit. This new bundle therefore supplies the intelligence modules, API registration, migrations, web pages/navigation, and tests at canonical repository paths directly at the ZIP root, so the existing LEXA ZIP extractor can materialize them rather than needing a local installer.

This source overlay is still awaiting extraction and tests on the exact resulting Git SHA. Phase 0 is considered complete and green as the project owner instructed; this report does not reopen Phase 0.

## Still required to close Phase 1

1. Verify the extractor writes `apps/api/app/intelligence/*`, registers the routers in `apps/api/app/main.py`, includes migration 045 in `migrations/reconstructed/clean_replay_order.json`, and creates a commit on `main`.
2. Run the full existing `apps/api/tests` suite (including AI assistant, analytics, RBAC, branch access and finance regressions), repository checks, and normal frontend test/typecheck/build on that exact source SHA.
3. Run the clean replay only against a fresh disposable PostgreSQL database, never Neon/production. The replay manifest now appends migrations 045 and 046. Validate forced RLS, exact grants, tenant/branch boundaries and append-only `intelligence_runs` behavior.
4. Confirm `GET /api/v1/intelligence/capabilities` accurately reflects the external AI default-deny policy and local document-tool availability; adding a provider key must not enable legacy `/api/v1/ai/assist`.
5. Record the actual CI and disposable replay result before marking Phase 1 complete.

## Phase 2 acceptance still required

- Verify the `/api/v1/intelligence/daily-brief` route reuses the existing deterministic insight handler and works for a fully authorized tenant/branch scope.
- Confirm daily brief currency and business date use LEXA saved settings, stale/missing insights go to data-quality warnings, and evidence links remain same-origin.
- Test the new `/daily-brief` page in the authenticated app; full Next.js typecheck/build is not possible in this offline bundle-only environment.

## Phase 3 acceptance still required

- Verify local document-tool availability in the deployed API. The included Dockerfile installs Poppler/Tesseract, but the currently configured Render service uses Native Python; a maintainer must separately approve a Docker-runtime migration or another system-package strategy before claiming hosted OCR is live. Without these tools, the system safely degrades to manual review.
- Run a clean database replay of migration 046, with explicit branch-scoped RLS/policy probes for both document tables and insert-only review-history grants.
- Run an authenticated staging test for upload/duplicate/view/download/edit/confirm/reject using synthetic documents; prove no invoice, expense, PO, journal, stock or fiscal record is created by confirmation.
- Complete mobile checks for upload, review, source evidence, file download and keyboard/screen-reader states.

## Verification performed in this preparation environment

- Phase 1/2/3 Python synthetic suite: **45 passed**.
- Phase 3 web source-contract suite: target 7 tests; see `VALIDATION_RESULTS.md` for the exact rerun result.
- Python compilation and TypeScript transpile syntax checks are separate from repository typecheck/build.
- No GitHub commit, hosted configuration change, deployment or database connection/write was performed by this session.

## Release gate

Phase 1/2/3 are implementation source candidates until the exact uploaded source SHA passes repository CI, a disposable Postgres replay/security assertions, and authenticated staging acceptance. Never apply candidate migrations 045/046 to production merely because ZIP extraction or Vercel is green.
