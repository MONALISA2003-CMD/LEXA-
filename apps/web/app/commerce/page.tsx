"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { usePathname } from "next/navigation";
import { AppShell } from "../../components/app-shell";
import { localDateISO } from "../../lib/date.mjs";
import {
  closeReconciliation,
  createCommerceCustomer,
  createCommerceSale,
  createPaymentChannel,
  createReconciliation,
  createSaleReturn,
  getCommerceCustomers,
  getCommerceDashboard,
  getCommerceProducts,
  getCommerceSale,
  getCommerceSales,
  getBranches,
  getLocations,
  getPaymentChannels,
  getReconciliations,
  getReceivables,
  getSaleReturns,
  payReceivable,
  resolveReconciliationLine,
  setReconciliationActual,
  type CommerceCustomer,
  type CommerceDashboard,
  type CommerceProduct,
  type CommerceSale,
  type CommerceSaleDetail,
  type Branch,
  type Location,
  type PaymentChannel,
  type Receivable,
  type Reconciliation,
  type ReconciliationLine,
  type SaleReturn,
} from "../../lib/api";

function money(v: string | number, currencyCode = "UGX") {
  try {
    return new Intl.NumberFormat("en-UG", { style: "currency", currency: currencyCode, maximumFractionDigits: 0 }).format(Number(v));
  } catch {
    return `${currencyCode} ${Number(v).toLocaleString("en-UG", { maximumFractionDigits: 0 })}`;
  }
}

function today() { return localDateISO(); }

function short(v: string) {
  return `${v.slice(0, 8)}…`;
}

type PaymentRow = { channelId: string; amount: string };
type CartLine = { id:string; variantId:string; quantity:string; unitPrice:string };
type CheckoutAttempt = { fingerprint:string; key:string };

export default function CommercePage() {
  const pathname = usePathname();
  const [tab, setTab] = useState(pathname === "/customers" ? "Customers" : "Sell");
  const [busy, setBusy] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<CommerceDashboard | null>(null);
  const [customers, setCustomers] = useState<CommerceCustomer[]>([]);
  const [channels, setChannels] = useState<PaymentChannel[]>([]);
  const [products, setProducts] = useState<CommerceProduct[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [sales, setSales] = useState<CommerceSale[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [receivables, setReceivables] = useState<Receivable[]>([]);
  const [reconciliations, setReconciliations] = useState<Reconciliation[]>([]);
  const [returns, setReturns] = useState<SaleReturn[]>([]);

  const [customerId, setCustomerId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [variantId, setVariantId] = useState("");
  const [qty, setQty] = useState("1");
  const [price, setPrice] = useState("0");
  const [saleDate, setSaleDate] = useState(today());
  const [paymentRows, setPaymentRows] = useState<PaymentRow[]>([{ channelId: "", amount: "0" }]);
  const [cart, setCart] = useState<CartLine[]>([]);
  const [productSearch, setProductSearch] = useState("");
  const [submittingSale, setSubmittingSale] = useState(false);
  const [lastCheckoutAttempt, setLastCheckoutAttempt] = useState<CheckoutAttempt | null>(null);
  const [salesSearch, setSalesSearch] = useState("");
  const [salesStatus, setSalesStatus] = useState("");
  const [salesStartDate, setSalesStartDate] = useState("");
  const [salesEndDate, setSalesEndDate] = useState("");
  const [salesBranchId, setSalesBranchId] = useState("");
  const [salesHistory, setSalesHistory] = useState<CommerceSale[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedSaleDetail, setSelectedSaleDetail] = useState<CommerceSaleDetail | null>(null);
  const [saleDetailLoading, setSaleDetailLoading] = useState(false);

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

  const selectedProduct = useMemo(() => products.find((x) => x.variant_id === variantId), [products, variantId]);
  const filteredProducts = useMemo(() => {
    const q = productSearch.trim().toLowerCase();
    if (!q) return products;
    return products.filter((x) => `${x.product_name} ${x.variant_name} ${x.sku}`.toLowerCase().includes(q));
  }, [products, productSearch]);
  const cartTotal = useMemo(() => cart.reduce((sum, line) => sum + Math.max(0, Number(line.quantity) || 0) * Math.max(0, Number(line.unitPrice) || 0), 0), [cart]);
  const selectedReconData = useMemo(() => reconciliations.find((x) => x.id === selectedRecon), [reconciliations, selectedRecon]);
  const currencyCode = dashboard?.currency_code || channels.find((x) => x.active)?.currency_code || "UGX";
  const moneyInWorkspace = (value: string | number) => money(value, currencyCode);
  const activeCurrencyChannels = useMemo(() => channels.filter((x) => x.active && x.currency_code === currencyCode), [channels, currencyCode]);
  const selectedReturnLine = useMemo(() => returnSale?.lines.find((x) => x.sale_line_id === returnLineId), [returnSale, returnLineId]);

  async function refresh() {
    setBusy(true);
    try {
      const [d, c, ch, p, l, s, r, re, rr] = await Promise.all([
        getCommerceDashboard(),
        getCommerceCustomers(),
        getPaymentChannels(),
        getCommerceProducts(),
        getLocations(),
        getCommerceSales(),
        getReceivables(),
        getReconciliations(),
        getSaleReturns(),
      ]);
      setDashboard(d);
      setCustomers(c);
      setChannels(ch);
      setProducts(p);
      setLocations(l);
      setSales(s);
      setSalesHistory(s);
      setReceivables(r);
      setReconciliations(re);
      setReturns(rr);
      // Branch selection is an optional reporting aid. Sales-role members may not
      // have organization.read; the server still enforces assigned-branch scope.
      void getBranches().then(setBranches).catch(() => setBranches([]));
      if (!locationId && l[0]) setLocationId(l[0].id);
      const usableChannels = ch.filter((x) => x.active && x.currency_code === currencyCode);
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

  useEffect(() => {
    if (pathname === "/customers") setTab("Customers");
    else if (pathname === "/sales") setTab("Sell");
  }, [pathname]);

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
      await createPaymentChannel({ name: channelName, channel_type: channelType, provider: provider || undefined, currency_code: currencyCode });
      setChannelName("");
      setProvider("");
      setMessage("Payment channel created.");
      await refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not create payment channel");
    }
  }

  function addCartLine() {
    if (!selectedProduct) { setMessage("Choose a product first."); return; }
    const quantity = Number(qty);
    const unitPrice = Number(price);
    if (!Number.isFinite(quantity) || quantity <= 0) { setMessage("Quantity must be greater than zero."); return; }
    if (!Number.isFinite(unitPrice) || unitPrice < 0) { setMessage("Selling price cannot be negative."); return; }
    setCart((current) => {
      const existing = current.find((line) => line.variantId === selectedProduct.variant_id && Number(line.unitPrice) === unitPrice);
      if (existing) return current.map((line) => line.id === existing.id ? { ...line, quantity: String((Number(line.quantity) || 0) + quantity) } : line);
      return [...current, { id: crypto.randomUUID(), variantId: selectedProduct.variant_id, quantity: String(quantity), unitPrice: String(unitPrice) }];
    });
    setMessage(`${selectedProduct.product_name} added to cart.`);
  }

  async function runSalesSearch() {
    if (salesStartDate && salesEndDate && salesStartDate > salesEndDate) {
      setMessage("Sales start date must be on or before end date.");
      return;
    }
    setHistoryLoading(true);
    setMessage(null);
    try {
      const result = await getCommerceSales({
        limit: 200,
        search: salesSearch,
        status: salesStatus,
        start_date: salesStartDate,
        end_date: salesEndDate,
        branch_id: salesBranchId,
      });
      setSalesHistory(result);
      setSelectedSaleDetail(null);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not load sales history");
    } finally {
      setHistoryLoading(false);
    }
  }

  async function openSaleDetail(id: string) {
    setSaleDetailLoading(true);
    try {
      const detail = await getCommerceSale(id);
      setSelectedSaleDetail(detail);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not load sale details");
    } finally {
      setSaleDetailLoading(false);
    }
  }

  async function submitSale(e: FormEvent) {
    e.preventDefault();
    if (submittingSale) return;
    try {
      if (!locationId || cart.length === 0) throw new Error("Select a location and add at least one cart item.");
      const payments = paymentRows
        .filter((x) => Number(x.amount) > 0)
        .map((x) => ({ payment_channel_id: x.channelId, amount: x.amount }));
      if (payments.some((x) => !x.payment_channel_id)) throw new Error("Select a payment channel for every payment amount.");
      const paid = payments.reduce((sum, x) => sum + Number(x.amount), 0);
      if (paid > cartTotal + 0.0001) throw new Error("Payments cannot exceed the checkout total.");
      if (paid < cartTotal - 0.0001 && !customerId) throw new Error("Select a customer to record an outstanding balance.");
      const body = {
        customer_party_id: customerId || null,
        location_id: locationId,
        currency_code: currencyCode,
        business_date: saleDate,
        lines: cart.map((line) => ({ variant_id: line.variantId, quantity: line.quantity, unit_price: line.unitPrice })),
        payments,
      };
      const fingerprint = JSON.stringify(body);
      const attempt = lastCheckoutAttempt?.fingerprint === fingerprint
        ? lastCheckoutAttempt
        : { fingerprint, key: crypto.randomUUID() };
      setLastCheckoutAttempt(attempt);
      setSubmittingSale(true);
      const created = await createCommerceSale(body, attempt.key);
      setMessage(`Sale ${short(created.id)} completed for ${moneyInWorkspace(created.total)}.`);
      setLastCheckoutAttempt(null);
      setCart([]);
      setPaymentRows([{ channelId: activeCurrencyChannels[0]?.id || "", amount: "0" }]);
      setSelectedSaleDetail(await getCommerceSale(created.id));
      await refresh();
    } catch (e) {
      // Keep the same idempotency key and unchanged payload on retry so a lost
      // response cannot accidentally create a second sale.
      setMessage(e instanceof Error ? e.message : "Could not complete sale. Check the status before retrying.");
    } finally {
      setSubmittingSale(false);
    }
  }

  async function submitReceivablePayment(id: string) {
    const amount = window.prompt(`Amount received (${currencyCode})`);
    if (!amount) return;
    const ch = paymentRows[0]?.channelId || activeCurrencyChannels[0]?.id;
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
      setMessage(`Return ${short(result.id)} completed for ${moneyInWorkspace(result.total)}.`);
      await refresh();
      await loadReturnSale(returnSale.id);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not process return");
    }
  }

  function updateCartLine(id:string, field:"quantity"|"unitPrice", value:string) {
    setCart((current) => current.map((line) => line.id === id ? { ...line, [field]: value } : line));
    setLastCheckoutAttempt(null);
  }

  function removeCartLine(id:string) {
    setCart((current) => current.filter((line) => line.id !== id));
    setLastCheckoutAttempt(null);
  }

  const totalPreview = cartTotal;

  const pageTitle = pathname === "/customers" ? "Customers" : "Sales & Commerce";
  const pageEyebrow = pathname === "/customers" ? "CUSTOMER RELATIONSHIPS" : "SALES OPERATIONS";

  return (
    <AppShell title={pageTitle} eyebrow={pageEyebrow}>
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
          <div className="stat-card"><span>TODAY SALES</span><strong>{moneyInWorkspace(dashboard.sales.sales)}</strong><small>Completed sales</small></div>
          <div className="stat-card"><span>COLLECTED</span><strong>{moneyInWorkspace(dashboard.sales.collected)}</strong><small>Recorded payments</small></div>
          <div className="stat-card"><span>CREDIT</span><strong>{moneyInWorkspace(dashboard.sales.credit)}</strong><small>Outstanding from sales</small></div>
          <div className="stat-card"><span>RECEIVABLES</span><strong>{moneyInWorkspace(dashboard.outstanding_receivables)}</strong><small>Open customer balance</small></div>
        </div>
      )}

      <section className="section inventory-section">
        <div className="inventory-tabs">
          {["Sell", "Customers", "Payment Channels", "Receivables", "Reconciliation", "Returns", "Sales History"].map((x) => (
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
                <label>Search product / SKU<input value={productSearch} onChange={(e) => setProductSearch(e.target.value)} placeholder="Search name or SKU…" autoComplete="off" /></label>
                <label>Product<select value={variantId} onChange={(e) => { setVariantId(e.target.value); const p = products.find((x) => x.variant_id === e.target.value); if (p) setPrice(p.selling_price || "0"); }} required><option value="">Select product</option>{filteredProducts.map((p) => <option key={p.variant_id} value={p.variant_id}>{p.product_name} · {p.sku}</option>)}</select><small>{filteredProducts.length} matching products</small></label>
                <div className="form-grid"><label>Quantity<input type="number" min="0.001" step="0.001" value={qty} onChange={(e) => setQty(e.target.value)} required /></label><label>Selling price<input type="number" min="0" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} required /><small>Cashiers use the catalogue price. Price overrides require manager pricing permission.</small></label></div>
                <button className="secondary" type="button" onClick={addCartLine}>Add item to cart</button>
                <section className="workflow-list" aria-label="Checkout cart">
                  <div className="eyebrow">CART · {cart.length} LINE{cart.length === 1 ? "" : "S"}</div>
                  {cart.length === 0 ? <div className="empty-inline">Search for a product and add it to start a sale.</div> : cart.map((line) => {
                    const product = products.find((item) => item.variant_id === line.variantId);
                    return <div className="workflow-row cart-line" key={line.id}>
                      <div><strong>{product?.product_name || "Product"}</strong><small>{product?.sku || "SKU unavailable"}</small></div>
                      <label>Qty<input aria-label={`Quantity ${product?.product_name || "product"}`} type="number" min="0.001" step="0.001" value={line.quantity} onChange={(e) => updateCartLine(line.id,"quantity",e.target.value)} required /></label>
                      <label>Unit price<input aria-label={`Unit price ${product?.product_name || "product"}`} type="number" min="0" step="0.01" value={line.unitPrice} onChange={(e) => updateCartLine(line.id,"unitPrice",e.target.value)} required /></label>
                      <strong>{moneyInWorkspace((Number(line.quantity)||0)*(Number(line.unitPrice)||0))}</strong>
                      <button type="button" className="secondary" onClick={() => removeCartLine(line.id)} aria-label={`Remove ${product?.product_name || "item"}`}>Remove</button>
                    </div>;
                  })}
                  <div className="inline-message">Checkout subtotal · {moneyInWorkspace(totalPreview)}. Taxes and any applicable charges are calculated by the server.</div>
                </section>
                <div className="workflow-list">
                  <div className="eyebrow">PAYMENT ALLOCATIONS</div>
                  {paymentRows.map((row, index) => (
                    <div className="workflow-row" key={`${index}-${row.channelId}`}>
                      <select value={row.channelId} onChange={(e) => updatePayment(index, "channelId", e.target.value)}>
                        <option value="">No payment</option>
                        {activeCurrencyChannels.map((c) => <option key={c.id} value={c.id}>{c.name} · {c.channel_type}</option>)}
                      </select>
                      <input type="number" min="0" step="0.01" value={row.amount} onChange={(e) => updatePayment(index, "amount", e.target.value)} aria-label={`Payment ${index + 1} amount`} />
                      {paymentRows.length > 1 && <button type="button" className="secondary" onClick={() => setPaymentRows((rows) => rows.filter((_, i) => i !== index))}>Remove</button>}
                    </div>
                  ))}
                  <button type="button" className="secondary" onClick={() => setPaymentRows((rows) => [...rows, { channelId: activeCurrencyChannels[0]?.id || "", amount: "0" }])}>Add another payment</button>
                </div>
                <div className="inline-message">{selectedProduct ? `${selectedProduct.product_name} · ${selectedProduct.sku}` : "Choose a product"} · Cart total {moneyInWorkspace(totalPreview)}</div>
                <button className="primary" type="submit" disabled={submittingSale || cart.length === 0}>{submittingSale ? "Completing sale…" : `Complete sale · ${moneyInWorkspace(totalPreview)}`}</button>
              </form>
              <div className="workflow-list"><p className="eyebrow">PAYMENT CHANNELS</p>{channels.length ? channels.map((c) => <div className="workflow-row" key={c.id}><div><strong>{c.name}</strong><small>{c.channel_type} · {c.provider || "Business configured"} · {c.currency_code}</small></div><span className="status good">READY</span></div>) : <div className="empty-inline">No payment channels configured yet.</div>}</div>
            </div>
          )}

          {tab === "Customers" && (
            <div className="split-panel">
              <form className="command-form" onSubmit={submitCustomer}><div><p className="eyebrow">CUSTOMER</p><h3>Add a customer</h3><p>Customer records do not require bank or mobile-money credentials.</p></div><label>Display name<input value={customerName} onChange={(e) => setCustomerName(e.target.value)} required /></label><label>Phone<input value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} /></label><button className="primary">Save customer</button></form>
              <div className="workflow-list">{customers.map((c) => <div className="workflow-row" key={c.party_id}><div><strong>{c.display_name}</strong><small>{c.phone || c.email || "No contact"}</small></div><span className="status neutral">{c.status}</span><span>{moneyInWorkspace(c.credit_limit)}</span></div>)}</div>
            </div>
          )}

          {tab === "Payment Channels" && (
            <div className="split-panel">
              <form className="command-form" onSubmit={submitChannel}><div><p className="eyebrow">PAYMENT CHANNEL</p><h3>Configure where money is received</h3><p>No account numbers, PINs, OTPs, passwords, API keys or access tokens are stored here.</p></div><label>Name<input value={channelName} onChange={(e) => setChannelName(e.target.value)} placeholder="MTN Line 2" required /></label><div className="form-grid"><label>Type<select value={channelType} onChange={(e) => setChannelType(e.target.value)}><option>CASH</option><option>MOBILE_MONEY</option><option>BANK</option><option>CARD</option><option>CHEQUE</option><option>OTHER</option></select></label><label>Provider<input value={provider} onChange={(e) => setProvider(e.target.value)} placeholder="MTN" /></label></div><button className="primary">Save channel</button></form>
              <div className="workflow-list">{channels.map((c) => <div className="workflow-row" key={c.id}><div><strong>{c.name}</strong><small>{c.channel_type} · {c.provider || ""} · {c.currency_code}</small></div><span className={c.active ? "status good" : "status neutral"}>{c.active ? "ACTIVE" : "INACTIVE"}</span></div>)}</div>
            </div>
          )}

          {tab === "Receivables" && <div className="workflow-list">{receivables.length ? receivables.map((r) => <div className="workflow-row" key={r.id}><div><strong>{r.customer_name}</strong><small>Sale {short(r.sale_id)} · {r.status}</small></div><span>{moneyInWorkspace(r.balance)}</span><button className="secondary" onClick={() => void submitReceivablePayment(r.id)}>Record payment</button></div>) : <div className="empty-inline">No open receivables.</div>}</div>}

          {tab === "Reconciliation" && (
            <div className="split-panel">
              <div className="command-form"><div><p className="eyebrow">DAILY CLOSING</p><h3>Reconcile the business day</h3><p>LEXA calculates expected settlement from recorded payments and refunds. You enter the actual amount seen or counted.</p></div><button className="primary" onClick={() => void startRecon()}>Open today</button>{reconciliations.length > 0 && <label>Business day<select value={selectedRecon} onChange={(e) => setSelectedRecon(e.target.value)}>{reconciliations.map((r) => <option key={r.id} value={r.id}>{r.business_date} · {r.status}</option>)}</select></label>}{selectedReconData && <button className="button-dark" onClick={() => void closeRecon()} disabled={selectedReconData.status === "CLOSED"}>Close business day</button>}</div>
              <div className="workflow-list">{selectedReconData?.lines.length ? selectedReconData.lines.map((line) => <div className="workflow-row" key={line.line_id}><div><strong>{line.channel_name}</strong><small>Expected {moneyInWorkspace(line.expected_amount)} · {line.line_status}{line.variance ? ` · Variance ${moneyInWorkspace(line.variance)}` : ""}</small></div><div><input className="recon-input" value={actuals[line.line_id] ?? line.actual_amount ?? ""} onChange={(e) => setActuals((s) => ({ ...s, [line.line_id]: e.target.value }))} placeholder="Actual" /></div><button className="secondary" onClick={() => void saveActual(line)}>Save</button>{Number(line.variance || 0) !== 0 && line.line_status !== "ACKNOWLEDGED" && <button className="secondary" onClick={() => void acknowledgeLine(line)}>Acknowledge</button>}</div>) : <div className="empty-inline">Open a business day. Active payment channels will appear here.</div>}</div>
            </div>
          )}

          {tab === "Returns" && (
            <div className="split-panel">
              <form className="command-form" onSubmit={submitReturn}><div><p className="eyebrow">RETURNS</p><h3>Record a sale return</h3><p>LEXA restores stock, reduces the sale value and records a refund or customer credit without deleting the original sale.</p></div><label>Completed sale<select value={returnSaleId} onChange={(e) => void loadReturnSale(e.target.value)} required><option value="">Select sale</option>{sales.filter((s) => s.status === "COMPLETED").map((s) => <option key={s.id} value={s.id}>{short(s.id)} · {s.customer_name || "Walk-in"} · {moneyInWorkspace(s.total)}</option>)}</select></label><label>Sale line<select value={returnLineId} onChange={(e) => setReturnLineId(e.target.value)} required><option value="">Select line</option>{returnSale?.lines.map((line) => <option key={line.sale_line_id} value={line.sale_line_id}>{line.variant_name || line.sku || short(line.sale_line_id)} · Qty {line.quantity}</option>)}</select></label><div className="form-grid"><label>Quantity<input type="number" min="0.001" step="0.001" value={returnQty} onChange={(e) => setReturnQty(e.target.value)} required /></label><label>Reason<input value={returnReason} onChange={(e) => setReturnReason(e.target.value)} required placeholder="Customer return" /></label></div><label>Settlement<select value={returnSettlement} onChange={(e) => setReturnSettlement(e.target.value as "NONE" | "REFUND" | "CUSTOMER_CREDIT")}><option value="NONE">No immediate settlement</option><option value="REFUND">Refund</option><option value="CUSTOMER_CREDIT" disabled={!returnSale?.customer_party_id}>Customer credit</option></select></label>{returnSettlement === "REFUND" && <label>Refund channel<select value={refundChannelId} onChange={(e) => setRefundChannelId(e.target.value)} required><option value="">Select refund channel</option>{activeCurrencyChannels.map((c) => <option key={c.id} value={c.id}>{c.name} · {c.channel_type}</option>)}</select></label>}<div className="inline-message">Selected line {selectedReturnLine ? `${selectedReturnLine.variant_name || selectedReturnLine.sku || short(selectedReturnLine.sale_line_id)} · ${moneyInWorkspace(selectedReturnLine.line_total)}` : "not selected"}</div><button className="primary" type="submit">Complete return</button></form>
              <div className="workflow-list">{returns.length ? returns.map((r) => <div className="workflow-row" key={r.id}><div><strong>{short(r.id)} · Sale {short(r.sale_id)}</strong><small>{r.status} · {r.reason}</small></div><span>{moneyInWorkspace(r.total)}</span><span className="status neutral">Refund {moneyInWorkspace(r.refunded)}</span><small>{r.journal_entry_id ? `Journal ${short(r.journal_entry_id)}` : "Journal pending"}{r.fiscal_document_id ? ` · Credit note ${r.fiscal_document_status || "PENDING"}` : ""}</small></div>) : <div className="empty-inline">No returns recorded yet.</div>}</div>
            </div>
          )}

          {tab === "Sales History" && <div className="sales-history-workspace">
            <form className="sales-history-filters" onSubmit={(e) => { e.preventDefault(); void runSalesSearch(); }}>
              <label>Search customer or sale reference<input value={salesSearch} onChange={(e) => setSalesSearch(e.target.value)} placeholder="Customer, sale ID or transaction ID" /></label>
              <label>Status<select value={salesStatus} onChange={(e) => setSalesStatus(e.target.value)}><option value="">All statuses</option><option value="COMPLETED">Completed</option><option value="DRAFT">Draft</option><option value="VOIDED">Voided</option></select></label>
              {branches.length > 0 && <label>Branch<select value={salesBranchId} onChange={(e) => setSalesBranchId(e.target.value)}><option value="">All accessible branches</option>{branches.map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}</select></label>}
              <label>From<input type="date" value={salesStartDate} onChange={(e) => setSalesStartDate(e.target.value)} /></label>
              <label>To<input type="date" value={salesEndDate} onChange={(e) => setSalesEndDate(e.target.value)} /></label>
              <button className="secondary" type="submit" disabled={historyLoading}>{historyLoading ? "Searching…" : "Apply filters"}</button>
              <button className="secondary" type="button" onClick={() => { setSalesSearch(""); setSalesStatus(""); setSalesStartDate(""); setSalesEndDate(""); setSalesBranchId(""); setTimeout(() => void getCommerceSales({limit:200}).then(setSalesHistory).catch((e) => setMessage(e instanceof Error ? e.message : "Could not refresh history")),0); }} disabled={historyLoading}>Clear</button>
            </form>
            <div className="workflow-list">{salesHistory.length ? salesHistory.map((s) => <div className="workflow-row sale-history-row" key={s.id}><div><strong>{s.customer_name || "Walk-in"}</strong><small>{short(s.id)} · {s.status} · {new Date(s.created_at).toLocaleString()}</small></div><span>{moneyInWorkspace(s.total)}</span><span className={Number(s.amount_due) > 0 ? "status warn" : "status good"}>{Number(s.amount_due) > 0 ? `Due ${moneyInWorkspace(s.amount_due)}` : "PAID"}</span><button className="secondary" type="button" onClick={() => void openSaleDetail(s.id)}>View sale</button></div>) : <div className="empty-inline">No sales match these filters.</div>}</div>
            {saleDetailLoading && <div className="inline-message" role="status">Loading sale details…</div>}
            {selectedSaleDetail && <section className="sale-detail-panel" aria-label="Sale details"><div className="panel-head"><div><p className="eyebrow">SALE DETAIL</p><h3>{short(selectedSaleDetail.id)} · {selectedSaleDetail.status}</h3><p>{selectedSaleDetail.customer_name || "Walk-in customer"} · {new Date(selectedSaleDetail.created_at).toLocaleString()}</p></div><button className="secondary" type="button" onClick={() => window.print()}>Print details</button></div><div className="table-wrap"><table><thead><tr><th scope="col">Item</th><th scope="col">Qty</th><th scope="col">Unit price</th><th scope="col">Discount</th><th scope="col">Line total</th></tr></thead><tbody>{selectedSaleDetail.lines.map((line) => <tr key={line.sale_line_id}><td>{line.variant_name || line.sku || short(line.sale_line_id)}<small>{line.sku || ""}</small></td><td>{Number(line.quantity).toLocaleString()}</td><td>{moneyInWorkspace(line.unit_price)}</td><td>{moneyInWorkspace(line.discount_amount)}</td><td>{moneyInWorkspace(line.line_total)}</td></tr>)}</tbody></table></div><div className="sale-detail-totals"><span>Subtotal <strong>{moneyInWorkspace(selectedSaleDetail.subtotal)}</strong></span><span>Discounts <strong>{moneyInWorkspace(selectedSaleDetail.discount_total)}</strong></span><span>Tax <strong>{moneyInWorkspace(selectedSaleDetail.tax_total)}</strong></span><span>Total <strong>{moneyInWorkspace(selectedSaleDetail.total)}</strong></span><span>Collected <strong>{moneyInWorkspace(selectedSaleDetail.amount_paid)}</strong></span><span>Outstanding <strong>{moneyInWorkspace(selectedSaleDetail.amount_due)}</strong></span></div><div className="sale-audit-ledger"><section className="sale-audit-section" aria-label="Sale payment ledger"><h4>Payment ledger</h4>{(selectedSaleDetail.payments || []).length ? (selectedSaleDetail.payments || []).map((payment) => <div className="workflow-row" key={payment.id}><div><strong>{payment.channel_name || payment.method}</strong><small>{payment.allocation_type} · {payment.business_date}{payment.reference ? ` · ${payment.reference}` : ""}</small></div><span>{moneyInWorkspace(payment.allocated_amount)}</span><span className="status good">{payment.status}</span></div>) : <p className="muted">No recorded payment allocations.</p>}</section><section className="sale-audit-section" aria-label="Sale returns and refunds"><h4>Returns and refunds</h4>{(selectedSaleDetail.returns || []).length ? (selectedSaleDetail.returns || []).map((item) => <div className="workflow-row" key={item.id}><div><strong>{item.reason}</strong><small>{item.status} · {short(item.id)}</small></div><span>{moneyInWorkspace(item.total)}</span><small>Refunded {moneyInWorkspace(item.refunded)} · Credit balance {moneyInWorkspace(item.credit_balance)}</small></div>) : <p className="muted">No returns recorded.</p>}{(selectedSaleDetail.refunds || []).length > 0 && <div className="refund-ledger">{(selectedSaleDetail.refunds || []).map((refund) => <div className="workflow-row" key={refund.id}><div><strong>{refund.channel_name || "Refund channel"}</strong><small>{refund.business_date}{refund.reference ? ` · ${refund.reference}` : ""} · {refund.status}</small></div><span>{moneyInWorkspace(refund.amount)}</span></div>)}</div>}</section></div><section className="sale-audit-section" aria-label="Accounting and fiscal ledger"><h4>Accounting and fiscal trail</h4>{(selectedSaleDetail.accounting_entries || []).length ? (selectedSaleDetail.accounting_entries || []).map((entry) => <div className="workflow-row" key={entry.id}><div><strong>{entry.entry_role.replaceAll("_", " ")}</strong><small>{entry.entry_date} · {entry.description} · {short(entry.id)}</small></div><span className="status good">{entry.status}</span></div>) : <p className="muted">No accounting entries are linked to this sale yet.</p>}{(selectedSaleDetail.returns || []).some((item) => item.fiscal_document_id) && <p className="muted">EFRIS credit notes are queued only when this workspace has an active EFRIS configuration; a queued note is not yet an accepted fiscal document.</p>}</section><p className="muted">Gross profit is not calculated on this receipt; sale total is not the same as net profit.</p></section>}
          </div>}
        </div>
      </section>
      </main>
    </AppShell>
  );
}
