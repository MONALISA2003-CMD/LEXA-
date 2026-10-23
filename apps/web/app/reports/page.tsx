"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getAnalyticsOverview,
  getAnalyticsProducts,
  getAnalyticsCustomers,
  getAnalyticsInventoryHealth,
  getAnalyticsInventoryValueByLocation,
  getAnalyticsBranches,
  getAnalyticsPaymentsByChannel,
  getBusinessProfile,
  refreshAnalytics,
  getExpenses,
  type AnalyticsOverview,
  type AnalyticsProductMetric,
  type AnalyticsCustomerMetric,
  type AnalyticsInventoryHealth,
  type AnalyticsInventoryLocationValue,
  type AnalyticsBranchMetric,
  type AnalyticsPaymentMethodMetric,
  type ExpenseRecord,
  userFacingError,
} from "../../lib/api";
import { AppShell } from "../../components/app-shell";
import { SalesTrendChart, ProductPerformanceBars, ExpenseCategoryBars, PaymentMethodBars, StockValueByLocationBars, CustomerBalanceBars, BranchPerformanceBars } from "../../components/dashboard-charts";
import { localDateISO, localMonthStartISO } from "../../lib/date.mjs";
import { toCsv } from "../../lib/report-export.mjs";

function today() { return localDateISO(); }
function monthStart() { return localMonthStartISO(); }
function shiftDate(value: string, offsetDays: number) {
  const date = new Date(`${value}T12:00:00`);
  date.setDate(date.getDate() + offsetDays);
  return localDateISO(date);
}
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
  const [inventoryLocationValues, setInventoryLocationValues] = useState<PanelResult<AnalyticsInventoryLocationValue[]>>({ data: null, error: null });
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
    setInventory(initialPanel()); setInventoryLocationValues(initialPanel()); setBranches(initialPanel()); setExpenses(initialPanel()); setPaymentMethods(initialPanel());
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
        getAnalyticsInventoryValueByLocation(),
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
      setInventoryLocationValues(asPanel(requests[4]));
      setBranches(asPanel(requests[5]));
      setExpenses(asPanel(requests[6]));
      setPaymentMethods(asPanel(requests[7]));
      const errors = requests.filter((r) => r.status === "rejected").length;
      if (errors) setMessage(`${errors} report panel${errors === 1 ? " is" : "s are"} unavailable. Other successfully loaded panels remain visible.`);
    } catch (error) {
      const description = userFacingError(error, "Your reports could not be loaded. Check your connection and try again.");
      setMessage(description);
      setOverview(initialPanel()); setProducts(initialPanel()); setCustomers(initialPanel());
      setInventory(initialPanel()); setInventoryLocationValues(initialPanel()); setBranches(initialPanel()); setExpenses(initialPanel()); setPaymentMethods(initialPanel());
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
    ["Receipts after refunds and expenses", overviewData?.totals.net_cash_movement],
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
    return [...totals.entries()].map(([label, value]) => ({ label, value, detail: "Recorded and posted expenses", href: "/accounting?tab=Expenses" })).sort((a, b) => b.value - a.value);
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
    return [...grouped.values()].sort((a,b)=>b.value-a.value).slice(0,8).map(row=>({...row,detail:`${row.units.toLocaleString("en-UG",{maximumFractionDigits:2})} units · left after product cost ${showMoney(row.margin)}`,href:`/products?q=${encodeURIComponent(row.label)}`}));
  })();
  const periodPaymentMethods = (paymentMethods.data || []).filter(row => row.currency_code === currencyCode).map(row => ({
    label: row.channel_name || "Not specified",
    value: Number(row.recorded_amount),
    detail: `${row.payment_count} recorded payment${row.payment_count === 1 ? "" : "s"}`,
    href: `/sales?view=history&start_date=${(appliedRange || {from,to}).from}&end_date=${(appliedRange || {from,to}).to}${row.channel_id ? `&payment_channel_id=${encodeURIComponent(row.channel_id)}` : ""}`,
  }));
  const branchBars = (() => {
    const grouped = new Map<string, { label: string; value: number; payments: number }>();
    for (const row of branches.data || []) {
      const key = row.branch_id || row.branch_name || "location";
      const current = grouped.get(key) || { label: row.branch_name || "Location", value: 0, payments: 0 };
      current.value += Number(row.net_sales) || 0;
      current.payments += Number(row.payments_collected) || 0;
      grouped.set(key, current);
    }
    const range = appliedRange || { from, to };
    return [...grouped.entries()].map(([id, row]) => ({ ...row, detail: `Money recorded ${showMoney(row.payments)}`, href: `/sales?view=history&start_date=${range.from}&end_date=${range.to}&branch_id=${encodeURIComponent(id)}` }));
  })();
  const customerBalanceBars = (customers.data || []).map(row => ({
    label: row.customer_name || "Customer",
    value: Number(row.outstanding_balance),
    detail: `Last sale ${row.last_sale_date || "not available"}`,
    href: `/customers?customer_id=${encodeURIComponent(row.customer_party_id)}`,
  }));
;

  function choosePreset(preset: "today" | "7days" | "30days" | "month" | "90days") {
    const end = today();
    const start = preset === "today" ? end
      : preset === "7days" ? shiftDate(end, -6)
      : preset === "30days" ? shiftDate(end, -29)
      : preset === "90days" ? shiftDate(end, -89)
      : monthStart();
    setFrom(start); setTo(end);
    void load(start, end);
  }

  const reportSectionsAvailable = [overview.data, products.data, customers.data, inventory.data, inventoryLocationValues.data, branches.data, expenses.data, paymentMethods.data].some(value => value !== null);
  function downloadReportCsv() {
    if (!reportSectionsAvailable) {
      setMessage("Load at least one report section before downloading. Unavailable information has not been treated as zero.");
      return;
    }
    const range = appliedRange || { from, to };
    const rows: unknown[][] = [];
    const add = (section: string, date: string, name: string, category = "", status = "", count: number | string = "", quantity: number | string = "", sales: number | string = "", recorded: number | string = "", owed: number | string = "", returnsOrExpenses: number | string = "", stockValue: number | string = "", productCost: number | string = "", profit: number | string = "", currency = currencyCode || "", reference = "", scope = `${range.from} to ${range.to}`) => rows.push([section, scope, date, name, category, status, count, quantity, sales, recorded, owed, returnsOrExpenses, stockValue, productCost, profit, currency, reference]);
    const state = (panel: PanelResult<unknown>, label: string, scope = `${range.from} to ${range.to}`) => {
      const empty = Array.isArray(panel.data) && panel.data.length === 0;
      add("Report availability", "", label, "", panel.error ? "Unavailable" : panel.data === null ? "Not loaded" : empty ? "No records" : "Loaded", "", "", "", "", "", "", "", "", "", currencyCode || "", panel.error || (empty ? "No records in this section" : ""), scope);
    };
    if (overview.data) overview.data.daily.forEach(row => add("Daily sales", row.business_date, "Sales and money recorded", "", "Recorded", row.sale_count, "", row.net_sales, row.payments_collected, "", `Returns ${row.returns_total}; refunds ${row.refunds_total}; recorded expenses ${row.expenses_total}; net recorded movement ${row.net_cash_movement}`, "", "", "", row.currency_code));
    if (branches.data) branches.data.forEach(row => add("Sales by location", row.business_date, row.branch_name || "Branch", "Location", "Recorded", row.sale_count, "", row.net_sales, row.payments_collected, "", row.returns_total, "", "", "", row.currency_code, row.branch_id));
    if (paymentMethods.data) paymentMethods.data.filter(row => row.currency_code === currencyCode).forEach(row => add("Money recorded by payment method", `${range.from} to ${range.to}`, row.channel_name || "Not specified", row.channel_type, "Recorded entries only", row.payment_count, "", "", row.recorded_amount, "", "", "", "", "", row.currency_code, row.channel_id || ""));
    if (expenses.data) periodExpenses.forEach(row => add("Expenses", row.expense_date, row.description, row.expense_account_name || "Other expenses", row.status, "", "", "", "", "", row.total, "", "", "", row.currency_code, row.reference || row.id));
    if (products.data) products.data.forEach(row => add("Product performance", row.business_date, [row.product_name, row.variant_name].filter(Boolean).join(" · ") || row.sku || "Product", row.sku || "", "Recorded", "", row.units_sold, row.net_sales, "", "", row.returns_amount, "", row.cogs, row.gross_margin, row.currency_code, row.variant_id));
    if (customers.data) customers.data.forEach(row => add("Customer balances", row.last_sale_date || "All dates", row.customer_name || "Customer", "Customer", "Current balance", row.sale_count, "", row.net_sales, row.total_paid, row.outstanding_balance, row.total_returns, "", "", "", currencyCode || "", row.customer_party_id, "All dates (current customer balance)"));
    if (inventory.data) inventory.data.forEach(row => add("Current stock", row.snapshot_date, [row.product_name, row.variant_name].filter(Boolean).join(" · ") || row.sku || "Product", row.location_name || "Stock location", "Current snapshot", "", row.available, "", "", "", "", row.stock_value, "", "", currencyCode || "", row.variant_id, "Current snapshot (not date-filtered)"));
    if (inventoryLocationValues.data) inventoryLocationValues.data.forEach(row => add("Stock value by location", row.snapshot_date, row.location_name || "Stock location", "Stock location", "Current snapshot", row.product_count, "", "", "", "", "", row.stock_value, "", "", currencyCode || "", row.location_id, "Current snapshot (not date-filtered)"));
    state(overview, "Sales and money recorded"); state(products, "Product performance"); state(customers, "Customer balances", "All dates (current balances)"); state(inventory, "Current stock details", "Current snapshot (not date-filtered)"); state(inventoryLocationValues, "Stock value by location", "Current snapshot (not date-filtered)"); state(branches, "Sales by location"); state(expenses, "Expenses"); state(paymentMethods, "Money by payment method");
    const csv = toCsv(["Section", "Report period / scope", "Business date / snapshot", "Name / description", "Category / method / location", "Status / note", "Count", "Quantity", "Sales after returns", "Money recorded", "Amount owed", "Returns / expenses / other movement", "Stock value", "Product cost", "Profit after product cost", "Currency", "Record reference"], rows);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = `lexa-business-reports-${range.from}-to-${range.to}.csv`;
    document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
    const unavailableCount = [overview, products, customers, inventory, inventoryLocationValues, branches, expenses, paymentMethods].filter(panel => panel.error || panel.data === null).length;
    setMessage(unavailableCount ? `Report downloaded. ${unavailableCount} section(s) were unavailable; check the Report availability rows in the file.` : "Report downloaded with the selected period and current business records.");
  }

  return <AppShell title="Business reports" eyebrow="See how your business is doing">
    <main className="workspace" style={{ maxWidth: 1500 }}>
      <div className="workspace-header">
        <div><span className="workspace-breadcrumb">LEXA · BUSINESS REPORTS</span><h1>Business reports</h1><p>See sales, money received, customer balances, stock and how your business is doing.</p></div>
        <div className="header-actions"><Link className="button button-soft" href="/">Home</Link><button className="button button-soft" onClick={downloadReportCsv} disabled={!reportSectionsAvailable || busy}>Download report (CSV)</button><button className="button button-soft" onClick={() => void load(from, to)} disabled={busy}>Reload figures</button></div>
      </div>
      {message && <div className="inline-message" role="status">{message}</div>}
      <section className="workspace-section">
        <div className="section-head"><div><span className="section-label">DATE RANGE</span><h2>Choose a date range</h2><p>Amounts use the currency saved in your business details.</p></div><div className="header-actions"><button className="button button-soft" onClick={() => void load(from, to)} disabled={busy || !from || !to || from > to}>Show these dates</button><button className="primary" onClick={() => void rebuild()} disabled={busy || rebuilding || !from || !to || from > to}>{rebuilding ? "Refreshing…" : "Refresh reports"}</button></div></div>
        <div className="report-period-presets" role="group" aria-label="Common reporting periods">
          <button type="button" className="button button-soft" onClick={() => choosePreset("today")} disabled={busy}>Today</button>
          <button type="button" className="button button-soft" onClick={() => choosePreset("7days")} disabled={busy}>Last 7 days</button>
          <button type="button" className="button button-soft" onClick={() => choosePreset("30days")} disabled={busy}>Last 30 days</button>
          <button type="button" className="button button-soft" onClick={() => choosePreset("month")} disabled={busy}>This month</button>
          <button type="button" className="button button-soft" onClick={() => choosePreset("90days")} disabled={busy}>Last 90 days</button>
        </div>
        <div className="form-grid"><label>From<input aria-label="Report start date" type="date" value={from} max={to || undefined} onChange={(event) => setFrom(event.target.value)} /></label><label>To<input aria-label="Report end date" type="date" value={to} min={from || undefined} onChange={(event) => setTo(event.target.value)} /></label></div>
        <p className="muted">{appliedRange ? `Showing ${appliedRange.from} through ${appliedRange.to}${currencyCode ? ` · ${currencyCode}` : ""}.` : "Select a period and apply it to load reports."}</p>
      </section>
      {overview.error && <div className="notice notice-error">Sales summary could not be loaded. Try refreshing reports.</div>}
      <div className="stat-grid">{kpis.map(([label, value]) => <section className="stat-card" key={label}><span>{label}</span><strong>{busy ? "Loading…" : overviewData ? (hasPeriodRows ? showMoney(value) : "No records") : "Unavailable"}</strong><small>{busy ? "Loading saved figures…" : overviewData ? `${overviewData.totals.sale_count} completed sales in this period` : "Saved figures could not be checked"}</small></section>)}</div>
      <div className="two-column">
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">DAY BY DAY</span><h2>Sales and money recorded</h2><p>Receipts after recorded refunds and expenses are not the same as the cash left in a till or a bank balance.</p></div></div>{busy ? <p className="empty-inline" role="status">Loading sales trend…</p> : overview.error ? <p className="empty-inline">This chart is unavailable right now. Try refreshing reports.</p> : <><SalesTrendChart daily={overviewData?.daily || []} startDate={overviewData?.from_date || from} endDate={overviewData?.to_date || to} currencyCode={currencyCode}/><div className="table-wrap"><table><thead><tr><th>Date</th><th>Sales after returns</th><th>Money recorded</th><th>Receipts after refunds and expenses</th></tr></thead><tbody>{overviewData?.daily.map((row) => <tr key={row.business_date}><td><Link href={`/sales?view=history&start_date=${row.business_date}&end_date=${row.business_date}`}>{row.business_date}</Link></td><td>{showMoney(row.net_sales)}</td><td>{showMoney(row.payments_collected)}</td><td>{showMoney(row.net_cash_movement)}</td></tr>)}{overviewData && !overviewData.daily.length && <tr><td colSpan={4}>No sales were recorded during these dates.</td></tr>}</tbody></table></div></>}</section>
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">BUSINESS LOCATIONS</span><h2>Sales by location</h2><p>Selected date range.</p></div></div>{busy ? <p className="empty-inline" role="status">Loading sales by location…</p> : branches.error ? <p className="empty-inline">This information could not be loaded. Check your business setup and try again.</p> : <><BranchPerformanceBars rows={branchBars} currencyCode={currencyCode}/><div className="table-wrap"><table><thead><tr><th>Branch</th><th>Sales after returns</th><th>Money recorded</th></tr></thead><tbody>{branches.data?.map((row) => <tr key={`${row.branch_id}-${row.business_date}`}><td><Link href={`/sales?view=history&start_date=${row.business_date}&end_date=${row.business_date}&branch_id=${encodeURIComponent(row.branch_id)}`}><b>{row.branch_name || "Branch"}</b></Link><small>{row.business_date}</small></td><td>{showMoney(row.net_sales)}</td><td>{showMoney(row.payments_collected)}</td></tr>)}{branches.data && !branches.data.length && <tr><td colSpan={3}>No location sales were recorded during these dates.</td></tr>}</tbody></table></div></>}</section>
      </div>
      <section className="workspace-section"><div className="section-head"><div><span className="section-label">RECORDED PAYMENTS</span><h2>Money recorded by payment method</h2><p>Customer payments entered in LEXA for the selected dates and business currency. These figures are recorded entries, not confirmation from a bank or mobile-money provider.</p></div></div>{busy ? <p className="empty-inline" role="status">Loading recorded payment totals…</p> : paymentMethods.error ? <p className="empty-inline">Payment-method totals could not be loaded. Try refreshing reports.</p> : <><PaymentMethodBars rows={periodPaymentMethods} currencyCode={currencyCode}/><div className="table-wrap"><table><thead><tr><th>Payment method</th><th>Recorded payments</th><th>Money recorded</th></tr></thead><tbody>{(paymentMethods.data || []).filter(row => row.currency_code === currencyCode).map(row => <tr key={`${row.channel_id || row.channel_name}-${row.currency_code}`}><td><Link href={`/sales?view=history&start_date=${(appliedRange || {from,to}).from}&end_date=${(appliedRange || {from,to}).to}${row.channel_id ? `&payment_channel_id=${encodeURIComponent(row.channel_id)}` : ""}`}>{row.channel_name || "Not specified"}</Link></td><td>{row.payment_count}</td><td>{showMoney(Number(row.recorded_amount))}</td></tr>)}{paymentMethods.data && !periodPaymentMethods.length && <tr><td colSpan={3}>No customer payments were recorded in this period.</td></tr>}</tbody></table></div></>}</section>
      <section className="workspace-section"><div className="section-head"><div><span className="section-label">EXPENSES</span><h2>Expenses by category</h2><p>Only recorded expenses in the selected dates and business currency are included.</p></div></div>{busy ? <p className="empty-inline" role="status">Loading recorded expenses…</p> : expenses.error ? <p className="empty-inline">Expense information could not be loaded. Try refreshing reports.</p> : <><ExpenseCategoryBars rows={expensesByCategory} currencyCode={currencyCode}/><div className="table-wrap"><table><thead><tr><th>Date</th><th>Expense</th><th>Category</th><th>Payment method</th><th>Amount</th></tr></thead><tbody>{periodExpenses.sort((a, b) => b.expense_date.localeCompare(a.expense_date)).map(row => <tr key={row.id}><td>{row.expense_date}</td><td><Link href={`/accounting?tab=Expenses&expense_id=${encodeURIComponent(row.id)}`}><b>{row.description}</b></Link><small>{row.reference || "No reference added"}</small></td><td>{row.expense_account_name}</td><td>{row.payment_channel_name || "Not specified"}</td><td>{showMoney(Number(row.total))}</td></tr>)}{expenses.data && !periodExpenses.length && <tr><td colSpan={5}>No posted expenses were recorded in this period.</td></tr>}</tbody></table></div></>}</section>
      <section className="workspace-section"><div className="section-head"><div><span className="section-label">PRODUCTS</span><h2>Best-selling products</h2><p>Ranked by sales after returns. This is before rent, wages and other running costs.</p></div></div>{busy ? <p className="empty-inline" role="status">Loading product results…</p> : products.error ? <p className="empty-inline">Product results are unavailable right now. Try refreshing reports.</p> : <><ProductPerformanceBars rows={productBars} currencyCode={currencyCode}/><div className="table-wrap"><table><thead><tr><th>Product</th><th>Units</th><th>Sales after returns</th><th>Product cost</th><th>Profit after product cost</th></tr></thead><tbody>{products.data?.map((row, index) => <tr key={`${row.variant_id}-${row.business_date}-${index}`}><td><Link href={`/products?q=${encodeURIComponent(row.sku || row.product_name || "")}`}><b>{row.product_name || "Product"}</b></Link><small>{row.variant_name || row.sku || ""}</small></td><td>{Number(row.units_sold).toLocaleString()}</td><td>{showMoney(row.net_sales)}</td><td>{showMoney(row.cogs)}</td><td>{showMoney(row.gross_margin)}</td></tr>)}{products.data && !products.data.length && <tr><td colSpan={5}>No product sales were recorded during these dates.</td></tr>}</tbody></table></div></>}</section>
      <div className="two-column">
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">CUSTOMER HISTORY</span><h2>Customer balances and activity</h2><p>Customer history covers all dates, not just the selected period.</p></div></div>{busy ? <p className="empty-inline" role="status">Loading customer balances…</p> : customers.error ? <p className="empty-inline">This information could not be loaded. Check your business setup and try again.</p> : <><CustomerBalanceBars rows={customerBalanceBars} currencyCode={currencyCode}/><div className="table-wrap"><table><thead><tr><th>Customer</th><th>Sales after returns</th><th>Outstanding</th></tr></thead><tbody>{customers.data?.map((row) => <tr key={row.customer_party_id}><td><Link href={`/customers?customer_id=${encodeURIComponent(row.customer_party_id)}`}>{row.customer_name || "Customer"}</Link><small>Last sale {row.last_sale_date || "—"}</small></td><td>{showMoney(row.net_sales)}</td><td>{showMoney(row.outstanding_balance)}</td></tr>)}{customers.data && !customers.data.length && <tr><td colSpan={3}>No customer sales records are available yet.</td></tr>}</tbody></table></div></>}</section>
      <section className="workspace-section"><div className="section-head"><div><span className="section-label">STOCK VALUE</span><h2>Stock value by location</h2><p>Current stock-cost snapshot. This is not sales revenue or cash.</p></div></div>{busy ? <p className="empty-inline" role="status">Loading stock value by location…</p> : inventoryLocationValues.error ? <p className="empty-inline">Stock value by location could not be loaded. Try refreshing reports.</p> : <><StockValueByLocationBars rows={(inventoryLocationValues.data || []).map(row => ({label:row.location_name || "Stock location",value:Number(row.stock_value),detail:`${row.product_count} product records · snapshot ${row.snapshot_date}`,href:`/inventory?tab=Stock&location_id=${encodeURIComponent(row.location_id)}`}))} currencyCode={currencyCode}/><div className="table-wrap"><table><thead><tr><th>Stock location</th><th>Stock value</th><th>Product records</th><th>Snapshot date</th></tr></thead><tbody>{inventoryLocationValues.data?.map(row => <tr key={row.location_id}><td><Link href={`/inventory?tab=Stock&location_id=${encodeURIComponent(row.location_id)}`}>{row.location_name || "Stock location"}</Link></td><td>{showMoney(row.stock_value)}</td><td>{row.product_count}</td><td>{row.snapshot_date}</td></tr>)}{inventoryLocationValues.data && !inventoryLocationValues.data.length && <tr><td colSpan={4}>Stock value by location is not available yet.</td></tr>}</tbody></table></div></>}</section>
      </div>
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">CURRENT STOCK</span><h2>Stock on hand</h2><p>Shows current stock, not stock as it was on the selected dates.</p></div></div>{busy ? <p className="empty-inline" role="status">Loading current stock…</p> : inventory.error ? <p className="empty-inline">This information could not be loaded. Check your business setup and try again.</p> : <div className="table-wrap"><table><thead><tr><th>Product</th><th>Available</th><th>Value</th><th>Estimated days of stock</th></tr></thead><tbody>{inventory.data?.map((row) => <tr key={`${row.location_id}-${row.variant_id}`}><td><b>{row.product_name || "Product"}</b><small>{row.location_name || "Location"}</small></td><td>{Number(row.available).toLocaleString()}</td><td>{showMoney(row.stock_value)}</td><td>{row.days_cover !== null && row.days_cover !== undefined ? Number(row.days_cover).toFixed(1) : "Not enough sales history"}</td></tr>)}{inventory.data && !inventory.data.length && <tr><td colSpan={4}>Stock information is not available yet.</td></tr>}</tbody></table></div>}</section>
    </main>
  </AppShell>;
}
