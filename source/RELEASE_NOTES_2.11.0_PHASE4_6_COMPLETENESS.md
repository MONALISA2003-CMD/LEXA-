# Release notes 2.11.0 — Phase 4–6 Completeness Increment 03

## Implemented

- Phase 4 report period validation/Apply Period workflow, verified workspace currency labels, and per-panel unavailable-vs-empty states.
- Inventory and product cost values use business-profile currency where available, avoiding silent UGX relabelling for these screens.
- Phase 5 return UI supports multiple sale lines while backend validation remains authoritative; prior return/refund/accounting guards retained.
- Phase 6 inventory stock-age and Stock Health views expose 30/60/90-day stock-age bands, unknown provenance, reconciliation gaps, out-of-stock risk, configured minimum breaches, completed-sale recency and gross/returned unit counts separately.
- Additive forward migrations 037 (inventory age index) and 038 (four concurrent stock-movement health indexes) included as candidates.
- CI static AST audit checks button handler/submit wiring, forms, and links; all current structural checks pass.
- Permanent six-file Phase 3 SQL replacement disposition remains closed in actual checkers and gate reports.

## Validation

- Python: 188 passed, 1 skipped, 0 failed. The local skip is due to the offline runner missing the Redis Python package.
- Frontend contract tests: 33 passed, 0 failed on Node 22.16.0.
- AST audit: 29 TypeScript/TSX files; 117 button-like controls, 27 forms, 33 links; pass.
- Python compile, source-recovery manifest and strict migration-source reconciliation pass.
- Clean replay plan verifies 42 SQL inputs; no SQL executed locally.

## Release status

This is a local full-source candidate, not production accepted. Node 24 `npm ci`/typecheck/build, actual disposable PostgreSQL replay, authenticated isolated staging E2E, exact-SHA Render/Vercel deployment verification and approved production migration rollout are pending. No production schema or deploy was changed.
