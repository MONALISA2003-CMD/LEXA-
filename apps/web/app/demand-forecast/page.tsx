"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../components/app-shell";
import { getDemandForecast, type DemandForecastItem, type DemandForecastResponse } from "../../lib/demand-forecast-api";
import styles from "./page.module.css";

function units(value: string | number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "Not measurable";
  return Number(value).toLocaleString("en-UG", { maximumFractionDigits: 3 });
}
function backtestLabel(value: string | null) {
  if (value === "BETTER_THAN_LAST_WEEK_BASELINE") return "Better than last-week baseline";
  if (value === "WORSE_THAN_LAST_WEEK_BASELINE") return "Worse than last-week baseline";
  if (value === "TIED_WITH_LAST_WEEK_BASELINE") return "Tied with last-week baseline";
  return "Not comparable yet";
}
function ForecastCard({ item }: { item: DemandForecastItem }) {
  return <article className={styles.card}>
    <div className={styles.cardHead}>
      <div><span className="section-label">{item.sku || "SKU not set"}</span><h3>{item.product_name} · {item.variant_name}</h3></div>
      <span className={`status ${item.status === "available" ? "good" : "warn"}`}>{item.status === "available" ? "Backtest measurable" : "Limited evidence"}</span>
    </div>
    <div className={styles.metrics}>
      <div><span>Total forecast</span><strong>{units(item.total_forecast_units)} units</strong><small>Next {item.horizon_days} days</small></div>
      <div><span>Mean absolute error</span><strong>{units(item.backtest.mae_units)} units</strong><small>{item.backtest.test_days_evaluated}-day rolling-origin holdout</small></div>
      <div><span>WAPE</span><strong>{item.backtest.wape_percent === null ? "Not measurable" : `${units(item.backtest.wape_percent)}%`}</strong><small>Last-week baseline: {item.backtest.last_week_baseline_wape_percent === null ? "not measurable" : `${units(item.backtest.last_week_baseline_wape_percent)}%`}</small></div>
    </div>
    <p className={styles.comparison}>{backtestLabel(item.backtest.comparison_to_baseline)}</p>
    <details className={styles.details}>
      <summary>Daily forecast and historical range</summary>
      <div className={styles.tableWrap}>
        <table>
          <thead><tr><th scope="col">Date</th><th scope="col">Forecast units</th><th scope="col">Historical same-weekday range</th></tr></thead>
          <tbody>{item.forecast.map(day => <tr key={day.date}><td>{day.date}</td><td>{units(day.forecast_units)}</td><td>{units(day.historical_same_weekday_low)} – {units(day.historical_same_weekday_high)}</td></tr>)}</tbody>
        </table>
      </div>
    </details>
    <p className={styles.meta}>Baseline: {item.method}. Active demand on {item.active_demand_days} of {item.history_days} days.</p>
  </article>;
}

export default function DemandForecastPage() {
  const [report, setReport] = useState<DemandForecastResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setReport(await getDemandForecast(14)); }
    catch (cause) { setReport(null); setError(cause instanceof Error ? cause.message : "LEXA couldn't load the demand forecast. Try again."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return <AppShell title="Demand forecast" eyebrow="LEXA intelligence">
    <main className={`workspace ${styles.page}`} style={{ maxWidth: 1240 }}>
      <div className="workspace-header">
        <div><span className="workspace-breadcrumb">LEXA · PREDICTIVE INTELLIGENCE</span><h1>Plan with a view of recorded demand.</h1><p>A transparent weekday-seasonal baseline, checked against a rolling 14-day holdout of historical sales.</p></div>
        <div className="header-actions"><Link href="/inventory" className="button button-soft">Open stock</Link><button className="button button-soft" type="button" onClick={() => void load()} disabled={loading}>{loading ? "Checking…" : "Refresh forecast"}</button></div>
      </div>
      <section className={styles.notice} aria-label="Forecast safety limits">
        <strong>Planning evidence only</strong>
        <p>LEXA does not create purchase orders or change stock from this forecast. Recorded sales can understate demand during stockouts, and the historical range is not a calibrated confidence interval.</p>
      </section>
      {error && <div className="notice notice-error" role="alert">{error}<button className="button button-soft" type="button" onClick={() => void load()} disabled={loading}>Try again</button></div>}
      {loading && <div className="empty-state compact" role="status">Checking the last 56 days of verified analytics history…</div>}
      {!loading && report && <>
        <section className={styles.summary}>
          <div className={styles.summaryHead}><div><span className="section-label">AS OF {report.as_of_date}</span><h2>{report.status === "unavailable" ? "A forecast is not available yet." : report.status === "partial" ? "Some items need more history." : "Forecasts are ready for review."}</h2><p>{report.message}</p><p className={styles.meta}>{report.scope}</p></div><span className={`status ${report.status === "available" ? "good" : report.status === "partial" ? "warn" : "neutral"}`}>{report.status === "available" ? "Available" : report.status === "partial" ? "Partial evidence" : "Unavailable"}</span></div>
          <div className={styles.summaryStats}><div><span>History verified</span><strong>{report.history_coverage_verified ? "Yes" : "No"}</strong><small>{report.history_from_date} – {report.history_to_date}</small></div><div><span>Eligible variants</span><strong>{report.items.length}</strong><small>Up to 30 highest-volume variants</small></div><div><span>Excluded variants</span><strong>{report.excluded_items.length}</strong><small>Insufficient usable history</small></div><div><span>Freshness</span><strong>{report.history_refresh_completed_at ? "Recent" : "Unavailable"}</strong><small>{report.history_refresh_completed_at ? `${report.history_refresh_completed_at.replace("T", " ").slice(0, 16)} UTC` : "No qualifying refresh"}</small></div></div>
        </section>
        {report.items.length > 0 ? <section className="workspace-section"><div className="section-head"><div><span className="section-label">14-DAY BASELINE</span><h2>Product demand forecasts</h2><p>Variants are ranked by recorded units sold in a complete, freshly refreshed 56-day window. WAPE is not shown when holdout demand is zero.</p></div></div><div className={styles.cards}>{report.items.map(item => <ForecastCard key={item.variant_id} item={item} />)}</div></section> : <div className={styles.empty}>No demand forecast was generated. LEXA does not convert absent or stale source data into a zero forecast.</div>}
        {report.excluded_items.length > 0 && <section className="workspace-section"><div className="section-head"><div><span className="section-label">DATA QUALITY</span><h2>Items not forecast</h2><p>These items did not pass the pilot's minimum demand-history requirement.</p></div></div><div className={styles.excluded}>{report.excluded_items.map(item => <article key={`${item.sku}-${item.variant_name}`}><strong>{item.product_name} · {item.variant_name}</strong><span>{item.sku || "No SKU"}</span><p>{item.message}</p></article>)}</div></section>}
        <details className={styles.method}><summary>How this baseline is calculated</summary><ul><li>Requires a successful analytics refresh covering the entire previous 56 days, completed in the last 72 hours.</li><li>Uses the median recorded units for the matching weekday in the previous eight weeks.</li><li>Compares a rolling 14-day holdout against the simple last-week-same-weekday baseline using MAE and WAPE.</li><li>Does not adjust for stockouts, holidays, promotions, branch-level differences or supplier lead times.</li><li>Forecasting is read-only. Replenishment calculations and purchasing workflows remain separate.</li></ul></details>
        <p className={styles.footer}>Source: {report.source_tables.join(", ")}. External AI used: no. Business writes performed: no.</p>
      </>}
    </main>
  </AppShell>;
}
