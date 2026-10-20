"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AppShell } from "../components/app-shell";
import { Skeleton } from "../components/ui";
import { localDateISO, localMonthStartISO } from "../lib/date.mjs";
import {
  getAnalyticsOverview, getCommerceDashboard, getInventoryBalances, getAdjustments, getStockCounts, getTransfers,
  getReadiness, type AnalyticsOverview, type CommerceDashboard, type InventoryAdjustment, type InventoryBalance,
  type StockCount, type Transfer,
} from "../lib/api";

type LoadState = "loading" | "success" | "error";
const today = () => localDateISO();
const monthStart = () => localMonthStartISO();
const money = (value: string | number) => new Intl.NumberFormat("en-UG", { style: "currency", currency: "UGX", maximumFractionDigits: 0 }).format(Number(value));
const short = (id: string) => `${id.slice(0, 8)}…`;

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
  const [balances, setBalances] = useState<InventoryBalance[]>([]);
  const [adjustments, setAdjustments] = useState<InventoryAdjustment[]>([]);
  const [counts, setCounts] = useState<StockCount[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [readiness, setReadiness] = useState("checking");
  const [dashboardState, setDashboardState] = useState<LoadState>("loading");
  const [analyticsState, setAnalyticsState] = useState<LoadState>("loading");
  const [balancesState, setBalancesState] = useState<LoadState>("loading");
  const [adjustmentsState, setAdjustmentsState] = useState<LoadState>("loading");
  const [countsState, setCountsState] = useState<LoadState>("loading");
  const [transfersState, setTransfersState] = useState<LoadState>("loading");
  const [readinessState, setReadinessState] = useState<LoadState>("loading");
  const [message, setMessage] = useState("");

  const busy = [dashboardState, analyticsState, balancesState, adjustmentsState, countsState, transfersState, readinessState].some(state => state === "loading");

  async function load() {
    setDashboardState("loading"); setAnalyticsState("loading"); setBalancesState("loading");
    setAdjustmentsState("loading"); setCountsState("loading"); setTransfersState("loading"); setReadinessState("loading");
    const tasks = [
      getCommerceDashboard().then(value => { setDashboard(value); setDashboardState("success"); }).catch(() => { setDashboard(null); setDashboardState("error"); }),
      getAnalyticsOverview(monthStart(), today()).then(value => { setAnalytics(value); setAnalyticsState("success"); }).catch(() => { setAnalytics(null); setAnalyticsState("error"); }),
      getInventoryBalances().then(value => { setBalances(value); setBalancesState("success"); }).catch(() => { setBalances([]); setBalancesState("error"); }),
      getAdjustments().then(value => { setAdjustments(value); setAdjustmentsState("success"); }).catch(() => { setAdjustments([]); setAdjustmentsState("error"); }),
      getStockCounts().then(value => { setCounts(value); setCountsState("success"); }).catch(() => { setCounts([]); setCountsState("error"); }),
      getTransfers().then(value => { setTransfers(value); setTransfersState("success"); }).catch(() => { setTransfers([]); setTransfersState("error"); }),
      getReadiness().then(value => { setReadiness(value.status); setReadinessState("success"); }).catch(() => { setReadiness("unavailable"); setReadinessState("error"); }),
    ];
    await Promise.all(tasks);
  }

  useEffect(() => { void load(); }, []);
  useEffect(() => {
    const query = new URLSearchParams(window.location.search).get("q");
    if (query) setMessage(`Search context: ${query}`);
  }, []);

  const attention = useMemo(() => [
    ...balances.filter(x => Number(x.available) <= 0).slice(0, 5).map(x => ({ tone:"danger", title:"Out of stock", detail:`${x.variant_id.slice(0,8)}… · location ${x.location_id.slice(0,8)}…`, href:"/inventory" })),
    ...balances.filter(x => Number(x.available) > 0 && Number(x.available) <= 5).slice(0, 5).map(x => ({ tone:"warning", title:"Low stock", detail:`${x.variant_id.slice(0,8)}… · ${Number(x.available)} available`, href:"/inventory" })),
    ...adjustments.filter(x => x.status === "DRAFT").slice(0, 4).map(x => ({ tone:"info", title:"Adjustment awaiting approval", detail:`${x.reason_code} · ${short(x.id)}`, href:"/inventory" })),
  ], [balances, adjustments]);

  const openWork = [
    { label:"Stock counts in progress", value:counts.filter(x => x.status === "COUNTING").length, state:countsState, href:"/inventory" },
    { label:"Transfers awaiting action", value:transfers.filter(x => ["DRAFT","APPROVED","DISPATCHED","PARTIALLY_RECEIVED"].includes(x.status)).length, state:transfersState, href:"/inventory" },
    { label:"Open receivables", value:dashboard ? money(dashboard.outstanding_receivables) : "—", state:dashboardState, href:"/sales" },
  ];

  return <AppShell title="Command Centre" eyebrow="Today">
    <div className="command-toolbar"><div><strong>What is happening in the business right now?</strong><span>Authoritative operational state with a light intelligence layer on top.</span></div><div className="toolbar-actions"><button className="button button-soft" onClick={() => void load()} disabled={busy}>Refresh</button><Link href="/sales" className="button button-dark">+ Create sale</Link></div></div>
    {message && <div className="notice notice-error">{message}</div>}

    <section className="home-status-row"><span className={`status ${readinessState === "success" && ["ready", "ok"].includes(readiness) ? "good" : "warn"}`}>● {readinessState === "loading" ? "Checking workspace" : readinessState === "error" ? "Readiness unavailable" : ["ready", "ok"].includes(readiness) ? "Workspace ready" : "Dependency attention"}</span><span>Business date · {dashboardState === "success" && dashboard ? dashboard.business_date : today()}</span></section>

    <div className="command-kpis">
      <div className="command-kpi"><span>Today's sales</span><strong>{dashboardState === "loading" ? "—" : dashboardState === "error" || !dashboard ? "Unavailable" : money(dashboard.sales.sales)}</strong><small>{dashboardState === "loading" ? "Loading authoritative state" : dashboardState === "error" || !dashboard ? "Sales data could not be loaded" : dashboard.sales.credit ? `Credit ${money(dashboard.sales.credit)}` : "Completed sales"}</small></div>
      <div className="command-kpi"><span>Collected</span><strong>{dashboardState === "loading" ? "—" : dashboardState === "error" || !dashboard ? "Unavailable" : money(dashboard.sales.collected)}</strong><small>{dashboardState === "loading" ? "Loading authoritative state" : dashboardState === "error" || !dashboard ? "Payment data could not be loaded" : "Recorded payments"}</small></div>
      <div className="command-kpi"><span>Month-to-date net sales</span><strong>{analyticsState === "loading" ? "—" : analyticsState === "error" || !analytics ? "Unavailable" : money(analytics.totals.net_sales)}</strong><small>{analyticsState === "loading" ? "Loading reporting data" : analyticsState === "error" || !analytics ? "Reporting data could not be loaded" : `${analytics.totals.sale_count} completed sales`}</small></div>
      <div className="command-kpi"><span>Inventory value</span><strong>{balancesState === "loading" ? "—" : balancesState === "error" ? "Unavailable" : money(balances.reduce((sum, row) => sum + Number(row.stock_value), 0))}</strong><small>{balancesState === "loading" ? "Loading stock balances" : balancesState === "error" ? "Stock valuation could not be loaded" : `${balances.length} balance rows`}</small></div>
    </div>

    <div className="command-grid">
      <section className="panel command-panel"><div className="panel-head"><div><p className="eyebrow">NEEDS ATTENTION</p><h2>Actions worth opening now</h2></div><Link href="/inventory" className="panel-link">Open inventory →</Link></div><div className="attention-list">
        {(balancesState === "loading" || adjustmentsState === "loading") ? <LoadingPlaceholder label="Loading operational exceptions…" />
          : (balancesState === "error" || adjustmentsState === "error") ? <><div className="empty-state compact"><strong>Exception list is incomplete</strong><span>{balancesState === "error" ? "Stock exceptions" : "Adjustment approvals"} could not be verified. Available information may be partial.</span><button className="button button-soft" type="button" onClick={() => void load()}>Refresh data</button></div>{attention.map((item, i) => <Link href={item.href} className="attention-row" key={`${item.title}-${i}`}><span className={`attention-dot ${item.tone}`}/><div><strong>{item.title}</strong><small>{item.detail}</small></div><span>›</span></Link>)}</>
          : attention.length ? attention.map((item, i) => <Link href={item.href} className="attention-row" key={`${item.title}-${i}`}><span className={`attention-dot ${item.tone}`}/><div><strong>{item.title}</strong><small>{item.detail}</small></div><span>›</span></Link>)
          : <div className="empty-state compact"><strong>Nothing urgent</strong><span>LEXA has no immediate operational exceptions in the loaded workspace.</span></div>}
      </div></section>
      <section className="panel command-panel"><div className="panel-head"><div><p className="eyebrow">TODAY'S WORK</p><h2>Operational queue</h2></div></div><div className="work-list">{openWork.map(item=><Link className="work-card" href={item.href} key={item.label}><strong>{item.state === "loading" ? "—" : item.state === "error" ? "Unavailable" : item.value}</strong><span>{item.label}</span><small>Open →</small></Link>)}</div></section>
    </div>

    <div className="command-grid"><section className="panel command-panel"><div className="panel-head"><div><p className="eyebrow">BUSINESS SIGNAL</p><h2>Daily movement</h2></div><Link href="/reports" className="panel-link">Reports →</Link></div><div className="signal-grid">{analyticsState === "loading" ? <LoadingPlaceholder label="Loading business movement…" /> : analyticsState === "error" || !analytics ? <LoadError title="Business movement" retry={() => void load()} /> : analytics.daily.length ? analytics.daily.slice(-7).map(day=><div className="signal-row" key={day.business_date}><span>{day.business_date}</span><strong>{money(day.net_sales)}</strong><small>{money(day.payments_collected)} collected</small></div>) : <div className="empty-state compact"><strong>No recorded movement</strong><span>No completed transactions were found for this reporting window.</span></div>}</div></section><section className="panel command-panel"><div className="panel-head"><div><p className="eyebrow">FAST PATHS</p><h2>Open a workspace</h2></div></div><div className="quick-links"><Link href="/products">Products <small>SKUs · barcodes · prices</small></Link><Link href="/inventory">Inventory <small>Stock · ledger · counts · transfers</small></Link><Link href="/sales">Sales <small>POS · payments · returns</small></Link><Link href="/accounting">Finance <small>Accounts · journals · reporting</small></Link></div></section></div>
  </AppShell>;
}
