# Phase 4 source reconciliation notes

**Date:** 21 October 2026

The Phase 4 patch is provided as an **overlay**, intended to be applied on top of the latest `LEXA_PHASE3_FINAL_CUTOVER_2026-10-21.zip` source handoff, not as a replacement archive that deletes or downgrades unspecified files.

## Shared-main source spot-checks

Connected GitHub `main` reader checks recorded matching SHA-1 blob identifiers between the local candidate and `MONALISA2003-CMD/LEXA-` for these unchanged baseline files:

| Path | GitHub blob SHA-1 |
|---|---|
| `README.md` | `bbb0ae5e8a74b8a291b1071f1bd93f2cebcaab66` |
| `apps/api/app/config.py` | `3e335431246a663b693adf569a462800a110613a` |
| `apps/api/app/db.py` | `d8066c21198e329de2707dda623ad2b07c5af13b` |
| `apps/api/app/dependencies.py` | `0f2c35310a15dafa164a81bce98b5d9059a16133` |
| `apps/web/package.json` | `84669703b659e0174b3a265937e11e9f9093d5f4` |
| `apps/web/package-lock.json` | `4fb2bc491527d91b03e6e99d65ce7a863872cdad` |
| `apps/web/app/layout.tsx` | `bece5d983b9ddb475272d49329967807434b3457` |

This is a spot-check, not a full-tree merge-base proof. The latest Phase 3 handoff contained source changes not committed to GitHub `main` at the time of inspection (including the Phase 3 workspace-context/membership-admin router mounts and applied migration `031_phase3_auth_surface_rls`). Therefore, taking the old Phase 4 full ZIP and replacing the whole project would risk regressing accepted Phase 3 state.

## Overlay strategy

- This ZIP includes only Phase 4 changed files, test additions/updates, KPI/acceptance documentation and the standalone product strategy.
- It deliberately does **not** include or replace `.github/workflows/**`, environment secrets, database migration history, or unrelated Phase 3 source files.
- Apply to an extracted copy of the latest Phase 3 final-cutover source, then perform full CI/typecheck/build acceptance before any deployment.
- No GitHub commit, deployment, production database write, or hosted configuration change occurred during this Phase 4 closeout attempt.
