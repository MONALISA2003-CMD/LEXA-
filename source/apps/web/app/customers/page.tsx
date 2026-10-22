"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "../../components/app-shell";
import {
  createCommerceCustomer,
  getCommerceCustomers,
  getCommerceSales,
  getReceivables,
  getBusinessProfile,
  userFacingError,
  type CommerceCustomer,
  type CommerceSale,
  type Receivable,
} from "../../lib/api";

type CustomerDraft = { display_name: string; phone: string; email: string; credit_limit: string };
const emptyDraft: CustomerDraft = { display_name: "", phone: "", email: "", credit_limit: "0" };
const fmtMoney = (value: number, currency: string | null) => { if (!currency || !/^[A-Z]{3}$/.test(currency)) return "Currency unavailable"; try { return new Intl.NumberFormat("en-UG", { style: "currency", currency, maximumFractionDigits: 0 }).format(Number.isFinite(value) ? value : 0); } catch { return "Currency unavailable"; } };
const statusLabel = (value: string) => ({ COMPLETED: "Completed", DRAFT: "Draft", VOIDED: "Cancelled", OPEN: "Open", PARTIALLY_PAID: "Partly paid", PAID: "Paid", CLOSED: "Completed" }[value] || value.replaceAll("_", " ").toLowerCase());

export default function CustomersPage() {
  const [customers, setCustomers] = useState<CommerceCustomer[]>([]);
  const [receivables, setReceivables] = useState<Receivable[]>([]);
  const [salesHistory, setSalesHistory] = useState<CommerceSale[]>([]);
  const [currency, setCurrency] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [draft, setDraft] = useState<CustomerDraft>(emptyDraft);
  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [message, setMessage] = useState("");
  const [selected, setSelected] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    const results = await Promise.allSettled([getCommerceCustomers(search), getReceivables(), getBusinessProfile()]);
    if (results[0].status === "fulfilled") {
      setCustomers(results[0].value);
      setSelected(current => current || results[0].value[0]?.party_id || "");
    } else setError(userFacingError(results[0].reason, "Customer details could not be loaded. Please try again."));
    if (results[1].status === "fulfilled") setReceivables(results[1].value);
    else setError(current => current || userFacingError(results[1].reason, "Customer balances could not be loaded. Please try again."));
    if (results[2].status === "fulfilled") {
      const code = results[2].value.currency_code?.toUpperCase();
      if (code && /^[A-Z]{3}$/.test(code)) setCurrency(code); else setCurrency(null);
    }
    setLoading(false);
  }, [search]);
  useEffect(() => { void load(); }, [load]);

  const balances = useMemo(() => {
    const map = new Map<string, { balance: number; count: number; lastDate: string }>();
    for (const row of receivables) {
      const old = map.get(row.customer_party_id) || { balance: 0, count: 0, lastDate: "" };
      old.balance += Math.max(0, Number(row.balance) || 0);
      old.count += 1;
      if (row.created_at > old.lastDate) old.lastDate = row.created_at;
      map.set(row.customer_party_id, old);
    }
    return map;
  }, [receivables]);
  const activeCustomer = customers.find(c => c.party_id === selected) || null;
  const balanceBySale = useMemo(() => new Map(receivables.map(row => [row.sale_id, row])), [receivables]);
  const totalDue = [...balances.values()].reduce((sum, value) => sum + value.balance, 0);

  useEffect(() => {
    if (!activeCustomer) { setSalesHistory([]); setHistoryError(""); setHistoryLoading(false); return; }
    let active = true;
    setHistoryLoading(true); setHistoryError(""); setSalesHistory([]);
    // Search the existing sales records by the customer's name, then filter by ID.
    // This keeps all paid and unpaid sales together without introducing a second ledger.
    void getCommerceSales({ search: activeCustomer.display_name, limit: 200 }).then(rows => {
      if (active) setSalesHistory(rows.filter(sale => sale.customer_party_id === activeCustomer.party_id).sort((a, b) => b.created_at.localeCompare(a.created_at)));
    }).catch(error => {
      if (active) setHistoryError(userFacingError(error, "This customer's sales history could not be loaded."));
    }).finally(() => { if (active) setHistoryLoading(false); });
    return () => { active = false; };
  }, [activeCustomer]);

  async function addCustomer(event: FormEvent) {
    event.preventDefault(); if (saving) return;
    setSaving(true); setError(""); setMessage("");
    try {
      const created = await createCommerceCustomer({ display_name: draft.display_name.trim(), phone: draft.phone.trim() || undefined, email: draft.email.trim() || undefined, credit_limit: draft.credit_limit || "0", party_type: "PERSON" });
      setDraft(emptyDraft); setSelected(created.party_id); setMessage(`${created.display_name} has been added.`); await load();
    } catch (e) { setError(userFacingError(e, "We couldn't save this customer. Check the details and try again.")); }
    finally { setSaving(false); }
  }

  return <AppShell title="Customers" eyebrow="People who buy from your business">
    <div className="customer-toolbar">
      <div><h2>Know your customers</h2><p>Keep contact details, sales and any money still owed together.</p></div>
      <button className="button button-soft" onClick={() => void load()} disabled={loading}>{loading ? "Refreshing…" : "Refresh"}</button>
    </div>
    {error && <div className="notice notice-error" role="alert">{error}</div>}
    {message && <div className="notice notice-success" role="status">{message}</div>}
    <div className="metric-strip customer-metrics"><div><span>Customers</span><strong>{customers.length}</strong></div><div><span>Money still owed</span><strong>{fmtMoney(totalDue,currency)}</strong></div><div><span>Customers with a balance</span><strong>{[...balances.values()].filter(x=>x.balance>0).length}</strong></div><div><span>Open customer balances</span><strong>{receivables.filter(row=>Number(row.balance)>0).length}</strong></div></div>
    <div className="customer-layout">
      <section className="panel customer-list-panel"><div className="panel-head"><div><h2>Customer list</h2><p>Choose a customer to see their full recorded sales and balances.</p></div><input aria-label="Search customers" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search names or phone" className="customer-search" /></div>
        {loading ? <p className="empty-inline">Loading customer list…</p> : customers.length===0 ? <div className="customer-empty"><span aria-hidden="true">☺</span><strong>No customers yet</strong><p>Add a customer here, or record a sale for a walk-in customer.</p></div> : <div className="customer-record-list">{customers.map(c=>{const row=balances.get(c.party_id);return <button type="button" key={c.party_id} onClick={()=>setSelected(c.party_id)} className={`customer-record ${selected===c.party_id?"selected":""}`}><span className="customer-avatar">{c.display_name.trim().slice(0,1).toUpperCase()||"C"}</span><span className="customer-record-main"><strong>{c.display_name}</strong><small>{c.phone||c.email||"No contact details"}</small></span><span className="customer-record-balance"><b>{fmtMoney(row?.balance||0,currency)}</b><small>{row?.count||0} open balance record{row?.count===1?"":"s"}</small></span></button>})}</div>}
      </section>
      <section className="panel customer-detail-panel">{activeCustomer ? <><div className="customer-detail-head"><span className="customer-avatar large">{activeCustomer.display_name.slice(0,1).toUpperCase()}</span><div><span className="detail-kicker">CUSTOMER DETAILS</span><h2>{activeCustomer.display_name}</h2><p>{activeCustomer.phone||activeCustomer.email||"Contact details not added"}</p></div></div><div className="detail-stat"><span>Balance still owed</span><strong>{fmtMoney(balances.get(activeCustomer.party_id)?.balance||0,currency)}</strong></div><div className="subsection"><strong className="subsection-head">Sales history</strong>{historyError&&<p className="notice notice-error" role="alert">{historyError}</p>}{historyLoading?<p className="empty-inline">Loading sales history…</p>:salesHistory.length===0?<p className="empty-inline">No recorded sales for this customer yet.</p>:salesHistory.map(sale=>{const receivable=balanceBySale.get(sale.id);return <div className="mini-row customer-sale-row" key={sale.id}><div><strong>{new Date(sale.created_at).toLocaleDateString("en-UG",{day:"numeric",month:"short",year:"numeric"})}</strong><small>Sale {sale.id.slice(0,8)} · {statusLabel(sale.status)}</small><small>Paid {fmtMoney(Number(sale.amount_paid)||0,currency)} of {fmtMoney(Number(sale.total)||0,currency)}</small></div><span>{Number(sale.amount_due)>0?`${fmtMoney(Number(sale.amount_due),currency)} due`:"Paid"}</span></div>})}</div><div className="subsection customer-limit"><span>Credit limit</span><strong>{fmtMoney(Number(activeCustomer.credit_limit)||0,currency)}</strong></div></>:<div className="customer-empty"><span aria-hidden="true">◎</span><strong>Select a customer</strong><p>Their contact details and recorded sales will appear here.</p></div>}
      </section>
    </div>
    <section className="panel customer-add-panel"><div className="panel-head"><div><h2>Add a customer</h2><p>Only enter the details your business needs.</p></div></div><form onSubmit={addCustomer} className="customer-add-form"><label>Customer name<input required maxLength={200} value={draft.display_name} onChange={e=>setDraft(d=>({...d,display_name:e.target.value}))} placeholder="e.g. Sarah Namusoke" /></label><label>Phone number (optional)<input type="tel" value={draft.phone} onChange={e=>setDraft(d=>({...d,phone:e.target.value}))} placeholder="e.g. 07…" /></label><label>Email (optional)<input type="email" value={draft.email} onChange={e=>setDraft(d=>({...d,email:e.target.value}))} placeholder="name@example.com" /></label><label>Credit limit ({currency})<input type="number" min="0" step="0.01" value={draft.credit_limit} onChange={e=>setDraft(d=>({...d,credit_limit:e.target.value}))} /></label><button type="submit" className="button button-dark" disabled={saving}>{saving?"Saving customer…":"Save customer"}</button></form></section>
  </AppShell>;
}
