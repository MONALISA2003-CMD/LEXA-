# LEXA live remediation verification — 13 October 2026

**Scope:** LEXA Neon project/branch, LEXA Render service in the user-approved `My Workspace`, and this LEXA source package only.

## Completed

- Approved migration 028 applied to Neon `LEXA` project `wispy-mud-75323042`, branch `lexa-live` (`br-soft-star-b1dj2m2w`), database `neondb`.
- Ledger records the migration exactly once. Lookup function exists exactly once; `lexa_app` can execute it; the function is `SECURITY DEFINER`; its owner has `BYPASSRLS`; an invalid test token returns no rows.
- The 24 raw USING/WITH CHECK expressions (12 policy pairs) were converted to empty-safe predicates; post-migration raw tenant cast count is zero.
- The refresh hash associated with a prior Render 500 now returns one valid session through the lookup function. No raw cookie value is present in this file.
- Vercel `lexa-green.vercel.app` has a `READY` production deployment on commit `fd59d989a8c4ecc3c6a3689dbc2ece315376f34b`, matching the latest Render deploy. Both `LEXA_API_URL` and `NEXT_PUBLIC_API_URL` are configured to the LEXA Render URL `https://lexa-n10e.onrender.com`.
- Render logs established the concrete failure: `POST /api/v1/auth/refresh` produced HTTP 500 because `public.lexa_find_session_by_refresh_hash(unknown)` did not exist.
- Package source and documentation have been updated with the applied SQL, readiness hardening, and live forensic evidence.

## Outstanding

- No post-migration authenticated browser/API request was captured; no successful production session restore can yet be claimed.
- The Render service's actual Health Check Path setting is blank, despite `render.yaml` specifying `/ready`.
- GitHub `main` remains behind this reviewed ZIP in `apps/api/app/health.py` and the migration 028 policy-rewrite implementation.
- Vercel production commit and API origin were verified, but Vercel runtime-error reads returned 403, so no post-migration runtime success record is available.
- No GitHub source push, Vercel deploy, or manual Render deploy was made. The ZIP must be delivered to the LEXA source/extractor pipeline, then the deployment and real browser smoke test must be checked.

## Production acceptance checklist

1. Deploy the reviewed source ZIP only to the LEXA repository/pipeline after checking the diff.
2. Set the LEXA Render service health check to `/ready`; confirm the service's DB identity and readiness result.
3. Verify the Vercel production commit and proxy API origin.
4. In a real browser, login → POST refresh → confirm cookie rotation → GET `/api/v1/auth/me` → reload → load dashboard/catalog/inventory → logout → confirm revoked-cookie behavior.
5. Check Render for no new refresh/me 5xx. Keep the Phase 0 acceptance gate open until this passes.
