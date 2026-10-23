from __future__ import annotations

from datetime import date
import re
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import text

from ..catalog import begin_idempotency, emit_event, finish_idempotency, write_audit
from ..dependencies import require_permission
from ..branch_access import require_full_branch_scope

router = APIRouter(prefix="/accounting", tags=["accounting"])
compliance = APIRouter(prefix="/compliance", tags=["compliance"])

_EXPENSE_REFERENCE_SECRET = re.compile(
    r"\b(?:pin|password|passcode|otp|one[- ]time(?: password| code)|verification code|security code|api key|access token|client secret|webhook secret)\b",
    re.IGNORECASE,
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AccountCreate(Strict):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=160)
    account_type: str = Field(pattern=r"^(ASSET|LIABILITY|EQUITY|REVENUE|EXPENSE)$")
    normal_balance: str = Field(pattern=r"^(DEBIT|CREDIT)$")
    system_key: str | None = Field(default=None, max_length=80)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    allow_posting: bool = True


class ExpenseCreate(Strict):
    expense_date: date = Field(default_factory=date.today)
    reference: str = Field(min_length=1, max_length=120, description="Receipt or expense reference only; never a password, PIN or verification code")
    description: str = Field(min_length=1, max_length=1000)
    expense_account_id: UUID
    payment_channel_id: UUID
    currency_code: str = Field(min_length=3, max_length=3)
    subtotal: Decimal = Field(ge=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    supplier_party_id: UUID | None = None

    @field_validator("reference")
    @classmethod
    def reference_is_not_a_credential(cls, value: str) -> str:
        cleaned = value.strip()
        if _EXPENSE_REFERENCE_SECRET.search(cleaned):
            raise ValueError("Enter a receipt reference only. Never enter a PIN, password or verification code.")
        return cleaned

    @model_validator(mode="after")
    def validate_expense(self):
        self.reference = self.reference.strip()
        self.description = self.description.strip()
        self.currency_code = self.currency_code.upper().strip()
        if not self.reference:
            raise ValueError("Enter a receipt or expense reference")
        if not self.description:
            raise ValueError("Describe what the money was spent on")
        if self.subtotal + self.tax_amount <= 0:
            raise ValueError("Enter an expense amount greater than zero")
        if not self.currency_code.isalpha():
            raise ValueError("Enter a valid three-letter currency code")
        return self


class ExpenseAction(Strict):
    reason: str = Field(min_length=3, max_length=500)


class EfrisConfigPatch(Strict):
    enabled: bool
    integration_mode: str = Field(pattern=r"^(MANUAL|PENDING_INTEGRATION|SYSTEM_TO_SYSTEM)$")
    # Registration status is server-controlled. Users cannot self-declare EFRIS
    # active; the verified URA adapter must do that after a successful handshake.
    tin: str | None = Field(default=None, max_length=40)
    legal_name: str | None = Field(default=None, max_length=200)
    effective_date: date | None = None


def out(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    d = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
    return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in d.items()}


@router.get("/accounts")
def accounts(ctx=Depends(require_permission("accounting.read"))):
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    rows = db.execute(text("""
      SELECT id,code,name,account_type,normal_balance,system_key,currency_code,allow_posting,status,created_at,updated_at
      FROM accounting_accounts WHERE tenant_id=:t ORDER BY code
    """), {"t": str(tenant_id)}).mappings().all()
    return [out(r) for r in rows]


@router.post("/accounts", status_code=201)
def create_account(body: AccountCreate, ctx=Depends(require_permission("accounting.manage"))):
    db, actor, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    try:
        account_id = db.execute(text("""
          INSERT INTO accounting_accounts(tenant_id,code,name,account_type,normal_balance,system_key,currency_code,allow_posting)
          VALUES(:t,:c,:n,:ty,:nb,:sk,:cc,:ap) RETURNING id
        """), {
            "t": str(tenant_id), "c": body.code.strip(), "n": body.name.strip(), "ty": body.account_type,
            "nb": body.normal_balance, "sk": body.system_key, "cc": body.currency_code.upper() if body.currency_code else None,
            "ap": body.allow_posting,
        }).scalar_one()
        write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="accounting.account.create", target_type="accounting_account", target_id=account_id, outcome="SUCCESS")
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    return out(db.execute(text("SELECT * FROM accounting_accounts WHERE tenant_id=:t AND id=:id"), {"t": str(tenant_id), "id": str(account_id)}).mappings().one())


@router.get("/periods")
def periods(ctx=Depends(require_permission("accounting.read"))):
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    rows = db.execute(text("SELECT id,period_name,start_date,end_date,status,closed_at,closed_by,created_at,updated_at FROM accounting_periods WHERE tenant_id=:t ORDER BY start_date DESC"), {"t": str(tenant_id)}).mappings().all()
    return [out(r) for r in rows]


@router.post("/periods/{period_id}/close")
def close_period(period_id: UUID, ctx=Depends(require_permission("periods.manage"))):
    db, actor, _, _ = ctx
    try:
        db.execute(text("SELECT close_accounting_period(:id,:u)"), {"id": str(period_id), "u": str(actor)})
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    return {"id": str(period_id), "status": "CLOSED"}


@router.get("/trial-balance")
def trial_balance(start_date: date, end_date: date, ctx=Depends(require_permission("accounting.read"))):
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date")
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    rows = db.execute(text("SELECT * FROM trial_balance(:t,:f,:to)"), {"t": str(tenant_id), "f": start_date, "to": end_date}).mappings().all()
    return [out(r) for r in rows]


@router.get("/income-statement")
def income_statement(start_date: date, end_date: date, ctx=Depends(require_permission("accounting.read"))):
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date")
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    rows = db.execute(text("SELECT * FROM income_statement(:t,:f,:to)"), {"t": str(tenant_id), "f": start_date, "to": end_date}).mappings().all()
    return [out(r) for r in rows]


@router.get("/balance-sheet")
def balance_sheet(as_of: date, ctx=Depends(require_permission("accounting.read"))):
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    rows = db.execute(text("SELECT * FROM balance_sheet(:t,:d)"), {"t": str(tenant_id), "d": as_of}).mappings().all()
    return [out(r) for r in rows]


@router.get("/journal-entries")
def journal_entries(status: str | None = Query(default=None), ctx=Depends(require_permission("accounting.read"))):
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    # Avoid a nullable placeholder in an ``IS NULL`` predicate: PostgreSQL may
    # not infer its type for an unfiltered request (status=None). Add the
    # filter only when the client supplied a status value.
    query = """
      SELECT id,entry_date,source_type,source_id,entry_role,reference,description,currency_code,status,posted_at,posted_by,created_at
      FROM journal_entries WHERE tenant_id=:t
    """
    params = {"t": str(tenant_id)}
    if status is not None:
        query += " AND status=:s"
        params["s"] = status
    query += " ORDER BY entry_date DESC,created_at DESC LIMIT 500"
    rows = db.execute(text(query), params).mappings().all()
    return [out(r) for r in rows]


@router.get("/journal-entries/{entry_id}")
def journal_entry(entry_id: UUID, ctx=Depends(require_permission("accounting.read"))):
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    header = db.execute(text("SELECT * FROM journal_entries WHERE tenant_id=:t AND id=:id"), {"t": str(tenant_id), "id": str(entry_id)}).mappings().first()
    if not header:
        raise HTTPException(404, "Journal entry not found")
    lines = db.execute(text("""
      SELECT jl.id,jl.line_no,jl.account_id,a.code account_code,a.name account_name,jl.description,jl.debit,jl.credit,jl.currency_code,jl.party_id
      FROM journal_lines jl JOIN accounting_accounts a ON a.id=jl.account_id AND a.tenant_id=jl.tenant_id
      WHERE jl.tenant_id=:t AND jl.journal_entry_id=:id ORDER BY jl.line_no
    """), {"t": str(tenant_id), "id": str(entry_id)}).mappings().all()
    return {"entry": out(header), "lines": [out(r) for r in lines]}


@router.post("/journal-entries/{entry_id}/post")
def post_entry(entry_id: UUID, ctx=Depends(require_permission("accounting.post"))):
    db, actor, _, _ = ctx
    try:
        db.execute(text("SELECT post_journal_entry(:id,:u)"), {"id": str(entry_id), "u": str(actor)})
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    return {"id": str(entry_id), "status": "POSTED"}


@router.post("/journal-entries/{entry_id}/reverse")
def reverse_entry(entry_id: UUID, ctx=Depends(require_permission("accounting.reverse"))):
    db, actor, _, _ = ctx
    try:
        new_id = db.execute(text("SELECT reverse_journal_entry(:id,:u,current_date)"), {"id": str(entry_id), "u": str(actor)}).scalar_one()
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    return {"id": str(new_id), "status": "POSTED", "reversal_of": str(entry_id)}


@router.post("/sales/{sale_id}/post")
def post_sale(sale_id: UUID, ctx=Depends(require_permission("accounting.post"))):
    db, actor, _, _ = ctx
    try:
        sale_journal = db.execute(text("SELECT post_sale_journal(:id,:u)"), {"id": str(sale_id), "u": str(actor)}).scalar_one()
        cogs_journal = db.execute(text("SELECT post_sale_cogs_journal(:id,:u)"), {"id": str(sale_id), "u": str(actor)}).scalar()
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    return {"sale_id": str(sale_id), "sale_journal_id": str(sale_journal), "cogs_journal_id": str(cogs_journal) if cogs_journal else None}


@router.post("/payments/{payment_id}/post")
def post_payment(payment_id: UUID, ctx=Depends(require_permission("accounting.post"))):
    db, actor, _, _ = ctx
    try:
        entry_id = db.execute(text("SELECT post_payment_journal(:id,:u)"), {"id": str(payment_id), "u": str(actor)}).scalar_one()
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    return {"payment_id": str(payment_id), "journal_entry_id": str(entry_id)}




class TaxRateCreate(Strict):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=160)
    rate_percent: Decimal = Field(ge=0, le=100)
    inclusive: bool = False
    effective_from: date = Field(default_factory=date.today)
    effective_to: date | None = None


class TaxConfigCreate(Strict):
    name: str = Field(min_length=1, max_length=160)
    tax_rate_id: UUID
    scope_type: str = Field(pattern=r"^(DEFAULT|PRODUCT|CATEGORY)$")
    scope_id: UUID | None = None
    effective_from: date = Field(default_factory=date.today)
    effective_to: date | None = None


@router.get("/tax-rates")
def tax_rates(ctx=Depends(require_permission("tax.read"))):
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    rows = db.execute(text("SELECT id,code,name,rate_percent,inclusive,effective_from,effective_to,status,created_at,updated_at FROM tax_rates WHERE tenant_id=:t ORDER BY code"), {"t": str(tenant_id)}).mappings().all()
    return [out(r) for r in rows]


@router.post("/tax-rates", status_code=201)
def create_tax_rate(body: TaxRateCreate, ctx=Depends(require_permission("tax.manage"))):
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    try:
        if body.effective_to and body.effective_to < body.effective_from:
            raise HTTPException(422, "Tax rate end date cannot precede start date")
        row = db.execute(text("""
          INSERT INTO tax_rates(tenant_id,code,name,rate_percent,inclusive,effective_from,effective_to)
          VALUES(:t,:c,:n,:r,:i,:f,:to) RETURNING id,code,name,rate_percent,inclusive,effective_from,effective_to,status,created_at,updated_at
        """), {"t": str(tenant_id), "c": body.code.strip().upper(), "n": body.name.strip(), "r": str(body.rate_percent), "i": body.inclusive, "f": body.effective_from, "to": body.effective_to}).mappings().one()
        db.commit()
    except HTTPException:
        db.rollback(); raise
    except Exception as exc:
        db.rollback(); raise HTTPException(400, str(exc)) from exc
    return out(row)


@router.get("/tax-configurations")
def tax_configurations(ctx=Depends(require_permission("tax.read"))):
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    rows = db.execute(text("""
      SELECT tc.id,tc.name,tc.tax_rate_id,tr.code tax_code,tr.rate_percent,tr.inclusive,tc.scope_type,tc.scope_id,tc.effective_from,tc.effective_to,tc.status
      FROM tax_configurations tc JOIN tax_rates tr ON tr.id=tc.tax_rate_id AND tr.tenant_id=tc.tenant_id
      WHERE tc.tenant_id=:t ORDER BY tc.effective_from DESC,tc.name
    """), {"t": str(tenant_id)}).mappings().all()
    return [out(r) for r in rows]


@router.post("/tax-configurations", status_code=201)
def create_tax_configuration(body: TaxConfigCreate, ctx=Depends(require_permission("tax.manage"))):
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    if body.scope_type == "DEFAULT" and body.scope_id is not None:
        raise HTTPException(422, "Default tax configuration cannot have a scope id")
    if body.scope_type != "DEFAULT" and body.scope_id is None:
        raise HTTPException(422, "Scoped tax configuration requires a scope id")
    try:
        row = db.execute(text("""
          INSERT INTO tax_configurations(tenant_id,name,tax_rate_id,scope_type,scope_id,effective_from,effective_to)
          VALUES(:t,:n,:r,:s,:sid,:f,:to)
          RETURNING id,name,tax_rate_id,scope_type,scope_id,effective_from,effective_to,status,created_at,updated_at
        """), {"t": str(tenant_id), "n": body.name.strip(), "r": str(body.tax_rate_id), "s": body.scope_type, "sid": str(body.scope_id) if body.scope_id else None, "f": body.effective_from, "to": body.effective_to}).mappings().one()
        db.commit()
    except Exception as exc:
        db.rollback(); raise HTTPException(400, str(exc)) from exc
    return out(row)

@router.get("/expenses")
def expenses(ctx=Depends(require_permission("expenses.read"))):
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    rows = db.execute(text("""
      SELECT er.id,er.expense_date,er.reference,er.description,er.expense_account_id,a.code expense_account_code,a.name expense_account_name,
             er.payment_channel_id,pc.name payment_channel_name,er.currency_code,er.subtotal,er.tax_amount,er.total,er.status,
             er.journal_entry_id,er.reversal_journal_entry_id,er.created_by,er.posted_by,er.created_at,er.updated_at
      FROM expense_records er JOIN accounting_accounts a ON a.id=er.expense_account_id AND a.tenant_id=er.tenant_id
      LEFT JOIN payment_channels pc ON pc.id=er.payment_channel_id AND pc.tenant_id=er.tenant_id
      WHERE er.tenant_id=:t ORDER BY er.expense_date DESC,er.created_at DESC LIMIT 500
    """), {"t": str(tenant_id)}).mappings().all()
    return [out(r) for r in rows]


@router.get("/expenses/{expense_id}/history")
def expense_history(expense_id: UUID, ctx=Depends(require_permission("expenses.read"))):
    """Return a plain, tenant-scoped timeline for the requested expense."""
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    exists = db.execute(text("SELECT id FROM expense_records WHERE tenant_id=:t AND id=:id"), {"t": str(tenant_id), "id": str(expense_id)}).scalar_one_or_none()
    if not exists:
        raise HTTPException(404, "Expense not found")
    rows = db.execute(text("""
      SELECT e.event_type, e.occurred_at, u.email AS actor_email, e.payload->>'reason' AS reason
      FROM outbox_events e
      LEFT JOIN users u ON u.id=e.actor_id
      WHERE e.tenant_id=:t AND e.aggregate_type='expense' AND e.aggregate_id=:id
      ORDER BY e.occurred_at ASC, e.created_at ASC
    """), {"t": str(tenant_id), "id": str(expense_id)}).mappings().all()
    return [{"event_type": row["event_type"], "occurred_at": row["occurred_at"], "actor_email": row["actor_email"], "reason": row["reason"]} for row in rows]


@router.post("/expenses", status_code=201)
def create_expense(body: ExpenseCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("expenses.manage"))):
    db, actor, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    payload = body.model_dump(mode="json")
    try:
        idem, cached = begin_idempotency(db, tenant_id=tenant_id, operation_type="accounting.expense.create", key=idempotency_key, payload=payload)
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, "This request could not be safely repeated. Refresh and try again.") from exc
    if cached:
        return cached[1]

    total = body.subtotal + body.tax_amount
    try:
        business_currency = db.execute(text(
            "SELECT currency_code FROM public.business_profiles WHERE tenant_id=:t"
        ), {"t": str(tenant_id)}).scalar_one_or_none()
        business_currency = str(business_currency or "").strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", business_currency):
            raise HTTPException(409, "Save a valid business currency in Settings before recording expenses.")
        if body.currency_code != business_currency:
            raise HTTPException(409, f"Foreign-currency expenses are not enabled. Use the saved business currency ({business_currency}) or configure an approved FX workflow first.")
        account = db.execute(text("""
          SELECT id FROM accounting_accounts
          WHERE tenant_id=:t AND id=:id AND account_type='EXPENSE' AND status='ACTIVE' AND allow_posting=true
        """), {"t": str(tenant_id), "id": str(body.expense_account_id)}).scalar_one_or_none()
        if not account:
            raise HTTPException(422, "Choose an active expense category")
        channel = db.execute(text("""
          SELECT id FROM payment_channels
          WHERE tenant_id=:t AND id=:id AND active=true AND currency_code=:cc
        """), {"t": str(tenant_id), "id": str(body.payment_channel_id), "cc": body.currency_code}).scalar_one_or_none()
        if not channel:
            raise HTTPException(422, "Choose an active payment method in the same currency as this expense")
        expense_id = db.execute(text("""
          INSERT INTO expense_records(tenant_id,expense_date,reference,description,expense_account_id,payment_channel_id,currency_code,subtotal,tax_amount,total,supplier_party_id,created_by)
          VALUES(:t,:d,:r,:desc,:a,:pc,:cc,:s,:tax,:tot,:sp,:u) RETURNING id
        """), {"t": str(tenant_id), "d": body.expense_date, "r": body.reference, "desc": body.description, "a": str(body.expense_account_id), "pc": str(body.payment_channel_id), "cc": body.currency_code, "s": str(body.subtotal), "tax": str(body.tax_amount), "tot": str(total), "sp": str(body.supplier_party_id) if body.supplier_party_id else None, "u": str(actor)}).scalar_one()
        result = {"id": str(expense_id), "status": "DRAFT", "total": str(total), "currency_code": body.currency_code}
        write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="expense.draft_created", target_type="expense", target_id=expense_id, correlation_id=request_id)
        emit_event(db, tenant_id=tenant_id, actor_user_id=actor, event_type="EXPENSE_DRAFT_CREATED", aggregate_type="expense", aggregate_id=expense_id, payload={"reference": body.reference, "total": str(total), "currency_code": body.currency_code}, correlation_id=request_id)
        finish_idempotency(db, idem, status_code=201, response_body=result, resource_type="expense", resource_id=expense_id)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, "The expense draft was not saved. Check the details and try again.") from exc


@router.post("/expenses/{expense_id}/post")
def post_expense(expense_id: UUID, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("expenses.manage"))):
    db, actor, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    payload = {"expense_id": str(expense_id)}
    try:
        idem, cached = begin_idempotency(db, tenant_id=tenant_id, operation_type="accounting.expense.post", key=idempotency_key, payload=payload)
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, "This request could not be safely repeated. Refresh and try again.") from exc
    if cached:
        return cached[1]
    try:
        expense = db.execute(text("SELECT id,status,journal_entry_id,total,currency_code FROM expense_records WHERE tenant_id=:t AND id=:id FOR UPDATE"), {"t": str(tenant_id), "id": str(expense_id)}).mappings().first()
        if not expense:
            raise HTTPException(404, "Expense not found")
        if expense["status"] == "POSTED" and expense["journal_entry_id"]:
            result = {"expense_id": str(expense_id), "journal_entry_id": str(expense["journal_entry_id"]), "status": "POSTED", "total": str(expense["total"]), "currency_code": expense["currency_code"]}
            finish_idempotency(db, idem, status_code=200, response_body=result, resource_type="expense", resource_id=expense_id)
            db.commit()
            return result
        if expense["status"] != "DRAFT":
            raise HTTPException(409, "Only a saved draft can be added to the official records")
        entry = db.execute(text("SELECT post_expense_journal(:id,:u)"), {"id": str(expense_id), "u": str(actor)}).scalar_one()
        write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="expense.posted", target_type="expense", target_id=expense_id, correlation_id=request_id)
        emit_event(db, tenant_id=tenant_id, actor_user_id=actor, event_type="EXPENSE_POSTED", aggregate_type="expense", aggregate_id=expense_id, payload={"journal_entry_id": str(entry)}, correlation_id=request_id)
        result = {"expense_id": str(expense_id), "journal_entry_id": str(entry), "status": "POSTED", "total": str(expense["total"]), "currency_code": expense["currency_code"]}
        finish_idempotency(db, idem, status_code=200, response_body=result, resource_type="expense", resource_id=expense_id)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, "This expense could not be added to the official records. Check its date and account setup.") from exc


@router.post("/expenses/{expense_id}/void")
def void_expense(expense_id: UUID, body: ExpenseAction, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("expenses.manage"))):
    db, actor, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    payload = {"expense_id": str(expense_id), "reason": body.reason.strip()}
    try:
        idem, cached = begin_idempotency(db, tenant_id=tenant_id, operation_type="accounting.expense.void", key=idempotency_key, payload=payload)
    except Exception as exc:
        db.rollback(); raise HTTPException(400, "This request could not be safely repeated.") from exc
    if cached: return cached[1]
    try:
        expense = db.execute(text("SELECT id,status FROM expense_records WHERE tenant_id=:t AND id=:id FOR UPDATE"), {"t": str(tenant_id), "id": str(expense_id)}).mappings().first()
        if not expense: raise HTTPException(404, "Expense not found")
        if expense["status"] == "VOIDED":
            result = {"expense_id": str(expense_id), "status": "VOIDED"}
        elif expense["status"] != "DRAFT":
            raise HTTPException(409, "Only a draft can be cancelled. To correct a posted expense, use the reversal action.")
        else:
            db.execute(text("UPDATE expense_records SET status='VOIDED',updated_at=now() WHERE tenant_id=:t AND id=:id AND status='DRAFT'"), {"t": str(tenant_id), "id": str(expense_id)})
            write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="expense.draft_cancelled", target_type="expense", target_id=expense_id, correlation_id=request_id)
            emit_event(db, tenant_id=tenant_id, actor_user_id=actor, event_type="EXPENSE_DRAFT_CANCELLED", aggregate_type="expense", aggregate_id=expense_id, payload={"reason": body.reason.strip()}, correlation_id=request_id)
            result = {"expense_id": str(expense_id), "status": "VOIDED"}
        finish_idempotency(db, idem, status_code=200, response_body=result, resource_type="expense", resource_id=expense_id)
        db.commit(); return result
    except HTTPException:
        db.rollback(); raise
    except Exception as exc:
        db.rollback(); raise HTTPException(400, "This draft could not be cancelled.") from exc


@router.post("/expenses/{expense_id}/reverse")
def reverse_expense(expense_id: UUID, body: ExpenseAction, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), request_id: str | None = Header(default=None, alias="X-Request-ID"), ctx=Depends(require_permission("expenses.manage"))):
    db, actor, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    payload = {"expense_id": str(expense_id), "reason": body.reason.strip()}
    try:
        idem, cached = begin_idempotency(db, tenant_id=tenant_id, operation_type="accounting.expense.reverse", key=idempotency_key, payload=payload)
    except Exception as exc:
        db.rollback(); raise HTTPException(400, "This request could not be safely repeated.") from exc
    if cached: return cached[1]
    try:
        expense = db.execute(text("SELECT id,status,journal_entry_id,reversal_journal_entry_id FROM expense_records WHERE tenant_id=:t AND id=:id FOR UPDATE"), {"t": str(tenant_id), "id": str(expense_id)}).mappings().first()
        if not expense: raise HTTPException(404, "Expense not found")
        if expense["status"] == "REVERSED" and expense["reversal_journal_entry_id"]:
            result = {"expense_id": str(expense_id), "status": "REVERSED", "reversal_journal_entry_id": str(expense["reversal_journal_entry_id"])}
        elif expense["status"] != "POSTED" or not expense["journal_entry_id"]:
            raise HTTPException(409, "Only a posted expense can be corrected this way")
        else:
            business_date = db.execute(text("SELECT public.lexa_business_date(now(), :tenant_id)"), {"tenant_id": str(tenant_id)}).scalar_one()
            reversal_id = db.execute(text("SELECT reverse_journal_entry(:id,:u,:d)"), {"id": str(expense["journal_entry_id"]), "u": str(actor), "d": business_date}).scalar_one()
            db.execute(text("UPDATE expense_records SET status='REVERSED',reversal_journal_entry_id=:r,updated_at=now() WHERE tenant_id=:t AND id=:id AND status='POSTED'"), {"r": str(reversal_id), "t": str(tenant_id), "id": str(expense_id)})
            write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="expense.reversed", target_type="expense", target_id=expense_id, correlation_id=request_id)
            emit_event(db, tenant_id=tenant_id, actor_user_id=actor, event_type="EXPENSE_REVERSED", aggregate_type="expense", aggregate_id=expense_id, payload={"reversal_journal_entry_id": str(reversal_id), "reason": body.reason.strip()}, correlation_id=request_id)
            result = {"expense_id": str(expense_id), "status": "REVERSED", "reversal_journal_entry_id": str(reversal_id)}
        finish_idempotency(db, idem, status_code=200, response_body=result, resource_type="expense", resource_id=expense_id)
        db.commit(); return result
    except HTTPException:
        db.rollback(); raise
    except Exception as exc:
        db.rollback(); raise HTTPException(400, "This expense could not be corrected. Review the record and try again.") from exc


@compliance.get("/efris/config")
def efris_config(ctx=Depends(require_permission("efris.read"))):
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    row = db.execute(text("SELECT id,enabled,integration_mode,registration_status,tin,legal_name,effective_date,created_at,updated_at FROM efris_configurations WHERE tenant_id=:t"), {"t": str(tenant_id)}).mappings().first()
    return out(row) if row else {}


@compliance.put("/efris/config")
def update_efris_config(body: EfrisConfigPatch, ctx=Depends(require_permission("efris.manage"))):
    db, actor, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    try:
        row = db.execute(text("""
          INSERT INTO efris_configurations(tenant_id,enabled,integration_mode,registration_status,tin,legal_name,effective_date)
          VALUES(:t,:e,:m,:r,:tin,:ln,:ed)
          ON CONFLICT(tenant_id) DO UPDATE SET enabled=EXCLUDED.enabled,integration_mode=EXCLUDED.integration_mode,
            registration_status=CASE WHEN EXCLUDED.integration_mode='MANUAL' THEN 'NOT_REGISTERED' ELSE 'PENDING' END,
            tin=EXCLUDED.tin,legal_name=EXCLUDED.legal_name,effective_date=EXCLUDED.effective_date,updated_at=now()
          RETURNING id,enabled,integration_mode,registration_status,tin,legal_name,effective_date,created_at,updated_at
        """), {"t": str(tenant_id), "e": body.enabled, "m": body.integration_mode, "r": 'NOT_REGISTERED' if body.integration_mode == 'MANUAL' else 'PENDING', "tin": body.tin, "ln": body.legal_name, "ed": body.effective_date}).mappings().one()
        write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="efris.configuration.update", target_type="efris_configuration", target_id=row["id"], outcome="SUCCESS")
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    return out(row)


@compliance.get("/fiscal-documents")
def fiscal_documents(status: str | None = Query(default=None), ctx=Depends(require_permission("efris.read"))):
    db, _, tenant_id, _ = ctx
    require_full_branch_scope(db, tenant_id=tenant_id, user_id=ctx[1])
    # Use the same typed, optional-filter pattern as journal entries; don't
    # place a null-only test on a bind parameter whose type PostgreSQL cannot infer.
    query = """
      SELECT id,source_type,source_id,document_type,currency_code,issue_date,status,document_number,fdn,verification_code,qr_code,
             efris_reference,response_code,response_message,submitted_at,accepted_at,voided_at,last_error,created_at,updated_at
      FROM fiscal_documents WHERE tenant_id=:t
    """
    params = {"t": str(tenant_id)}
    if status is not None:
        query += " AND status=:s"
        params["s"] = status
    query += " ORDER BY issue_date DESC,created_at DESC LIMIT 500"
    rows = db.execute(text(query), params).mappings().all()
    return [out(r) for r in rows]


@compliance.post("/sales/{sale_id}/fiscalize")
def fiscalize_sale(sale_id: UUID, document_type: str = "INVOICE", ctx=Depends(require_permission("efris.submit"))):
    db, actor, _, _ = ctx
    if document_type not in {"INVOICE", "RECEIPT"}:
        raise HTTPException(400, "Unsupported fiscal document type")
    try:
        document_id = db.execute(text("SELECT create_fiscal_document_for_sale(:id,:dt)"), {"id": str(sale_id), "dt": document_type}).scalar_one()
        write_audit(db, tenant_id=ctx[2], actor_user_id=actor, action="efris.fiscalize.request", target_type="fiscal_document", target_id=document_id, outcome="QUEUED")
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    return {"fiscal_document_id": str(document_id), "status": "PENDING"}
