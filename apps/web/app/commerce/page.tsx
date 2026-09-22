"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  closeReconciliation,
  createCommerceCustomer,
  createCommerceSale,
  createPaymentChannel,
  createReconciliation,
  createSaleReturn,
  allocateCustomerCredit,
  getCommerceCustomers,
  getCommerceDashboard,
  getCommerceProducts,
  getCommerceSale,
  getCommerceSales,
  getLocations,
  getPaymentChannels,
  getReconciliations,
  getReceivables,
  getSaleReturns,
  getCustomerCredits,
  payReceivable,
  resolveReconciliationLine,
  setReconciliationActual,
  type CommerceCustomer,
  type CommerceDashboard,
  type CommerceProduct,
  type CommerceSale,
  type CommerceSaleDetail,
  type CustomerCredit,
  type Location,
  type PaymentChannel,
  type Receivable,
  type Reconciliation,
  type ReconciliationLine,
  type SaleReturn,
} from "../../lib/api";

function money(v: string | number) {
  return new Intl.NumberFormat("en-UG", { style: "currency", currency: "UGX", maximumFractionDigits: 0 }).format(Number(v));
}

function today() {
  const d = new Date();
  const month = `${d.getMonth() + 1}`.padStart(2, "0");
  const day = `${d.getDate()}`.padStart(2, "0");
  return `${d.getFullYear()}-${month}-${day}`;
}

function short(v: string) {
  return `${v.slice(0, 8)}…`;
}

type PaymentRow = { channelId: string; amount: string };

export default function CommercePage() {
  const [tab, setTab] = useState("Sell");
  const [busy, setBusy] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<CommerceDashboard | null>(null);
  const [customers, setCustomers] = useState<CommerceCustomer[]>([]);
  const [channels, setChannels] = useState<PaymentChannel[]>([]);
  const [products, setProducts] = useState<CommerceProduct[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [sales, setSales] = useState<CommerceSale[]>([]);
  const [receivables, setReceivables] = useState<Receivable[]>([]);
  const [reconciliations, setReconciliations] = useState<Reconciliation[]>([]);
  const [returns, setReturns] = useState<SaleReturn[]>([]);
  const [customerCredits, setCustomerCredits] = useState<CustomerCredit[]>([]);

  const [customerId, setCustomerId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [variantId, setVariantId] = useState("");
  const [qty, setQty] = useState("1");
  const [price, setPrice] = useState("0");
  const [saleDate, setSaleDate] = useState(today());
  const [paymentRows, setPaymentRows] = useState<PaymentRow[]>([{ channelId: "", amount: "0" }]);

  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [channelName, setChannelName] = useState("");
  const [channelType, setChannelType] = useState("MOBILE_MONEY");
  const [provider, setProvider] = useState("");

  const [selectedRecon, setSelectedRecon] = useState("");
  const [actuals, setActuals] = useState<Record<string, string>>({});

  const [returnSaleId, setReturnSaleId] = useState("");
  const [returnSale, setReturnSale] = useState<CommerceSaleDetail | null>(null);
  const [returnLineId, setReturnLineId] = useState("");
  const [returnQty, setReturnQty] = useState("1");
  const [returnReason, setReturnReason] = useState("");
  const [returnSettlement, setReturnSettlement] = useState<"NONE" | "REFUND" | "CUSTOMER_CREDIT">("NONE");
  const [refundChannelId, setRefundChannelId] = useState("");
  const [creditReceivableId, setCreditReceivableId] = useState("");
  const [creditAmount, setCreditAmount] = useState("");

  const selectedProduct = useMemo(() => products.find((x) => x.variant_id === variantId), [products, variantId]);
  const selectedReconData = useMemo(() => reconciliations.find((x) => x.id === selectedRecon), [reconciliations, selectedRecon]);
  const activeUgxChannels = useMemo(() => channels.filter((x) => x.active && x.currency_code === "UGX"), [channels]);
  const selectedReturnLine = useMemo(() => returnSale?.lines.find((x) => x.sale_line_id === returnLineId), [returnSale, returnLineId]);

  async function refresh() {
    setBusy(true);
    setMessage(null);
    try {
      const date = today();
      const [d, c, ch, p, l, s, r, re, rr, cc] = await Promise.all([
        getCommerceDashboard(date),
        getCommerceCustomers(),
        getPaymentChannels(),
        getCommerceProducts(),
        getLocations(),
        getCommerceSales(),
        getReceivables(),
        getReconciliations(),
        getSaleReturns(),
        getCustomerCredits(),
      ]);
      setDashboard(d);
      setCustomers(c);
      setChannels(ch);
      setProducts(p);
      setLocations(l);
      setSales(s);
      setReceivables(r);
      setReconciliations(re);
      setReturns(rr);
      setCustomerCredits(cc);
      if (!locationId && l[0]) setLocationId(l[0].id);
      const usableChannels = ch.filter((x) => x.active && x.currency_code === "UGX");
      if (!paymentRows[0]?.channelId && usableChannels[0]) setPaymentRows([{ channelId: usableChannels[0].id, amount: "0" }]);
      if (!refundChannelId && usableChannels[0]) setRefundChannelId(usableChannels[0].id);
      if (!variantId && p[0]) {
        setVariantId(p[0].variant_id);
        setPrice(p[0].selling_price || "0");
      }
      if (!selectedRecon && re[0]) setSelectedRecon(re[0].id);
      if (!returnSaleId && s[0]) {
        setReturnSaleId(s[0].id);
        const detail = await getCommerceSale(s[0].id);
        setReturnSale(detail);
        if (detail.lines[0]) setReturnLineId(detail.lines[0].sale_line_id);
      }
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Unable to load commerce workspace");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void refresh();
    // The initial load is intentionally one time only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function updatePayment(index: number, field: keyof PaymentRow, value: string) {
    setPaymentRows((rows) => rows.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  }

  async function submitCustomer(e: FormEvent) {
    e.preventDefault();
    try {
      await createCommerceCustomer({ display_name: customerName, phone: customerPhone || undefined });
      setCustomerName("");
      setCustomerPhone("");
      setMessage("Customer created.");
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not create customer");
    }
  }

  async function submitChannel(e: FormEvent) {
    e.preventDefault();
    try {
      await createPaymentChannel({ name: channelName, channel_type: channelType, provider: provider || undefined, currency_code: "UGX" });
      setChannelName("");
      setProvider("");
      setMessage("Payment channel created.");
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not create payment channel");
    }
  }

  async function submitSale(e: FormEvent) {
    e.preventDefault();
    try {
      if (!locationId || !variantId) throw new Error("Select a location and product.");
      const payments = paymentRows
        .filter((x) => Number(x.amount) > 0)
        .map((x) => ({ payment_channel_id: x.channelId, amount: x.amount }));
      if (payments.some((x) => !x.payment_channel_id)) throw new Error("Select a payment channel for every payment amount.");
      const created = await createCommerceSale({
        customer_party_id: customerId || null,
        location_id: locationId,
        currency_code: "UGX",
        business_date: saleDate,
        lines: [{ variant_id: variantId, quantity: qty, unit_price: price }],
        payments,
      });
      setMessage(`Sale ${short(created.id)} completed for ${money(created.total)}.`);
      setPaymentRows([{ channelId: activeUgxChannels[0]?.id || "", amount: "0" }]);
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not complete sale");
    }
  }

  async function submitReceivablePayment(id: string) {
    const amount = window.prompt("Amount received (UGX)");
    if (!amount) return;
    const ch = paymentRows[0]?.channelId || activeUgxChannels[0]?.id;
    if (!ch) {
      setMessage("Configure a payment channel first.");
      return;
    }
    try {
      await payReceivable(id, { payment_channel_id: ch, amount, business_date: today() });
      setMessage("Receivable payment recorded.");
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not record payment");
    }
  }

  async function startRecon() {
    try {
      const x = await createReconciliation({ business_date: today() });
      setSelectedRecon(x.id);
      setMessage("Daily reconciliation opened.");
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not open reconciliation");
    }
  }

  async function saveActual(line: ReconciliationLine) {
    try {
      const value = actuals[line.line_id];
      if (value === undefined || value === "") throw new Error("Enter the actual amount first.");
      await setReconciliationActual(line.line_id, { actual_amount: value });
      setMessage("Actual amount saved.");
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not save actual");
    }
  }

  async function acknowledgeLine(line: ReconciliationLine) {
    try {
      await resolveReconciliationLine(line.line_id, { status: "ACKNOWLEDGED" });
      setMessage("Variance acknowledged.");
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not acknowledge variance");
    }
  }

  async function closeRecon() {
    if (!selectedRecon) return;
    try {
      await closeReconciliation(selectedRecon);
      setMessage("Business day closed.");
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Reconciliation cannot be closed yet");
    }
  }

  async function submitCreditAllocation(creditId: string, e: FormEvent) {
    e.preventDefault();
    const credit = customerCredits.find((x) => x.id === creditId);
    if (!credit) return;
    if (!creditReceivableId || !creditAmount) {
      setMessage("Select a receivable and enter an amount.");
      return;
    }
    try {
      await allocateCustomerCredit(credit.id, { receivable_id: creditReceivableId, amount: creditAmount });
      setMessage("Customer credit allocated to the receivable.");
      setCreditAmount("");
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not allocate customer credit");
    }
  }

  async function loadReturnSale(id: string) {
    setReturnSaleId(id);
    setReturnSale(null);
    setReturnLineId("");
    if (!id) return;
    try {
      const detail = await getCommerceSale(id);
      setReturnSale(detail);
      if (detail.lines[0]) setReturnLineId(detail.lines[0].sale_line_id);
      setReturnSettlement("NONE");
      setReturnReason("");
      setReturnQty("1");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not load sale");
    }
  }

  async function submitReturn(e: FormEvent) {
    e.preventDefault();
    if (!returnSale || !returnLineId) {
      setMessage("Select a completed sale and sale line.");
      return;
    }
    try {
      const result = await createSaleReturn(returnSale.id, {
        reason: returnReason,
        inventory_location_id: returnSale.location_id || locationId,
        business_date: today(),
        settlement_type: returnSettlement,
        refund_channel_id: returnSettlement === "REFUND" ? refundChannelId : null,
        lines: [{ sale_line_id: returnLineId, quantity: returnQty }],
      });
      setMessage(`Return ${short(result.id)} completed for ${money(result.total)}.`);
      await refresh();
      await loadReturnSale(returnSale.id);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not process return");
    }
  }

  const totalPreview = Number(qty || 0) * Number(price || 0);

  return (
    <main className="module-page commerce-page">
      <div className="inventory-summary">
        <div>
          <span className="eyebrow">COMMERCE OPERATIONS</span>
          <h2>Sales, money and reconciliation</h2>
          <p>The business records what happened. LEXA calculates totals, keeps stock connected, tracks receivables and reconciles expected versus actual settlements.</p>
        </div>
        <button className="secondary" onClick={() => void refresh()} disabled={busy}>{busy ? "Refreshing…" : "Refresh"}</button>
      </div>

      {message && <div className="inline-message">{message}</div>}

      {dashboard && (
        <div className="stat-grid">
          <div className="stat-card"><span>TODAY SALES</span><strong>{money(dashboard.sales.sales)}</strong><small>Completed sales</small></div>
          <div className="stat-card"><span>COLLECTED</span><strong>{money(dashboard.sales.collected)}</strong><small>Recorded payments</small></div>
          <div className="stat-card"><span>CREDIT</span><strong>{money(dashboard.sales.credit)}</strong><small>Outstanding from sales</small></div>
          <div className="stat-card"><span>RECEIVABLES</span><strong>{money(dashboard.outstanding_receivables)}</strong><small>Open customer balance</small></div>
        </div>
      )}

      <section className="section inventory-section">
        <div className="inventory-tabs">
          {["Sell", "Customers", "Payment Channels", "Receivables", "Customer Credits", "Reconciliation", "Returns", "Sales History"].map((x) => (
            <button key={x} className={tab === x ? "selected" : ""} onClick={() => setTab(x)}>{x}</button>
          ))}
        </div>

        <div className="commerce-body">
          {tab === "Sell" && (
            <div className="split-panel">
              <form className="command-form" onSubmit={submitSale}>
                <div><p className="eyebrow">CHECKOUT</p><h3>Complete a sale</h3><p>LEXA calculates the sale, reduces stock, records payments and creates a receivable when money is still due.</p></div>
                <label>Business date<input type="date" value={saleDate} onChange={(e) => setSaleDate(e.target.value)} required /></label>
                <label>Customer<select value={customerId} onChange={(e) => setCustomerId(e.target.value)}><option value="">Walk-in customer</option>{customers.map((c) => <option key={c.party_id} value={c.party_id}>{c.display_name}</option>)}</select></label>
                <label>Location<select value={locationId} onChange={(e) => setLocationId(e.target.value)} required><option value="">Select location</option>{locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}</select></label>
                <label>Product / SKU<select value={variantId} onChange={(e) => { setVariantId(e.target.value); const p = products.find((x) => x.variant_id === e.target.value); if (p) setPrice(p.selling_price || "0"); }} required><option value="">Select product</option>{products.map((p) => <option key={p.variant_id} value={p.variant_id}>{p.product_name} · {p.sku}</option>)}</select></label>
                <div className="form-grid"><label>Quantity<input type="number" min="0.001" step="0.001" value={qty} onChange={(e) => setQty(e.target.value)} required /></label><label>Selling price<input type="number" min="0" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} required /></label></div>
                <div className="workflow-list">
                  <div className="eyebrow">PAYMENT ALLOCATIONS</div>
                  {paymentRows.map((row, index) => (
                    <div className="workflow-row" key={`${index}-${row.channelId}`}>
                      <select value={row.channelId} onChange={(e) => updatePayment(index, "channelId", e.target.value)}>
                        <option value="">No payment</option>
                        {activeUgxChannels.map((c) => <option key={c.id} value={c.id}>{c.name} · {c.channel_type}</option>)}
                      </select>
                      <input type="number" min="0" step="0.01" value={row.amount} onChange={(e) => updatePayment(index, "amount", e.target.value)} aria-label={`Payment ${index + 1} amount`} />
                      {paymentRows.length > 1 && <button type="button" className="secondary" onClick={() => setPaymentRows((rows) => rows.filter((_, i) => i !== index))}>Remove</button>}
                    </div>
                  ))}
                  <button type="button" className="secondary" onClick={() => setPaymentRows((rows) => [...rows, { channelId: activeUgxChannels[0]?.id || "", amount: "0" }])}>Add another payment</button>
                </div>
                <div className="inline-message">{selectedProduct ? `${selectedProduct.product_name} · ${selectedProduct.sku}` : "Choose a product"} · Total {money(totalPreview)}</div>
                <button className="primary" type="submit">Complete sale</button>
              </form>
              <div className="workflow-list"><p className="eyebrow">PAYMENT CHANNELS</p>{channels.length ? channels.map((c) => <div className="workflow-row" key={c.id}><div><strong>{c.name}</strong><small>{c.channel_type} · {c.provider || "Business configured"} · {c.currency_code}</small></div><span className="status good">READY</span></div>) : <div className="empty-inline">No payment channels configured yet.</div>}</div>
            </div>
          )}

          {tab === "Customers" && (
            <div className="split-panel">
              <form className="command-form" onSubmit={submitCustomer}><div><p className="eyebrow">CUSTOMER</p><h3>Add a customer</h3><p>Customer records do not require bank or mobile-money credentials.</p></div><label>Display name<input value={customerName} onChange={(e) => setCustomerName(e.target.value)} required /></label><label>Phone<input value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} /></label><button className="primary">Save customer</button></form>
              <div className="workflow-list">{customers.map((c) => <div className="workflow-row" key={c.party_id}><div><strong>{c.display_name}</strong><small>{c.phone || c.email || "No contact"}</small></div><span className="status neutral">{c.status}</span><span>{money(c.credit_limit)}</span></div>)}</div>
            </div>
          )}

          {tab === "Payment Channels" && (
            <div className="split-panel">
              <form className="command-form" onSubmit={submitChannel}><div><p className="eyebrow">PAYMENT CHANNEL</p><h3>Configure where money is received</h3><p>No account numbers, PINs, OTPs, passwords, API keys or access tokens are stored here.</p></div><label>Name<input value={channelName} onChange={(e) => setChannelName(e.target.value)} placeholder="MTN Line 2" required /></label><div className="form-grid"><label>Type<select value={channelType} onChange={(e) => setChannelType(e.target.value)}><option>CASH</option><option>MOBILE_MONEY</option><option>BANK</option><option>CARD</option><option>CHEQUE</option><option>OTHER</option></select></label><label>Provider<input value={provider} onChange={(e) => setProvider(e.target.value)} placeholder="MTN" /></label></div><button className="primary">Save channel</button></form>
              <div className="workflow-list">{channels.map((c) => <div className="workflow-row" key={c.id}><div><strong>{c.name}</strong><small>{c.channel_type} · {c.provider || ""} · {c.currency_code}</small></div><span className={c.active ? "status good" : "status neutral"}>{c.active ? "ACTIVE" : "INACTIVE"}</span></div>)}</div>
            </div>
          )}

          {tab === "Receivables" && <div className="workflow-list">{receivables.length ? receivables.map((r) => <div className="workflow-row" key={r.id}><div><strong>{r.customer_name}</strong><small>Sale {short(r.sale_id)} · {r.status}</small></div><span>{money(r.balance)}</span><button className="secondary" onClick={() => void submitReceivablePayment(r.id)}>Record payment</button></div>) : <div className="empty-inline">No open receivables.</div>}</div>}

          {tab === "Customer Credits" && (
            <div className="workflow-list">
              {customerCredits.length ? customerCredits.map((credit) => (
                <div className="workflow-row" key={credit.id}>
                  <div>
                    <strong>{credit.customer_name}</strong>
                    <small>Credit {short(credit.id)} · {credit.status} · Source return {short(credit.source_return_id)}</small>
                  </div>
                  <span>{money(credit.balance)}</span>
                  <form className="credit-allocation-form" onSubmit={(e) => void submitCreditAllocation(credit.id, e)}>
                    <select value={creditReceivableId} onChange={(e) => setCreditReceivableId(e.target.value)}>
                      <option value="">Select receivable</option>
                      {receivables.filter((r) => r.customer_party_id === credit.customer_party_id).map((r) => (
                        <option key={r.id} value={r.id}>{short(r.id)} · {money(r.balance)}</option>
                      ))}
                    </select>
                    <input type="number" min="0.01" step="0.01" value={creditAmount} onChange={(e) => setCreditAmount(e.target.value)} placeholder="Amount" />
                    <button className="secondary" type="submit">Apply credit</button>
                  </form>
                </div>
              )) : <div className="empty-inline">No customer credits available.</div>}
            </div>
          )}

          {tab === "Reconciliation" && (
            <div className="split-panel">
              <div className="command-form"><div><p className="eyebrow">DAILY CLOSING</p><h3>Reconcile the business day</h3><p>LEXA calculates expected settlement from recorded payments and refunds. You enter the actual amount seen or counted.</p></div><button className="primary" onClick={() => void startRecon()}>Open today</button>{reconciliations.length > 0 && <label>Business day<select value={selectedRecon} onChange={(e) => setSelectedRecon(e.target.value)}>{reconciliations.map((r) => <option key={r.id} value={r.id}>{r.business_date} · {r.status}</option>)}</select></label>}{selectedReconData && <button className="button-dark" onClick={() => void closeRecon()} disabled={selectedReconData.status === "CLOSED"}>Close business day</button>}</div>
              <div className="workflow-list">{selectedReconData?.lines.length ? selectedReconData.lines.map((line) => <div className="workflow-row" key={line.line_id}><div><strong>{line.channel_name}</strong><small>Expected {money(line.expected_amount)} · {line.line_status}{line.variance ? ` · Variance ${money(line.variance)}` : ""}</small></div><div><input className="recon-input" value={actuals[line.line_id] ?? line.actual_amount ?? ""} onChange={(e) => setActuals((s) => ({ ...s, [line.line_id]: e.target.value }))} placeholder="Actual" /></div><button className="secondary" onClick={() => void saveActual(line)}>Save</button>{Number(line.variance || 0) !== 0 && line.line_status !== "ACKNOWLEDGED" && <button className="secondary" onClick={() => void acknowledgeLine(line)}>Acknowledge</button>}</div>) : <div className="empty-inline">Open a business day. Active payment channels will appear here.</div>}</div>
            </div>
          )}

          {tab === "Returns" && (
            <div className="split-panel">
              <form className="command-form" onSubmit={submitReturn}><div><p className="eyebrow">RETURNS</p><h3>Record a sale return</h3><p>LEXA restores stock, reduces the sale value and records a refund or customer credit without deleting the original sale.</p></div><label>Completed sale<select value={returnSaleId} onChange={(e) => void loadReturnSale(e.target.value)} required><option value="">Select sale</option>{sales.filter((s) => s.status === "COMPLETED").map((s) => <option key={s.id} value={s.id}>{short(s.id)} · {s.customer_name || "Walk-in"} · {money(s.total)}</option>)}</select></label><label>Sale line<select value={returnLineId} onChange={(e) => setReturnLineId(e.target.value)} required><option value="">Select line</option>{returnSale?.lines.map((line) => <option key={line.sale_line_id} value={line.sale_line_id}>{line.variant_name || line.sku || short(line.sale_line_id)} · Qty {line.quantity}</option>)}</select></label><div className="form-grid"><label>Quantity<input type="number" min="0.001" step="0.001" value={returnQty} onChange={(e) => setReturnQty(e.target.value)} required /></label><label>Reason<input value={returnReason} onChange={(e) => setReturnReason(e.target.value)} required placeholder="Customer return" /></label></div><label>Settlement<select value={returnSettlement} onChange={(e) => setReturnSettlement(e.target.value as "NONE" | "REFUND" | "CUSTOMER_CREDIT")}><option value="NONE">No immediate settlement</option><option value="REFUND">Refund</option><option value="CUSTOMER_CREDIT" disabled={!returnSale?.customer_party_id}>Customer credit</option></select></label>{returnSettlement === "REFUND" && <label>Refund channel<select value={refundChannelId} onChange={(e) => setRefundChannelId(e.target.value)} required><option value="">Select refund channel</option>{activeUgxChannels.map((c) => <option key={c.id} value={c.id}>{c.name} · {c.channel_type}</option>)}</select></label>}<div className="inline-message">Selected line {selectedReturnLine ? `${selectedReturnLine.variant_name || selectedReturnLine.sku || short(selectedReturnLine.sale_line_id)} · ${money(selectedReturnLine.line_total)}` : "not selected"}</div><button className="primary" type="submit">Complete return</button></form>
              <div className="workflow-list">{returns.length ? returns.map((r) => <div className="workflow-row" key={r.id}><div><strong>{short(r.id)} · Sale {short(r.sale_id)}</strong><small>{r.status} · {r.reason}</small></div><span>{money(r.total)}</span><span className="status neutral">Refund {money(r.refunded)}</span></div>) : <div className="empty-inline">No returns recorded yet.</div>}</div>
            </div>
          )}

          {tab === "Sales History" && <div className="workflow-list">{sales.map((s) => <div className="workflow-row" key={s.id}><div><strong>{s.customer_name || "Walk-in"}</strong><small>{short(s.id)} · {s.status} · {new Date(s.created_at).toLocaleString()}</small></div><span>{money(s.total)}</span><span className={Number(s.amount_due) > 0 ? "status warn" : "status good"}>{Number(s.amount_due) > 0 ? `Due ${money(s.amount_due)}` : "PAID"}</span></div>)}</div>}
        </div>
      </section>
    </main>
  );
}
