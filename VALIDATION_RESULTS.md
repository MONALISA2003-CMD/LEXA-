# LEXA Intelligence Phase 1–3 — local validation results

**Date:** 24 October 2026  
**Scope:** Bundled source overlay tests and static checks. No live service/provider calls.

## Passed

| Check | Result | Scope |
|---|---:|---|
| Python contract/policy, daily-brief and document-extraction tests | **45 passed** | `apps/api/tests/test_intelligence_phase1.py`, `test_intelligence_phase2.py`, `test_intelligence_phase3.py` |
| Web contract tests | **7 passed** | `apps/web/tests/phase3-document-intelligence.test.mjs` |
| Python compileall | **PASS** | `apps/api/app` and `apps/api/tests` |
| Replay manifest JSON parse | **PASS** | `migrations/reconstructed/clean_replay_order.json`; appends 045 then 046 |
| TypeScript/TSX syntax transpilation | **PASS** | AI assistant, documents page, daily-brief page and two new typed API modules |
| Extractor package markers | **PASS** | Checked before packaging: `apps/web/package.json`, `apps/api/app/main.py`, and `migrations/` present at ZIP root |

## What the tests exercise

- Fail-closed policy defaults, schema contracts, synthetic event validation and safe insight evidence.
- Daily-brief prioritization, stale/unavailable data quarantine, currency checks and prevention of automatic business writes.
- Local document candidate extraction, Uganda day/month/year date normalization, evidence lines, file-type/size checks, content-signature checks, bounded OCR subprocess timeout paths and manual-review fallback.
- SQL migration source contracts, tenant/branch/RLS/grant markers, replay order, route registration and the external-AI pause gate.
- Navigation route/search contracts, authenticated raw file upload headers, explicit confirmation/rejection UX, no provider-side OCR calls, and the separate daily-brief data-quality section.

## Not verified here

- Full backend suite or upstream CI against the entire LEXA checkout. This bundle is a source overlay, not a complete clone of the repository.
- Full Next.js typecheck/production build. The web package requires Node 24.x; this runtime has Node 22.16.0 and the project's React/Next dependencies are not installed here. Only TypeScript/TSX syntax transpilation was run.
- PostgreSQL clean replay, SQL execution, actual forced-RLS behavior or cross-tenant adversarial tests. `psql`, a disposable DB URL and the runtime DB driver are unavailable in this environment. The manifest is prepared to include 045 and 046 in a future disposable replay; neither migration has been applied.
- Authenticated staging/browser/visual acceptance at mobile widths.
- OCR on the hosted Render service. The Dockerfile in this overlay installs Poppler/Tesseract for Docker-based runs, but the currently inspected Render configuration uses the Native Python runtime. The service type was not changed. `/api/v1/intelligence/capabilities` reports tool availability, and extraction safely degrades to manual review if tools are missing.
- Direct GitHub commit/upload or deploy. The connected GitHub integration is read-only for branch writes in this session.

## Safety boundary

No provider was called, no AI quota consumed, no secrets/configuration changed, no database SQL applied, and no hosted service deployed by this preparation. AI assistant execution remains blocked until a separately approved policy integration is implemented.

**Release status:** `IMPLEMENTATION CANDIDATE — LOCAL SYNTHETIC VALIDATION ONLY`. Do not mark Phase 1–3 production accepted until exact-source CI, disposable database/RLS replay and authenticated staging checks pass.
