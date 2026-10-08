# LEXA Phase 3 — International Research Synthesis

Research basis: September 2026.

## Market pattern

Leading business platforms are converging on a governed operational layer where transactional truth, workflow state, permissions, approvals and auditability remain deterministic, while AI operates inside those boundaries.

- Microsoft Business Central increasingly combines finance, supply chain and operational workflows with autonomous agents, while keeping actions transparent, reviewable and permissioned.
- Oracle Fusion Agentic Applications coordinate specialized agents against unified data, workflows, policies, approvals, permissions and transactional context.
- SAP Joule combines business-process expertise, assistants and agents so intent can become connected workflow execution.
- ServiceNow is treating workflow execution, context, governance and AI observability as one operating layer.
- Camunda explicitly separates deterministic orchestration from AI judgment and human tasks, keeping process state and policy outside the agent.
- Odoo demonstrates the importance of configurable automation and approval rules for business users.
- ERPNext shows the durable ERP core across accounting, HR, CRM, manufacturing, order management and asset management.

## LEXA architectural implication

The next LEXA capability should therefore be the **Operational Execution Core**, starting with inventory because catalog and universal transactions already exist and inventory is the missing physical execution ledger.

Design decisions adopted in Phase 3:

1. Inventory transactions are immutable history.
2. Inventory balances are rebuildable projections.
3. Weighted-average cost is deterministic per location.
4. Negative committed stock is blocked.
5. Adjustments, counts and transfers are state machines with approval boundaries.
6. State-changing commands are idempotent.
7. Tenant isolation is enforced in PostgreSQL with forced RLS and composite tenant-consistency foreign keys.
8. AI may consume inventory context later, but it does not replace the ledger or post stock outside the operational command layer.
9. The frontend exposes operational state rather than infrastructure internals.

## Africa-first consideration

The World Bank's 2025 AI foundations work emphasizes connectivity, compute, context/data and competency as core foundations for inclusive AI adoption. LEXA therefore keeps the operational layer authoritative, lightweight and usable without requiring AI for basic business execution.
