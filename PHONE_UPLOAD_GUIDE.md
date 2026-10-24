# LEXA central AI policy build — phone upload guide

This ZIP is a guarded source overlay for `MONALISA2003-CMD/LEXA-`. It is not a full copy of the application.

## Apply it from GitHub on Android

1. Download `ZZZ_LEXA_CENTRAL_POLICY_EXECUTION_MAIN_2026-10-24.zip` to your phone.
2. Open `https://github.com/MONALISA2003-CMD/LEXA-`, sign in, choose **Add file → Upload files**, select this ZIP, and commit the upload on `main`. The repository's existing LEXA ZIP Extractor handles the overlay and removes old temporary bundle markers listed in `DELETE.txt`.
3. Wait for the LEXA ZIP Extractor workflow to finish. If it fails, do not enable provider settings; share the failing run link so the exact error can be diagnosed.
4. The extractor protects `.github/workflows` from ZIP writes. Therefore, in GitHub create `.github/workflows/lexa-ai-router-build.yml`, copy the full contents of `docs/LEXA_AI_ROUTER_WORKFLOW.yml` into it, and commit. Keep the filename ending in `.yml`.
5. Open **Actions → LEXA Model Registry and AI Router Build → Run workflow** on `main`, keep the confirmation checked, and run it. This job checks the API suite, offline AI tests, frontend typecheck/contracts/build, Docker Compose and HAProxy. It pushes application changes only if all checks pass.
6. After it completes, verify the new source commit and the normal main CI workflow. This package has not itself been run against a full checkout from this chat, so do not treat the integration as validated until both are green.

## Render settings while integration is in progress

Do not enable external execution to make CI pass. Keep these values in the private Render API service environment:

- `LEXA_AI_EXTERNAL_PROVIDERS_ENABLED=false`
- `LEXA_AI_ALLOWED_PROVIDERS` empty
- `LEXA_AI_ALLOWED_MODELS` empty
- `LEXA_AI_PAID_PROVIDERS_ENABLED=false`
- `LEXA_AI_AGGREGATES_EXTERNAL_ENABLED=false`
- `LEXA_AI_CONFIDENTIAL_EXTERNAL_ENABLED=false`

Provider API keys are optional and not used by the CI tests. If you choose to store one for a later approved phase, use the exact variable and official account page in `API_KEYS_FOR_RENDER.md`. Never put a key in GitHub source or send it in a chat. Adding a key does not enable provider execution.
