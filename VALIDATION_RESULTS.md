# Validation record — LEXA central AI policy integration package

**Target repository:** `MONALISA2003-CMD/LEXA-`  
**Branch:** `main`  
**Current branch head inspected for this package:** `1958b27ba3b54bb5930c0b79b119a4951188379b`

## Checks completed during package preparation

- Read current central policy, routing contracts, API assistant route, settings, tests and current branch head using the GitHub repository connection.
- Confirmed that the checked-out Git blob IDs for `apps/api/app/main.py` (`6ebd746b06a05d257ce2f266a94d463a4b1411cf`) and `apps/web/package.json` (`a28a43c9e435f4838c85fb124d194f8b51326b3c`) match the source-marker files shipped with the overlay.
- Python syntax compilation passed for `scripts/lexa_apply_ai_router.py`, `docs/LEXA_AI_MODEL_REGISTRY_SOURCE.py`, and the expanded mock-only test asset `docs/LEXA_AI_MODEL_REGISTRY_TESTS.py` after this turn's edits.
- Added a central model-level policy gate that requires exact provider/model registration and allowlists, task support, server-side key configuration, model cost classification, paid-use approval where required, and approved sensitivity. No request-supplied safety status is trusted.
- Kept `input_safety_checked=False` in the legacy user free-text route and retained the separate middleware gate. Provider execution remains unavailable while trusted input classification/redaction is not wired.
- Added offline synthetic examples for small businesses in Kampala, Wakiso, Mbarara and Jinja, including UGX amounts, missing values and accounting caution. Added mock-only tests for Redis rate-limit exhaustion, provider 429/quota exhaustion, provider 5xx errors, and privacy-gate bypass attempts.
- Adjusted the aggregate-only summary query to preserve NULL/missing values rather than coalescing them to numeric zero. Added a regression test for this contract.
- Provider/Redis tests are written with fakes/mocks and do not require production keys, live provider credits or a running Redis server.

## Not yet verified / deployment boundary

- The full API pytest suite has **not** been run against the complete current repository after these latest edits.
- The complete frontend typecheck, frontend test suite, production build, Compose validation and HAProxy validation have **not** been run against the current package after these latest edits.
- GitHub write integration remains unavailable (earlier repository write attempts were rejected with HTTP 403), so this package has not been committed or run in GitHub Actions by this session.
- No provider keys or environment variables were added to Render. No production data, DB schema, accounting transactions or deployment settings were changed.
- No live provider request was made.

## Release gate

Keep external provider execution disabled. In Render keep `LEXA_AI_EXTERNAL_PROVIDERS_ENABLED=false`; leave provider and model allowlists empty, and keep paid-use, aggregate-data and confidential-data approval flags false. Do not open the legacy assistant middleware or set `input_safety_checked=True` until trusted input classification/redaction, privacy review and the full CI gate are complete. The provider-key guide is provided for later setup only; keys do not by themselves authorize execution.
