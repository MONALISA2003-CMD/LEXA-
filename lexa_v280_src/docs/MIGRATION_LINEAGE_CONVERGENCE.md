# LEXA migration lineage convergence

## Problem fixed
The live Neon branch and repository used the same numeric migration identifiers for different historical work. Production contained purchasing markers 023–026 while GitHub contained the identity/tenancy 023 migration. The release contract now preserves both histories and converges at migration 027 rather than renumbering or deleting production history.

## Release contract
The canonical branch is `wispy-mud-75323042 / br-soft-star-b1dj2m2w / neondb`. Production readiness requires canonical database identity, the complete operational schema, the convergence marker, and Redis availability.

## Frontend
The invitation page isolates `useSearchParams()` under `Suspense`, matching the Next.js production requirement for static routes.

## Authentication
Malformed legacy/dev password hash values now fail closed as invalid credentials rather than becoming internal server errors. Actual user credentials are not auto-reset by this patch.

## Analytics
Inventory sales velocity counts sale-referenced negative inventory movements only, and business-date calculations are tenant-timezone aware.
