# LEXA Phase 2 — Increment 03 Report

**Date:** 20 October 2026  
**Increment:** Product and Inventory workflow reliability, Vercel build repair, complete-source packaging  
**Status:** Source increment packaged; production release is **not yet cleared**.

## Summary

This increment builds on the existing Phase 2 shell and shared primitives. It keeps API endpoints and backend transaction/authorization behavior unchanged while improving product catalogue lookup, reducing unnecessary inventory requests, correcting the observed nullable-state TypeScript errors, and adding a repeatable archive integrity check.

## Source changes

- `apps/web/app/page.tsx`: the Command Centre now guards nullable `dashboard` and `analytics` state in the descriptions as well as the metric values. The hosted Vercel build log identified these as `TS18047` errors at the time of verification.
- `apps/web/app/products/page.tsx` and `apps/web/lib/api.ts`: product search now combines product-name search with the existing catalogue lookup endpoint for variant names, SKUs, and barcodes. Results are deduplicated by product ID, missing product details are fetched with a cap of 10 distinct IDs, requests use cancellation/stale-result protection, and catalogue reference lists no longer refetch on every search edit.
- `apps/web/app/inventory/page.tsx` and `apps/web/lib/api.ts`: filter changes refresh only the stock balance and ledger queries, debounce rapid input, abort superseded requests, guard late responses, and avoid displaying the previous summary as current while a refresh is running.
- `apps/web/tests/phase2-workflow-resilience.test.mjs`: regression contracts cover the Command Centre nullable-state issue, product query cancellation and SKU/barcode lookup, inventory filter isolation, and Render readiness contract.
- `scripts/package_phase2_zip.py`: creates a root-folder archive, embeds per-file SHA-256 checksums, compares packaged bytes to source bytes, checks ZIP CRCs, verifies file coverage, and excludes real environment-secret files and generated runtime artifacts.
- Existing Render health-check source configuration is preserved at `healthCheckPath: /ready`; no hosted Render configuration was changed.

No database writes, migrations, production settings changes, Git pushes, or deployments were performed.

## Local verification

| Check | Result |
|---|---|
| Backend and Phase 0 regression suite | 109 passed, 1 skipped (Redis dependency unavailable in local test environment) |
| Phase 1 runtime-role security tests | 5 passed |
| Frontend contract tests | 17 passed |
| Frontend TypeScript/TSX syntax transpilation | 27 files passed syntax contract |
| Migration manifest consistency (non-strict) | Ran; 7 historical SQL source files missing |
| Full frontend `npm run typecheck` | **Blocked / not verified**: installed dependencies unavailable |
| Full frontend `npm run build` | **Blocked / not verified**: installed dependencies unavailable |
| Browser screenshot, mobile viewport and accessibility QA | **Not run** |
| Archive content/hash/CRC verification | Runs as a mandatory step of the accompanying packaging script; final output details are in the external manifest |

The available runtime is Node `v22.16.0`; `apps/web/package.json` requires Node `24.x`. Installing from npm was blocked by registry DNS (`EAI_AGAIN`), and offline installation could not find all packages. The available global TypeScript compiler cannot substitute for the missing React and Next.js type declarations. Therefore local success here does not certify the full Next.js typecheck/build.

## Hosted-platform observations (read-only)

### Vercel

- Project: `lexa` (`prj_QicfCnse8LU6hnq4ik9liHc289VW`), configured for Node `24.x`.
- Latest production-target deployment observed: `dpl_8evPB3PscmYmF5QUBUAtYLP9ZQYD`, commit `b7da77cda94424326b777d87d7612974e67dceab`, state `ERROR`, error code `lint_or_type_error`.
- Build output specifically reported nullable `dashboard` and `analytics` dereferences in `app/page.tsx`. This source package contains a local fix; that fix has **not** been deployed to Vercel and the hosted build has not been rerun.
- The configured project alias did render the sign-in page during a read-only fetch. This does not turn the latest failed deployment into a successful build.

### Render

- Service: `LEXA`, `https://lexa-n10e.onrender.com`, latest observed deployment state `live` on the same backend commit noted above.
- Read-only HTTP response from `/health`: `status=ok`.
- Read-only HTTP response from `/ready`: `status=ready`, `database=ok`, `cache=ok`.
- Service metadata reports an empty Render `healthCheckPath`, whereas the repository deployment blueprint declares `/ready`. The endpoint works, but the hosted service setting and source blueprint are not yet reconciled. No service setting was changed.

### Neon

- Project: `LEXA` (`wispy-mud-75323042`); default/live branch `lexa-live` (`br-soft-star-b1dj2m2w`); database `neondb`.
- Read-only validation confirmed the project/branch/database identity matches the expected canonical identity.
- All 28 health-check-required tables exist.
- Migration `028_phase0_auth_rls_runtime_hardening` exists; `public.lexa_find_session_by_refresh_hash(text)` exists; `lexa_app` can execute it; the function is `SECURITY DEFINER` and its owner has `BYPASSRLS`.
- These read-only schema checks passed. They do not replace authenticated HTTP end-to-end tests or strict replay of every historical migration source.

## Release blockers and follow-up

1. Run the source package through Node 24 with `npm ci`, `npm run typecheck`, frontend tests, and `npm run build`; the local environment could not complete those commands.
2. Apply the source fix through the authorized Git/preview workflow and confirm a new Vercel build completes before promotion.
3. Reconcile the hosted Render health-check path with the repository's `/ready` declaration through an approved infrastructure change.
4. Recover the seven exact historical migration sources listed by `python scripts/check_migration_sources.py --strict` before claiming strict migration replay is clean.
5. Complete authenticated browser end-to-end tests and responsive/accessibility reviews.

**Release statement:** This is a complete source-package increment with static/backend tests passing, not a certified deployment. A zero-bug or all-hosted-green claim would be unsupported until the outstanding gates above pass.
