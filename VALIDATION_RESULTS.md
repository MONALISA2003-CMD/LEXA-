# Validation record — LEXA AI router build

**Target:** `MONALISA2003-CMD/LEXA-`, `main`  
**Main commit inspected:** `92cde279faeda3f379bcb83b6c0d219710c146d7`

## Checks completed in this session

- The current main commit and relevant source files were re-read through the GitHub connection.
- The source-overlay `apps/api/app/main.py` marker matches the current Git blob SHA `6ebd746b06a05d257ce2f266a94d463a4b1411cf`.
- The `apps/web/package.json` marker matches the current Git blob SHA `a28a43c9e435f4838c85fb124d194f8b51326b3c`.
- Python syntax compilation passed for the model-registry source asset, the installer script, and the mock-only test asset.
- A synthetic checkout fixture applied the script successfully and a second application made no further changes (idempotency check).
- The isolated registry smoke test was rerun against the current source and passed for built-in model records, exact provider/model matching, cost classification, allowlist parsing, JSON size limits, duplicate-ID rejection, OpenRouter dynamic-alias restrictions, and secret-free status output.
- The guarded workflow template parsed as YAML. The installer fixture passed a second-application idempotency check after materializing the registry and mock-test assets.
- The script's CI patch map reflects stale assertions observed in the current main CI log: navigation labels, assistant-disabled wording, daily overview data-quality wording and demand-forecast search copy.
- The guarded installer materializes the registry/test into active paths only when the workflow runs, avoiding a partially applied app commit, and bumps the central policy version to `phase2-model-registry-v1`. The model registry design restricts free/trial/unknown-cost models to synthetic public input; blocks personal data to every external model; requires a provider allowlist + model allowlist; and caps potentially billable enabled model IDs at four.

## Not yet verified

- The complete LEXA API test suite has not been run against a full checkout with these edits.
- The complete frontend typecheck, test suite and production build have not been run locally against the full repository.
- The updated CI and source changes have not been committed to GitHub from this session; the GitHub write integration previously returned `403 Resource not accessible by integration`.
- No live model/provider request has been made, and no hosted secrets, Neon schema, production data or deployments were changed.
- Full main CI and deployment status must be checked after the workflow is installed and run in GitHub. Zero bugs cannot be guaranteed before those full checks pass.

## Release gate

Keep external model execution disabled. Treat the CI workflow as the final source gate. Do not remove the legacy assistant middleware or enable a provider until a trusted classification/redaction stage, privacy approval, paid-use controls and full CI are complete.
