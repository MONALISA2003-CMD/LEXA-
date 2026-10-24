# Validation record — LEXA full business-language package

**Target:** `MONALISA2003-CMD/LEXA-`, branch `main`  
**Baseline inspected:** `36f894b0b0e9203840a333548980e569502cc8c7`

## Verified in this session

- Re-checked that `main` still points to `36f894b0b0e9203840a333548980e569502cc8c7`.
- Inspected failed main CI run `40071295539`: the frontend typecheck and Docker/HAProxy checks passed; frontend contract tests and API unit/contract tests failed on stale visible-language expectations and the disabled Assistant contract.
- Verified the Render LEXA service and Vercel production deployment were both built from the inspected main commit; Vercel reported no grouped runtime errors in the 7-day query.
- Verified Neon project `LEXA`, default branch `lexa-live`, and database `neondb`; no schema, production data or connection settings were modified.
- The language application script passes Python syntax compilation.
- The workflow template parses as YAML, the module inventory and language test asset are present, and the final package is checked for CRC integrity and SHA-256 checksums.
- Focused language/document regression tests from the prepared overlay passed 12/12 in the available partial workspace.

## What is not yet verified

The complete frontend typecheck, all frontend tests, production frontend build, full API suite and deployment checks have **not** been run against a full checkout containing the complete language pass. The full repository could not be cloned in this session, GitHub write operations returned `403 Resource not accessible by integration`, and Vercel Sandbox creation was denied by the current snapshot-storage limit.

The ZIP extractor blocks `.github/workflows` paths, so this package contains the workflow as a template under `docs/`. After upload to `main`, create `.github/workflows/lexa-language-overhaul.yml` through GitHub's web editor by copying that template. Run the workflow on `main`; it applies the wording pass on the actual full source tree and commits only if every check succeeds. Full CI success must be confirmed after that run.

## Guardrails

The script updates literal customer-facing copy and related test expectations across active frontend modules, shared UI, navigation/search and browser-facing errors. It does not intentionally change accounting calculations, financial posting behaviour, tax rules, APIs, permissions, access policy, secrets, provider configuration, database schema or production records. The Business assistant remains unavailable.
