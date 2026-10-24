# LEXA CI contract-test repair — run 40085513968

This ZIP is an overlay for the existing LEXA ZIP Extractor. Upload the ZIP to the **repository root** on `main`, using GitHub's web UI on your phone if necessary. Do not unzip it locally and do not rename any archive paths.

The repository's `.github/workflows/lexa-zip-extract.yml` recognizes this as a LEXA source package because it contains the two expected source markers and a file under `migrations/`. It extracts the files, commits the changed tests, and dispatches the canonical `LEXA Main Build CI` workflow. The archive is then removed by the extractor.

## What changes

Six test files are updated to match the current source contracts:

- API phase-3 test: expects the assistant to remain unavailable while privacy/execution gates are not approved. It explicitly guards against execution-enabled UI instead of expecting the obsolete `executionAvailable` path.
- Phase 1 UX and visible-product contracts: current navigation label is `Business details`, not `Business settings`.
- Phase 3 document-intelligence contract: checks the actual unavailable assistant copy and current daily-brief data-quality wording.
- Phase 4 forecast contract: the current navigation label is `Sales forecast`; the natural-language search suggestion is `Expected demand and sales forecast`.
- Phase 8 foundation contract: the current finance navigation label is `Money & records`, not `Finance`.

The following three paths are included only as unchanged markers required by the ZIP Extractor:
`apps/web/package.json`, `apps/api/app/main.py`, and `migrations/README.md`.
Their Git blob hashes were checked against the current `main` source before packaging.

## Safety

No application routes, provider adapters, API keys, policy code, deployment settings, or database migrations are changed by this package. External AI execution remains unavailable/denied. The tests are being brought in line with the current fail-closed behavior, not the other way around.

## Verification performed here

- Python syntax compilation of the changed API test: passed.
- `node --check` for all five changed frontend test files: passed.
- ZIP package layout and required extractor markers: validated.

The complete API/frontend suites and production frontend build still need the GitHub Actions run to verify them. A green result is not claimed until that run completes.
