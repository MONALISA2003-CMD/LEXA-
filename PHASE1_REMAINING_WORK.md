# LEXA intelligence release gates — Phases 1–4

**Review date:** 24 October 2026  
**Repository:** `MONALISA2003-CMD/LEXA-`  
**Upload target:** `main`

## Source status

This overlay contains canonical Phase 1–3 intelligence implementation files, fixes for the CI errors observed in runs 40063918855 and 40064896058, and a read-only Phase 4 demand-forecast pilot. The existing extractor must create a follow-on `[lexa-extractor]` commit with source changes before the revision can be validated remotely. Phase 0 remains complete and green as instructed by the project owner.

## Phase 1 — intelligence foundation

Implementation in the bundle: strict contracts, default-deny external policy, local Python routing for the forecast baseline, bounded provenance/event contracts, API capability reporting, candidate migration 045, and an explicit block on legacy AI execution until its policy gate is wired.

Acceptance still required: full repository regression tests; run all API routes against a staging fixture; execute clean replay and verify grants/forced RLS/tenant isolation on a disposable PostgreSQL database; confirm no external request occurs when providers are configured but disabled.

## Phase 2 — daily brief

Implementation in the bundle: reuses the canonical saved-insight calculation, explicit business date and currency, safe evidence/action links, deterministic priority, and separation of stale/unavailable data.

Acceptance still required: authenticated staging test against populated and stale analytics fixtures, cross-branch permission boundaries, timezone/business-date edge cases, and full frontend typecheck/build.

## Phase 3 — document intake/review

Implementation in the bundle: bounded PDF/JPEG/PNG/WebP upload, content signature checks, local candidate extraction with evidence, duplicate detection, branch authorization, review history, explicit confirm/reject, and no transaction write on confirmation. Candidate migration 046 provides forced RLS and insert-only review history.

Acceptance still required: disposable database replay, runtime RLS probes, and authenticated staging upload/duplicate/download/edit/confirm/reject using synthetic documents. Render currently uses Native Python while the Dockerfile installs Poppler/Tesseract. Check `/api/v1/intelligence/capabilities`; never claim OCR is live if the binaries are unavailable. No hosted runtime change is part of this bundle.

## Phase 4 — demand forecast baseline pilot

Implementation in the bundle: an endpoint and page using a weekday-seasonal median over a complete, fresh 56-day sales-unit history; 14-day rolling-origin backtest with MAE/WAPE and last-week comparison; top-30 volume bound; sparse-series exclusion; and explicit stockout/forecast limitations.

Acceptance still required: test the endpoint against synthetic database fixtures with full, stale, missing and partial-refresh scenarios; compare backtest metrics on representative Ugandan SME data; inspect sales-vs-stock availability to quantify stockout censoring; add location-level estimates, caching and batch scheduling only when validated. This first pilot has no learned coefficients, no external AI, and no inventory or purchasing write path.

## CI correction for run 40064896058

Typecheck and API tests were green; two frontend contracts incorrectly expected optional staging/clean-replay jobs in the default lightweight workflow. The updated contracts test the three actual default jobs and continue testing the staging protections in the E2E spec/global setup. They do not require secrets or staging to be present for every push.

## Required release checks

1. Upload the ZIP to `main`; inspect the `[lexa-extractor]` commit and ensure actual source files, not only the ZIP, changed.
2. Confirm all jobs in GitHub Actions pass for the exact extracted SHA, including frontend contract tests, TypeScript and Next build.
3. Confirm Render and Vercel complete successful deployments for that same SHA; test `/health`, `/ready`, login-protected `/intelligence/capabilities` and `/intelligence/demand-forecast` in staging.
4. Run clean migration replay and forced-RLS/branch-isolation tests on a fresh disposable PostgreSQL instance. Never use production/Neon for a replay.
5. Run authenticated staging tests; retain synthetic fixtures and avoid any live business write.

No production migration, database write, secrets, hosted setting or deployment is changed by this overlay. Migrations 045 and 046 remain review candidates.
