"""Phase 7 purchase approval limits, supplier-return reversals and reconciliation.

This router is registered before the legacy purchasing router so that the
approval endpoint can enforce the amount policy before delegating to the existing
lifecycle implementation. The database migration repeats the limit check in a
trigger, so the web route is not the only enforcement boundary.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..branch_access import ensure_branch_access, ensure_location_access, require_full_branch_scope
from ..catalog import emit_event, write_audit
from ..dependencies import require_permission
from ..inventory import post_ledger
from ..purchasing_approval_rules import (
    PurchaseApprovalLimitError,
    effective_purchase_approval_limit,
    needs_governance_override_reason,
)
from . import purchasing

router = APIRouter(prefix="/purchasing", tags=["purchasing-approval-limits"])


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApprovalLimitIn(Strict):
    role_name: str = Field(min_length=2, max_length=100)
    currency_code: str = Field(pattern=r"^[A-Za-z]{3}$")
    max_approval_amount: Decimal = Field(ge=0, max_digits=20, decimal_places=2)

    @field_validator("role_name")
    @classmethod
    def normalize_role(cls, value: str) -> str:
        return value.strip()

    @field_validator("currency_code", mode="before")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return str(value or "").strip().upper()


class ReturnReversalIn(Strict):
    reason: str = Field(min_length=5, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return value.strip()


def _limit_payload(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "role_name": row["role_name"],
        "currency_code": row["currency_code"],
        "max_approval_amount": str(row["max_approval_amount"]),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


@router.get("/approval-limits")
def list_approval_limits(ctx=Depends(require_permission("purchasing.approval_limits.manage"))):
    db, _, tenant_id, _ = ctx
    rows = db.execute(text("""
        SELECT id, role_name, currency_code, max_approval_amount, created_at, updated_at
          FROM public.purchase_approval_limits
         WHERE tenant_id=:t
         ORDER BY role_name, currency_code
    """), {"t": str(tenant_id)}).mappings().all()
    eligible = db.execute(text("""
        SELECT DISTINCT r.name
          FROM public.roles r
          JOIN public.role_permissions rp ON rp.role_id=r.id
          JOIN public.permissions p ON p.id=rp.permission_id AND p.code='purchasing.approve'
         WHERE r.tenant_id=:t AND r.name NOT IN ('Owner','Administrator','Admin')
         ORDER BY r.name
    """), {"t": str(tenant_id)}).scalars().all()
    return {"items": [_limit_payload(dict(row)) for row in rows], "eligible_roles": list(eligible)}


@router.put("/approval-limits")
def upsert_approval_limit(body: ApprovalLimitIn, ctx=Depends(require_permission("purchasing.approval_limits.manage"))):
    db, actor, tenant_id, _ = ctx
    if body.role_name.casefold() in {"owner", "administrator", "admin"}:
        raise HTTPException(422, "Owner and Administrator approvals are governed by the workspace override policy; no monetary cap can be configured for these roles.")
    role = db.execute(text("""
        SELECT r.name
          FROM public.roles r
          JOIN public.role_permissions rp ON rp.role_id=r.id
          JOIN public.permissions p ON p.id=rp.permission_id AND p.code='purchasing.approve'
         WHERE r.tenant_id=:t AND r.name=:role
         LIMIT 1
    """), {"t": str(tenant_id), "role": body.role_name}).mappings().first()
    if not role:
        raise HTTPException(422, "Select a role that already has purchasing approval permission in this workspace.")
    row = db.execute(text("""
        INSERT INTO public.purchase_approval_limits
            (tenant_id, role_name, currency_code, max_approval_amount, created_by, updated_by)
        VALUES (:t, :role, :cc, :amount, :actor, :actor)
        ON CONFLICT (tenant_id, role_name, currency_code)
        DO UPDATE SET max_approval_amount=EXCLUDED.max_approval_amount,
                      updated_by=EXCLUDED.updated_by, updated_at=now()
        RETURNING id, role_name, currency_code, max_approval_amount, created_at, updated_at
    """), {
        "t": str(tenant_id), "role": role["name"], "cc": body.currency_code,
        "amount": body.max_approval_amount, "actor": str(actor),
    }).mappings().one()
    policy_id = UUID(str(row["id"]))
    write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="purchasing.approval_limit.upserted", target_type="purchase_approval_limit", target_id=policy_id)
    emit_event(db, tenant_id=tenant_id, actor_user_id=actor, event_type="purchasing.approval_limit.upserted.v1", aggregate_type="purchase_approval_limit", aggregate_id=policy_id, payload={"role_name": role["name"], "currency_code": body.currency_code, "max_approval_amount": str(body.max_approval_amount)})
    db.commit()
    return _limit_payload(dict(row))


@router.post("/purchase-orders/{order_id}/approve", include_in_schema=False)
def approve_purchase_order_with_limit(
    order_id: UUID,
    body: dict | None = None,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    ctx=Depends(require_permission("purchasing.approve")),
):
    db, actor, tenant_id, _ = ctx
    order = purchasing._ensure_order_access(db, tenant_id=tenant_id, user_id=actor, order_id=order_id, lock=True)
    # Preserve safe replay behaviour: the legacy lifecycle owns state-transition
    # validation and idempotency response replay once the order is no longer SUBMITTED.
    if order["status"] != "SUBMITTED":
        return purchasing.approve_purchase_order(order_id, body, idempotency_key, ctx)

    role_names = [str(row[0]) for row in db.execute(text("""
        SELECT DISTINCT r.name
          FROM public.tenant_memberships tm
          JOIN public.membership_roles mr ON mr.membership_id=tm.id
          JOIN public.roles r ON r.id=mr.role_id AND r.tenant_id=tm.tenant_id
          JOIN public.role_permissions rp ON rp.role_id=r.id
          JOIN public.permissions p ON p.id=rp.permission_id AND p.code='purchasing.approve'
         WHERE tm.tenant_id=:t AND tm.user_id=:u AND tm.status='ACTIVE'
    """), {"t": str(tenant_id), "u": str(actor)}).all()]
    currency = str(order["currency_code"]).upper()
    policy_rows = db.execute(text("""
        SELECT role_name, currency_code, max_approval_amount
          FROM public.purchase_approval_limits
         WHERE tenant_id=:t AND currency_code=:cc
    """), {"t": str(tenant_id), "cc": currency}).mappings().all()
    policies = {(str(row["role_name"]), str(row["currency_code"]).upper()): row["max_approval_amount"] for row in policy_rows}
    try:
        purchase_total = Decimal(str(order["total"]))
        if needs_governance_override_reason(
            role_names=role_names, currency_code=currency,
            purchase_total=purchase_total, policies=policies,
        ) and len(str((body or {}).get("reason") or "").strip()) < 5:
            raise HTTPException(status_code=409, detail={
                "code": "PURCHASE_APPROVAL_OVERRIDE_REASON_REQUIRED",
                "message": "An Owner/Administrator override above the highest configured approval limit needs an audit reason of at least five characters.",
            })
        effective_purchase_approval_limit(
            role_names=role_names,
            currency_code=currency,
            purchase_total=purchase_total,
            policies=policies,
        )
    except PurchaseApprovalLimitError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc
    # This call retains the established transition history, audit/outbox event,
    # optimistic lifecycle guard and response idempotency implementation.
    return purchasing.approve_purchase_order(order_id, body, idempotency_key, ctx)


@router.post("/returns/{return_id}/reverse")
def reverse_posted_supplier_return(
    return_id: UUID,
    body: ReturnReversalIn,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    ctx=Depends(require_permission("purchasing.returns.reverse")),
):
    db, actor, tenant_id, _ = ctx
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(428, detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "message": "A unique Idempotency-Key is required to reverse a posted supplier return."})
    idem, replay = purchasing._idempotency(
        db, tenant_id, "purchasing.return.reverse", idempotency_key,
        {"return_id": str(return_id), "reason": body.reason},
    )
    if replay:
        return replay[1]
    row = purchasing._one(db, "SELECT * FROM public.purchase_returns WHERE tenant_id=:t AND id=:id FOR UPDATE", {"t": str(tenant_id), "id": str(return_id)})
    if not row:
        raise HTTPException(404, "Supplier return not found")
    if row["status"] != "POSTED":
        raise HTTPException(409, "Only a posted supplier return can be reversed, and a posted return can be reversed only once.")
    receipt = purchasing._one(db, "SELECT * FROM public.purchase_receipts WHERE tenant_id=:t AND id=:id", {"t": str(tenant_id), "id": str(row["purchase_receipt_id"])})
    if not receipt:
        raise HTTPException(409, "The source goods receipt is unavailable; no stock was changed.")
    order = purchasing._ensure_order_access(db, tenant_id=tenant_id, user_id=actor, order_id=receipt["purchase_order_id"], lock=True)
    ensure_location_access(db, tenant_id=tenant_id, user_id=actor, location_id=UUID(str(row["receiving_location_id"])))
    if UUID(str(row["receiving_location_id"])) != UUID(str(receipt["receiving_location_id"])) or UUID(str(receipt["receiving_location_id"])) != UUID(str(order["receiving_location_id"])):
        raise HTTPException(409, detail={"code": "PURCHASE_RETURN_LOCATION_MISMATCH", "message": "The return's source location no longer matches its original receipt."})

    original_credit = purchasing._one(db, """
        SELECT id, currency_code, credit_amount
          FROM public.supplier_ledger_entries
         WHERE tenant_id=:t AND source_type='purchase_return' AND source_id=:return_id AND entry_type='RETURN_CREDIT'
         FOR UPDATE
    """, {"t": str(tenant_id), "return_id": str(return_id)})
    if not original_credit:
        raise HTTPException(409, "The original supplier credit is missing. Reversal was stopped so stock and supplier records cannot diverge.")
    lines = purchasing._many(db, "SELECT * FROM public.purchase_return_lines WHERE tenant_id=:t AND purchase_return_id=:id ORDER BY id FOR UPDATE", {"t": str(tenant_id), "id": str(return_id)})
    if not lines:
        raise HTTPException(409, "The return has no lines to reverse.")

    restored_quantity = Decimal("0")
    for line in lines:
        original_tx = purchasing._one(db, """
            SELECT id, unit_cost FROM public.inventory_transactions
             WHERE tenant_id=:t AND transaction_type='PURCHASE_RETURN'
               AND reference_type='purchase_return' AND reference_id=:return_id
               AND metadata->>'receipt_line_id'=:receipt_line_id
             ORDER BY occurred_at, id LIMIT 1
        """, {"t": str(tenant_id), "return_id": str(return_id), "receipt_line_id": str(line["purchase_receipt_line_id"])})
        if not original_tx:
            raise HTTPException(409, "An original stock-ledger row is missing for this return line; no reversal was posted.")
        qty = Decimal(str(line["quantity"]))
        post_ledger(
            db, tenant_id=tenant_id, actor_user_id=actor,
            location_id=UUID(str(row["receiving_location_id"])), variant_id=UUID(str(line["variant_id"])),
            quantity_delta=qty, unit_cost=Decimal(str(original_tx["unit_cost"])),
            transaction_type="PURCHASE_RETURN_REVERSAL", reference_type="purchase_return_reversal", reference_id=return_id,
            metadata={"return_number": row["return_number"], "reverses_transaction_id": str(original_tx["id"]), "reason": body.reason, "receipt_line_id": str(line["purchase_receipt_line_id"])},
            idempotency_key=f"purchasing:return-reversal:{return_id}:line:{line['id']}",
        )
        restored_quantity += qty

    now_row = purchasing._one(db, """
        UPDATE public.purchase_returns
           SET status='REVERSED', reversed_by=:actor, reversed_at=now(), reversal_reason=:reason, updated_at=now()
         WHERE tenant_id=:t AND id=:id
        RETURNING id, return_number, status, reversed_at
    """, {"actor": str(actor), "reason": body.reason, "t": str(tenant_id), "id": str(return_id)})
    # The supplier-ledger entry is an append-only debit which offsets the original
    # RETURN_CREDIT. Migration 048 creates the exact, posted reversing GL journal
    # from this entry in the same transaction.
    db.execute(text("""
        INSERT INTO public.supplier_ledger_entries
            (tenant_id,supplier_party_id,currency_code,entry_type,source_type,source_id,reference,debit_amount,credit_amount,actor_user_id,metadata)
        VALUES (:t,:supplier,:cc,'RETURN_REVERSAL','purchase_return_reversal',:source,:ref,:amount,0,:actor,CAST(:metadata AS jsonb))
        ON CONFLICT (tenant_id,source_type,source_id,entry_type) DO NOTHING
    """), {
        "t": str(tenant_id), "supplier": str(order["supplier_party_id"]), "cc": str(original_credit["currency_code"]),
        "source": str(return_id), "ref": str(row["return_number"]), "amount": original_credit["credit_amount"],
        "actor": str(actor), "metadata": __import__("json").dumps({"original_supplier_ledger_entry_id": str(original_credit["id"]), "reason": body.reason, "restored_quantity": str(restored_quantity)}),
    })
    purchasing._audit(db, tenant_id, actor, "purchasing.return.reversed", "purchase_return", return_id, "purchasing.return.reversed.v1", {"return_number": row["return_number"], "reason": body.reason, "restored_quantity": str(restored_quantity), "original_credit": str(original_credit["credit_amount"])})
    response = {"id": str(return_id), "return_number": str(row["return_number"]), "status": "REVERSED", "restored_quantity": str(restored_quantity), "supplier_credit_reversed": str(original_credit["credit_amount"]), "currency_code": str(original_credit["currency_code"]), "reason": body.reason, "reversed_at": now_row["reversed_at"].isoformat() if now_row and now_row.get("reversed_at") else None}
    return purchasing._commit(db, idem, response, "purchase_return", return_id)


@router.get("/reconciliation")
def purchasing_reconciliation(ctx=Depends(require_permission("purchasing.read"))):
    """Cross-check stock ledger, posted purchasing journals and supplier balances.

    The endpoint is intentionally tenant-wide because supplier ledgers currently
    aggregate across branches; it fails closed unless the caller can see every
    active branch. It is read-only and returns mismatches rather than repairing them.
    """
    db, actor, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=actor)
    t = str(tenant_id)
    stock_rows = db.execute(text("""
        WITH ledger AS (
          SELECT tenant_id, location_id, variant_id, SUM(quantity_delta) AS ledger_quantity
            FROM public.inventory_transactions WHERE tenant_id=:t GROUP BY tenant_id,location_id,variant_id
        ), keys AS (
          SELECT tenant_id,location_id,variant_id FROM public.inventory_balances WHERE tenant_id=:t
          UNION SELECT tenant_id,location_id,variant_id FROM ledger
        )
        SELECT k.location_id,k.variant_id,COALESCE(b.on_hand,0) AS balance_quantity,
               COALESCE(l.ledger_quantity,0) AS ledger_quantity
          FROM keys k
          LEFT JOIN public.inventory_balances b ON b.tenant_id=k.tenant_id AND b.location_id=k.location_id AND b.variant_id=k.variant_id
          LEFT JOIN ledger l ON l.tenant_id=k.tenant_id AND l.location_id=k.location_id AND l.variant_id=k.variant_id
         WHERE abs(COALESCE(b.on_hand,0)-COALESCE(l.ledger_quantity,0))>0.000001
         ORDER BY k.location_id,k.variant_id LIMIT 100
    """), {"t": t}).mappings().all()
    missing_receipt_journals = int(db.execute(text("""
        SELECT count(*) FROM public.purchase_receipts r
         WHERE r.tenant_id=:t AND r.status='POSTED'
           AND NOT EXISTS (SELECT 1 FROM public.journal_entries j WHERE j.tenant_id=r.tenant_id AND j.source_type='PURCHASE_RECEIPT' AND j.source_id=r.id AND j.entry_role='RECEIPT_RECOGNITION' AND j.status IN ('POSTED','REVERSED'))
    """), {"t": t}).scalar_one())
    missing_supplier_journals = int(db.execute(text("""
        SELECT count(*) FROM public.supplier_ledger_entries e
         WHERE e.tenant_id=:t AND (
           (e.entry_type IN ('BILL','PAYMENT','RETURN_CREDIT') AND NOT EXISTS (
             SELECT 1 FROM public.journal_entries j WHERE j.tenant_id=e.tenant_id AND j.source_type='SUPPLIER_LEDGER' AND j.source_id=e.id AND j.entry_role=e.entry_type AND j.status IN ('POSTED','REVERSED')
           )) OR
           (e.entry_type='RETURN_REVERSAL' AND NOT EXISTS (
             SELECT 1 FROM public.supplier_ledger_entries original
             JOIN public.journal_entries oj ON oj.tenant_id=original.tenant_id AND oj.source_type='SUPPLIER_LEDGER' AND oj.source_id=original.id AND oj.entry_role='RETURN_CREDIT'
             JOIN public.journal_entries rj ON rj.tenant_id=oj.tenant_id AND rj.reversal_of_id=oj.id AND rj.status='POSTED'
             WHERE original.tenant_id=e.tenant_id AND original.source_type='purchase_return' AND original.source_id=e.source_id AND original.entry_type='RETURN_CREDIT'
           ))
         )
    """), {"t": t}).scalar_one())
    unbalanced_journals = int(db.execute(text("""
        SELECT count(*) FROM (
          SELECT j.id FROM public.journal_entries j
          LEFT JOIN public.journal_lines l ON l.tenant_id=j.tenant_id AND l.journal_entry_id=j.id
         WHERE j.tenant_id=:t AND j.status IN ('POSTED','REVERSED')
         GROUP BY j.id
        HAVING abs(COALESCE(sum(l.debit),0)-COALESCE(sum(l.credit),0))>0.0001 OR count(l.id)<2
        ) q
    """), {"t": t}).scalar_one())
    supplier_diffs = db.execute(text("""
        WITH suppliers AS (
          SELECT tenant_id,supplier_party_id,currency_code FROM public.supplier_ledger_entries WHERE tenant_id=:t
          UNION SELECT tenant_id,supplier_party_id,currency_code FROM public.supplier_bills WHERE tenant_id=:t
          UNION SELECT tenant_id,supplier_party_id,currency_code FROM public.supplier_payments WHERE tenant_id=:t
        ), subledger AS (
          SELECT tenant_id,supplier_party_id,currency_code,sum(debit_amount-credit_amount) AS net
            FROM public.supplier_ledger_entries WHERE tenant_id=:t GROUP BY tenant_id,supplier_party_id,currency_code
        ), accounts AS (
          SELECT map.tenant_id, map.mapping_key, map.account_id FROM public.accounting_mappings map
           WHERE map.tenant_id=:t AND map.mapping_key IN ('ACCOUNTS_PAYABLE','SUPPLIER_ADVANCES')
        ), gl AS (
          SELECT s.tenant_id,s.supplier_party_id,s.currency_code,
            COALESCE(sum(CASE WHEN a.mapping_key='ACCOUNTS_PAYABLE' THEN l.credit-l.debit ELSE 0 END),0)
            - COALESCE(sum(CASE WHEN a.mapping_key='SUPPLIER_ADVANCES' THEN l.debit-l.credit ELSE 0 END),0) AS net
          FROM suppliers s
          LEFT JOIN accounts a ON a.tenant_id=s.tenant_id
          LEFT JOIN public.journal_lines l ON l.tenant_id=s.tenant_id AND l.account_id=a.account_id AND l.party_id=s.supplier_party_id AND l.currency_code=s.currency_code
            AND EXISTS (SELECT 1 FROM public.journal_entries j WHERE j.tenant_id=l.tenant_id AND j.id=l.journal_entry_id AND j.status IN ('POSTED','REVERSED'))
         GROUP BY s.tenant_id,s.supplier_party_id,s.currency_code
        )
        SELECT s.supplier_party_id,s.currency_code,
               round(COALESCE(sub.net,0),2) AS supplier_ledger_net,
               round(COALESCE(gl.net,0),2) AS accounting_net,
               round(COALESCE(sub.net,0)-COALESCE(gl.net,0),2) AS difference
          FROM suppliers s
          LEFT JOIN subledger sub USING(tenant_id,supplier_party_id,currency_code)
          LEFT JOIN gl USING(tenant_id,supplier_party_id,currency_code)
         WHERE abs(COALESCE(sub.net,0)-COALESCE(gl.net,0))>0.01
         ORDER BY s.supplier_party_id,s.currency_code LIMIT 100
    """), {"t": t}).mappings().all()
    stock_cost_rows = db.execute(text("""
        WITH source_costs AS (
          SELECT COALESCE(receipt_po.currency_code,return_po.currency_code) AS currency_code,
                 CASE
                   WHEN tx.transaction_type='PURCHASE_RECEIPT' THEN abs(tx.total_cost)
                   WHEN tx.transaction_type='PURCHASE_RETURN' THEN -abs(tx.total_cost)
                   WHEN tx.transaction_type='PURCHASE_RETURN_REVERSAL' THEN abs(tx.total_cost)
                   ELSE 0 END AS cost_delta
            FROM public.inventory_transactions tx
            LEFT JOIN public.purchase_receipts receipt
              ON tx.transaction_type='PURCHASE_RECEIPT'
             AND tx.reference_type='purchase_receipt'
             AND receipt.tenant_id=tx.tenant_id AND receipt.id=tx.reference_id
            LEFT JOIN public.purchase_orders receipt_po
              ON receipt_po.tenant_id=receipt.tenant_id AND receipt_po.id=receipt.purchase_order_id
            LEFT JOIN public.purchase_returns r
              ON tx.transaction_type IN ('PURCHASE_RETURN','PURCHASE_RETURN_REVERSAL')
             AND r.tenant_id=tx.tenant_id AND r.id=tx.reference_id
            LEFT JOIN public.purchase_receipts return_receipt
              ON return_receipt.tenant_id=r.tenant_id AND return_receipt.id=r.purchase_receipt_id
            LEFT JOIN public.purchase_orders return_po
              ON return_po.tenant_id=return_receipt.tenant_id AND return_po.id=return_receipt.purchase_order_id
           WHERE tx.tenant_id=:t
             AND tx.transaction_type IN ('PURCHASE_RECEIPT','PURCHASE_RETURN','PURCHASE_RETURN_REVERSAL')
        )
        SELECT currency_code, round(COALESCE(sum(cost_delta),0),2) AS stock_cost, count(*) AS transaction_count
          FROM source_costs GROUP BY currency_code
    """), {"t": t}).mappings().all()
    stock_cost_by_currency: dict[str, Decimal] = {}
    unmapped_purchase_transactions = 0
    for row in stock_cost_rows:
        if not row["currency_code"]:
            unmapped_purchase_transactions += int(row["transaction_count"] or 0)
        else:
            code = str(row["currency_code"]).upper()
            stock_cost_by_currency[code] = Decimal(str(row["stock_cost"] or 0))
    journal_cost_rows = db.execute(text("""
        WITH source_entries AS (
          SELECT j.id, j.currency_code FROM public.journal_entries j
           WHERE j.tenant_id=:t AND j.source_type='PURCHASE_RECEIPT' AND j.entry_role='RECEIPT_RECOGNITION'
          UNION
          SELECT j.id, j.currency_code FROM public.journal_entries j
          JOIN public.supplier_ledger_entries e ON e.tenant_id=j.tenant_id AND e.id=j.source_id
           WHERE j.tenant_id=:t AND j.source_type='SUPPLIER_LEDGER' AND e.entry_type='RETURN_CREDIT'
          UNION
          SELECT rj.id, rj.currency_code FROM public.journal_entries rj
          JOIN public.journal_entries oj ON oj.tenant_id=rj.tenant_id AND oj.id=rj.reversal_of_id
          JOIN public.supplier_ledger_entries e ON e.tenant_id=oj.tenant_id AND e.id=oj.source_id
           WHERE rj.tenant_id=:t AND rj.source_type='REVERSAL' AND e.entry_type='RETURN_CREDIT'
        )
        SELECT s.currency_code, round(COALESCE(sum(l.debit-l.credit),0),2) AS journal_value
          FROM source_entries s
          JOIN public.journal_entries j ON j.tenant_id=:t AND j.id=s.id AND j.status IN ('POSTED','REVERSED')
          JOIN public.journal_lines l ON l.tenant_id=j.tenant_id AND l.journal_entry_id=j.id
          JOIN public.accounting_mappings m ON m.tenant_id=l.tenant_id AND m.account_id=l.account_id AND m.mapping_key='INVENTORY'
         GROUP BY s.currency_code
    """), {"t": t}).mappings().all()
    journal_cost_by_currency = {
        str(row["currency_code"]).upper(): Decimal(str(row["journal_value"] or 0))
        for row in journal_cost_rows if row["currency_code"]
    }
    currency_codes = sorted(set(stock_cost_by_currency) | set(journal_cost_by_currency))
    value_by_currency = []
    for code in currency_codes:
        stock_value = stock_cost_by_currency.get(code, Decimal("0")).quantize(Decimal("0.01"))
        journal_value = journal_cost_by_currency.get(code, Decimal("0")).quantize(Decimal("0.01"))
        difference = (stock_value - journal_value).quantize(Decimal("0.01"))
        value_by_currency.append({
            "currency_code": code,
            "inventory_stock_cost": str(stock_value),
            "inventory_journal_value": str(journal_value),
            "difference": str(difference),
        })
    # Preserve the single-currency scalar for existing clients, but never create a
    # meaningless cross-currency sum when more than one currency is present.
    single_currency_difference = value_by_currency[0]["difference"] if len(value_by_currency) == 1 and not unmapped_purchase_transactions else None
    single_currency_stock_cost = value_by_currency[0]["inventory_stock_cost"] if len(value_by_currency) == 1 and not unmapped_purchase_transactions else None
    single_currency_journal_value = value_by_currency[0]["inventory_journal_value"] if len(value_by_currency) == 1 and not unmapped_purchase_transactions else None
    stock_mismatches = [dict(row) for row in stock_rows]
    supplier_mismatches = [dict(row) for row in supplier_diffs]
    checks = {
        "stock_balance_ledger_mismatches": len(stock_mismatches),
        "posted_receipts_missing_journals": missing_receipt_journals,
        "supplier_ledger_entries_missing_journals": missing_supplier_journals,
        "unbalanced_posted_journals": unbalanced_journals,
        "supplier_subledger_gl_mismatches": len(supplier_mismatches),
        "purchase_inventory_value_difference": single_currency_difference,
        "purchase_inventory_value_by_currency": value_by_currency,
        "unmapped_purchase_inventory_transactions": unmapped_purchase_transactions,
    }
    values_reconcile = not unmapped_purchase_transactions and all(abs(Decimal(row["difference"])) <= Decimal("0.01") for row in value_by_currency)
    ok = not stock_mismatches and not missing_receipt_journals and not missing_supplier_journals and not unbalanced_journals and not supplier_mismatches and values_reconcile
    return {
        "status": "ok" if ok else "mismatch",
        "scope": "tenant-wide; all active branches verified for caller",
        "checks": checks,
        "stock_mismatches": stock_mismatches,
        "supplier_mismatches": supplier_mismatches,
        "purchase_inventory_stock_cost": single_currency_stock_cost,
        "purchase_inventory_journal_value": single_currency_journal_value,
        "purchase_inventory_value_by_currency": value_by_currency,
        "currency_note": "Supplier balances and purchase inventory/journal values are reconciled per currency; no cross-currency netting or FX conversion is performed.",
        "read_only": True,
    }
