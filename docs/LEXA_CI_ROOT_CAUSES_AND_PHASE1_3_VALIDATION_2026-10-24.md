# LEXA CI root-cause fixes and Phase 1–3 release check

**Prepared:** 24 October 2026  
**Repository:** `MONALISA2003-CMD/LEXA-`  
**Target:** `main`  
**Incident:** [GitHub Actions run 40063918855](https://github.com/MONALISA2003-CMD/LEXA-/actions/runs/40063918855)  
**Inspected source revision:** `c1a3ef18134404eaf12727f42cda0789034c0b45`

## Root causes fixed in this source overlay

### 1. Frontend TypeScript failure was a nullable profile dereference

The original daily-brief API client accessed `.currency_code` directly from `getBusinessProfile()`. Its return type includes `null`, so `tsc` correctly stopped at `lib/daily-brief-api.ts(56,36)` before running frontend contract tests or the Next.js production build.

**Fix:** resolve the profile to a local variable, optional-chain its currency field, and return a clear setup error when the business profile/currency is absent or invalid. This preserves normal behaviour while making the type/runtime boundary explicit.

### 2. Provider dotenv settings were missing from the Pydantic model

The legacy AI assistant resolves provider settings through `getattr(settings, env_name.lower(), default)`, but `Settings` did not define provider key/model fields. Because Pydantic Settings ignores extra `.env` values, the field was unavailable even when `GROQ_API_KEY` and `GROQ_MODEL` were supplied. The CI test failed when attempting to assign those missing attributes and then failed again during monkeypatch teardown.

**Fix:** define explicit provider key/model fields and AI policy configuration fields in `Settings`. Every provider key defaults to an empty string. All external-provider, paid-provider, aggregate-sharing and confidential-sharing controls remain `False` by default, so adding a key does not enable external execution. A new dotenv regression test verifies the load path and fail-closed defaults.

### 3. Migration replay tests had outdated “last migration” assumptions

Two older tests required migration `044_phase3_password_reset_security.sql` to be the final item in the replay manifest. Phase 1 and Phase 3 now correctly append forward-only candidate migrations `045_intelligence_foundation.sql` and `046_intelligence_documents.sql`, which made these positional assertions stale even though the older migrations remained in order.

**Fix:** keep the existing historical ordering checks for 042, 043 and 044, then assert that 045 and 046 follow in order. This changes the tests’ release contract, not production SQL or migration execution.

## Phase scope represented in the source overlay

- **Phase 1:** versioned intelligence contracts, default-deny routing/policy, safe capability reporting, event/job/run contracts, policy-safe provenance migration candidate 045, explicit AI pause while the legacy adapter is not wired through policy.
- **Phase 2:** deterministic daily brief built from LEXA's existing `business_insights()` output; evidence links; prioritized action/information items; stale/unavailable metrics isolated as data-quality items; no external AI and no business writes.
- **Phase 3:** bounded PDF/image upload and signature validation; local candidate extraction with evidence; content-hash duplicate detection; branch-scoped access; explicit confirm/reject; review history; `/documents` UI. Confirmation does not create or post a business transaction.

These features are implemented at source level in this overlay. They are not yet certified for production acceptance: CI after applying this fix, SQL clean replay/RLS tests on a disposable PostgreSQL instance, and authenticated staging acceptance remain release gates.

## Deployment alignment observed during this inspection

- The latest Vercel production attempt on revision `c1a3ef1` was **ERROR** and failed during TypeScript checking on the same nullable currency issue.
- The previous READY production deployment pointed at the ZIP-upload commit `efb0c75207e70d99f260727cae1c57c5ced32511`, not the current extracted source revision. It is therefore not proof that the Phase 1–3 source or the failing revision is deployed green.
- This overlay does not trigger a deployment itself. After upload to `main`, verify the follow-on `[lexa-extractor]` commit, its CI run, and the Vercel deployment for that exact source SHA.
- Render has not yet been validated live in this handoff. Its tool requires explicit confirmation of the workspace before listing services or deployments.

## Phase 3 hosted OCR blocker

`render.yaml` currently declares the service as a Native Python runtime. The extraction code relies on local `pdftotext`, `pdftoppm`, and `tesseract` binaries; the overlay's Dockerfile installs Poppler and Tesseract only for Docker-based deployment. On a Native Python runtime where these binaries are absent, the API intentionally reports extraction unavailable and leaves the document in manual review instead of sending business data to a third party. Do not claim hosted OCR is operational until tool availability is checked or a separately approved Docker/runtime change is deployed.

## Safety and validation

- No secrets or provider keys were added.
- No production SQL/migration was run; migrations 045 and 046 remain candidate migrations.
- No production service configuration or deployment was changed by preparing this ZIP.
- The local overlay does not include the complete LEXA repository. Running all legacy backend tests against just this overlay is not a valid full-suite result because some files they inspect belong to the surrounding repository and are intentionally not duplicated in the ZIP. Exact full-suite results must come from GitHub Actions after extraction.
