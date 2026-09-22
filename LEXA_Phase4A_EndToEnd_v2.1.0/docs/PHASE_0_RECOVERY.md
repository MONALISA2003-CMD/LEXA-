# LEXA Phase 0 — Recovery & Baseline Lock

**Status:** Source implementation complete. Final hosted-runtime confirmation requires the repository/Render control plane that owns `lexa-api`.

## Exit gate

Phase 0 is complete only when these boundaries are green together:

```text
Render API process
      ↓
/health
      ↓
/ready
      ↓
Canonical LEXA Neon identity
      ↓
Required schema
      ↓
Dev-session / real auth boundary
      ↓
Frontend bootstrap
```

## Canonical database boundary

All readiness checks are hard-locked to the LEXA Neon project only:

- Project: `wispy-mud-75323042`
- Branch: `br-soft-star-b1dj2m2w` (`lexa-live`)
- Database: `neondb`
- Endpoint: `ep-fragrant-grass-b1n0moer`

Identity values are normalized with `.strip()` before comparison so a managed environment value with a trailing newline cannot produce a false branch mismatch.

The backend also verifies `neon.project_id`, not only the branch ID. Production readiness returns only the stable failure code, while non-production exposes bounded diagnostics useful on Render free compute where no interactive shell is available.

## Source fixes included

- Canonical LEXA project ID added to backend configuration.
- Canonical LEXA project ID added to Render configuration.
- Canonical branch and project identity normalized before comparison.
- Development readiness diagnostics report the first identity mismatch and missing required tables without exposing database secrets.
- Frontend catalog contract aligned without weakening its existing test.
- Phase 0 readiness contract tests added.
- Existing backend suite remains green.

## Neon safety

No Phase 0 migration, seed reset, branch creation, branch deletion, or production data operation is required by this change. Read-only verification was performed only against the LEXA project.

## Deployment boundary

The connected GitHub integration exposes no repositories and the connected Vercel account exposes no teams, so this environment cannot directly push the source to the hosted control plane. The package is deploy-ready; the remaining hosted step is a normal Render deployment from the repository that owns `lexa-api`.
