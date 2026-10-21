"use client";

import { useEffect, useState } from "react";
import {
  getAnalyticsOverview,
  getAnalyticsProducts,
  getAnalyticsCustomers,
  getAnalyticsInventoryHealth,
  getAnalyticsBranches,
  getBusinessProfile,
  refreshAnalytics,
  type AnalyticsOverview,
  type AnalyticsProductMetric,
  type AnalyticsCustomerMetric,
  type AnalyticsInventoryHealth,
  type AnalyticsBranchMetric,
} from "../../lib/api";
import { AppShell } from "../../components/app-shell";
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
    try {
      const profile = await getBusinessProfile();
      const verifiedCurrency = profile?.currency_code?.trim().toUpperCase();
      if (!verifiedCurrency || !/^[A-Z]{3}$/.test(verifiedCurrency)) {
        setCurrencyCode(null);
        throw new Error("Workspace currency is unavailable. Configure the business profile before using monetary reports.");
      }
      setCurrencyCode(verifiedCurrency);
      setAppliedRange({ from: nextFrom, to: nextTo });
      const requests = await Promise.allSettled([
        getAnalyticsOverview(nextFrom, nextTo, verifiedCurrency),
        getAnalyticsProducts(nextFrom, nextTo, verifiedCurrency),
        getAnalyticsCustomers(),
        getAnalyticsInventoryHealth(),
        getAnalyticsBranches(nextFrom, nextTo, verifiedCurrency),
      ] as const);
      const asPanel = <T,>(result: PromiseSettledResult<T>): PanelResult<T> => result.status === "fulfilled"
        ? { data: result.value, error: null }
        : { data: null, error: result.reason instanceof Error ? result.reason.message : "This report could not be loaded." };
      setOverview(asPanel(requests[0]));
      setProducts(asPanel(requests[1]));
      setCustomers(asPanel(requests[2]));
      setInventory(asPanel(requests[3]));
      setBranches(asPanel(requests[4]));
      const errors = requests.filter((r) => r.status === "rejected").length;
      if (errors) setMessage(`${errors} report panel${errors === 1 ? " is" : "s are"} unavailable. Other successfully loaded panels remain visible.`);
    } catch (error) {
      const description = error instanceof Error ? error.message : "Workspace reports could not be loaded.";
      setMessage(description);
      setOverview(initialPanel()); setProducts(initialPanel()); setCustomers(initialPanel());
      setInventory(initialPanel()); setBranches(initialPanel());
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(monthStart(), today()); }, []);

  async function rebuild() {
    if (!from || !to || from > to) {
      setMessage("Choose a valid reporting period before rebuilding analytics.");
      return;
    }
    setRebuilding(true);
    setMessage("");
    try {
      await refreshAnalytics(from, to);
      await load(from, to);
      setMessage((current) => current ? `${current} Analytics refresh completed.` : "Analytics refreshed from authoritative transactions.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to refresh analytics for the selected period.");
    } finally {
      setRebuilding(false);
    }
  }

  const overviewData = overview.data;
  const hasPeriodRows = Boolean(overviewData && overviewData.daily.length > 0);
  const kpis: Array<[string, string | number | undefined]> = [
    ["Net sales", overviewData?.totals.net_sales],
    ["Collected", overviewData?.totals.payments_collected],
    ["Credit created", overviewData?.totals.credit_created],
    ["Net cash movement", overviewData?.totals.net_cash_movement],
  ];
  const showMoney = (value: string | number | undefined) => currencyCode && value !== undefined
    ? money(value, currencyCode) : "Unavailable";

  return <AppShell title="Reports & Business Intelligence" eyebrow="Reports">
    <main className="workspace" style={{ maxWidth: 1500 }}>
      <div className="workspace-header">
        <div><span className="workspace-breadcrumb">LEXA · BUSINESS INTELLIGENCE</span><h1>Reports & Business Intelligence</h1><p>Deterministic business reporting built from sales, payments, inventory and accounting truth.</p></div>
        <div className="header-actions"><a className="button button-soft" href="/">Back</a><button className="button button-soft" onClick={() => void load(from, to)} disabled={busy}>Refresh</button></div>
      </div>
      {message && <div className="inline-message" role="status">{message}</div>}
      <section className="workspace-section">
        <div className="section-head"><div><span className="section-label">REPORTING WINDOW</span><h2>Performance period</h2><p>Monetary reports use the currency configured in the workspace business profile.</p></div><div className="header-actions"><button className="button button-soft" onClick={() => void load(from, to)} disabled={busy || !from || !to || from > to}>Apply period</button><button className="primary" onClick={() => void rebuild()} disabled={busy || rebuilding || !from || !to || from > to}>{rebuilding ? "Rebuilding…" : "Rebuild analytics"}</button></div></div>
        <div className="form-grid"><label>From<input type="date" value={from} max={to || undefined} onChange={(event) => setFrom(event.target.value)} /></label><label>To<input type="date" value={to} min={from || undefined} onChange={(event) => setTo(event.target.value)} /></label></div>
        <p className="muted">{appliedRange ? `Showing ${appliedRange.from} through ${appliedRange.to}${currencyCode ? ` · ${currencyCode}` : ""}.` : "Select a period and apply it to load reports."}</p>
      </section>
      {overview.error && <div className="notice notice-error">Performance summary unavailable: {overview.error}</div>}
      <div className="stat-grid">{kpis.map(([label, value]) => <section className="stat-card" key={label}><span>{label}</span><strong>{busy ? "Loading…" : overviewData ? (hasPeriodRows ? showMoney(value) : "No records") : "Unavailable"}</strong><small>{overviewData ? `${overviewData.totals.sale_count} completed sales in window` : "Source data was not confirmed"}</small></section>)}</div>
      <div className="two-column">
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">DAILY TREND</span><h2>Sales and cash movement</h2></div></div>{overview.error ? <p className="empty-inline">Unavailable until the performance summary loads.</p> : <div className="table-wrap"><table><thead><tr><th>Date</th><th>Net sales</th><th>Collected</th><th>Net cash</th></tr></thead><tbody>{overviewData?.daily.map((row) => <tr key={row.business_date}><td>{row.business_date}</td><td>{showMoney(row.net_sales)}</td><td>{showMoney(row.payments_collected)}</td><td>{showMoney(row.net_cash_movement)}</td></tr>)}{overviewData && !overviewData.daily.length && <tr><td colSpan={4}>No records for the selected reporting period.</td></tr>}</tbody></table></div>}</section>
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">BRANCHES</span><h2>Branch performance</h2><p>Selected reporting period.</p></div></div>{branches.error ? <p className="empty-inline">Unavailable: {branches.error}</p> : <div className="table-wrap"><table><thead><tr><th>Branch</th><th>Net sales</th><th>Collected</th></tr></thead><tbody>{branches.data?.map((row) => <tr key={`${row.branch_id}-${row.business_date}`}><td><b>{row.branch_name || "Branch"}</b><small>{row.business_date}</small></td><td>{showMoney(row.net_sales)}</td><td>{showMoney(row.payments_collected)}</td></tr>)}{branches.data && !branches.data.length && <tr><td colSpan={3}>No branch records for the selected period.</td></tr>}</tbody></table></div>}</section>
      </div>
      <section className="workspace-section"><div className="section-head"><div><span className="section-label">PRODUCT PERFORMANCE</span><h2>Sales, COGS and margin</h2><p>Selected reporting period. Gross margin is before operating expenses.</p></div></div>{products.error ? <p className="empty-inline">Unavailable: {products.error}</p> : <div className="table-wrap"><table><thead><tr><th>Product</th><th>Units</th><th>Net sales</th><th>COGS</th><th>Gross margin</th></tr></thead><tbody>{products.data?.map((row, index) => <tr key={`${row.variant_id}-${row.business_date}-${index}`}><td><b>{row.product_name || "Product"}</b><small>{row.variant_name || row.sku || ""}</small></td><td>{Number(row.units_sold).toLocaleString()}</td><td>{showMoney(row.net_sales)}</td><td>{showMoney(row.cogs)}</td><td>{showMoney(row.gross_margin)}</td></tr>)}{products.data && !products.data.length && <tr><td colSpan={5}>No product records for the selected period.</td></tr>}</tbody></table></div>}</section>
      <div className="two-column">
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">CUSTOMER PATTERNS</span><h2>Commercial relationships</h2><p>All-time customer history; not filtered by the selected period.</p></div></div>{customers.error ? <p className="empty-inline">Unavailable: {customers.error}</p> : <div className="table-wrap"><table><thead><tr><th>Customer</th><th>Net sales</th><th>Outstanding</th></tr></thead><tbody>{customers.data?.map((row) => <tr key={row.customer_party_id}><td>{row.customer_name || "Customer"}<small>Last sale {row.last_sale_date || "—"}</small></td><td>{showMoney(row.net_sales)}</td><td>{showMoney(row.outstanding_balance)}</td></tr>)}{customers.data && !customers.data.length && <tr><td colSpan={3}>No customer records.</td></tr>}</tbody></table></div>}</section>
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">INVENTORY HEALTH</span><h2>Current stock cover</h2><p>Current inventory snapshot; not historical at the selected period.</p></div></div>{inventory.error ? <p className="empty-inline">Unavailable: {inventory.error}</p> : <div className="table-wrap"><table><thead><tr><th>Product</th><th>Available</th><th>Value</th><th>Days cover</th></tr></thead><tbody>{inventory.data?.map((row) => <tr key={`${row.location_id}-${row.variant_id}`}><td><b>{row.product_name || "Product"}</b><small>{row.location_name || "Location"}</small></td><td>{Number(row.available).toLocaleString()}</td><td>{showMoney(row.stock_value)}</td><td>{row.days_cover !== null && row.days_cover !== undefined ? Number(row.days_cover).toFixed(1) : "No velocity"}</td></tr>)}{inventory.data && !inventory.data.length && <tr><td colSpan={4}>No current inventory health records.</td></tr>}</tbody></table></div>}</section>
      </div>
    </main>
  </AppShell>;
}
