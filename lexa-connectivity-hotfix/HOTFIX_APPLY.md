# LEXA hotfix application

Copy these three files into the existing repository root without replacing the rest of the current LEXA tree:

- `files/apps/web/app/page.tsx`
- `files/apps/web/app/globals.css`
- `files/apps/web/lib/api.ts`

This is intentionally a focused patch. It does not contain or replace the database migrations already present in the current repository.

Before redeploying, verify Render is running an API commit that includes `/api/v1/auth/dev-session` and is connected to the LEXA `lexa-live` branch.
