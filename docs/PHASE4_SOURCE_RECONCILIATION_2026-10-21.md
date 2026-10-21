# Phase 4 source reconciliation notes

**Date:** 21 October 2026  
**Status:** Incomplete — exact final Phase 3 handoff is not available in the active filesystem for a full-tree rebase.

The Phase 4 candidate was developed from the preserved LEXA source archive and the Phase 3 source overlays in that archive. The standalone Phase 3 final-cutover ZIP from the prior turn is not mounted in the active workspace. This file therefore records verification evidence, not a claim of exact full-tree merge-base parity.

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

## Files requiring explicit reconciliation

The API route candidates do **not** byte-match the current GitHub `main` versions, because the preserved source contains additional API source-overlay changes alongside the Phase 4 work. Current GitHub blob identifiers observed for comparison:

| Path | Current GitHub `main` blob | Candidate file size after Phase 4 work |
|---|---|---:|
| `apps/api/app/routes/commerce.py` | `8a23d985faecd0ef6ca08b5e1d4ece50cb39ed80` | 48,246 bytes |
| `apps/api/app/routes/inventory.py` | `5d82e253f877866d4fd33d2773d85c5ecf791b78` | 41,662 bytes |
| `apps/api/app/routes/analytics.py` | `ce6f62f58479898a48bc75f53f6acc6a8b8580a3` | 9,474 bytes |

These three files must be compared/merged against the **exact accepted Phase 3 final-cutover source** before a blind overwrite of `main`. This is especially important for `commerce.py` (sales/payment semantics) and `inventory.py` (branch/tenant scope). The archive's extra lines may be prior source overlay fixes, but their exact parity with the accepted final ZIP could not be proven here.

The current GitHub `main` also has a distinct Phase 3 state: migration `migrations/031_phase3_auth_surface_rls.sql` is present, but `apps/api/app/main.py` does not include the Phase 3 `workspace_context` / `membership_admin` router mounts observed in the accepted final-cutover handoff. Do not overwrite `main.py` with this Phase 4 overlay; it is not included here.

## Safe application rule

- This archive is a **Phase 4 source candidate**, not permission to replace the complete repository tree.
- The ZIP contains repo-relative changed paths only; it does not contain a schema migration, `.env`, credentials or `.github/workflows/**`.
- Do not push the three API route replacement files blindly. Reconcile them against the accepted final-cutover handoff, preserve `main.py` and migration `031`, then run the release matrix.
- No GitHub commit, deployment, production database write, or environment change occurred in this Phase 4 work.
