# LEXA — Experience Foundation v1.4.1

LEXA is being implemented as a real multi-purpose, multi-tenant business operating system. This package continues the existing LEXA implementation and focuses on the customer-facing experience, workspace authentication, responsive navigation and deployment readiness. It does not rebuild the application or reset business data.

## What this release delivers

- LEXA branded public landing experience using the supplied LEXA identity
- Responsive desktop, tablet and mobile workspace shell
- Mobile navigation drawer and bottom navigation
- Branded sign in and workspace creation flows
- Password validation and friendly sign-in errors
- Automatic workspace resolution for accounts with one workspace
- Workspace picker for accounts with multiple workspaces
- Session persistence for the active workspace
- Friendly workspace connection messaging with no infrastructure diagnostics in the customer UI
- Product workspace connected to the live tenant catalog APIs
- Existing inventory workspace retained in the source package for the next product phase
- Browser icons and metadata aligned to the LEXA brand
- Additive workspace registration hardening migration 008
- Additive workspace selection function migration 009

## Customer experience boundary

The browser experience does not expose database names, internal service names, request identifiers, HTTP diagnostics, migration names or deployment details. Technical diagnostics remain server-side.

## Database state

Migrations 008 and 009 have been applied and verified on the LEXA development branch `lexa-phase1-dev`. The LEXA production branch remains untouched.

The inventory migration `005_inventory_foundation.sql` remains in the repository as an existing implementation artifact, but it is not part of this release's database deployment.

## Validation

The Python test suite passes. Frontend source files were syntax-checked successfully with TypeScript transpilation. A full Next.js production build was not run in this environment because the package dependencies are not installed locally.
