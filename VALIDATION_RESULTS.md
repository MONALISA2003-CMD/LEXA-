# LEXA CI fixes + Intelligence Phase 1–3 — local validation results

**Date:** 24 October 2026  
**Scope:** CI root-cause fixes in the bundled source overlay plus Phase 1–3 contract tests and static checks. No live service/provider calls.

## Passed

| Check | Result | Scope |
|---|---:|---|
| Python contract/policy, daily-brief and document-extraction tests | **45 passed** | `apps/api/tests/test_intelligence_phase1.py`, `test_intelligence_phase2.py`, `test_intelligence_phase3.py` |
| Provider `.env` settings regression | **1 passed** | `apps/api/tests/test_config_provider_settings.py`; verifies provider values load while external-AI controls stay disabled |
| Web contract tests | **7 passed** | `apps/web/tests/phase3-document-intelligence.test.mjs` |
| Python compileall | **PASS** | `apps/api/app` and `apps/api/tests` |
| Replay manifest JSON parse | **PASS** | `migrations/reconstructed/clean_replay_order.json`; appends 045 then 046 |
| TypeScript/TSX syntax transpilation | **PASS** | AI assistant, documents page, daily-brief page and two new typed API modules |
| CI regression source fixes | **PASS (source review)** | Null-safe daily-brief currency; explicit Pydantic provider fields; order-relative assertions for historical migrations 042–044 and appended 045–046 |
| Extractor package markers | **PASS** | Checked before packaging: `apps/web/package.json`, `apps/api/app/main.py`, and `migrations/` present at ZIP root |

## CI run root causes addressed

The observed run failed because (1) the daily-brief client dereferenced a nullable profile currency, (2) provider values from `.env` had no declared Pydantic fields, causing both the provider settings test and its monkeypatch teardown to fail, and (3) older migration tests incorrectly required migration 044 to remain last after forward-only migrations 045 and 046 were appended. The fixes are in the overlay. The next exact-source GitHub Actions run after extraction is still required to confirm the entire repository suite and Next.js build.

## What the tests exercise

- Fail-closed policy defaults, schema contracts, synthetic event validation and safe insight evidence.
- Daily-brief prioritization, stale/unavailable data quarantine, currency checks and prevention of automatic business writes.
- Local document candidate extraction, Uganda day/month/year date normalization, evidence lines, file-type/size checks, content-signature checks, bounded OCR subprocess timeout paths and manual-review fallback.
- SQL migration source contracts, tenant/branch/RLS/grant markers, replay order, route registration and the external-AI pause gate.
- Navigation route/search contracts, authenticated raw file upload headers, explicit confirmation/rejection UX, no provider-side OCR calls, and the separate daily-brief data-quality section.

## Not verified here

- Full backend suite or upstream CI after the fixes against the entire LEXA checkout. The CI run inspected here was before these fixes; this bundle is a source overlay, not a complete clone of the repository. Running all included legacy tests against only the overlay fails because their non-overlay source files are intentionally not duplicated in the ZIP.
- Full Next.js typecheck/production build. The web package requires Node 24.x; this runtime has Node 22.16.0, the overlay intentionally lacks the repository lockfile, and dependencies cannot be installed with `npm ci` against this overlay alone. Only TypeScript/TSX syntax transpilation was run. The source nullable dereference that stopped the CI typecheck is fixed, but a post-fix full `tsc`/build is not claimed.
- PostgreSQL clean replay, SQL execution, actual forced-RLS behavior or cross-tenant adversarial tests. `psql`, a disposable DB URL and the runtime DB driver are unavailable in this environment. The manifest is prepared to include 045 and 046 in a future disposable replay; neither migration has been applied.
- Authenticated staging/browser/visual acceptance at mobile widths.
- OCR on the hosted Render service. The Dockerfile in this overlay installs Poppler/Tesseract for Docker-based runs, but the currently inspected Render configuration uses the Native Python runtime. The service type was not changed. `/api/v1/intelligence/capabilities` reports tool availability, and extraction safely degrades to manual review if tools are missing.
- Direct GitHub commit/upload or deploy. The connected GitHub integration is read-only for branch writes in this session.

See `docs/LEXA_CI_ROOT_CAUSES_AND_PHASE1_3_VALIDATION_2026-10-24.md` for the exact failing job findings and deployment revision comparison.

## Safety boundary

No provider was called, no AI quota consumed, no secrets/configuration changed, no database SQL applied, and no hosted service deployed by this preparation. AI assistant execution remains blocked until a separately approved policy integration is implemented.

**Release status:** `CI ROOT CAUSES PATCHED IN SOURCE OVERLAY — POST-EXTRACTION CI AND DEPLOYMENT GREEN STATUS NOT YET VERIFIED`. Do not mark Phase 1–3 production accepted until exact-source CI, disposable database/RLS replay and authenticated staging checks pass.
