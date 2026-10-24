# LEXA model registry + central policy build

**Target repository:** `MONALISA2003-CMD/LEXA-`  
**Target branch:** `main`  
**Current main commit inspected for this package:** `1958b27ba3b54bb5930c0b79b119a4951188379b`

This is a guarded source-overlay package for the existing LEXA ZIP Extractor. It carries the reviewed model-registry source and mock-only test as documentation assets, materializes them into active paths only when the guarded build runs, then applies controlled edits to the current source and stale CI assertions using `scripts/lexa_apply_ai_router.py`.

## Changes in this build

- Registry support for up to 20 provider/model entries.
- At most four enabled/allowlisted entries that might incur a charge (`paid`, `trial_credit`, or `unknown`). Only a model verified as zero-priced can be classed `free_quota` without using one of those billable slots.
- Separate provider and model allowlists; exact model IDs; server-side JSON model catalogue; duplicate/invalid IDs rejected.
- Central model-aware policy for provider configuration, model enablement, task support, data sensitivity, model-level and global aggregate/confidential-data approvals, paid-use opt-in, and the four potentially billable model cap.
- The model selected by the policy is the model passed to the existing provider adapter.
- Mock-only tests for registry parsing, policy cases, model ID selection and blocked adapter execution.
- CI assertions corrected to match the UI currently committed on `main`. UI copy itself is not changed in this build.
- Local Compose and `.env.example` declare the registry controls with all external execution and paid/data-sharing flags defaulting to `false`.

## Why the assistant remains closed

The public `POST /api/v1/ai/assist` is still intercepted by LEXA's existing fail-closed middleware. The route handler itself also rejects requests until a trusted input-screening/redaction stage is wired and marks the request safe. That is intentional: this build supplies the central registry and policy layer, not the missing trusted input classifier. It must not be enabled by simply adding a provider key or changing an environment flag.

No provider is contacted during the build or CI. The mock tests replace the HTTP adapter and Redis rate-limit dependency. No provider secrets, hosted Render settings, production data, database schema, accounting transactions or business permissions are changed by this package. A synthetic prompt scenario validates the safety contract and prompt guidance; it is not a live model-quality evaluation.

## Installation steps

1. Upload this ZIP itself to the repository root on `main` and wait for **LEXA ZIP Extractor** to finish. The source markers are included byte-for-byte from the inspected `main` commit; the temporary migration marker and older archive names are listed in `DELETE.txt`.
2. Because the extractor intentionally skips `.github/workflows`, create `.github/workflows/lexa-ai-router-build.yml` manually on `main` by copying `docs/LEXA_AI_ROUTER_WORKFLOW.yml`, then commit that workflow file.
3. Open GitHub Actions, run **LEXA Model Registry and AI Router Build** on `main`, and confirm the update input.
4. The workflow applies source changes, runs Python compilation and the complete API suite, runs all frontend contract tests/typecheck/production build and validates Compose/HAProxy. It commits changes only if every check passes.
5. Inspect the resulting source commit and the subsequent standard **LEXA Main Build CI** run. Confirm Vercel and Render are on the intended commit before any production gate is considered satisfied.

The package does not directly change the active workflow directory. The separate workflow installation is a required repository step, not an application-code limitation.


## Render API key names

See [`API_KEYS_FOR_RENDER.md`](API_KEYS_FOR_RENDER.md) for the exact supported key environment-variable names and the official provider pages where each can be created. During this integration, do **not** enable external execution: keep `LEXA_AI_EXTERNAL_PROVIDERS_ENABLED=false`, `LEXA_AI_ALLOWED_PROVIDERS` and `LEXA_AI_ALLOWED_MODELS` empty, and paid/aggregate/confidential approvals false. Keys are not needed by CI and should not be added merely to make tests pass.

The additional synthetic regression cases and expected behavior are listed in [`docs/LEXA_AI_SYNTHETIC_TEST_PLAN.md`](docs/LEXA_AI_SYNTHETIC_TEST_PLAN.md).
