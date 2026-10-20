# LEXA Phase 0–2 Closure Audit — Increment 06

**Audit date:** 20 October 2026 (Africa/Kampala)  
**Disposition:** **NOT RELEASE-ACCEPTED — Phase 3 schema-changing work remains on hold.**  
**Scope:** Source-level remediation, migration provenance recovery, automated tests, current read-only Vercel/Render/Neon evidence, release controls and UI/UX research.  
**Safety boundary:** No production deployment, Git push/merge, hosted Render setting change, production SQL write, production credential change, or database role cutover was performed.

This is the authoritative current closeout status for the local Increment 06 candidate. It supersedes older Phase 0–2 reports' source-gap and test counts where those reports predate the 027 recovery and Increment 06 code changes.

## Executive decision

The source candidate can move forward for controlled review and CI, but Phase 0–2 cannot honestly be called fully finished yet. The source now has the previously verified frontend null-guard and SQLAlchemy `RowMapping` fixes, tenant-business-date dashboard defaults, a same-origin return-path guard, safer API proxy cache/security headers, better sign-in tablet/focus behavior, an updated pinned CI workflow design, and a researched Phase 0–2 security/release runbook. The 027 historical SQL has been restored with traceable Git blob provenance.

Three blockers cannot be safely closed from the current evidence alone: six exact historic migrations remain unrecovered; production's elevated database login and five tables without RLS need a reviewed cutover/policy design; and the root workflow/branch protection/Render health-check setting require authorized hosted changes. Credentialed business E2E and clean Node 24 build acceptance also remain pending. They are recorded below rather than “fixed” by guessing, weakening tests, or changing production blindly.

## What this increment changes

### Migration provenance

- Restored `migrations/027_release_convergence.sql` from tracked source path `lexa_v280_src/migrations/027_release_convergence.sql`, source commit `51355d941eb50e075e3d4f884838a11b6807778b`.
- Source file size is 16,980 bytes. The reconstructed Git blob SHA-1 exactly matches `e6d9242d7dedb2cbf7b1a71a46fe635b3ab051d8`; SHA-256 is `404334dde3e34a80d3176b1ba38347eb1def3cc8793f6b52d3a663cbc05b19cd`.
- Updated `migrations/source_gaps.json`, `migrations/SOURCE_RECOVERY.md`, migration README and integrity tests. Current strict replay has six missing exact sources, not seven.
- Kept the full version strings because `023_phase2_identity_tenancy_authorization_foundation` and `023_phase4_purchasing_core` share the numeric prefix 023 but are different migrations.

### CI/release workflow source

- Reworked `.github/workflows/lexa-ci.yml` to use verified full-length action SHA pins, `contents: read`, Node 24, backend tests/compile/source reconciliation, frontend `npm ci`/typecheck/tests/production build, and a separate opt-in strict migration gate.
- The strict gate defaults off during normal workflow dispatch; selecting it is expected to fail until the six exact source files have been recovered.
- This workflow source is ready for an authorized reviewed root-path installation. It has **not** been installed on active GitHub `main`: direct branch creation returned HTTP 403, and the current ZIP extractor deliberately protects root `.github/workflows/**`. No Git push or PR was made.

### Application behavior

- `out()` handles SQLAlchemy `RowMapping` and `Row` shapes; existing serializer regression tests cover both and Decimal output.
- Commerce dashboard defaults to `public.lexa_business_date(now(), tenant_id)` and filters sales using the tenant business calendar, rather than the API server's raw UTC calendar date.
- Command Centre and Commerce let the backend choose the default business date; user-selected date fields use local calendar helpers instead of UTC ISO slicing.
- The sign-in return-path helper rejects protocol-relative or URL-normalized external destinations.
- The Next.js API proxy sends `Cache-Control: no-store`, `Pragma: no-cache` and `X-Content-Type-Options: nosniff` for normal and generic upstream-failure responses while preserving request-ID semantics.
- Sign-in intermediate tablet layout stacks the story/form at 601–800 CSS px; keyboard focus styling is explicit and the password reveal target is at least 44 px high.

## Current verification

| Check | Result | Notes |
|---|---|---|
| `node --test apps/web/tests/*.test.mjs` | **23 passed, 0 failed** | Static/contract tests, including new date, safe-return URL, responsive/focus, proxy-header and tenant-business-date contracts |
| `python -m pytest -q tests apps/api/tests` | **113 passed, 1 skipped** | Skip is `apps/api/tests/test_auth_refresh.py` because local `redis` package is unavailable; CI installation is expected to include API dev dependencies |
| `python -m pytest -q tests/unit/test_migration_source_integrity.py apps/api/tests/test_commerce_business_date_contract.py` | **5 passed** | Migration gap/source hash check plus dashboard business-date contract |
| `python scripts/check_migration_sources.py` | **Expected non-strict result: 6 source gaps** | Correctly preserves the replay blocker |
| `python scripts/check_migration_sources.py --strict` | **Expected fail** | Strict gate is intentionally blocked by the six exact sources that remain missing |
| `python -m compileall -q apps/api/app apps/api/tests scripts` | **Passed** | Backend modules, backend tests and script sources compile cleanly |
| `python -m py_compile scripts/package_phase2_zip.py scripts/check_migration_sources.py` | **Passed** | Packaging and migration checker compile cleanly |
| `bash -n scripts/verify-phase0.sh scripts/verify-phase1.sh scripts/verify-phase3.sh` | **Passed** | All three verification scripts pass shell syntax validation |
| TypeScript/TSX transpilation syntax check | **26 files passed, 0 syntax errors** | Uses available global TypeScript 5.8.3; syntax-only and does not replace full typecheck/build |
| Frontend typecheck | **Blocked / not verified** | Runner Node is v22.16.0, while `apps/web/package.json` requires `24.x`; a network `npm ci` attempt timed out and only an incomplete `node_modules` directory exists. `tsc --noEmit` reports missing `@types/node`, `@types/react`, and `@types/react-dom` |
| Local frontend production build | **Not verified** | Cannot substitute static tests or live Vercel READY status for a clean Node 24 build of this exact candidate |
| Browser accessibility/visual acceptance | **Partial / not signed off** | Source contracts and page captures are useful, but the actual live browser viewport capture did not reliably establish the requested 390 CSS px width. Complete the stated viewport/keyboard matrix against a real rendered candidate |
| Credentialed browser/API E2E | **Not run** | Requires a dedicated non-production test account and disposable business records; no write requests were made to production |

## Final source archive verification

The final Increment 06 package was produced with `scripts/package_phase2_zip.py` and independently inspected after creation:

- 233 project source files plus the embedded manifest (234 ZIP entries).
- ZIP CRC verification passed; source-file coverage and per-file SHA-256 checks passed.
- Root-overlay paths verified; no `LEXA-Phase1-2.9.1/` enclosing prefix.
- No secret environment files included; `.env.example` is retained.
- Restored `migrations/027_release_convergence.sql` in the archive still recomputes to Git blob SHA-1 `e6d9242d7dedb2cbf7b1a71a46fe635b3ab051d8` and SHA-256 `404334dde3e34a80d3176b1ba38347eb1def3cc8793f6b52d3a663cbc05b19cd`.
- The external manifest records the exact archive SHA-256, byte size and per-file hashes.

This proves package integrity and source provenance, not that this source ZIP has been built/deployed on the current hosted commit.

## Hosted state observed read-only

- Vercel latest production-target deployment `dpl_FnFNF8mB4PxJPvGUvwyHFHagYEpL`: `READY`, commit `2cbfda1b24864d7cc03ad2cbb3972639545fe28d`.
- Render latest live deployment `dep-dbbfa06k1f9s73bplsg0`: `live`, same commit `2cbfda1b24864d7cc03ad2cbb3972639545fe28d`.
- Public frontend root/login and frontend API proxy health returned HTTP 200. Render `/health` and `/ready` returned HTTP 200 with database/cache `ok`. Anonymous dashboard and inventory probes returned expected HTTP 401, confirming an auth boundary but not authenticated business success.
- Latest GitHub status for that commit reports only Vercel success; GitHub Actions run listing is empty. Repository `main` has no required checks/branch protection.
- Render service metadata still reports an empty `healthCheckPath`, although `render.yaml` declares `/ready`.
- Production `lexa_runtime` remains an elevated Neon login/member of `neon_superuser`. `lexa_runtime_safe` does not exist on canonical production and migration 029 is not applied there. Read-only checks on isolated test branch `br-red-voice-b16z9b0i` show the safe role has the intended constrained attributes and can `SET ROLE lexa_app`; the safe role has no production password provisioned by this task.
- Production has RLS disabled/no policies on `permissions`, `registration_requests`, `schema_migrations`, `tenants`, and `users`. The ten sampled Universal Business Engine tables had RLS enabled and forced with policies. This is encouraging but does not prove the whole database's tenant-isolation invariants.

## Historical migration recovery investigation

The following 11 local ZIP archives were searched by exact migration basename. None contained a match for the six remaining sources; the prior candidate ZIPs did not contain the recovered 027 either, because that source was found separately in tracked Git history:

- `LEXA_Phase0-2_Final_Readiness_Candidate_2026-10-20.zip`
- `LEXA_Phase1_Consolidated_Source_and_Docs_2.9.1_2026-10-20.zip`
- Phase 2 Increment 01, 02, 03 and 04 ZIPs
- `LEXA_Visible_Frontend_Implementation_v0.7.0.zip`
- `LEXA_Visible_Product_Integration_v0.7.1.zip`
- `LEXA_Inventory_Foundation_v0.8.0.zip`
- `LEXA_Deployment_Integration_v0.6.2_Flat_Audited(1).zip`
- duplicated materialized Phase 1 consolidated source ZIP

Also checked the complete recursively listed GitHub tree, direct path history for each expected canonical filename, repository commit search by exact filename, and public web queries. Exact hits were found only for the tracked 027 source. The older `lexa_v280_src/migrations/README.md` describes `023`–`026` as historical purchasing lineage markers, but it does not contain the SQL source files. The database migration ledger records version names, not a hash of executed source bytes.

Remaining gaps:

- `010_phase2_catalog_intelligence.sql`
- `011_phase2_catalog_runtime_constraints.sql`
- `023_phase4_purchasing_core.sql`
- `024_phase4_purchasing_security.sql`
- `025_phase4_purchasing_permissions.sql`
- `026_phase4_membership_branch_integrity.sql`

They must be recovered from an owner-held backup, CI/build artifact, release package or other exact authoritative source. Do not synthesize them from the live schema.

## UI/UX research summary

The visual direction should remain a calm, professional operations workspace—restrained navy, clear surface hierarchy, status color only where meaningful, legible typography and predictable task-oriented tables. The main candidate updates focus on tablet reflow, focus visibility and touch controls. The dedicated research document [`research/LEXA_PHASE0_2_UI_UX_RESEARCH_2026-10-20.md`](research/LEXA_PHASE0_2_UI_UX_RESEARCH_2026-10-20.md) covers findings, source grounding and viewport acceptance. Sources include [W3C WCAG 2.2 target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum), [W3C focus not obscured](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum), and IBM [Carbon table guidelines](https://www.carbondesignsystem.com/building-blocks/core/components/data-table/guidelines/) and [table accessibility](https://www.carbondesignsystem.com/building-blocks/core/components/data-table/accessibility/).

## Required actions before Phase 3

1. Recover the six missing exact migration files or formally narrow the allowed next work to non-schema discovery while strict replay remains blocked.
2. Install root CI through an authorized reviewed GitHub change; run clean Node 24 and backend jobs on the candidate's exact commit, then enable required branch checks. Do not rely on ZIP extraction to install `.github/workflows/**` because the extractor protects that path.
3. Design and validate table-by-table RLS/grants behavior on an isolated Neon branch. Do not apply blanket RLS or use schema inference as source recovery.
4. Provision `lexa_runtime_safe` with an authorized secret workflow, then use the security cutover runbook for a coordinated staging/production credential change and rollback. Do not alter the elevated login in place.
5. Reconcile Render's hosted `healthCheckPath` with `/ready` using an approved release and verify the control-plane setting after the change.
6. Complete authenticated E2E on a dedicated non-production account and record tenant/branch isolation, session rotation/revocation, read/write workflows and negative paths.
7. Run a real browser viewport matrix at 320, 360, 390, 430, 600, 601, 768, 800 and 1280 CSS px plus keyboard/focus/responsive acceptance; do not claim WCAG conformity from source tests alone.

**Phase 3 go/no-go: NO-GO for production schema changes.** Non-mutating Phase 3 discovery can be prepared separately, but the current evidence does not warrant declaring Phase 0–2 fully release-accepted.
