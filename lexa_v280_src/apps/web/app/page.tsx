"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AppShell } from "../components/app-shell";
import {
  getAnalyticsOverview, getCommerceDashboard, getInventoryBalances, getAdjustments, getStockCounts, getTransfers,
  getReadiness, type AnalyticsOverview, type CommerceDashboard, type InventoryAdjustment, type InventoryBalance,
  type StockCount, type Transfer,
} from "../lib/api";

const today = () => new Date().toISOString().slice(0, 10);
const monthStart = () => { const d = new Date(); d.setDate(1); return d.toISOString().slice(0, 10); };
const money = (value: string | number) => new Intl.NumberFormat("en-UG", { style: "currency", currency: "UGX", maximumFractionDigits: 0 }).format(Number(value));
const short = (id: string) => `${id.slice(0, 8)}…`;

export default function HomePage() {
  const [dashboard, setDashboard] = useState<CommerceDashboard | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [balances, setBalances] = useState<InventoryBalance[]>([]);
  const [adjustments, setAdjustments] = useState<InventoryAdjustment[]>([]);
  const [counts, setCounts] = useState<StockCount[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [readiness, setReadiness] = useState("checking");
  const [busy, setBusy] = useState(true);
  const [message, setMessage] = useState("");

  async function load() {
    setBusy(true); setMessage("");
    try {
      const [d, a, b, adj, cnt, tr, r] = await Promise.all([
        getCommerceDashboard(today()), getAnalyticsOverview(monthStart(), today()), getInventoryBalances(),
        getAdjustments(), getStockCounts(), getTransfers(), getReadiness(),
      ]);
      setDashboard(d); setAnalytics(a); setBalances(b); setAdjustments(adj); setCounts(cnt); setTransfers(tr); setReadiness(r.status);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to load the Command Centre."); }
    finally { setBusy(false); }
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
    { label:"Stock counts in progress", value:counts.filter(x => x.status === "COUNTING").length, href:"/inventory" },
    { label:"Transfers awaiting action", value:transfers.filter(x => ["DRAFT","APPROVED","DISPATCHED","PARTIALLY_RECEIVED","RECEIVED"].includes(x.status)).length, href:"/inventory" },
    { label:"Open receivables", value:dashboard?.outstanding_receivables ? money(dashboard.outstanding_receivables) : "—", href:"/sales" },
  ];

  return <AppShell title="Command Centre" eyebrow="Today">
    <div className="command-toolbar"><div><strong>What is happening in the business right now?</strong><span>Authoritative operational state with a light intelligence layer on top.</span></div><div className="toolbar-actions"><button className="button button-soft" onClick={() => void load()} disabled={busy}>Refresh</button><Link href="/sales" className="button button-dark">+ Create sale</Link></div></div>
    {message && <div className="notice notice-error">{message}</div>}

    <section className="home-status-row"><span className={`status ${readiness === "ready" || readiness === "ok" ? "good" : "warn"}`}>● {readiness === "ready" || readiness === "ok" ? "Workspace ready" : "Dependency attention"}</span><span>Today · {today()}</span></section>

    <div className="command-kpis">
      <div className="command-kpi"><span>Today's sales</span><strong>{busy ? "—" : money(dashboard?.sales.sales || 0)}</strong><small>{busy ? "Loading authoritative state" : dashboard?.sales.credit ? `Credit ${money(dashboard.sales.credit)}` : "Completed sales"}</small></div>
      <div className="command-kpi"><span>Collected</span><strong>{busy ? "—" : money(dashboard?.sales.collected || 0)}</strong><small>{busy ? "Loading authoritative state" : "Recorded payments"}</small></div>
      <div className="command-kpi"><span>Month-to-date net sales</span><strong>{busy ? "—" : money(analytics?.totals.net_sales || 0)}</strong><small>{busy ? "Loading authoritative state" : `${analytics?.totals.sale_count || 0} completed sales`}</small></div>
      <div className="command-kpi"><span>Inventory value</span><strong>{busy ? "—" : money(balances.reduce((sum, row) => sum + Number(row.stock_value), 0))}</strong><small>{busy ? "Loading authoritative state" : `${balances.length} balance rows`}</small></div>
    </div>

    <div className="command-grid">
      <section className="panel command-panel"><div className="panel-head"><div><p className="eyebrow">NEEDS ATTENTION</p><h2>Actions worth opening now</h2></div><Link href="/inventory" className="panel-link">Open inventory →</Link></div><div className="attention-list">{busy ? <div className="loading-placeholder">Loading operational exceptions…</div> : attention.length ? attention.map((item, i) => <Link href={item.href} className="attention-row" key={`${item.title}-${i}`}><span className={`attention-dot ${item.tone}`}/><div><strong>{item.title}</strong><small>{item.detail}</small></div><span>›</span></Link>) : <div className="empty-state compact"><strong>Nothing urgent</strong><span>LEXA has no immediate operational exceptions in the loaded workspace.</span></div>}</div></section>
      <section className="panel command-panel"><div className="panel-head"><div><p className="eyebrow">TODAY'S WORK</p><h2>Operational queue</h2></div></div><div className="work-list">{openWork.map(item=><Link className="work-card" href={item.href} key={item.label}><strong>{busy ? "—" : item.value}</strong><span>{item.label}</span><small>Open →</small></Link>)}</div></section>
    </div>

    <div className="command-grid"><section className="panel command-panel"><div className="panel-head"><div><p className="eyebrow">BUSINESS SIGNAL</p><h2>Daily movement</h2></div><Link href="/reports" className="panel-link">Reports →</Link></div><div className="signal-grid">{busy ? <div className="loading-placeholder">Loading business movement…</div> : analytics?.daily.slice(-7).map(day=><div className="signal-row" key={day.business_date}><span>{day.business_date}</span><strong>{money(day.net_sales)}</strong><small>{money(day.payments_collected)} collected</small></div>)}</div></section><section className="panel command-panel"><div className="panel-head"><div><p className="eyebrow">FAST PATHS</p><h2>Open a workspace</h2></div></div><div className="quick-links"><Link href="/products">Products <small>SKUs · barcodes · prices</small></Link><Link href="/inventory">Inventory <small>Stock · ledger · counts · transfers</small></Link><Link href="/sales">Sales <small>POS · payments · returns</small></Link><Link href="/accounting">Finance <small>Accounts · journals · reporting</small></Link></div></section></div>
  </AppShell>;
}