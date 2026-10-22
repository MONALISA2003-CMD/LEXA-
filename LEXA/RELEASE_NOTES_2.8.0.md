# LEXA v2.8.0 — Workspace Convergence & Inventory Operations

## Release focus

This release takes the v2.7.0 Catalog and Inventory UI foundation deeper into an operational workspace. The emphasis is reusable workspace structure, real inventory workflows, and commercially meaningful product identity.

## Frontend

- Added a coherent authenticated `AppShell` across core workspace routes.
- Replaced the monolithic Home surface with a Command Centre focused on today's business state, attention items, operational work and fast paths.
- Deepened Products with variant lifecycle, SKU/costing fields, barcode management, price lists, effective-dated prices and per-variant inventory visibility.
- Deepened Inventory with stock/ledger investigation plus adjustment, stock-count, transfer and location workflows.
- Added product and inventory loading/error boundaries.
- Added route aliases for Sales and Customers to remove broken shell navigation.
- Added global search/command navigation with Ctrl/Meta+K and explicit loading/error state boundaries.
- Added honest foundation routes for Purchasing, AI Intelligence, Administration and Settings while their deeper domain slices remain scheduled for subsequent vertical releases.
- Converged Accounting, Reports and Compliance into the shared workspace shell.

## Backend

- Added active barcode listing by variant.
- Added idempotency handling, audit records and domain events to warehouse/location creation while retaining Neon as the authoritative source of business state.
- Extended mutation replay safety to variant updates, barcode creation, price-list creation and price creation.
- Preserved deterministic inventory state transitions and existing authorization requirements.

## Authentication UX

- Introduced a typed `ApiError` so the browser can distinguish a real 401 sign-out condition from a temporary upstream/service failure.
- The authenticated shell no longer silently redirects to login when the API/database is temporarily unavailable.

## Verification

- `python -m pytest -q` → **96 passed**.
- Visible frontend contract → **PASS**.
- Frontend TypeScript/TSX syntax transpilation → **PASS (25 files)**.
- Backend Python compilation → **PASS**.
- Full Next.js dependency-backed typecheck/build was not rerun locally because the sandbox has no installed frontend dependency tree; Vercel sandbox creation was denied by account permissions. The release therefore does not claim a fresh full Next.js build in this package.

## Database / deployment

- No production Neon migration was introduced for this UI release.
- GitHub write access remains unavailable in the current integration, so this release is packaged for manual deployment.
- Render production readiness remains separately blocked by the unresolved Neon connection failure documented in the existing deployment hardening work.

## Next vertical

The next substantive domain slice is Purchasing: suppliers, purchase orders, receiving, partial receipt and purchase-to-inventory posting. Sales/POS follows with deterministic payment and receivable behavior.