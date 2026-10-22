"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AppShell } from "../components/app-shell";
import { Skeleton } from "../components/ui";
import { SalesTrendChart } from "../components/dashboard-charts";
import { localDateISO } from "../lib/date.mjs";
import {
  getAnalyticsOverview, getAnalyticsProductSummary, getCommerceDashboard, getInventorySummary, getAdjustments, getStockCounts, getTransfers,
  getReadiness, getBusinessProfile, getSetupProgress, type SetupProgress, type AnalyticsOverview, type AnalyticsProductSummary, type CommerceDashboard, type InventoryAdjustment, type InventorySummary,
  type StockCount, type Transfer,
} from "../lib/api";

type LoadState = "loading" | "success" | "error";
type DashboardPeriod = "7d" | "30d" | "90d";
const today = () => localDateISO();
const money = (value: string | number, currencyCode?: string | null) => {
  if (!currencyCode || !/^[A-Z]{3}$/.test(currencyCode)) return "Currency unavailable";
  try { return new Intl.NumberFormat("en-UG", { style: "currency", currency: currencyCode, maximumFractionDigits: 0 }).format(Number(value)); }
  catch { return `${currencyCode} ${Number(value).toLocaleString("en-UG", { maximumFractionDigits: 0 })}`; }
};
const short = (id: string) => `${id.slice(0, 8)}…`;
const periodDays: Record<DashboardPeriod, number> = { "7d": 7, "30d": 30, "90d": 90 };
const periodLabels: Record<DashboardPeriod, string> = { "7d": "Last 7 days", "30d": "Last 30 days", "90d": "Last 90 days" };

function shiftDateISO(value: string, days: number) {
  const date = new Date(`${value}T12:00:00`);
  date.setDate(date.getDate() + days);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function rangeFor(period: DashboardPeriod, businessDate = today()) {
  // Prefer the API's tenant-authoritative business date; the browser clock is
  // only a safe first-render fallback before the workspace dashboard returns.
  const end = businessDate;
  return { start: shiftDateISO(end, -(periodDays[period] - 1)), end };
}

function dateLabel(value: string) {
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("en-UG", { day: "numeric", month: "short", year: "numeric" }).format(date);
}

function LoadingPlaceholder({ label }: { label: string }) {
  return <div className="loading-placeholder loading-placeholder-skeleton" role="status" aria-live="polite">
    <strong>{label}</strong>
    <Skeleton shape="text" width="78%" />
    <Skeleton shape="text" width="58%" />
    <Skeleton shape="rect" height={24} />
  </div>;
}

function LoadError({ title, retry }: { title: string; retry: () => void }) {
  return <div className="empty-state compact"><strong>{title} unavailable</strong><span>LEXA could not verify this data. Refresh to try again.</span><button className="button button-soft" type="button" onClick={retry}>Retry</button></div>;
}

export default function HomePage() {
  const [dashboard, setDashboard] = useState<CommerceDashboard | null>(null);
  const [businessCurrency, setBusinessCurrency] = useState<string | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [productMetrics, setProductMetrics] = useState<AnalyticsProductSummary[]>([]);
  const [inventorySummary, setInventorySummary] = useState<InventorySummary | null>(null);
  const [adjustments, setAdjustments] = useState<InventoryAdjustment[]>([]);
  const [counts, setCounts] = useState<StockCount[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [readiness, setReadiness] = useState("checking");
  const [setupProgress, setSetupProgress] = useState<SetupProgress | null>(null);
  const [analyticsPeriod, setAnalyticsPeriod] = useState<DashboardPeriod>("30d");
  const [dashboardState, setDashboardState] = useState<LoadState>("loading");
  const [analyticsState, setAnalyticsState] = useState<LoadState>("loading");
  const [productsState, setProductsState] = useState<LoadState>("loading");
  const [inventorySummaryState, setInventorySummaryState] = useState<LoadState>("loading");
  const [adjustmentsState, setAdjustmentsState] = useState<LoadState>("loading");
  const [countsState, setCountsState] = useState<LoadState>("loading");
  const [transfersState, setTransfersState] = useState<LoadState>("loading");
  const [readinessState, setReadinessState] = useState<LoadState>("loading");
  const [message, setMessage] = useState("");
  const analyticsRequest = useRef(0);
  const periodEffectMounted = useRef(false);

  const busy = [dashboardState, analyticsState, productsState, inventorySummaryState, adjustmentsState, countsState, transfersState, readinessState].some(state => state === "loading");
  const selectedRange = useMemo(() => rangeFor(analyticsPeriod, dashboard?.business_date ?? today()), [analyticsPeriod, dashboard?.business_date, dashboard?.currency_code]);

  async function loadAnalyticsRange(period: DashboardPeriod, businessDate = dashboard?.business_date ?? today()) {
    const requestId = ++analyticsRequest.current;
    const range = rangeFor(period, businessDate);
    setAnalyticsState("loading");
    setProductsState("loading");
    const currencyCode = businessCurrency;
    if (!currencyCode || !/^[A-Z]{3}$/.test(currencyCode)) {
      setAnalytics(null); setAnalyticsState("error");
      setProductMetrics([]); setProductsState("error");
      return;
    }
    const tasks = [
      getAnalyticsOverview(range.start, range.end, currencyCode).then(value => {
        if (requestId === analyticsRequest.current) { setAnalytics(value); setAnalyticsState("success"); }
      }).catch(() => {
        if (requestId === analyticsRequest.current) { setAnalytics(null); setAnalyticsState("error"); }
      }),
      getAnalyticsProductSummary(range.start, range.end, currencyCode).then(value => {
        if (requestId === analyticsRequest.current) { setProductMetrics(value); setProductsState("success"); }
      }).catch(() => {
        if (requestId === analyticsRequest.current) { setProductMetrics([]); setProductsState("error"); }
      }),
    ];
    await Promise.all(tasks);
  }

  async function loadOperationalData() {
    setDashboardState("loading"); setInventorySummaryState("loading"); setAdjustmentsState("loading");
    setCountsState("loading"); setTransfersState("loading"); setReadinessState("loading");
    const tasks = [
      getCommerceDashboard().then(value => {
        setDashboard(value); setDashboardState("success");
        const reported = value.currency_code && /^[A-Z]{3}$/i.test(value.currency_code) ? value.currency_code.toUpperCase() : null;
        setBusinessCurrency(current => current || reported);
      }).catch(() => { setDashboard(null); setDashboardState("error"); }),
      getBusinessProfile().then(profile => {
        const code = profile?.currency_code && /^[A-Z]{3}$/i.test(profile.currency_code) ? profile.currency_code.toUpperCase() : null;
        if (code) setBusinessCurrency(code);
      }).catch(() => { /* Fall back to the currency explicitly reported by the authorized dashboard API. */ }),
      getInventorySummary().then(value => { setInventorySummary(value); setInventorySummaryState("success"); }).catch(() => { setInventorySummary(null); setInventorySummaryState("error"); }),
      getAdjustments().then(value => { setAdjustments(value); setAdjustmentsState("success"); }).catch(() => { setAdjustments([]); setAdjustmentsState("error"); }),
      getStockCounts().then(value => { setCounts(value); setCountsState("success"); }).catch(() => { setCounts([]); setCountsState("error"); }),
      getTransfers().then(value => { setTransfers(value); setTransfersState("success"); }).catch(() => { setTransfers([]); setTransfersState("error"); }),
      getReadiness().then(value => { setReadiness(value.status); setReadinessState("success"); }).catch(() => { setReadiness("unavailable"); setReadinessState("error"); }),
      getSetupProgress().then(value => setSetupProgress(value)).catch(() => setSetupProgress(null)),
    ];
    await Promise.all(tasks);
  }

  async function load() {
    await Promise.all([loadOperationalData(), loadAnalyticsRange(analyticsPeriod)]);
  }

  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (!periodEffectMounted.current) { periodEffectMounted.current = true; return; }
    void loadAnalyticsRange(analyticsPeriod);
  }, [analyticsPeriod]);
  useEffect(() => {
    if (dashboard?.business_date || businessCurrency) void loadAnalyticsRange(analyticsPeriod, dashboard?.business_date ?? today());
  }, [dashboard?.business_date, dashboard?.currency_code, businessCurrency]);
  useEffect(() => {
    const query = new URLSearchParams(window.location.search).get("q");
    if (query) setMessage(`Search for: ${query}`);
  }, []);

  const attention = useMemo(() => [
    ...(inventorySummary?.attention ?? []).map(row => ({
      tone: Number(row.available) <= 0 ? "danger" : "warning",
      title: Number(row.available) <= 0 ? "Out of stock" : "Low stock",
      detail: `${row.product_name}${row.sku ? ` · ${row.sku}` : ""} · ${row.location_name} · ${Number(row.available)} available`,
      href: "/inventory",
    })),
    ...adjustments.filter(x => x.status === "DRAFT").slice(0, 4).map(x => ({ tone: "info", title: "Stock correction awaiting approval", detail: `${x.reason_code} · ${short(x.id)}`, href: "/inventory" })),
  ], [inventorySummary, adjustments]);

  const topProducts = useMemo(() => productMetrics.map(row => ({
    id: row.variant_id,
    name: [row.product_name, row.variant_name].filter(Boolean).join(" · ") || row.sku || "Unnamed product",
    sku: row.sku || "—",
    units: Number(row.units_sold) || 0,
    netSales: Number(row.net_sales) || 0,
    grossMargin: Number(row.gross_margin) || 0,
  })).sort((a, b) => b.netSales - a.netSales).slice(0, 5), [productMetrics]);

  const maxProductSales = Math.max(1, ...topProducts.map(product => product.netSales));
  const openWork = [
    { label: "Stock counts in progress", value: counts.filter(x => x.status === "COUNTING").length, state: countsState, href: "/inventory" },
    { label: "Transfers awaiting action", value: transfers.filter(x => ["DRAFT", "APPROVED", "DISPATCHED", "PARTIALLY_RECEIVED"].includes(x.status)).length, state: transfersState, href: "/inventory" },
    { label: "Money customers still owe", value: dashboard ? money(dashboard.outstanding_receivables, businessCurrency) : "—", state: dashboardState, href: "/sales" },
  ];

  return <AppShell title="Business overview" eyebrow="Your business at a glance">
    <div className="command-toolbar phase4-command-toolbar">
      <div><strong>A clear view of how your business is doing.</strong><span>Sales, recorded money and stock in one place. We show when information is missing instead of guessing.</span></div>
      <div className="toolbar-actions"><button className="button button-soft" type="button" onClick={() => void load()} disabled={busy}>{busy ? "Refreshing…" : "Refresh"}</button><Link href="/sales" className="button button-dark">+ Create sale</Link></div>
    </div>
    {message && <div className="notice notice-info" role="status">{message}<button type="button" className="inline-dismiss" aria-label="Dismiss search context" onClick={() => setMessage("")}>×</button></div>}

    <section className="home-status-row" aria-label="Business status"><span className={`status ${readinessState === "success" && ["ready", "ok"].includes(readiness) ? "good" : "warn"}`}><span aria-hidden="true">●</span> {readinessState === "loading" ? "Checking connection" : readinessState === "error" ? "Connection not confirmed" : ["ready", "ok"].includes(readiness) ? "Connected" : "Connection needs attention"}</span><span>Business date · {dashboardState === "success" && dashboard ? dashboard.business_date : today()}</span></section>
    {setupProgress && !setupProgress.complete && <section className="setup-notice" role="status"><span className="setup-notice-icon" aria-hidden="true">✦</span><div><strong>Finish setting up your business</strong><p>Your main branch and stock location need to be ready before all sales, stock and reports can work together.</p></div><Link href="/onboarding" className="button button-dark">Finish setup</Link></section>}

    <section className="command-kpis" aria-label="Key business indicators">
      <div className="command-kpi"><span>Today's sales</span><strong>{dashboardState === "loading" ? "—" : dashboardState === "error" || !dashboard ? "Unavailable" : money(dashboard.sales.sales, dashboard.currency_code)}</strong><small>{dashboardState === "loading" ? "Loading today’s sales" : dashboardState === "error" || !dashboard ? "Sales data could not be loaded" : dashboard.sales.credit ? `Credit recorded ${money(dashboard.sales.credit, dashboard.currency_code)}` : "Completed sales"}</small></div>
      <div className="command-kpi"><span>Money recorded today</span><strong>{dashboardState === "loading" ? "—" : dashboardState === "error" || !dashboard ? "Unavailable" : money(dashboard.sales.collected, dashboard.currency_code)}</strong><small>{dashboardState === "loading" ? "Loading recorded payments" : dashboardState === "error" || !dashboard ? "Payment data could not be loaded" : "Recorded payments, not total sales"}</small></div>
      <div className="command-kpi"><span>Sales after returns · {periodLabels[analyticsPeriod].toLowerCase()}</span><strong>{analyticsState === "loading" ? "—" : analyticsState === "error" || !analytics ? "Unavailable" : money(analytics.totals.net_sales, analytics.currency_code || businessCurrency)}</strong><small>{analyticsState === "loading" ? "Loading sales figures" : analyticsState === "error" || !analytics ? "Reporting data could not be loaded" : `${analytics.totals.sale_count} recorded sales · ${dateLabel(selectedRange.start)} – ${dateLabel(selectedRange.end)}`}</small></div>
      <div className="command-kpi"><span>Stock value</span><strong>{inventorySummaryState === "loading" ? "—" : inventorySummaryState === "error" || !inventorySummary ? "Unavailable" : money(inventorySummary.stock_value, businessCurrency)}</strong><small>{inventorySummaryState === "loading" ? "Calculating stock value" : inventorySummaryState === "error" || !inventorySummary ? "Stock valuation could not be verified" : `${inventorySummary.balance_rows} stock records · ${inventorySummary.out_of_stock_rows} out · ${inventorySummary.low_stock_rows} low`}</small></div>
    </section>

    <section className="phase4-analytics-grid" aria-label="Sales performance">
      <div className="panel command-panel trend-panel">
        <div className="panel-head phase4-panel-head"><div><p className="eyebrow">SALES PERFORMANCE</p><h2>Sales and money recorded</h2><p className="panel-subtitle">Sales after returns and payments recorded are different totals.</p></div>
          <div className="period-control" role="group" aria-label="Sales reporting period">{(["7d", "30d", "90d"] as DashboardPeriod[]).map(period => <button key={period} type="button" className={`period-button ${analyticsPeriod === period ? "active" : ""}`} aria-pressed={analyticsPeriod === period} onClick={() => setAnalyticsPeriod(period)} disabled={analyticsState === "loading"}>{period}</button>)}</div>
        </div>
        {analyticsState === "loading" ? <LoadingPlaceholder label="Loading the sales trend…" /> : analyticsState === "error" || !analytics ? <LoadError title="Sales trend" retry={() => void loadAnalyticsRange(analyticsPeriod)} /> : <SalesTrendChart daily={analytics.daily} startDate={analytics.from_date} endDate={analytics.to_date} currencyCode={analytics.currency_code || businessCurrency} />}
      </div>
      <div className="panel command-panel top-products-panel">
        <div className="panel-head"><div><p className="eyebrow">PRODUCT PERFORMANCE</p><h2>Top products</h2><p className="panel-subtitle">Ranked by sales after returns over {periodLabels[analyticsPeriod].toLowerCase()}.</p></div><Link href="/reports" className="panel-link">See all reports →</Link></div>
        {productsState === "loading" ? <LoadingPlaceholder label="Loading best-selling products…" /> : productsState === "error" ? <LoadError title="Product performance" retry={() => void loadAnalyticsRange(analyticsPeriod)} /> : topProducts.length ? <div className="top-product-list">{topProducts.map((product, index) => <div className="top-product-row" key={product.id}>
          <div className="top-product-rank">{index + 1}</div><div className="top-product-info"><div className="top-product-name"><strong>{product.name}</strong><small>{product.sku} · {product.units.toLocaleString("en-UG", { maximumFractionDigits: 2 })} units</small></div><div className="product-bar-track" aria-hidden="true"><span style={{ width: `${Math.max(3, (product.netSales / maxProductSales) * 100)}%` }} /></div></div><div className="top-product-value">{money(product.netSales, analytics?.currency_code || businessCurrency)}<small>Sales left after product cost {money(product.grossMargin, analytics?.currency_code || businessCurrency)}</small></div>
        </div>)}</div> : <div className="empty-state compact"><strong>No product sales yet</strong><span>Best-selling products will appear here after your first completed sales.</span><Link href="/sales" className="button button-soft">Open sales</Link></div>}
      </div>
    </section>

    <section className="command-grid phase4-operations-grid">
      <div className="panel command-panel"><div className="panel-head"><div><p className="eyebrow">NEEDS ATTENTION</p><h2>Actions worth opening now</h2></div><Link href="/inventory" className="panel-link">Open inventory →</Link></div><div className="attention-list">
        {(inventorySummaryState === "loading" || adjustmentsState === "loading") ? <LoadingPlaceholder label="Loading items that need attention…" />
          : (inventorySummaryState === "error" || adjustmentsState === "error") ? <><div className="empty-state compact"><strong>Some items need attention</strong><span>{inventorySummaryState === "error" ? "Stock checks" : "Adjustment approvals"} could not be verified. Available information may be partial.</span><button className="button button-soft" type="button" onClick={() => void load()}>Refresh data</button></div>{attention.map((item, i) => <Link href={item.href} className="attention-row" key={`${item.title}-${i}`}><span className={`attention-dot ${item.tone}`} /><div><strong>{item.title}</strong><small>{item.detail}</small></div><span aria-hidden="true">›</span></Link>)}</>
          : attention.length ? attention.map((item, i) => <Link href={item.href} className="attention-row" key={`${item.title}-${i}`}><span className={`attention-dot ${item.tone}`} /><div><strong>{item.title}</strong><small>{item.detail}</small></div><span aria-hidden="true">›</span></Link>)
          : <div className="empty-state compact"><strong>Nothing urgent</strong><span>Nothing urgent has been reported in the information currently available.</span></div>}
      </div></div>
      <div className="panel command-panel"><div className="panel-head"><div><p className="eyebrow">TODAY'S WORK</p><h2>Work to finish</h2></div></div><div className="work-list">{openWork.map(item => <Link className="work-card" href={item.href} key={item.label}><strong>{item.state === "loading" ? "—" : item.state === "error" ? "Unavailable" : item.value}</strong><span>{item.label}</span><small>Open →</small></Link>)}</div></div>
    </section>

    <section className="command-grid phase4-lower-grid">
      <div className="panel command-panel"><div className="panel-head"><div><p className="eyebrow">QUICK LINKS</p><h2>Get to the next task</h2></div></div><div className="quick-links"><Link href="/sales">Sales <small>Complete sales · record payments · handle returns</small></Link><Link href="/products">Products <small>Product codes · barcodes · prices</small></Link><Link href="/inventory">Inventory <small>Stock · counts · transfers</small></Link><Link href="/purchasing">Purchases <small>Suppliers · orders · receiving</small></Link><Link href="/accounting">Finance <small>Money in and out · expenses · reports</small></Link><Link href="/reports">Reports <small>Trends · product performance</small></Link></div></div>
      <div className="panel command-panel"><div className="panel-head"><div><p className="eyebrow">ABOUT THESE NUMBERS</p><h2>Know what the numbers mean</h2></div></div><div className="data-confidence-list"><div><span className="confidence-icon" aria-hidden="true">✓</span><div><strong>Saved business records</strong><small>Sales, payments and stock are loaded independently.</small></div></div><div><span className="confidence-icon" aria-hidden="true">↗</span><div><strong>Selected date range</strong><small>Choose 7, 30 or 90 days and read the exact dates.</small></div></div><div><span className="confidence-icon" aria-hidden="true">≠</span><div><strong>Revenue is not cash</strong><small>Net sales and money collected are labelled separately.</small></div></div><div><span className="confidence-icon" aria-hidden="true">!</span><div><strong>Missing information is not zero</strong><small>If LEXA cannot verify a metric, it reports that state clearly.</small></div></div></div></div>
    </section>
  </AppShell>;
}
