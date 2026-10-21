# Increment 08 patch application

This patch is an overlay for the supplied `LEXA_Phase0-2_Closure_Increment_07_2026-10-20.zip`. Paths are repository-relative. It contains reconstructed-source equivalents, provenance/replay evidence, a hash/separation checker, a candidate CI workflow and the portable browser acceptance test source.

1. Apply the overlay on a **new feature branch** in an authorized LEXA repository checkout; do not unzip directly into `main` or a live deployment workspace.
2. Review every SQL file in `migrations/reconstructed/`. None is the historical source. Never rename an equivalent to an original migration path.
3. Run `python scripts/check_migration_recovery_manifest.py`, `python scripts/check_migration_sources.py`, the Python suites, and the clean Node 24 frontend checks.
4. The CI candidate has not been installed in GitHub. Submit it through a reviewed pull request and enable required checks/branch protection after successful runs on the exact commit.
5. Playwright sources are included but the Playwright package and lock update are not. In an authorized Node 24 environment, add the test dependency, install Chromium, regenerate and review `apps/web/package-lock.json`, run `npx playwright test`, and only then wire this browser job into required CI.
6. Do not execute reconstructed SQL against the production database. Use a new isolated replay database, synthetic fixtures and a complete schema/function/policy diff.

Applying this patch does not itself authorize a production release or indicate that Phase 3 gates are passed.
