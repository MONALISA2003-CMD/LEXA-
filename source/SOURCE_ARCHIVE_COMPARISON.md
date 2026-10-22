# Original ZIP vs Phase 1 ZIP — Comparison Record

Comparison date: 2026-10-20

## Source archives compared

- Original: `LEXA_First_Increment_Source_Package_2026-10-19 (2).zip`
  - Bytes: 1,412,226
  - SHA-256: `f1f4eb819dbaf292f15c1686cc96e7fff517e2358b55cb84805e6d29ddbde832`
  - Files after normalizing the top-level folder: 195
- Phase 1: `LEXA_Phase1_Security_Stability_2.9.1_FULL_SOURCE_2026-10-19.zip`
  - Bytes: 1,415,212
  - SHA-256: `80dc30df29010e527675596d489e030bd5f044920fb4d6ce123e7aa45b6698bc`
  - Files after normalizing the top-level folder: 198

## Findings

- **No substantive original source or documentation file was missing from the Phase 1 ZIP.** The only original paths absent from Phase 1 were 4 disposable pytest cache files listed below.
- 10 paths existed in both archives with intentional Phase 1 differences; those differences are listed below.
- 7 Phase 1 additions were not present in the original source archive.
- The Phase 1 archive was built from the original source tree, then changed for the Phase 1 runtime-role/security work. The cache files were correctly excluded rather than copied into the deliverable.
- This consolidated ZIP additionally includes the external audit/status/module-matrix/statement-of-truth documents, the Phase 2+ handoff, and the original first-increment patch for provenance and continuity.

## Original files omitted from Phase 1

- `.pytest_cache/.gitignore` — 37 bytes; disposable pytest cache, intentionally excluded.
- `.pytest_cache/CACHEDIR.TAG` — 191 bytes; disposable pytest cache, intentionally excluded.
- `.pytest_cache/README.md` — 302 bytes; disposable pytest cache, intentionally excluded.
- `.pytest_cache/v/cache/nodeids` — 10,449 bytes; disposable pytest cache, intentionally excluded.

## Paths with changed content

- `.env.example` — original 536 bytes / Phase 1 569 bytes.
- `LEXA_PACKAGE_MANIFEST.json` — original 11,966 bytes / Phase 1 11,779 bytes.
- `README.md` — original 9,032 bytes / Phase 1 10,193 bytes.
- `RELEASE.txt` — original 362 bytes / Phase 1 558 bytes.
- `apps/api/app/config.py` — original 2,289 bytes / Phase 1 3,093 bytes.
- `apps/api/app/db.py` — original 1,444 bytes / Phase 1 2,014 bytes.
- `apps/api/app/health.py` — original 8,146 bytes / Phase 1 8,376 bytes.
- `render.yaml` — original 959 bytes / Phase 1 1,012 bytes.
- `scripts/verify-phase1.sh` — original 299 bytes / Phase 1 930 bytes.
- `tests/unit/test_deployment_audit.py` — original 4,970 bytes / Phase 1 5,018 bytes.

## Phase 1-only additions

- `PHASE1_ZIP_README.md` — 1,687 bytes.
- `RELEASE_NOTES_2.9.1_PHASE1_SECURITY_STABILITY.md` — 1,213 bytes.
- `SHA256SUMS.txt` — 19,869 bytes.
- `apps/api/tests/test_phase1_runtime_security.py` — 4,534 bytes.
- `docs/PHASE1_SECURITY_STABILITY_REPORT_2026-10-19.md` — 3,876 bytes.
- `docs/PHASE1_SECURITY_STABILITY_RUNBOOK.md` — 4,678 bytes.
- `migrations/029_phase1_runtime_role_least_privilege.sql` — 2,904 bytes.

## Important limits

- This comparison proves archive-path coverage and byte differences between the two supplied ZIPs; it does not prove that either archive contains every file ever present in the GitHub repository.
- The seven historical SQL migration sources documented in the Phase 1 report remain unavailable and were not invented or reconstructed.
- Runtime secrets, installed dependencies, external service configuration, and production state are not source files and are not included.
- No production deployment or mutation is implied by this package.
