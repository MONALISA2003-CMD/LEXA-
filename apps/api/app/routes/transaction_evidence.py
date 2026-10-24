"""Tenant- and branch-scoped read-only evidence for a completed sale.

This deliberately exposes event names and lifecycle metadata, not outbox payloads,
customer details, credentials, or arbitrary SQL. It supports the authenticated
Phase 2 acceptance journey and the same auditability contract used by operators.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from ..branch_access import ensure_branch_access
from ..dependencies import require_permission

router = APIRouter(prefix="/commerce", tags=["commerce-evidence"])

# Reuse the same scoped relation set for the event and audit queries. The sale is
# always checked first, and every related record remains constrained to its tenant.
_RELATED_CTES = """
WITH sale_scope AS (
    SELECT s.id AS sale_id, s.transaction_id, s.branch_id
    FROM sales s
    WHERE s.tenant_id = CAST(:tenant_id AS uuid)
      AND s.id = CAST(:sale_id AS uuid)
), payment_ids AS (
    SELECT p.id
    FROM payments p
    JOIN sale_scope s ON s.transaction_id = p.transaction_id
    WHERE p.tenant_id = CAST(:tenant_id AS uuid)
    UNION
    SELECT p.id
    FROM payment_allocations pa
    JOIN payments p ON p.tenant_id = pa.tenant_id AND p.id = pa.payment_id
    LEFT JOIN receivables r ON r.tenant_id = pa.tenant_id AND r.id = pa.receivable_id
    JOIN sale_scope s ON (pa.sale_id = s.sale_id OR r.sale_id = s.sale_id)
    WHERE pa.tenant_id = CAST(:tenant_id AS uuid)
), related_ids(id) AS (
    SELECT sale_id FROM sale_scope
    UNION
    SELECT it.id
    FROM inventory_transactions it
    JOIN sale_scope s ON it.reference_type = 'sale' AND it.reference_id = s.sale_id
    WHERE it.tenant_id = CAST(:tenant_id AS uuid)
    UNION
    SELECT id FROM payment_ids
    UNION
    SELECT r.id FROM receivables r
    JOIN sale_scope s ON r.sale_id = s.sale_id
    WHERE r.tenant_id = CAST(:tenant_id AS uuid)
    UNION
    SELECT sr.id FROM sale_returns sr
    JOIN sale_scope s ON sr.sale_id = s.sale_id
    WHERE sr.tenant_id = CAST(:tenant_id AS uuid)
    UNION
    SELECT je.id
    FROM journal_entries je
    JOIN sale_scope s ON (
        (je.source_type = 'SALE' AND je.source_id = s.sale_id)
        OR (je.source_type = 'PAYMENT' AND je.source_id IN (SELECT id FROM payment_ids))
        OR (je.source_type = 'SALE_RETURN' AND je.source_id IN (
            SELECT sr.id FROM sale_returns sr WHERE sr.tenant_id = CAST(:tenant_id AS uuid) AND sr.sale_id = s.sale_id
        ))
    )
    WHERE je.tenant_id = CAST(:tenant_id AS uuid)
), related_event_ids(id) AS (
    SELECT e.id
    FROM outbox_events e
    WHERE e.tenant_id = CAST(:tenant_id AS uuid)
      AND (e.aggregate_id IN (SELECT id FROM related_ids) OR e.payload->>'sale_id' = :sale_id)
)
"""


@router.get("/sales/{sale_id}/evidence")
def sale_evidence(sale_id: UUID, ctx=Depends(require_permission("sales.read"))):
    """Return safe audit/outbox evidence for one sale after verifying branch access."""
    db, actor_id, tenant_id, _ = ctx
    sale = db.execute(text("""
        SELECT id, branch_id, status
        FROM sales
        WHERE tenant_id = CAST(:tenant_id AS uuid) AND id = CAST(:sale_id AS uuid)
    """), {"tenant_id": str(tenant_id), "sale_id": str(sale_id)}).mappings().first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    if sale["branch_id"] is None:
        raise HTTPException(status_code=403, detail="Sale is not linked to an accessible branch")
    ensure_branch_access(db, tenant_id=tenant_id, user_id=actor_id, branch_id=sale["branch_id"])

    params = {"tenant_id": str(tenant_id), "sale_id": str(sale_id)}
    events = db.execute(text(_RELATED_CTES + """
        SELECT e.id, e.event_type, e.aggregate_type, e.aggregate_id, e.status,
               e.attempt_count, e.occurred_at, e.processed_at, e.correlation_id
        FROM outbox_events e
        WHERE e.tenant_id = CAST(:tenant_id AS uuid)
          AND (e.aggregate_id IN (SELECT id FROM related_ids)
               OR e.payload->>'sale_id' = :sale_id)
        ORDER BY e.occurred_at, e.id
        LIMIT 250
    """), params).mappings().all()
    audits = db.execute(text(_RELATED_CTES + """
        SELECT a.id, a.action, a.target_type, a.target_id, a.outcome,
               a.correlation_id, a.created_at
        FROM audit_logs a
        WHERE a.tenant_id = CAST(:tenant_id AS uuid)
          AND (a.target_id IN (SELECT id FROM related_ids)
               OR a.target_id IN (SELECT id FROM related_event_ids))
        ORDER BY a.created_at, a.id
        LIMIT 250
    """), params).mappings().all()
    idempotency_count = db.execute(text("""
        SELECT count(*)
        FROM idempotency_records ir
        WHERE ir.tenant_id = CAST(:tenant_id AS uuid)
          AND ir.resource_type = 'sale'
          AND ir.resource_id = CAST(:sale_id AS uuid)
          AND ir.response_status BETWEEN 200 AND 299
    """), params).scalar_one()

    # Do not return payloads or the idempotency keys themselves. Those may contain
    # business details and are neither needed nor appropriate for an evidence view.
    return {
        "sale_id": str(sale_id),
        "sale_status": sale["status"],
        "event_count": len(events),
        "audit_count": len(audits),
        "successful_sale_idempotency_records": int(idempotency_count or 0),
        "events": [dict(row) for row in events],
        "audit": [dict(row) for row in audits],
    }
