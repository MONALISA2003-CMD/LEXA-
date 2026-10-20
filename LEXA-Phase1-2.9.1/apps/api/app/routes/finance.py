from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from ..catalog import write_audit
from ..dependencies import require_permission

router = APIRouter(prefix="/accounting", tags=["accounting"])
compliance = APIRouter(prefix="/compliance", tags=["compliance"])


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
    reference: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    expense_account_id: UUID
    payment_channel_id: UUID | None = None
    currency_code: str = Field(min_length=3, max_length=3)
    subtotal: Decimal = Field(ge=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    supplier_party_id: UUID | None = None


class EfrisConfigPatch(Strict):
    enabled: bool
    integration_mode: str = Field(pattern=r"^(MANUAL|PENDING_INTEGRATION|SYSTEM_TO_SYSTEM)$")
    registration_status: str = Field(pattern=r"^(NOT_REGISTERED|PENDING|ACTIVE|SUSPENDED)$")
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
    rows = db.execute(text("""
      SELECT id,code,name,account_type,normal_balance,system_key,currency_code,allow_posting,status,created_at,updated_at
      FROM accounting_accounts WHERE tenant_id=:t ORDER BY code
    """), {"t": str(tenant_id)}).mappings().all()
    return [out(r) for r in rows]


@router.post("/accounts", status_code=201)
def create_account(body: AccountCreate, ctx=Depends(require_permission("accounting.manage"))):
    db, actor, tenant_id, _ = ctx
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
    db, _, tenant_id, _ = ctx
    rows = db.execute(text("SELECT * FROM trial_balance(:t,:f,:to)"), {"t": str(tenant_id), "f": start_date, "to": end_date}).mappings().all()
    return [out(r) for r in rows]


@router.get("/income-statement")
def income_statement(start_date: date, end_date: date, ctx=Depends(require_permission("accounting.read"))):
    db, _, tenant_id, _ = ctx
    rows = db.execute(text("SELECT * FROM income_statement(:t,:f,:to)"), {"t": str(tenant_id), "f": start_date, "to": end_date}).mappings().all()
    return [out(r) for r in rows]


@router.get("/balance-sheet")
def balance_sheet(as_of: date, ctx=Depends(require_permission("accounting.read"))):
    db, _, tenant_id, _ = ctx
    rows = db.execute(text("SELECT * FROM balance_sheet(:t,:d)"), {"t": str(tenant_id), "d": as_of}).mappings().all()
    return [out(r) for r in rows]


@router.get("/journal-entries")
def journal_entries(status: str | None = Query(default=None), ctx=Depends(require_permission("accounting.read"))):
    db, _, tenant_id, _ = ctx
    rows = db.execute(text("""
      SELECT id,entry_date,source_type,source_id,entry_role,reference,description,currency_code,status,posted_at,posted_by,created_at
      FROM journal_entries WHERE tenant_id=:t AND (:s IS NULL OR status=:s) ORDER BY entry_date DESC,created_at DESC LIMIT 500
    """), {"t": str(tenant_id), "s": status}).mappings().all()
    return [out(r) for r in rows]


@router.get("/journal-entries/{entry_id}")
def journal_entry(entry_id: UUID, ctx=Depends(require_permission("accounting.read"))):
    db, _, tenant_id, _ = ctx
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
    rows = db.execute(text("SELECT id,code,name,rate_percent,inclusive,effective_from,effective_to,status,created_at,updated_at FROM tax_rates WHERE tenant_id=:t ORDER BY code"), {"t": str(tenant_id)}).mappings().all()
    return [out(r) for r in rows]


@router.post("/tax-rates", status_code=201)
def create_tax_rate(body: TaxRateCreate, ctx=Depends(require_permission("tax.manage"))):
    db, _, tenant_id, _ = ctx
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
    rows = db.execute(text("""
      SELECT tc.id,tc.name,tc.tax_rate_id,tr.code tax_code,tr.rate_percent,tr.inclusive,tc.scope_type,tc.scope_id,tc.effective_from,tc.effective_to,tc.status
      FROM tax_configurations tc JOIN tax_rates tr ON tr.id=tc.tax_rate_id AND tr.tenant_id=tc.tenant_id
      WHERE tc.tenant_id=:t ORDER BY tc.effective_from DESC,tc.name
    """), {"t": str(tenant_id)}).mappings().all()
    return [out(r) for r in rows]


@router.post("/tax-configurations", status_code=201)
def create_tax_configuration(body: TaxConfigCreate, ctx=Depends(require_permission("tax.manage"))):
    db, _, tenant_id, _ = ctx
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
    rows = db.execute(text("""
      SELECT er.id,er.expense_date,er.reference,er.description,er.expense_account_id,a.code expense_account_code,a.name expense_account_name,
             er.payment_channel_id,pc.name payment_channel_name,er.currency_code,er.subtotal,er.tax_amount,er.total,er.status,er.journal_entry_id,er.created_at,er.updated_at
      FROM expense_records er JOIN accounting_accounts a ON a.id=er.expense_account_id AND a.tenant_id=er.tenant_id
      LEFT JOIN payment_channels pc ON pc.id=er.payment_channel_id AND pc.tenant_id=er.tenant_id
      WHERE er.tenant_id=:t ORDER BY er.expense_date DESC,er.created_at DESC LIMIT 500
    """), {"t": str(tenant_id)}).mappings().all()
    return [out(r) for r in rows]


@router.post("/expenses", status_code=201)
def create_expense(body: ExpenseCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), ctx=Depends(require_permission("expenses.manage"))):
    db, actor, tenant_id, _ = ctx
    total = body.subtotal + body.tax_amount
    try:
        expense_id = db.execute(text("""
          INSERT INTO expense_records(tenant_id,expense_date,reference,description,expense_account_id,payment_channel_id,currency_code,subtotal,tax_amount,total,supplier_party_id,created_by)
          VALUES(:t,:d,:r,:desc,:a,:pc,:cc,:s,:tax,:tot,:sp,:u) RETURNING id
        """), {"t": str(tenant_id), "d": body.expense_date, "r": body.reference.strip(), "desc": body.description.strip(), "a": str(body.expense_account_id), "pc": str(body.payment_channel_id) if body.payment_channel_id else None, "cc": body.currency_code.upper(), "s": str(body.subtotal), "tax": str(body.tax_amount), "tot": str(total), "sp": str(body.supplier_party_id) if body.supplier_party_id else None, "u": str(actor)}).scalar_one()
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    return {"id": str(expense_id), "status": "DRAFT", "total": str(total)}


@router.post("/expenses/{expense_id}/post")
def post_expense(expense_id: UUID, ctx=Depends(require_permission("expenses.manage"))):
    db, actor, _, _ = ctx
    try:
        entry = db.execute(text("SELECT post_expense_journal(:id,:u)"), {"id": str(expense_id), "u": str(actor)}).scalar_one()
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    return {"expense_id": str(expense_id), "journal_entry_id": str(entry), "status": "POSTED"}


@compliance.get("/efris/config")
def efris_config(ctx=Depends(require_permission("efris.read"))):
    db, _, tenant_id, _ = ctx
    row = db.execute(text("SELECT id,enabled,integration_mode,registration_status,tin,legal_name,effective_date,created_at,updated_at FROM efris_configurations WHERE tenant_id=:t"), {"t": str(tenant_id)}).mappings().first()
    return out(row) if row else {}


@compliance.put("/efris/config")
def update_efris_config(body: EfrisConfigPatch, ctx=Depends(require_permission("efris.manage"))):
    db, actor, tenant_id, _ = ctx
    try:
        row = db.execute(text("""
          INSERT INTO efris_configurations(tenant_id,enabled,integration_mode,registration_status,tin,legal_name,effective_date)
          VALUES(:t,:e,:m,:r,:tin,:ln,:ed)
          ON CONFLICT(tenant_id) DO UPDATE SET enabled=EXCLUDED.enabled,integration_mode=EXCLUDED.integration_mode,
            registration_status=EXCLUDED.registration_status,tin=EXCLUDED.tin,legal_name=EXCLUDED.legal_name,effective_date=EXCLUDED.effective_date,updated_at=now()
          RETURNING id,enabled,integration_mode,registration_status,tin,legal_name,effective_date,created_at,updated_at
        """), {"t": str(tenant_id), "e": body.enabled, "m": body.integration_mode, "r": body.registration_status, "tin": body.tin, "ln": body.legal_name, "ed": body.effective_date}).mappings().one()
        write_audit(db, tenant_id=tenant_id, actor_user_id=actor, action="efris.configuration.update", target_type="efris_configuration", target_id=row["id"], outcome="SUCCESS")
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    return out(row)


@compliance.get("/fiscal-documents")
def fiscal_documents(status: str | None = Query(default=None), ctx=Depends(require_permission("efris.read"))):
    db, _, tenant_id, _ = ctx
    rows = db.execute(text("""
      SELECT id,source_type,source_id,document_type,currency_code,issue_date,status,document_number,fdn,verification_code,qr_code,
             efris_reference,response_code,response_message,submitted_at,accepted_at,voided_at,last_error,created_at,updated_at
      FROM fiscal_documents WHERE tenant_id=:t AND (:s IS NULL OR status=:s) ORDER BY issue_date DESC,created_at DESC LIMIT 500
    """), {"t": str(tenant_id), "s": status}).mappings().all()
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
