# LEXA — visible product integration v0.7.1

This package continues the existing LEXA implementation. It does not reset the database, reseed business data, or rebuild the application from scratch.

## What changed
- The web app now calls the FastAPI backend through a same-origin Next.js proxy at `/api/lexa/*`.
- Browser CORS is no longer the dependency for ordinary frontend API calls.
- The frontend exposes the existing register/login API so authenticated tenant workspaces can be tested from the product UI.
- Products are loaded from the authenticated tenant catalog API. There are no invented preview products.
- Overview language describes LEXA as a real multi-purpose, multi-tenant business operating system.
- Inventory, Sales, Purchasing, Transfers, Reports and Brain have visible workspace boundaries and explicitly avoid pretending unimplemented business records are live.

## Deployment variables
Vercel may keep `NEXT_PUBLIC_API_URL=https://lexa-n10e.onrender.com` for compatibility. For the server-side proxy, prefer:

`LEXA_API_URL=https://lexa-n10e.onrender.com`

The proxy falls back to `NEXT_PUBLIC_API_URL` if `LEXA_API_URL` is not supplied.

## Important
The existing FastAPI catalog endpoints require authentication and tenant membership. The UI therefore asks the user to sign in before loading tenant data. This is not seeded demo data.
