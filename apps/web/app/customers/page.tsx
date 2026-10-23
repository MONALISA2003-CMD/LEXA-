"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "../../components/app-shell";
import {
  createCommerceCustomer,
  getCommerceCustomers,
  getCustomerSalesHistory,
  getReceivables,
  getBusinessProfile,
  userFacingError,
  type CommerceCustomer,
  type CustomerSaleHistory,
  type Receivable,
} from "../../lib/api";

type CustomerDraft = { display_name: string; phone: string; email: string; credit_limit: string };
const emptyDraft: CustomerDraft = { display_name: "", phone: "", email: "", credit_limit: "0" };
const fmtMoney = (value: number, currency: string | null) => { if (!currency || !/^[A-Z]{3}$/.test(currency)) return "Business currency not set"; try { return new Intl.NumberFormat("en-UG", { style: "currency", currency, maximumFractionDigits: 0 }).format(Number.isFinite(value) ? value : 0); } catch { return "Business currency not set"; } };
const statusLabel = (value: string) => ({ COMPLETED: "Completed", DRAFT: "Draft", VOIDED: "Cancelled", OPEN: "Open", PARTIALLY_PAID: "Partly paid", PAID: "Paid", CLOSED: "Completed" }[value] || value.replaceAll("_", " ").toLowerCase());

export default function CustomersPage() {
  const [customers, setCustomers] = useState<CommerceCustomer[]>([]);
  const [receivables, setReceivables] = useState<Receivable[]>([]);
  const [salesHistory, setSalesHistory] = useState<CustomerSaleHistory[]>([]);
  const [currency, setCurrency] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [draft, setDraft] = useState<CustomerDraft>(emptyDraft);
  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyMoreLoading, setHistoryMoreLoading] = useState(false);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [historyHasMore, setHistoryHasMore] = useState(false);
  const historyRequestRef = useRef(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [historyError, setHistoryError] = useState("");
  const [message, setMessage] = useState("");
  const [selected, setSelected] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    const results = await Promise.allSettled([getCommerceCustomers(search), getReceivables(), getBusinessProfile()]);
    const customerResult = results[0];
    if (customerResult.status === "fulfilled") {
      const loadedCustomers = customerResult.value;
      setCustomers(loadedCustomers);
      setSelected(current => current || loadedCustomers[0]?.party_id || "");
    } else setError(userFacingError(customerResult.reason, "Customer details could not be loaded. Please try again."));
    const receivableResult = results[1];
    if (receivableResult.status === "fulfilled") setReceivables(receivableResult.value);
    else setError(current => current || userFacingError(receivableResult.reason, "Customer balances could not be loaded. Please try again."));
    const profileResult = results[2];
    if (profileResult.status === "fulfilled") {
      const code = profileResult.value?.currency_code?.toUpperCase();
      if (code && /^[A-Z]{3}$/.test(code)) setCurrency(code); else setCurrency(null);
    }
    setLoading(false);
  }, [search]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    const requestedCustomer = new URLSearchParams(window.location.search).get("customer_id");
    if (requestedCustomer) setSelected(requestedCustomer);
  }, []);

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
    const requestToken = ++historyRequestRef.current;
    if (!activeCustomer) {
      setSalesHistory([]); setHistoryError(""); setHistoryLoading(false);
      setHistoryOffset(0); setHistoryHasMore(false); setHistoryMoreLoading(false);
      return;
    }
    let active = true;
    setHistoryLoading(true); setHistoryError(""); setSalesHistory([]);
    setHistoryOffset(0); setHistoryHasMore(false); setHistoryMoreLoading(false);
    // Query by stable customer ID on the server. This avoids name-matching false
    // positives and keeps return/refund/credit totals tied to the same sale history.
    void getCustomerSalesHistory(activeCustomer.party_id, 100, 0).then(rows => {
      if (active && requestToken === historyRequestRef.current) {
        setSalesHistory(rows); setHistoryOffset(rows.length); setHistoryHasMore(rows.length === 100);
      }
    }).catch(error => {
      if (active && requestToken === historyRequestRef.current) setHistoryError(userFacingError(error, "This customer's sales history could not be loaded."));
    }).finally(() => { if (active && requestToken === historyRequestRef.current) setHistoryLoading(false); });
    return () => { active = false; };
  }, [activeCustomer]);

  async function loadMoreHistory() {
    const partyId = activeCustomer?.party_id;
    if (!partyId || historyMoreLoading || !historyHasMore) return;
    const requestToken = historyRequestRef.current;
    const offset = historyOffset;
    setHistoryMoreLoading(true); setHistoryError("");
    try {
      const rows = await getCustomerSalesHistory(partyId, 100, offset);
      if (requestToken === historyRequestRef.current && selected === partyId) {
        setSalesHistory(current => [...current, ...rows]);
        setHistoryOffset(offset + rows.length);
        setHistoryHasMore(rows.length === 100);
      }
    } catch (error) {
      if (requestToken === historyRequestRef.current && selected === partyId) {
        setHistoryError(userFacingError(error, "Older sales history could not be loaded. Please retry."));
      }
    } finally {
      if (requestToken === historyRequestRef.current) setHistoryMoreLoading(false);
    }
  }

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
      <section className="panel customer-detail-panel">{activeCustomer ? <><div className="customer-detail-head"><span className="customer-avatar large">{activeCustomer.display_name.slice(0,1).toUpperCase()}</span><div><span className="detail-kicker">CUSTOMER DETAILS</span><h2>{activeCustomer.display_name}</h2><p>{activeCustomer.phone||activeCustomer.email||"Contact details not added"}</p></div></div><div className="detail-stat"><span>Balance still owed</span><strong>{fmtMoney(balances.get(activeCustomer.party_id)?.balance||0,currency)}</strong></div><div className="subsection"><strong className="subsection-head">Sales history</strong>{historyError&&<p className="notice notice-error" role="alert">{historyError}</p>}{historyLoading?<p className="empty-inline">Loading sales history…</p>:salesHistory.length===0?<p className="empty-inline">No recorded sales for this customer yet.</p>:salesHistory.map(sale=>{const receivable=balanceBySale.get(sale.id);return <div className="mini-row customer-sale-row" key={sale.id}><div><strong>{new Date(sale.created_at).toLocaleDateString("en-UG",{day:"numeric",month:"short",year:"numeric"})}</strong><small>Sale {sale.id.slice(0,8)} · {statusLabel(sale.status)}</small><small>Paid {fmtMoney(Number(sale.amount_paid)||0,currency)} of original sale {fmtMoney(Number(sale.total)||0,currency)}</small>{sale.return_count>0&&<small>Returns: {sale.return_count} · value {fmtMoney(Number(sale.returned_total)||0,currency)} · refunds {fmtMoney(Number(sale.refund_total)||0,currency)}</small>}{Number(sale.customer_credit_total)>0&&<small>Customer credit issued {fmtMoney(Number(sale.customer_credit_total)||0,currency)} · remaining {fmtMoney(Number(sale.remaining_customer_credit)||0,currency)}</small>}</div><span>{Number(sale.amount_due)>0?`${fmtMoney(Number(sale.amount_due),currency)} due`:"Paid"}</span></div>})}{historyHasMore&&<button type="button" className="button button-soft" onClick={() => void loadMoreHistory()} disabled={historyMoreLoading}>{historyMoreLoading?"Loading older sales…":"Load older sales"}</button>}<p className="empty-inline">Original sale amounts, returned value, cash refunds and customer credit are shown separately.</p></div><div className="subsection customer-limit"><span>Credit limit</span><strong>{fmtMoney(Number(activeCustomer.credit_limit)||0,currency)}</strong></div></>:<div className="customer-empty"><span aria-hidden="true">◎</span><strong>Select a customer</strong><p>Their contact details and recorded sales will appear here.</p></div>}
      </section>
    </div>
    <section className="panel customer-add-panel"><div className="panel-head"><div><h2>Add a customer</h2><p>Only enter the details your business needs.</p></div></div><form onSubmit={addCustomer} className="customer-add-form"><label>Customer name<input required maxLength={200} value={draft.display_name} onChange={e=>setDraft(d=>({...d,display_name:e.target.value}))} placeholder="e.g. Sarah Namusoke" /></label><label>Phone number (optional)<input type="tel" value={draft.phone} onChange={e=>setDraft(d=>({...d,phone:e.target.value}))} placeholder="e.g. 07…" /></label><label>Email (optional)<input type="email" value={draft.email} onChange={e=>setDraft(d=>({...d,email:e.target.value}))} placeholder="name@example.com" /></label><label>Credit limit ({currency})<input type="number" min="0" step="0.01" value={draft.credit_limit} onChange={e=>setDraft(d=>({...d,credit_limit:e.target.value}))} /></label><button type="submit" className="button button-dark" disabled={saving}>{saving?"Saving customer…":"Save customer"}</button></form></section>
  </AppShell>;
}
