"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AppShell } from "../components/app-shell";
import { Skeleton } from "../components/ui";
import { SalesTrendChart } from "../components/dashboard-charts";
import { localDateISO } from "../lib/date.mjs";
import {
  getAnalyticsOverview, getAnalyticsProductSummary, getCommerceDashboard, getInventorySummary, getAdjustments, getStockCounts, getTransfers,
  getReadiness, type AnalyticsOverview, type AnalyticsProductSummary, type CommerceDashboard, type InventoryAdjustment, type InventorySummary,
  type StockCount, type Transfer,
} from "../lib/api";

type LoadState = "loading" | "success" | "error";
type DashboardPeriod = "7d" | "30d" | "90d";
const today = () => localDateISO();
const money = (value: string | number, currencyCode = "UGX") => new Intl.NumberFormat("en-UG", { style: "currency", currency: currencyCode, maximumFractionDigits: 0 }).format(Number(value));
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
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [productMetrics, setProductMetrics] = useState<AnalyticsProductSummary[]>([]);
  const [inventorySummary, setInventorySummary] = useState<InventorySummary | null>(null);
  const [adjustments, setAdjustments] = useState<InventoryAdjustment[]>([]);
  const [counts, setCounts] = useState<StockCount[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [readiness, setReadiness] = useState("checking");
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
    const tasks = [
      getAnalyticsOverview(range.start, range.end, dashboard?.currency_code ?? "UGX").then(value => {
        if (requestId === analyticsRequest.current) { setAnalytics(value); setAnalyticsState("success"); }
      }).catch(() => {
        if (requestId === analyticsRequest.current) { setAnalytics(null); setAnalyticsState("error"); }
      }),
      getAnalyticsProductSummary(range.start, range.end, dashboard?.currency_code ?? "UGX").then(value => {
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
      getCommerceDashboard().then(value => { setDashboard(value); setDashboardState("success"); }).catch(() => { setDashboard(null); setDashboardState("error"); }),
      getInventorySummary().then(value => { setInventorySummary(value); setInventorySummaryState("success"); }).catch(() => { setInventorySummary(null); setInventorySummaryState("error"); }),
      getAdjustments().then(value => { setAdjustments(value); setAdjustmentsState("success"); }).catch(() => { setAdjustments([]); setAdjustmentsState("error"); }),
      getStockCounts().then(value => { setCounts(value); setCountsState("success"); }).catch(() => { setCounts([]); setCountsState("error"); }),
      getTransfers().then(value => { setTransfers(value); setTransfersState("success"); }).catch(() => { setTransfers([]); setTransfersState("error"); }),
      getReadiness().then(value => { setReadiness(value.status); setReadinessState("success"); }).catch(() => { setReadiness("unavailable"); setReadinessState("error"); }),
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
    if (dashboard?.business_date) void loadAnalyticsRange(analyticsPeriod, dashboard.business_date);
  }, [dashboard?.business_date, dashboard?.currency_code]);
  useEffect(() => {
    const query = new URLSearchParams(window.location.search).get("q");
    if (query) setMessage(`Search context: ${query}`);
  }, []);

  const attention = useMemo(() => [
    ...(inventorySummary?.attention ?? []).map(row => ({
      tone: Number(row.available) <= 0 ? "danger" : "warning",
      title: Number(row.available) <= 0 ? "Out of stock" : "Low stock",
      detail: `${row.product_name}${row.sku ? ` · ${row.sku}` : ""} · ${row.location_name} · ${Number(row.available)} available`,
      href: "/inventory",
    })),
    ...adjustments.filter(x => x.status === "DRAFT").slice(0, 4).map(x => ({ tone: "info", title: "Adjustment awaiting approval", detail: `${x.reason_code} · ${short(x.id)}`, href: "/inventory" })),
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
    { label: "Open receivables", value: dashboard ? money(dashboard.outstanding_receivables, dashboard.currency_code) : "—", state: dashboardState, href: "/sales" },
  ];

  return <AppShell title="Command Centre" eyebrow="Business overview">
    <div className="command-toolbar phase4-command-toolbar">
      <div><strong>Make the next business decision with confidence.</strong><span>Live operational totals and daily metrics from your selected workspace. Missing data is shown as unavailable, never as zero.</span></div>
      <div className="toolbar-actions"><button className="button button-soft" type="button" onClick={() => void load()} disabled={busy}>{busy ? "Refreshing…" : "Refresh data"}</button><Link href="/sales" className="button button-dark">+ Create sale</Link></div>
    </div>
    {message && <div className="notice notice-info" role="status">{message}<button type="button" className="inline-dismiss" aria-label="Dismiss search context" onClick={() => setMessage("")}>×</button></div>}

    <section className="home-status-row" aria-label="Workspace status"><span className={`status ${readinessState === "success" && ["ready", "ok"].includes(readiness) ? "good" : "warn"}`}><span aria-hidden="true">●</span> {readinessState === "loading" ? "Checking workspace" : readinessState === "error" ? "Readiness unavailable" : ["ready", "ok"].includes(readiness) ? "Workspace ready" : "Dependency attention"}</span><span>Business date · {dashboardState === "success" && dashboard ? dashboard.business_date : today()}</span></section>

    <section className="command-kpis" aria-label="Key business indicators">
      <div className="command-kpi"><span>Today's sales</span><strong>{dashboardState === "loading" ? "—" : dashboardState === "error" || !dashboard ? "Unavailable" : money(dashboard.sales.sales, dashboard.currency_code)}</strong><small>{dashboardState === "loading" ? "Loading authoritative state" : dashboardState === "error" || !dashboard ? "Sales data could not be loaded" : dashboard.sales.credit ? `Credit recorded ${money(dashboard.sales.credit, dashboard.currency_code)}` : "Completed sales"}</small></div>
      <div className="command-kpi"><span>Collected today</span><strong>{dashboardState === "loading" ? "—" : dashboardState === "error" || !dashboard ? "Unavailable" : money(dashboard.sales.collected, dashboard.currency_code)}</strong><small>{dashboardState === "loading" ? "Loading payment state" : dashboardState === "error" || !dashboard ? "Payment data could not be loaded" : "Recorded payments, not total sales"}</small></div>
      <div className="command-kpi"><span>Net sales · {periodLabels[analyticsPeriod].toLowerCase()}</span><strong>{analyticsState === "loading" ? "—" : analyticsState === "error" || !analytics ? "Unavailable" : money(analytics.totals.net_sales, analytics.currency_code || dashboard?.currency_code || "UGX")}</strong><small>{analyticsState === "loading" ? "Loading reporting data" : analyticsState === "error" || !analytics ? "Reporting data could not be loaded" : `${analytics.totals.sale_count} recorded sales · ${dateLabel(selectedRange.start)} – ${dateLabel(selectedRange.end)}`}</small></div>
      <div className="command-kpi"><span>Inventory value</span><strong>{inventorySummaryState === "loading" ? "—" : inventorySummaryState === "error" || !inventorySummary ? "Unavailable" : money(inventorySummary.stock_value, dashboard?.currency_code || "UGX")}</strong><small>{inventorySummaryState === "loading" ? "Calculating authorized stock value" : inventorySummaryState === "error" || !inventorySummary ? "Stock valuation could not be verified" : `${inventorySummary.balance_rows} balance rows · ${inventorySummary.out_of_stock_rows} out · ${inventorySummary.low_stock_rows} low`}</small></div>
    </section>

    <section className="phase4-analytics-grid" aria-label="Sales analytics">
      <div className="panel command-panel trend-panel">
        <div className="panel-head phase4-panel-head"><div><p className="eyebrow">SALES PERFORMANCE</p><h2>Net sales vs money collected</h2><p className="panel-subtitle">Different business measures, shown together without treating them as interchangeable.</p></div>
          <div className="period-control" role="group" aria-label="Analytics date range">{(["7d", "30d", "90d"] as DashboardPeriod[]).map(period => <button key={period} type="button" className={`period-button ${analyticsPeriod === period ? "active" : ""}`} aria-pressed={analyticsPeriod === period} onClick={() => setAnalyticsPeriod(period)} disabled={analyticsState === "loading"}>{period}</button>)}</div>
        </div>
        {analyticsState === "loading" ? <LoadingPlaceholder label="Loading daily business metrics…" /> : analyticsState === "error" || !analytics ? <LoadError title="Sales trend" retry={() => void loadAnalyticsRange(analyticsPeriod)} /> : <SalesTrendChart daily={analytics.daily} startDate={analytics.from_date} endDate={analytics.to_date} currencyCode={analytics.currency_code || dashboard?.currency_code || "UGX"} />}
      </div>
      <div className="panel command-panel top-products-panel">
        <div className="panel-head"><div><p className="eyebrow">PRODUCT PERFORMANCE</p><h2>Top products</h2><p className="panel-subtitle">Ranked by aggregated net sales across {periodLabels[analyticsPeriod].toLowerCase()}.</p></div><Link href="/reports" className="panel-link">Explore reports →</Link></div>
        {productsState === "loading" ? <LoadingPlaceholder label="Loading product performance…" /> : productsState === "error" ? <LoadError title="Product performance" retry={() => void loadAnalyticsRange(analyticsPeriod)} /> : topProducts.length ? <div className="top-product-list">{topProducts.map((product, index) => <div className="top-product-row" key={product.id}>
          <div className="top-product-rank">{index + 1}</div><div className="top-product-info"><div className="top-product-name"><strong>{product.name}</strong><small>{product.sku} · {product.units.toLocaleString("en-UG", { maximumFractionDigits: 2 })} units</small></div><div className="product-bar-track" aria-hidden="true"><span style={{ width: `${Math.max(3, (product.netSales / maxProductSales) * 100)}%` }} /></div></div><div className="top-product-value">{money(product.netSales, analytics?.currency_code || dashboard?.currency_code || "UGX")}<small>Gross margin {money(product.grossMargin, analytics?.currency_code || dashboard?.currency_code || "UGX")}</small></div>
        </div>)}</div> : <div className="empty-state compact"><strong>No product metrics yet</strong><span>Completed, reported sales will appear here after analytics metrics are available.</span><Link href="/sales" className="button button-soft">Open sales</Link></div>}
      </div>
    </section>

    <section className="command-grid phase4-operations-grid">
      <div className="panel command-panel"><div className="panel-head"><div><p className="eyebrow">NEEDS ATTENTION</p><h2>Actions worth opening now</h2></div><Link href="/inventory" className="panel-link">Open inventory →</Link></div><div className="attention-list">
        {(inventorySummaryState === "loading" || adjustmentsState === "loading") ? <LoadingPlaceholder label="Loading operational exceptions…" />
          : (inventorySummaryState === "error" || adjustmentsState === "error") ? <><div className="empty-state compact"><strong>Exception list is incomplete</strong><span>{inventorySummaryState === "error" ? "Stock exceptions" : "Adjustment approvals"} could not be verified. Available information may be partial.</span><button className="button button-soft" type="button" onClick={() => void load()}>Refresh data</button></div>{attention.map((item, i) => <Link href={item.href} className="attention-row" key={`${item.title}-${i}`}><span className={`attention-dot ${item.tone}`} /><div><strong>{item.title}</strong><small>{item.detail}</small></div><span aria-hidden="true">›</span></Link>)}</>
          : attention.length ? attention.map((item, i) => <Link href={item.href} className="attention-row" key={`${item.title}-${i}`}><span className={`attention-dot ${item.tone}`} /><div><strong>{item.title}</strong><small>{item.detail}</small></div><span aria-hidden="true">›</span></Link>)
          : <div className="empty-state compact"><strong>Nothing urgent</strong><span>LEXA has no immediate operational exceptions in the loaded workspace.</span></div>}
      </div></div>
      <div className="panel command-panel"><div className="panel-head"><div><p className="eyebrow">TODAY'S WORK</p><h2>Operational queue</h2></div></div><div className="work-list">{openWork.map(item => <Link className="work-card" href={item.href} key={item.label}><strong>{item.state === "loading" ? "—" : item.state === "error" ? "Unavailable" : item.value}</strong><span>{item.label}</span><small>Open →</small></Link>)}</div></div>
    </section>

    <section className="command-grid phase4-lower-grid">
      <div className="panel command-panel"><div className="panel-head"><div><p className="eyebrow">WORKSPACE SHORTCUTS</p><h2>Get to the next task</h2></div></div><div className="quick-links"><Link href="/sales">Sales <small>Checkout · payments · returns</small></Link><Link href="/products">Products <small>SKUs · barcodes · prices</small></Link><Link href="/inventory">Inventory <small>Stock · counts · transfers</small></Link><Link href="/purchasing">Purchasing <small>Suppliers · orders · receiving</small></Link><Link href="/accounting">Finance <small>Accounts · journals · reporting</small></Link><Link href="/reports">Reports <small>Trends · product performance</small></Link></div></div>
      <div className="panel command-panel"><div className="panel-head"><div><p className="eyebrow">DATA CONFIDENCE</p><h2>Understand each number</h2></div></div><div className="data-confidence-list"><div><span className="confidence-icon" aria-hidden="true">✓</span><div><strong>Live operational records</strong><small>Sales, payments and stock are loaded independently.</small></div></div><div><span className="confidence-icon" aria-hidden="true">↗</span><div><strong>Period-aware analytics</strong><small>Choose 7, 30 or 90 days and read the exact dates.</small></div></div><div><span className="confidence-icon" aria-hidden="true">≠</span><div><strong>Revenue is not cash</strong><small>Net sales and money collected are labelled separately.</small></div></div><div><span className="confidence-icon" aria-hidden="true">!</span><div><strong>Missing is not zero</strong><small>If LEXA cannot verify a metric, it reports that state clearly.</small></div></div></div></div>
    </section>
  </AppShell>;
}
