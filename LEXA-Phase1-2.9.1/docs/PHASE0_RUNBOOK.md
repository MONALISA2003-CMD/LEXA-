# Phase 0 smoke and rollout runbook

This runbook is for the existing LEXA deployment only:

- Render API service: `LEXA` (`srv-dakm8k95efls73egg9a0`), root `apps/api`
- Vercel web project: `lexa`, root `apps/web`
- Neon business database: project `wispy-mud-75323042`, branch `lexa-live` (`br-soft-star-b1dj2m2w`), database `neondb`

No second Render service or transactional database should be created.

## 1. Local source verification

From the repository root:

```bash
bash scripts/verify-phase0.sh
python scripts/check_migration_sources.py --strict
```

The normal verification command exercises the available source checks. The strict migration command is expected to fail until every exact historical migration source listed in `migrations/source_gaps.json` has been recovered and reviewed. Do not make up replacement migrations, reset the live database, or replay the current subset on production.

## 2. Public hosted probes

Use the standard-library HTTP smoke runner:

```bash
python scripts/smoke_phase0.py
```

It checks `/health`, `/ready`, a refresh request without a cookie (must be `401`, not `422`), and anonymous logout idempotence. Readiness must include both `dependencies.database: ok` and `dependencies.cache: ok`; HTTP 200 by itself is insufficient.

## 3. Credentialed session acceptance

Use a dedicated test account only. Do not use an owner's personal account. Provide secrets through environment variables; never commit them or include them in shell history:

```bash
export LEXA_SMOKE_API_URL='https://lexa-n10e.onrender.com'
export LEXA_SMOKE_EMAIL='phase0-test-account@example.test'
read -s LEXA_SMOKE_PASSWORD && export LEXA_SMOKE_PASSWORD
# Set only if this account belongs to multiple workspaces:
export LEXA_SMOKE_TENANT_ID='the-authorized-test-workspace-uuid'
python scripts/smoke_phase0.py
unset LEXA_SMOKE_PASSWORD LEXA_SMOKE_EMAIL LEXA_SMOKE_TENANT_ID
```

With explicit credentials, the runner logs in, checks refresh cookie presence and rotation, calls `/api/v1/auth/me`, performs a protected tenant-scoped product-list read, logs out, verifies the rotated refresh token is rejected, and confirms the access token no longer authorizes identity. It does not print passwords, access tokens, or refresh-cookie values. Run it only with an approved dedicated test account because login creates a session row and the script intentionally revokes it at the end.

## 4. Deployment reconciliation

Before promoting the updated source:

1. Apply `DELETE.txt` to an existing checkout with `bash scripts/apply-deletion-manifest.sh` and review the resulting diff. The obsolete unregistered API route module must be removed along with the retired frontend-only routes.
2. Ensure the GitHub source reflects the reviewed ZIP, `apps/web/package-lock.json` is committed, and the standard Vercel build runs from `apps/web` with `npm ci`.
3. Update the health-check setting on the existing Render service `LEXA` to `/ready`. The current connected Render tool cannot directly update this field; the `render.yaml` change alone does not alter an already-created service's dashboard setting.
4. Deploy the reviewed code through the existing service integration, then verify `/ready` reports both database and cache dependencies.
5. Complete the credentialed smoke runner and keep its non-secret output alongside the release review.

Do not deploy this candidate while the reviewed source files are not reflected in the connected GitHub repository. GitHub branch creation returned `403 Resource not accessible by integration`, so this archive is the handoff path until write access is available.
