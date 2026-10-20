# LEXA Phase 0–3 closure index — 20 October 2026

**Repository:** `MONALISA2003-CMD/LEXA-`  
**Pinned source baseline:** `8124cca301062eac6ffe59f68d02fc689a3ffae1`  
**Delivery state:** reviewable candidate only; not committed, merged, migrated into production, or deployed.

## Current Phase 3 candidate

- [Combined Phase 3 Increments 01–06 closure archive](LEXA_Phase3_Increments_01_06_Closure_2026-10-20.zip) — setup, workspace switching/onboarding, memberships/invitations/branch assignments, member role assignment, core branch enforcement, and role/permission administration.
- [Phase 3 README](LEXA_Phase3_Increments_01_06/README.md)
- [Implementation report](LEXA_Phase3_Increments_01_06/docs/IMPLEMENTATION_REPORT.md)
- [Acceptance matrix](LEXA_Phase3_Increments_01_06/docs/ACCEPTANCE_MATRIX.md)
- [Phase 0–3 closure matrix](LEXA_Phase3_Increments_01_06/docs/PHASE0_TO_PHASE3_CLOSURE_MATRIX.md)
- [Patch manifest](LEXA_Phase3_Increments_01_06/PATCH_MANIFEST.json)
- [Validation results](LEXA_Phase3_Increments_01_06/VALIDATION_RESULTS.json)
- [Archive SHA-256](LEXA_Phase3_Increments_01_06_Closure_2026-10-20.zip.sha256)

## Phase 0–2 recovery and historical evidence

- [Phase 0–2 closure report](LEXA_Phase0-2_Closure_Report_2026-10-20.md)
- [Phase 0–2 closure / Increment 08 archive](LEXA_Phase0-2_Closure_Increment_08_2026-10-20.zip)
- [Phase 2 recovery / CI patch](LEXA_Phase2_Recovery_CI_Patch_2026-10-20.zip)
- [Phase 2 recovery patch manifest](LEXA_Phase2_Recovery_Patch_Manifest_2026-10-20.json)
- [Phase 2 validation results](LEXA_Phase2_Validation_Results_2026-10-20.json)
- [Historical ZIP recovery scan](LEXA_Historical_ZIP_Recovery_Scan_2026-10-20.json)
- [Isolated schema replay diff/evidence](LEXA_Isolated_Schema_Replay_Diff_2026-10-20.json)
- [Phase 3 plan and scope definition](LEXA_Phase3_Plan_2026-10-20.md)
- [Reconstructed source manifest](LEXA_Reconstructed_Source_Manifest_2026-10-20.json)

## Validation and limits

The package suite passes **34 Python tests**, **8 Node source-contract tests**, Python compilation and the isolated TypeScript contract fixture. The full Python suite against a disposable installed-overlay checkout recorded **116 passed and 1 skipped**; the skipped auth-refresh test needs Redis. Full app Node 24 overlay install/typecheck/tests/build, authenticated API/browser E2E, a new empty-database full replay, and canonical schema parity are still unproven. Six exact historical SQL files (`010`, `011`, `023`–`026`) remain unrecovered; the equivalents are explicitly labelled.

No production database, credentials, runtime role, hosted service setting, repository branch, release, or deployment was changed. A previous GitHub branch-creation call returned 403, so the source is not in a hosted feature branch or pull request. Use the Phase 3 README and acceptance matrix for detailed release gates.
