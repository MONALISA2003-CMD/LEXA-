# LEXA Phase 4A End-to-End Release 2.1.0

This package contains the Phase 4A commerce application layer and the aligned Neon migration history.

## Included

- FastAPI commerce routes
- Next.js commerce workspace
- frontend API contracts
- Phase 4A migrations 016 and 017
- application integrity migration 018
- financial architecture lock 015
- backend/source contract tests
- frontend contract TypeScript configuration
- Phase 4A end-to-end verification report
- earlier LEXA deployment repair changes already present in the working tree

## Canonical database

`wispy-mud-75323042 / lexa-live / neondb`

## Verification

- `python -m pytest -q`: 79 passed
- `python -m compileall -q apps/api/app`: passed
- `tsc -p tsconfig.contract.json`: passed using the package's local contract stubs because production npm dependencies are not installed in the sandbox
- canonical Neon runtime test: passed
- canonical Neon validation data removed after testing

## Hosted deployment note

This source package is ready for deployment, but it does not claim that a fresh Render/Vercel deployment has completed. The existing repository integration previously returned a GitHub write permission error, so deployment still requires repository write access and successful provider builds.
