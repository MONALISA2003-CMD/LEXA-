"use client";

import { useEffect, useState } from "react";
import {
  getAnalyticsOverview,
  getAnalyticsProducts,
  getAnalyticsCustomers,
  getAnalyticsInventoryHealth,
  getAnalyticsBranches,
  getAnalyticsPaymentsByChannel,
  getBusinessProfile,
  refreshAnalytics,
  getExpenses,
  type AnalyticsOverview,
  type AnalyticsProductMetric,
  type AnalyticsCustomerMetric,
  type AnalyticsInventoryHealth,
  type AnalyticsBranchMetric,
  type AnalyticsPaymentMethodMetric,
  type ExpenseRecord,
  userFacingError,
} from "../../lib/api";
import { AppShell } from "../../components/app-shell";
import { SalesTrendChart, ProductPerformanceBars, ExpenseCategoryBars, PaymentMethodBars } from "../../components/dashboard-charts";
import { localDateISO, localMonthStartISO } from "../../lib/date.mjs";

function today() { return localDateISO(); }
function monthStart() { return localMonthStartISO(); }
function money(value: string | number, currencyCode: string) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "Unavailable";
  try {
    return new Intl.NumberFormat("en-UG", {
      style: "currency", currency: currencyCode, maximumFractionDigits: 0,
    }).format(numeric);
  } catch {
    return `${currencyCode} ${numeric.toLocaleString("en-UG", { maximumFractionDigits: 0 })}`;
  }
}

type Range = { from: string; to: string };
type PanelResult<T> = { data: T | null; error: string | null };
const initialPanel = <T,>(): PanelResult<T> => ({ data: null, error: null });

export default function ReportsPage() {
  const [from, setFrom] = useState(monthStart());
  const [to, setTo] = useState(today());
  const [appliedRange, setAppliedRange] = useState<Range | null>(null);
  const [currencyCode, setCurrencyCode] = useState<string | null>(null);
  const [overview, setOverview] = useState<PanelResult<AnalyticsOverview>>({ data: null, error: null });
  const [products, setProducts] = useState<PanelResult<AnalyticsProductMetric[]>>({ data: null, error: null });
  const [customers, setCustomers] = useState<PanelResult<AnalyticsCustomerMetric[]>>({ data: null, error: null });
  const [inventory, setInventory] = useState<PanelResult<AnalyticsInventoryHealth[]>>({ data: null, error: null });
  const [branches, setBranches] = useState<PanelResult<AnalyticsBranchMetric[]>>({ data: null, error: null });
  const [expenses, setExpenses] = useState<PanelResult<ExpenseRecord[]>>({ data: null, error: null });
  const [paymentMethods, setPaymentMethods] = useState<PanelResult<AnalyticsPaymentMethodMetric[]>>({ data: null, error: null });
  const [busy, setBusy] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [message, setMessage] = useState("");

  async function load(nextFrom: string, nextTo: string) {
    if (!nextFrom || !nextTo) {
      setMessage("Choose both the start and end dates.");
      return;
    }
    if (nextFrom > nextTo) {
      setMessage("The start date must be on or before the end date.");
      return;
    }
    setBusy(true);
    setMessage("");
    setAppliedRange({ from: nextFrom, to: nextTo });
    setCurrencyCode(null);
    setOverview(initialPanel()); setProducts(initialPanel()); setCustomers(initialPanel());
    setInventory(initialPanel()); setBranches(initialPanel()); setExpenses(initialPanel()); setPaymentMethods(initialPanel());
    try {
      const profile = await getBusinessProfile();
      const verifiedCurrency = profile?.currency_code?.trim().toUpperCase();
      if (!verifiedCurrency || !/^[A-Z]{3}$/.test(verifiedCurrency)) {
        setCurrencyCode(null);
        throw new Error("Your business currency is not set. Save it in Business details before opening money reports.");
      }
      setCurrencyCode(verifiedCurrency);
      const requests = await Promise.allSettled([
        getAnalyticsOverview(nextFrom, nextTo, verifiedCurrency),
        getAnalyticsProducts(nextFrom, nextTo, verifiedCurrency),
        getAnalyticsCustomers(),
        getAnalyticsInventoryHealth(),
        getAnalyticsBranches(nextFrom, nextTo, verifiedCurrency),
        getExpenses(),
        getAnalyticsPaymentsByChannel(nextFrom, nextTo, verifiedCurrency),
      ] as const);
      const asPanel = <T,>(result: PromiseSettledResult<T>): PanelResult<T> => result.status === "fulfilled"
        ? { data: result.value, error: null }
        : { data: null, error: userFacingError(result.reason, "This report could not be loaded. Check your access or try again.") };
      setOverview(asPanel(requests[0]));
      setProducts(asPanel(requests[1]));
      setCustomers(asPanel(requests[2]));
      setInventory(asPanel(requests[3]));
      setBranches(asPanel(requests[4]));
      setExpenses(asPanel(requests[5]));
      setPaymentMethods(asPanel(requests[6]));
      const errors = requests.filter((r) => r.status === "rejected").length;
      if (errors) setMessage(`${errors} report panel${errors === 1 ? " is" : "s are"} unavailable. Other successfully loaded panels remain visible.`);
    } catch (error) {
      const description = userFacingError(error, "Your reports could not be loaded. Check your connection and try again.");
      setMessage(description);
      setOverview(initialPanel()); setProducts(initialPanel()); setCustomers(initialPanel());
      setInventory(initialPanel()); setBranches(initialPanel()); setExpenses(initialPanel()); setPaymentMethods(initialPanel());
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(monthStart(), today()); }, []);

  async function rebuild() {
    if (!from || !to || from > to) {
      setMessage("Choose a valid date range before refreshing reports.");
      return;
    }
    setRebuilding(true);
    setMessage("");
    try {
      await refreshAnalytics(from, to);
      await load(from, to);
      setMessage((current) => current ? `${current} Report refresh completed.` : "Reports refreshed from your saved transactions.");
    } catch (error) {
      setMessage(userFacingError(error, "Reports could not be refreshed for these dates. Try again."));
    } finally {
      setRebuilding(false);
    }
  }

  const overviewData = overview.data;
  const hasPeriodRows = Boolean(overviewData && overviewData.daily.length > 0);
  const kpis: Array<[string, string | number | undefined]> = [
    ["Sales after returns", overviewData?.totals.net_sales],
    ["Money recorded", overviewData?.totals.payments_collected],
    ["Credit given", overviewData?.totals.credit_created],
    ["Money in and out", overviewData?.totals.net_cash_movement],
  ];
  const showMoney = (value: string | number | undefined) => currencyCode && value !== undefined
    ? money(value, currencyCode) : "Unavailable";
  const periodExpenses = (expenses.data || []).filter(row =>
    row.status === "POSTED" && row.currency_code === currencyCode && row.expense_date >= (appliedRange?.from || from) && row.expense_date <= (appliedRange?.to || to)
  );
  const expensesByCategory = (() => {
    const totals = new Map<string, number>();
    for (const row of periodExpenses) {
      const category = row.expense_account_name || "Other expenses";
      totals.set(category, (totals.get(category) || 0) + (Number(row.total) || 0));
    }
    return [...totals.entries()].map(([label, value]) => ({ label, value, detail: "Recorded and posted expenses" })).sort((a, b) => b.value - a.value);
  })();
  const productBars = (() => {
    const grouped = new Map<string, {label:string;value:number;units:number;margin:number}>();
    for (const row of products.data || []) {
      const key = row.variant_id || row.product_name || row.sku || "product";
      const prior = grouped.get(key) || {label:[row.product_name,row.variant_name].filter(Boolean).join(" · ") || row.sku || "Product",value:0,units:0,margin:0};
      prior.value += Number(row.net_sales) || 0;
      prior.units += Number(row.units_sold) || 0;
      prior.margin += Number(row.gross_margin) || 0;
      grouped.set(key, prior);
    }
    return [...grouped.values()].sort((a,b)=>b.value-a.value).slice(0,8).map(row=>({...row,detail:`${row.units.toLocaleString("en-UG",{maximumFractionDigits:2})} units · left after product cost ${showMoney(row.margin)}`}));
  })();

  return <AppShell title="Business reports" eyebrow="See how your business is doing">
    <main className="workspace" style={{ maxWidth: 1500 }}>
      <div className="workspace-header">
        <div><span className="workspace-breadcrumb">LEXA · BUSINESS REPORTS</span><h1>Business reports</h1><p>See sales, money received, customer balances, stock and how your business is doing.</p></div>
        <div className="header-actions"><a className="button button-soft" href="/">Back</a><button className="button button-soft" onClick={() => void load(from, to)} disabled={busy}>Refresh</button></div>
      </div>
      {message && <div className="inline-message" role="status">{message}</div>}
      <section className="workspace-section">
        <div className="section-head"><div><span className="section-label">DATE RANGE</span><h2>Choose a date range</h2><p>Amounts use the currency saved in your business details.</p></div><div className="header-actions"><button className="button button-soft" onClick={() => void load(from, to)} disabled={busy || !from || !to || from > to}>Show these dates</button><button className="primary" onClick={() => void rebuild()} disabled={busy || rebuilding || !from || !to || from > to}>{rebuilding ? "Refreshing…" : "Refresh reports"}</button></div></div>
        <div className="form-grid"><label>From<input type="date" value={from} max={to || undefined} onChange={(event) => setFrom(event.target.value)} /></label><label>To<input type="date" value={to} min={from || undefined} onChange={(event) => setTo(event.target.value)} /></label></div>
        <p className="muted">{appliedRange ? `Showing ${appliedRange.from} through ${appliedRange.to}${currencyCode ? ` · ${currencyCode}` : ""}.` : "Select a period and apply it to load reports."}</p>
      </section>
      {overview.error && <div className="notice notice-error">Sales summary could not be loaded. Try refreshing reports.</div>}
      <div className="stat-grid">{kpis.map(([label, value]) => <section className="stat-card" key={label}><span>{label}</span><strong>{busy ? "Loading…" : overviewData ? (hasPeriodRows ? showMoney(value) : "No records") : "Unavailable"}</strong><small>{busy ? "Loading saved figures…" : overviewData ? `${overviewData.totals.sale_count} completed sales in this period` : "Saved figures could not be checked"}</small></section>)}</div>
      <div className="two-column">
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">DAY BY DAY</span><h2>Sales and money recorded</h2><p>Receipts after recorded refunds and expenses are not the same as the cash left in a till or a bank balance.</p></div></div>{busy ? <p className="empty-inline" role="status">Loading sales trend…</p> : overview.error ? <p className="empty-inline">This chart is unavailable right now. Try refreshing reports.</p> : <><SalesTrendChart daily={overviewData?.daily || []} startDate={overviewData?.from_date || from} endDate={overviewData?.to_date || to} currencyCode={currencyCode}/><div className="table-wrap"><table><thead><tr><th>Date</th><th>Sales after returns</th><th>Money recorded</th><th>Receipts after refunds and expenses</th></tr></thead><tbody>{overviewData?.daily.map((row) => <tr key={row.business_date}><td>{row.business_date}</td><td>{showMoney(row.net_sales)}</td><td>{showMoney(row.payments_collected)}</td><td>{showMoney(row.net_cash_movement)}</td></tr>)}{overviewData && !overviewData.daily.length && <tr><td colSpan={4}>No sales were recorded during these dates.</td></tr>}</tbody></table></div></>}</section>
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">BUSINESS LOCATIONS</span><h2>Sales by location</h2><p>Selected date range.</p></div></div>{busy ? <p className="empty-inline" role="status">Loading sales by location…</p> : branches.error ? <p className="empty-inline">This information could not be loaded. Check your business setup and try again.</p> : <div className="table-wrap"><table><thead><tr><th>Branch</th><th>Sales after returns</th><th>Money recorded</th></tr></thead><tbody>{branches.data?.map((row) => <tr key={`${row.branch_id}-${row.business_date}`}><td><b>{row.branch_name || "Branch"}</b><small>{row.business_date}</small></td><td>{showMoney(row.net_sales)}</td><td>{showMoney(row.payments_collected)}</td></tr>)}{branches.data && !branches.data.length && <tr><td colSpan={3}>No location sales were recorded during these dates.</td></tr>}</tbody></table></div>}</section>
      </div>
      <section className="workspace-section"><div className="section-head"><div><span className="section-label">RECORDED PAYMENTS</span><h2>Money recorded by payment method</h2><p>Customer payments entered in LEXA for the selected dates and business currency. These figures are recorded entries, not confirmation from a bank or mobile-money provider.</p></div></div>{busy ? <p className="empty-inline" role="status">Loading recorded payment totals…</p> : paymentMethods.error ? <p className="empty-inline">Payment-method totals could not be loaded. Try refreshing reports.</p> : <><PaymentMethodBars rows={periodPaymentMethods} currencyCode={currencyCode}/><div className="table-wrap"><table><thead><tr><th>Payment method</th><th>Recorded payments</th><th>Money recorded</th></tr></thead><tbody>{(paymentMethods.data || []).filter(row => row.currency_code === currencyCode).map(row => <tr key={`${row.channel_id || row.channel_name}-${row.currency_code}`}><td>{row.channel_name || "Not specified"}</td><td>{row.payment_count}</td><td>{showMoney(Number(row.recorded_amount))}</td></tr>)}{paymentMethods.data && !periodPaymentMethods.length && <tr><td colSpan={3}>No customer payments were recorded in this period.</td></tr>}</tbody></table></div></>}</section>
      <section className="workspace-section"><div className="section-head"><div><span className="section-label">EXPENSES</span><h2>Expenses by category</h2><p>Only recorded expenses in the selected dates and business currency are included.</p></div></div>{busy ? <p className="empty-inline" role="status">Loading recorded expenses…</p> : expenses.error ? <p className="empty-inline">Expense information could not be loaded. Try refreshing reports.</p> : <><ExpenseCategoryBars rows={expensesByCategory} currencyCode={currencyCode}/><div className="table-wrap"><table><thead><tr><th>Date</th><th>Expense</th><th>Category</th><th>Payment method</th><th>Amount</th></tr></thead><tbody>{periodExpenses.sort((a, b) => b.expense_date.localeCompare(a.expense_date)).map(row => <tr key={row.id}><td>{row.expense_date}</td><td><b>{row.description}</b><small>{row.reference || "No reference added"}</small></td><td>{row.expense_account_name}</td><td>{row.payment_channel_name || "Not specified"}</td><td>{showMoney(Number(row.total))}</td></tr>)}{expenses.data && !periodExpenses.length && <tr><td colSpan={5}>No posted expenses were recorded in this period.</td></tr>}</tbody></table></div></>}</section>
      <section className="workspace-section"><div className="section-head"><div><span className="section-label">PRODUCTS</span><h2>Best-selling products</h2><p>Ranked by sales after returns. This is before rent, wages and other running costs.</p></div></div>{busy ? <p className="empty-inline" role="status">Loading product results…</p> : products.error ? <p className="empty-inline">Product results are unavailable right now. Try refreshing reports.</p> : <><ProductPerformanceBars rows={productBars} currencyCode={currencyCode}/><div className="table-wrap"><table><thead><tr><th>Product</th><th>Units</th><th>Sales after returns</th><th>Product cost</th><th>Profit after product cost</th></tr></thead><tbody>{products.data?.map((row, index) => <tr key={`${row.variant_id}-${row.business_date}-${index}`}><td><b>{row.product_name || "Product"}</b><small>{row.variant_name || row.sku || ""}</small></td><td>{Number(row.units_sold).toLocaleString()}</td><td>{showMoney(row.net_sales)}</td><td>{showMoney(row.cogs)}</td><td>{showMoney(row.gross_margin)}</td></tr>)}{products.data && !products.data.length && <tr><td colSpan={5}>No product sales were recorded during these dates.</td></tr>}</tbody></table></div></>}</section>
      <div className="two-column">
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">CUSTOMER HISTORY</span><h2>Customer balances and activity</h2><p>Customer history covers all dates, not just the selected period.</p></div></div>{busy ? <p className="empty-inline" role="status">Loading customer balances…</p> : customers.error ? <p className="empty-inline">This information could not be loaded. Check your business setup and try again.</p> : <div className="table-wrap"><table><thead><tr><th>Customer</th><th>Sales after returns</th><th>Outstanding</th></tr></thead><tbody>{customers.data?.map((row) => <tr key={row.customer_party_id}><td>{row.customer_name || "Customer"}<small>Last sale {row.last_sale_date || "—"}</small></td><td>{showMoney(row.net_sales)}</td><td>{showMoney(row.outstanding_balance)}</td></tr>)}{customers.data && !customers.data.length && <tr><td colSpan={3}>No customer sales records are available yet.</td></tr>}</tbody></table></div>}</section>
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">STOCK</span><h2>Stock on hand</h2><p>Shows current stock, not stock as it was on the selected dates.</p></div></div>{busy ? <p className="empty-inline" role="status">Loading current stock…</p> : inventory.error ? <p className="empty-inline">This information could not be loaded. Check your business setup and try again.</p> : <div className="table-wrap"><table><thead><tr><th>Product</th><th>Available</th><th>Value</th><th>Estimated days of stock</th></tr></thead><tbody>{inventory.data?.map((row) => <tr key={`${row.location_id}-${row.variant_id}`}><td><b>{row.product_name || "Product"}</b><small>{row.location_name || "Location"}</small></td><td>{Number(row.available).toLocaleString()}</td><td>{showMoney(row.stock_value)}</td><td>{row.days_cover !== null && row.days_cover !== undefined ? Number(row.days_cover).toFixed(1) : "Not enough sales history"}</td></tr>)}{inventory.data && !inventory.data.length && <tr><td colSpan={4}>Stock information is not available yet.</td></tr>}</tbody></table></div>}</section>
      </div>
    </main>
  </AppShell>;
}
