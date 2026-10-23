# LEXA Phases 0–2 Implementation Candidate

**Status date:** 23 October 2026  
**Scope:** Phase 0 baseline/release safety, Phase 1 shared front-end UX foundation, Phase 2 business setup and configuration readiness.  
**Release state:** local implementation candidate only; not merged, deployed, or applied to live database.

## Phase 0 — baseline and release safety

### Verified baseline

- GitHub `MONALISA2003-CMD/LEXA-`, `main`: `f56e8429bcca25e966e8e78aee0588635036bf08`.
- Vercel production alias `lexa-green.vercel.app`: READY deployment `dpl_Eea4a15ogFy3DXsNKT71WAjRNBZp`, source commit `f56e8429bcca25e966e8e78aee0588635036bf08`.
- Render API service `LEXA` (`srv-dakm8k95efls73egg9a0`): latest live deploy uses that same commit; auto-deploy is enabled on `main`.
- Neon `lexa-live` branch `br-soft-star-b1dj2m2w`: read-only migration-ledger check shows the latest recorded migration is `031_phase3_auth_surface_rls`.
- Existing CI workflow already defines backend contract tests, frontend Node 24 typecheck/contracts/build, guarded clean PostgreSQL replay and opt-in disposable-staging E2E. This candidate has not run on GitHub Actions because it could not be pushed as a branch.

### Release blockers still open

1. **GitHub write permission:** creating `codex/phase-0-2-readiness-2026-10-23` returned HTTP 403 (`Resource not accessible by integration`). The candidate is therefore not in a remote branch or PR.
2. **Database source drift:** current live `lexa-live` is recorded through migration 031 while source/replay manifests include forward candidates through 042. The 46-input replay *plan* passes, but it executes no SQL and does not prove those migrations work. Six reconstructed historical replacements remain pending semantic validation through an isolated clean replay. Never run the clean replay against production.
3. **Build gate:** frontend dependencies are not installed in this runtime; its Node version is 22.16.0 while the project CI/build target is Node 24. Full package typecheck and production build therefore remain unverified here.
4. **Hosting readiness:** Render service configuration currently has no health-check path configured even though the source exposes readiness endpoints. Align and test this in hosting settings before treating readiness monitoring as closed.
5. **Capacity and recovery:** no concurrent-user load test or backup/restore drill was performed. No 5,000-user capacity claim is made.

No production deployment, production SQL, migration, or business-record mutation was performed for this implementation.

## Phase 1 — shared front-end UX foundation

- Same-tab authenticated navigation now reuses the verified session snapshot and shares in-flight session restoration rather than refreshing the cookie-backed session on every page-shell mount.
- Setup progress retains the last verified, tenant-keyed snapshot while refreshing. The shell no longer blanks an already-open module while the setup-progress request is pending on route changes.
- Mobile tables and forms are constrained to their parent width; wide compliance tables scroll within their own wrapper. Report-period controls retain wrapping/touch sizing on narrow viewports.
- Compliance screens distinguish empty tax/document history from unavailable data, use an internal Next link for the Back action, and expose status/error feedback accessibly.

## Phase 2 — business setup and readiness

Required readiness checks are derived from persisted configuration, not a previously stored “completed” flag:

1. Business name and country are present.
2. A well-formed three-letter business currency is saved.
3. An active branch exists.
4. An active stock room exists.
5. An active stock location exists.
6. At least one active payment channel exists in the **same currency** as the business profile.
7. Accounting accounts and mappings exist for basic money tracking.

Tax-rule review and team-access review are visible recommended checks but do not block basic setup completion. The Tax and official receipts screen now includes validated forms to add a tax rate and assign a saved rate to a default rule. It does not prescribe legal tax rates or invent values; the user must enter values confirmed for the business. Product/category scoped rules remain outside that form because they require choosing the relevant product/category identifier.

- The administration and settings pages share the same country/currency options and render dropdowns instead of requiring users to type codes.
- The setup screen explains which settings must be checked, shows required progress separately from recommended checks, and routes payment-method setup directly to the matching Sales tab.
- The Sales tab selector now honours `?tab=Payment methods` instead of immediately overwriting it with `New sale`.
- First-run initialization adds a currency-specific active Cash method if needed; it retains old rows and history. It refuses to guess UGX when a legacy business profile has no valid currency. Initialization remains owner/administrator-permission gated, idempotent, audited, and is triggered only by an explicit setup action.

## Validation performed on this candidate

| Check | Result |
|---|---:|
| Frontend contract tests (`node --test tests/*.test.mjs`) | **58 passed, 0 failed** |
| Python suites (`PYTHONPATH=apps/api pytest -q tests apps/api/tests`) | **280 passed, 0 failed; 1 existing Starlette deprecation warning** |
| Backend `compileall` | **Pass** |
| Frontend action audit | **Pass** — 29 TypeScript/TSX files; 205 button-like controls, 48 forms, 72 links checked |
| Migration recovery manifest/hash checks | **Pass** |
| Strict migration-source reconciliation | **Pass for recorded source dispositions; semantic validation still pending** |
| Clean replay planning | **Pass** — 46 migration inputs hashed; no database connection and no SQL executed |
| Node 24 typecheck / Next production build | **Not run** — runtime/dependency constraint described above |
| Authenticated staging E2E | **Not run** |
| Production data/schema/hosting mutation | **None** |

## Review and rollout gate

This is not a production release yet. First apply the candidate to a remote review branch, run the complete CI workflow on that exact SHA, get clean-replay evidence from isolated PostgreSQL, verify Vercel and Render builds on the same approved source revision, then complete staged role/currency/payment setup flows and a rollback plan. Only then should a release be considered. Live Neon migrations remain untouched.

### Additional Phase 2 tax configuration

- Added a controlled tax-rate form for code, name, percentage (0–100), inclusivity, start date and optional end date, including date-range validation.
- Added a default-rule form that requires explicit selection of a saved rate and effective dates. It validates date ranges and does not silently pick a tax rate. Product/category scopes are disclosed as not covered by this default-rule form.
- Added saved tax-rule table and explicit save/error feedback. Empty tax rates/rules remain distinct from a failed fetch.
- This UI does not assert regulatory correctness of a tax rate and does not replace an approved URA/EFRIS connector.
