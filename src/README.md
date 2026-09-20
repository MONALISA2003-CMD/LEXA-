# LEXA — Open Development v1.5.1

LEXA is being implemented as a real multi-purpose, multi-tenant business operating system. This package continues the existing LEXA implementation and focuses on the customer-facing experience, workspace authentication, responsive navigation and deployment readiness. It does not rebuild the application or reset business data.

## What this release delivers

- LEXA branded public landing experience using the supplied LEXA identity
- Responsive desktop, tablet and mobile workspace shell
- Mobile navigation drawer and bottom navigation
- Branded sign in and workspace creation flows
- Password validation, reveal control and friendly sign-in errors
- Mobile keyboard-safe and focus-managed authentication modal
- Customer-safe network failure handling with no raw browser diagnostics
- Automatic workspace resolution for accounts with one workspace
- Workspace picker for accounts with multiple workspaces
- Session persistence for the active workspace
- Friendly workspace connection messaging with no infrastructure diagnostics in the customer UI
- Authentication state cleanup and active-workspace session persistence
- Product workspace connected to the live tenant catalog APIs
- Existing inventory workspace retained in the source package for the next product phase
- Browser icons and metadata aligned to the LEXA brand
- Additive workspace registration hardening migration 008
- Additive workspace selection function migration 009
- Canonical database readiness guard bound to the LEXA live Neon branch

## Customer experience boundary

The browser experience does not expose database names, internal service names, request identifiers, HTTP diagnostics, migration names or deployment details. Technical diagnostics remain server-side.

## Database state

The canonical populated LEXA database is Neon branch `lexa-live` (`br-soft-star-b1dj2m2w`) in project `LEXA` (`wispy-mud-75323042`). It has no expiry, is the project default branch, and is the branch the application readiness check accepts. The empty legacy `production` branch remains untouched.

Migrations 008 and 009 are applied and verified on `lexa-live`. The inventory migration `005_inventory_foundation.sql` remains in the repository as an existing implementation artifact, but it is not part of this release's database deployment.

The current Neon plan does not allow another protected branch, so `lexa-live` is non-expiring and default but not protected by the branch protection flag.

## Validation

The Python test suite passes with 44 tests. Frontend TSX/TS source files were syntax-checked with TypeScript parsing and the customer-language/product-contract audits pass. A full Next.js production build was not run in this environment because dependency installation was unavailable within the execution window.


## Canonical deployment target

The production LEXA application uses the Neon project `LEXA`, branch `lexa-live` (`br-soft-star-b1dj2m2w`), database `neondb`. The branch is permanent and is the project default. Do not point the application at the legacy empty `production` branch.

The repository root is the single deployment source. Vercel serves `apps/web`; Render serves `apps/api`. Do not deploy a nested copy of the application.
