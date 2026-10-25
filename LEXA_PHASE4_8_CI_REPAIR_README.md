# LEXA Phase 4–8 CI repair overlay

**This ZIP is built from the current Phase 7 purchasing/authorization package plus repairs for CI run `40184725822`.**

## Contents

- Phase 7 approval-limit, partial-allocation, supplier-return reversal and reconciliation source/specs from the current Phase 7 package.
- Updated `apps/api/tests/test_intelligence_phase3.py`: the clean-replay manifest assertion now checks all four additive migrations (045–048).
- Updated `apps/web/tests/phase2-transaction-acceptance-contract.test.mjs` and `apps/web/tests/phase5-e2e-safety-contract.test.mjs`: the test matcher contracts allow the additional explicit, safety-gated Phase 7 Playwright specs without dropping the Phase 2 or Phase 5–8 suites.
- `PHASE4_8_RELEASE_AUDIT_2026-10-25.md`: scope review and current CI/Vercel/Neon/Render evidence.

## Integrity and rollout

This is an extractable source overlay, not a whole-repository snapshot. It intentionally does not run production SQL or trigger a Render deploy. CI must pass on the exact extracted commit. The live Neon branch was observed missing migration 048; the Phase 7 readiness gate is therefore not green until the safe migration rollout is completed. Render needs workspace confirmation before its service/deploy status can be checked in the connected account.
