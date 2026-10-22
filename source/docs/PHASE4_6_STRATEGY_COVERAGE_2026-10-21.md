# Product-strategy coverage — Phases 4–6

This coverage map is grounded in `FRESH_NEW_PRODUCT_STRATEGY.md`, Sections 4–6. It distinguishes source implementation from gates that require actual cloud/database/browser evidence.

## Phase 4 — UX and product-system reset

| Strategy commitment | Candidate implementation | Current evidence boundary |
|---|---|---|
| Consistent action labels and useful loading/empty/error states | Existing shared shell/components plus reports per-panel resilience and explicit unavailable vs no-records states | Local contracts + static control audit; real browser task acceptance pending |
| Remove dead/misleading buttons | TypeScript AST audit covers app/components; submit buttons are explicitly typed; CI step wired | Static wiring PASS, does not prove a handler’s business behavior |
| Document KPI date/currency semantics | Reports validates and applies period; dynamic business-profile currency; all-time/current-snapshot cards labelled distinctly | Local contracts PASS; API reconciliation and hosted E2E pending |
| Mobile usability/accessibility | Existing responsive shell/table/dialog/accessibility tests retained; audit does not substitute real-device testing | Contract coverage exists; real phone/device E2E not executed in this environment |

## Phase 5 — sales cockpit and POS excellence

| Strategy commitment | Candidate implementation | Current evidence boundary |
|---|---|---|
| Safer checkout, payment and collection distinction | Existing sales cockpit and payment-channel flow; workspace-aware currency used in commerce | Contract tests exist; authenticated browser acceptance pending |
| Multi-line returns and refund controls | Return UI submits multiple sale lines; backend validates cumulative prior returns; refund and receivable limits are guarded | 188 backend tests + frontend contracts; actual database replay pending |
| Return-aware accounting and COGS | Candidate migrations 033–035, journal references and fiscal-document path | SQL source exists, not applied to production; clean replay required |
| Sales and reports reconcile | Reports period/currency handling and source-specific unavailable states | Local contracts only; exact dataset reconciliation and E2E pending |

## Phase 6 — inventory intelligence

| Strategy commitment | Candidate implementation | Current evidence boundary |
|---|---|---|
| Available, reserved, inbound and on-hand | Inventory balance/ledger projections and stock view | Source exists; authenticated module E2E pending |
| Stocktakes, adjustments, transfers | Existing controlled workflow UI/API states with authorization | Source exists; end-to-end reconciliation pending |
| Low/out-of-stock exception queue | New `/api/v1/inventory/movement-health` + Stock Health tab; configurable minimum, demand/return counters, last sale and recency bands | Source contract pass; replay/DB E2E pending |
| Aged/slow-moving stock | New `/api/v1/inventory/ageing` with 30/60/90-day bands and unknown provenance; no false serial/lot/FIFO claim | Source contract pass; age method remains an advisory analytical convention |
| Explainable replenishment | Replenishment policy and deterministic Decimal recommendation formulas; no auto-creation of PO/stock movements | Source contract pass; actual DB replay and staging E2E pending |
| Correct reports and inventory valuation | Workspace currency now sourced from business profile for inventory/product cost amounts; cost-value labels distinguish cost from retail/profit | Source and contract checks; browser and accounting review pending |

## Product work intentionally left for later phases

The strategy puts purchasing/supplier management in Phase 7, receivables/payables and deeper finance in Phase 8, multi-branch/customer growth refinements in Phase 9, verified Uganda payment/EFRIS integrations in Phase 10, explainable predictive intelligence in Phase 11, and operational launch/restore/scaling proof in Phase 12. These are not falsely marked complete by the Phase 4–6 source increment.

## Release blockers are separate from product history

The six historical SQL originals are permanently dispositioned as replacements per Phase 3 approval. They do not remain an open recovery blocker. Clean replay validation of those equivalents is still required. Independently, candidate release still needs Node 24 CI, actual disposable PostgreSQL replay, authenticated E2E in a sanitized staging environment, matching candidate SHA on Render/Vercel, and approved production migration rollout.
