# Apply the LEXA authentication/RLS hotfix

This ZIP is a source overlay for the LEXA repository. It does not deploy itself.

## Contents

- `apps/api/app/routes/auth.py` — fixed backend route, at the same root path Render runs from.
- `apps/api/tests/test_auth_login_workspace_context.py` — focused regression tests.
- `AUTH_RLS_CONTEXT_FORENSIC_REPORT_2026-10-22.md` — evidence, root causes, fix summary, test results, and release blocker.
- `TEST_RESULTS.txt` — commands and observed results.

## Apply

1. Extract the ZIP at the **repository root** so `apps/api/app/routes/auth.py` overlays the same path configured as the Render service's `rootDir: apps/api`.
2. Review the file diff before committing; this hotfix changes authentication route context only, plus regression tests.
3. Run the focused test command in `TEST_RESULTS.txt` and the repository's normal CI suite.
4. Publish to the repository branch Render deploys (`main`) once GitHub write permission is restored.
5. Confirm the exact Render deployed commit, then test login and new workspace registration with disposable test credentials.

Do not copy the file to `source/apps/api/...` and assume Render will use it. The live Render service is configured to run from the repository-root `apps/api` tree.

No migration is included or needed for this code fix. Do not modify live RLS policies or production account data to work around the bug.
