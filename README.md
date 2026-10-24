# LEXA CI correction + Intelligence Phases 1–4 source overlay

**Upload this single ZIP to `main`** using the existing LEXA ZIP Extractor. This is a canonical-path source overlay, not an installer. It includes `apps/web/package.json`, `apps/api/app/main.py`, and `migrations/` at the ZIP root so the extractor can recognize it. It does not include `.github/workflows/`, credentials, or secrets.

## CI failure addressed

The latest inspected run, [40064896058](https://github.com/MONALISA2003-CMD/LEXA-/actions/runs/40064896058), had a green TypeScript check and green API/Compose jobs; two frontend source-contract tests failed because they required optional write-enabled staging and database-replay jobs inside the lightweight canonical workflow. The tests now validate the three jobs that really run by default and keep the staging safety checks located in their Playwright E2E files. Default CI remains quick and does not require staging credentials, provider credits, disposable tenants or database replay.

The previous failures in [40063918855](https://github.com/MONALISA2003-CMD/LEXA-/actions/runs/40063918855) are also addressed in the overlay: safe handling of a nullable business profile currency, declared Pydantic provider key/model fields with blank-key defaults, and migration-history tests that preserve the original 042–044 order while allowing forward-only 045–046 candidates.

## What is in this increment

- **Phase 1 — intelligence foundation:** strict, versioned contracts; central default-deny external-AI policy; explicit local Python forecast routing; safe capability response; event/job/run contracts; candidate migration 045.
- **Phase 2 — daily brief:** deterministic cross-module summary reusing LEXA's saved business-insight calculations, with evidence links and separate action, information, and data-quality sections.
- **Phase 3 — document intelligence:** bounded PDF/image intake, local extraction candidates with source evidence, duplicate detection, explicit human review/rejection, and review history. Confirming a document does not create or post a business transaction. Candidate migration 046.
- **Phase 4 — demand forecast pilot:** read-only weekday-seasonal median forecasts for qualifying product variants, using a complete fresh 56-day history, 14-day rolling-origin holdout, MAE/WAPE compared with a last-week baseline, and explicit exclusions for sparse history.
- **CI regression fixes:** the stale Phase 5 sales/Phase 7 purchasing workflow assertions now accurately distinguish lightweight CI from opt-in, write-enabled staging tests. The E2E guard checks are retained in their relevant specs/setup.
- **AI assistant language:** human-readable status and a paused external-provider path until the central provider execution gate is fully implemented and approved.

## Forecasting safety and boundaries

The forecast endpoint first requires full authorized branch scope and a successful analytics refresh that covers the full 56-day window and finished within the last 72 hours. It does not treat an incomplete/stale projection as zero demand. It sums unit quantities, not money, across currencies. A series needs at least six active demand days. It reports a rolling-origin MAE/WAPE and a simple last-week baseline comparison; WAPE is omitted when test actuals are zero. The seasonal range is historical evidence, not a calibrated prediction interval.

This is a baseline pilot, not a trained/independently validated model. Recorded sales can understate demand during stockouts; stockout correction, holiday/promotion features, branch/location forecasting, batch caching and broader out-of-sample evaluation remain future work. Forecast output cannot create orders, change stock or reorder points, reserve inventory, or call an external model.

## Deployment observations before this upload

The most recent inspected Render deployment and Vercel production deployment were both **READY/LIVE on commit `2214dffa81f1d858cdfe51d695bd32758c3a56bd`**. That is the currently observed revision, not this new ZIP. After upload, check the extractor's `[lexa-extractor]` commit, GitHub CI, and both deployment providers for that exact new SHA.

Render is currently configured as Native Python. The included Dockerfile installs Poppler/Tesseract for Docker-based runs, but this bundle does not change the hosted runtime; hosted OCR is operational only if the capability endpoint confirms the local tools exist. Missing tools continue to trigger manual review.

## Validation boundary

The checks below are focused source/unit tests and static checks. They do **not** prove full repository CI, a complete Next.js typecheck/production build, SQL execution, RLS isolation on PostgreSQL, or authenticated staging browser acceptance. The full post-extraction CI run is the release gate. Migrations 045 and 046 remain candidates and must only be clean-replayed on a fresh disposable PostgreSQL database before any production migration decision.
