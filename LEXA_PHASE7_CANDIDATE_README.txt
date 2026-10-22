LEXA Phase 7 Login & Frontend Repair Candidate

This archive contains the updated LEXA application source and regression tests. It includes the sign-in context fix and the user-facing Settings, Business insights, reporting and inventory wording improvements.

This is a tested candidate package, not a live release. The live login is not yet repaired because the connected GitHub action refused to create a release branch, so the fix has not been deployed.

Checks completed: 218 backend tests passed; 43 frontend contract tests passed; backend compilation and frontend action audit passed. The full Next.js production build/typecheck and authenticated Phase 7 end-to-end tests remain blocked by missing local dependencies and the lack of an isolated staging API/cache. Production migrations were not applied.

Read LEXA_PHASE7_LOGIN_UX_REPAIR_AUDIT_2026-10-22.md for the full checks and blockers.
