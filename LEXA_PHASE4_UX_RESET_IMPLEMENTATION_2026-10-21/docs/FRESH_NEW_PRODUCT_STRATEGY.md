# LEXA — Fresh Product Strategy

**Version:** 1.0  
**Strategy date:** 21 October 2026  
**Status:** Fresh product direction following the Phase 3 security and acceptance milestone  
**Product thesis:** LEXA should help small and medium businesses sell faster, keep trustworthy stock records, understand cash and profit, and take the next best action with confidence.

---

## 1. The strategic decision

Build LEXA as a **business operating system for growing Ugandan SMEs**, starting with retail and inventory-led businesses. The product should combine point of sale, inventory, purchasing, customer credit, finance and owner reporting on top of one consistent, auditable transaction model.

LEXA should not compete by having the most menu items. It should win by making everyday work easier and giving owners a reliable answer to five questions:

1. What did we sell?
2. What did we actually collect, and what is still owed?
3. What did we earn after the relevant costs?
4. What stock is running out, stuck or consuming too much cash?
5. What should I or my team do next?

**Product promise:** *Sell faster. Know your numbers. Keep the right stock. Control your cash. Make better decisions.*

## 2. Who LEXA serves first

### Primary customer: owner-operated retail SME

A business with one shop today, possibly multiple branches later, managed by an owner and a small team. It needs a practical record of sales, stock, cash, customer balances and supplier obligations without enterprise-software overhead.

### Priority user groups

- **Owner / managing director:** wants a trustworthy daily summary, cash and credit visibility, margin signals and branch comparisons.
- **Cashier / salesperson:** needs fast search, fewer checkout steps, reliable payments and receipts, and simple returns workflows.
- **Storekeeper:** needs correct stock by location, auditable adjustments, stocktakes and transfers.
- **Purchasing / operations manager:** needs reorder guidance, supplier lead-time visibility, receiving and outstanding purchase orders.
- **Bookkeeper / finance manager:** needs payment allocation, receivables/payables, expenses, reconciliations and report definitions that do not change between screens.
- **Branch manager:** needs branch-level results, controlled approvals and clear visibility of work awaiting action.

### Start with retail; expand deliberately

Begin with the general retail core. Add industry templates only where the operational need is clear. For example, appliance retailers may need serial numbers, warranty history and delivery scheduling; grocery or pharmacy workflows may need batch and expiry tracking; distributors may need route sales and case/pack conversions. These should build on shared inventory, sales and permission primitives rather than create disconnected products.

## 3. Customer problems LEXA must solve

| Customer problem | LEXA product response | Evidence of value |
|---|---|---|
| Sales and collections are confused | Separate sales, payments, credit and refunds | Dashboard totals reconcile to underlying records |
| Stock figures cannot be trusted | Traceable movement ledger, location-level balances, stocktakes and transfers | Counts and adjustments reconcile; users can explain every difference |
| Money is tied up in the wrong items | Low-stock, slow-moving and aged-stock views; configurable reorder suggestions | Fewer avoidable stockouts and less obsolete inventory |
| Purchasing is reactive | Supplier lead times, order history, goods received and reorder queue | More planned reorders, fewer emergency purchases |
| Owners see numbers but not actions | Alerts linked to records and clear next steps | Higher completion of operational work with fewer unresolved exceptions |
| Software is hard to use on a phone | Mobile-first screens, large touch controls, short forms and clear feedback | Common workflows completed successfully on mobile |
| Managers cannot compare branches | Consistent branch filters, permissions and period comparisons | Comparable, auditable reports across authorised branches |

## 4. Product pillars and investment priorities

### Pillar A — Effortless daily work

- Fast, searchable product selection and checkout.
- Predictable navigation and familiar page layouts.
- Clear action labels; no dead buttons, surprise actions or hidden saves.
- Strong loading, empty, error, permission-denied and success states.
- Keyboard accessibility and mobile-friendly touch targets.
- Drafts and recovery for longer forms and workflows when they can be implemented safely.

### Pillar B — Trustworthy operational records

- One authoritative sales/payment/return and inventory-movement history.
- Idempotency for retried writes, particularly payments and sales.
- Corrections through traceable reversals/adjustments, not silent destructive edits.
- Tenant and branch access enforced server-side and in the database.
- Audit history for sensitive approvals, stock changes, role changes and financial actions.
- Clear ownership of business dates, currency, tax, cost and status transitions.

### Pillar C — Owner dashboards that lead to action

- Today, week and month-period KPI summaries.
- Net sales and payments collected shown separately.
- Returns, credit created, receivables, expenses and net cash movement with explicit definitions.
- Product performance by net sales, units and gross margin value.
- Inventory health and operational exceptions.
- Branch comparison for users with appropriate scope.
- Drill-through from summary and chart to source records.

### Pillar D — Inventory intelligence

- Available stock and reserved stock shown separately.
- Low-stock and out-of-stock exception queues.
- Stock ageing, sell-through, demand velocity and days-of-cover when source data supports them.
- Reorder-point recommendations using demand during lead time plus a deliberate safety buffer.
- Supplier lead times, case sizes, minimum order quantities and budget constraints as later model inputs.
- Human review and approval before purchases are sent or stock/financial records are altered automatically.

### Pillar E — Finance clarity

- Receivables, overdue customer balances and payment allocations.
- Payables, expenses, cashbook and reconciliation workflows.
- Accounting reports with documented definitions and drill-through.
- Consistent treatment of discounts, returns, taxes, cost of goods sold and credit.
- Separate operational cash measures from accounting revenue and profit measures.

### Pillar F — Uganda-first operations

- UGX as a first-class default, with currency-aware formatting and storage.
- Mobile-money workflows designed with asynchronous payment-status handling and duplicate protection.
- Receipt printing and barcode workflows for common shop hardware.
- Resilient user experience on variable connectivity; queued/offline writes only after conflict, identity, idempotency and compliance rules are defined.
- EFRIS applicability assessment and integration behind a separately tested compliance boundary.

## 5. Dashboard and analytics contract

The dashboard must prefer correctness and explainability over visual density.

### Core KPI definitions

| KPI | Definition | Important guardrail |
|---|---|---|
| Today's sales | Sum of completed sales for the business date, using the commerce dashboard's documented business-date rules | Do not include a draft sale or confuse it with collected cash |
| Collected today | Payments actually recorded/confirmed for the business date | Do not count an unconfirmed mobile-money request as money collected |
| Net sales | Sales total less return adjustments according to the analytics source contract | Always display the reporting period and currency |
| Outstanding receivables | Remaining due balances on customer credit | Payments, approved credits and returns must be allocated consistently |
| Inventory value | Valuation from stock balances and their valuation method | State the valuation basis; never imply retail selling value if the figure is cost value |
| Units sold | Sold units less returned units when using a net-units definition | Label gross units vs net units clearly |
| Gross margin value | Net sales less cost of goods sold according to approved cost rules | Do not call this net profit; operating expenses are still separate |
| Net cash movement | Cash inflows less outflows included by the defined report | Document included transaction classes and period boundaries |

**Every metric contract needs:** name, business meaning, formula, source endpoint/table or approved view, currency behavior, date basis, return/void treatment, permission requirement, refresh behavior, empty state and automated reconciliation test.

A metric that cannot be verified should display `Unavailable` or an explicit no-records state. It should not quietly turn a loading or API error into zero. Charts need labels and an accessible table. When the source omits dates, LEXA must not invent zero-activity records unless the backend contract guarantees a complete daily series.

## 6. Roadmap and release outcomes

### Phase 4 — UX and product-system reset

Create a consistent design system; audit every screen and action; improve mobile navigation, form feedback, empty/error/loading states and touch accessibility; document KPI definitions; remove dead or misleading controls. The newly implemented dashboard experience is the first concrete application of this direction.

### Phase 5 — Sales cockpit and POS excellence

Make checkout faster and safer. Improve transaction search, returns/refunds, receipts, payment states and sales analysis. Reconcile daily dashboards to commerce records.

### Phase 6 — Inventory intelligence

Improve location-level truth, stocktake, adjustments and transfers. Add low-stock, out-of-stock, aged-stock and reorder-recommendation workflows with transparent reasons.

### Phase 7 — Purchasing and supplier management

Track supplier terms, purchase orders, partial receiving, stock increases, landed/other supported costs, returns and supplier balances end-to-end.

### Phase 8 — Finance and profitability

Make receivables, payables, cash movement, expense reporting, reconciliation and gross-margin logic dependable and traceable.

### Phase 9 — Multi-branch and customer growth

Make role/branch separation intuitive; support staff approvals, customer history, controlled customer credit and industry-specific options that reuse the shared core.

### Phase 10 — Uganda integrations and operational readiness

Validate mobile-money provider requirements, payment-status callbacks/polling, EFRIS applicability, receipts, scanners and printers. Add integrations one at a time and verify failure-path and reconciliation behavior before production activation.

### Phase 11 — Explainable business intelligence

Introduce demand forecasting, stockout risk, margin erosion and unusual-pattern alerts only when trustworthy history is available. Recommendations should show their reasons, data period, confidence/limitations and intended action.

### Phase 12 — Scale and launch readiness

Prove backup/restore, monitoring, performance, deployment recovery, role/branch acceptance, security, onboarding, support and real-device usability using realistic datasets.

## 7. What LEXA should deliberately not do yet

- Do not launch AI-generated business advice before the underlying figures reconcile.
- Do not execute purchases automatically in the early replenishment phases.
- Do not equate sales with profit or payment requests with collected funds.
- Do not implement offline financial writes without idempotency, conflict resolution, auditability and fiscal/compliance policy.
- Do not integrate with a payment provider based only on API availability; provider credentials, country/product access, settlement and exception flows must be verified.
- Do not claim EFRIS applies identically to every business. Confirm current URA requirements for each relevant taxpayer/sector profile before enabling a compliance workflow.
- Do not rewrite working modules solely to change their appearance.
- Do not claim a phase complete on a green indicator alone; require source, test, authenticated and deployed evidence.

## 8. Success metrics

Track these over time, segmented by business type and branch where appropriate:

**Adoption and usability**
- Activation rate: businesses completing setup and recording a legitimate first sale.
- Time and number of steps to complete common checkout workflows.
- Task completion and abandonment on phone-sized screens.
- Frequency of failed submissions, duplicate attempts and support-needed flows.

**Operational trust**
- Difference between recorded cash/mobile-money settlement and reconciled payment records.
- Stocktake variance rate and unresolved inventory-integrity exceptions.
- Percentage of dashboard KPIs that pass automated source reconciliation.
- Rate of failed or replayed idempotent requests.

**Business value**
- Stockout frequency for actively selling items.
- Share of stock value held in slow-moving/aged items.
- On-time supplier receipt and open purchase-order age.
- Overdue receivable rate and time-to-collection.
- Gross margin trend with documented cost rules.

**Reliability and safety**
- Critical authenticated E2E pass rate per release.
- Release rollback/recovery rate and restore drill outcomes.
- Latency and error rates for checkout, inventory balance and analytics routes.
- Security/authorization regression count, particularly cross-tenant and cross-branch access.

Set numerical business targets only after measuring a trustworthy baseline; do not invent target improvements from an untested build.

## 9. Commercial direction

Start with a focused, high-trust offer for Ugandan retail SMEs. The initial wedge is reliable sales + stock + customer credit + owner visibility, supported by practical onboarding. Use a small pilot group representing different transaction volumes and connectivity conditions. Observe actual task completion and reconcile reports with user records before expanding the marketing claim.

Potential pricing should be tied to delivered value and support cost, not a long feature checklist. Evaluate a core plan for one location, a multi-branch plan with advanced controls, and optional integration/support services only after operating costs and usage patterns are known. Keep onboarding, exports, and a clear account/data policy understandable to small business owners.

## 10. Decision principles

1. Correctness before cleverness.
2. Fast workflows before feature breadth.
3. Mobile usability as a primary requirement.
4. Reports must be explainable and traceable.
5. One transaction model across the product.
6. Role/tenant security is always enforced server-side.
7. Keep changes small enough to test and roll back.
8. Recommendations are advisory until users trust them.
9. Uganda-first compliance and payment integration, with explicit provider and taxpayer checks.
10. A phase is finished only when its acceptance gate passes.

## 11. Research references

- Uganda Revenue Authority, **EFRIS** — applicability, use and official process: <https://ura.go.ug/en/efris/>.
- Uganda Revenue Authority, **Additional taxpayers required to use EFRIS** — official sector guidance published 11 August 2026: <https://ura.go.ug/en/additional-taxpayers-required-to-use-efris/>.
- MTN MoMo, **API** — Collection, Disbursement, request-to-pay tutorial and sandbox-development resources: <https://momo.mtn.com/api/> and <https://momoapi.mtn.com/content/html_widgets/90azl.html>.
- W3C WAI, **WCAG 2.2 Target Size (Minimum)** — touch and pointer target-size accessibility guidance: <https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum>.
- Square Support, **Create and manage purchase orders** — examples of supplier-linked purchase and inventory receiving flows: <https://squareup.com/help/us/en/article/8258-create-purchase-orders-with-square-for-retail>.
- Oracle documentation, **inventory replenishment / reorder-point methods**: <https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/article_0702045810.html>.

These references inform the product direction; they do not establish that LEXA has completed a provider certification, fiscal integration or accounting review.
