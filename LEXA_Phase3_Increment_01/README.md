# LEXA Phase 3 — Increment 01: Workspace Configuration

**Target repository:** `MONALISA2003-CMD/LEXA-`  
**Pinned base:** `f48e201fc8c4ed0a9ff1551c0b99451a7eb500dd`  
**State:** source-only candidate overlay; not committed, merged, deployed, or applied to a remote repository.

## What this increment implements

- Replaces the Administration placeholder with a real workspace-configuration screen for business profile, branches, warehouses, and stock locations.
- Adds client API helpers for reading/creating/updating the business profile and creating/updating branches. Mutations send an `Idempotency-Key`.
- Adds business-profile update and branch update endpoints, and upgrades profile/branch/POS writes to the same idempotent, audit/outbox pattern already used by warehouse/location creation.
- Normalizes input names and codes, rejects empty patches, maps idempotency conflicts to HTTP 409, handles uniqueness conflicts, and checks branch/warehouse parent IDs against the selected tenant.
- Disables writes in the UI when any initial workspace configuration dataset could not be loaded, avoiding a create flow based on incomplete state.
- Adds source-contract and route-unit tests.

## Files

- `overrides/` — full replacement source for the API organization routes and Administration page.
- `scripts/extend-api-helpers.py` — hash-anchor-based, fail-closed insertion of API client helpers.
- `scripts/apply-phase3-increment01.sh` — local apply script. It refuses to run unless `HEAD`, the worktree cleanliness, and the three source blob hashes match the pinned base.
- `scripts/validate-phase3-increment01.sh` — full validation command to run after applying the candidate in the real LEXA checkout; enforces Node 24.
- `scripts/validate-bundle.sh` — self-validation using disposable fixture models, static contracts and a TypeScript contract fixture.
- `tests/` — route source-contract, route mutation-unit, and UI/client contract tests.
- `docs/PHASE3_INCREMENT_01_IMPLEMENTATION_REPORT.md` — evidence and limitations.
- `docs/PHASE3_INCREMENT_01_VALIDATION_RESULTS.json` — structured results and explicit not-run items.
- `docs/PHASE3_INCREMENT_01_ACCEPTANCE_MATRIX.md` — next required isolated-database and credentialed browser acceptance.
- `fixtures/` — isolated test fixtures for validating the bundle without the LEXA working tree.

## Apply (only to the pinned, clean LEXA checkout)

Run from inside the repository checkout:

```bash
bash /path/to/LEXA_Phase3_Increment_01/scripts/apply-phase3-increment01.sh
```

Review the resulting diff before running tests or committing. The script changes only the listed API, frontend, and test source files. It does not execute migrations, touch database resources, change credentials, configure CI/branch protection, or deploy services.

## Validate in the real checkout

After applying, run:

```bash
bash /path/to/LEXA_Phase3_Increment_01/scripts/validate-phase3-increment01.sh
```

This performs the full local Python suite and frontend clean install/typecheck/tests/build. Credentialed browser acceptance and two-tenant PostgreSQL/RLS integration remain separate release gates and are not represented as passed by the local contract tests.

## Important safety boundary

This increment is intentionally limited to non-schema business-configuration workflows. It does not implement workspace invitations, membership management, permission assignment UX, branch-user assignments, or session/device controls; those remain subsequent Phase 3 increments. It introduces **no migration SQL**. Production release remains NO-GO until the existing migration provenance, least-privilege role, CI/protection, and acceptance gates are satisfied.
