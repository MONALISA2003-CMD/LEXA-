# Applying the LEXA main-branch AI and Docker increment

1. Confirm the selected target branch is **main** (not `LEXA-branch`).
2. Upload this ZIP to the repository so the existing LEXA ZIP Extractor workflow validates and extracts it. It is a source overlay, not a full replacement of the repository.
3. Wait for the extractor to create its `[lexa-extractor]` commit, then inspect the changed files on main.
4. Configure provider keys only as backend secrets/environment variables. Leave keys blank to disable a provider. Do not put keys in browser variables or commit them.
5. For local Docker, set environment variables as needed and run `docker compose up --build`; use `http://localhost:3000` as the entry point. This is a local single-host development topology, not production HA.
6. Review `docs/AI_AND_DOCKER_MAIN_BUILD.md` before sending business data to any external model.

## Validation boundary

This increment includes source/unit tests, a frontend route, and Compose/HAProxy configuration. It does not use provider keys, consume AI quota, mutate production hosting, run expensive staging/pre-production E2E gates, or approve a production release.

## Workflow discovery issue

In the inspected `main` tree, the LEXA CI workflow appears nested at `.github/workflows/.github/workflows/lexa-ci.yml`, rather than directly under `.github/workflows/`. GitHub Actions only discovers workflow files directly in `.github/workflows/`. The ZIP extractor intentionally protects that directory, so moving/creating the lightweight main CI workflow requires a separate repository workflow change. Do not assume CI ran merely because the ZIP extractor succeeded.
