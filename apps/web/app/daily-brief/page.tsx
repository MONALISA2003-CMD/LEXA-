"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../components/app-shell";
import { getDailyBrief, type BriefItem, type DailyBrief } from "../../lib/daily-brief-api";
import styles from "./page.module.css";

function money(value: string | number | undefined, currency: string) {
  if (value === undefined || value === null || !Number.isFinite(Number(value))) return "Unavailable";
  try { return new Intl.NumberFormat("en-UG", { style: "currency", currency, maximumFractionDigits: 0 }).format(Number(value)); }
  catch { return `${currency} ${Number(value).toLocaleString("en-UG", { maximumFractionDigits: 0 })}`; }
}
function metric(item: BriefItem, currency: string) {
  if (!item.metric) return null;
  if (item.metric.unit === "money") return money(item.metric.value, item.metric.currency_code || currency);
  if (item.metric.unit === "percent") return `${Number(item.metric.value).toFixed(2)}%`;
  return `${Number(item.metric.value).toLocaleString("en-UG")} ${item.metric.unit === "items" ? "items" : ""}`.trim();
}
function badge(item: BriefItem) {
  if (item.status === "stale") return "Refresh needed";
  if (item.status === "unavailable") return "Unavailable";
  if (item.severity === "critical") return "Urgent review";
  if (item.severity === "attention") return "Needs review";
  if (item.severity === "positive") return "Improved";
  return "For your information";
}
function Card({ item, currency }: { item: BriefItem; currency: string }) {
  return <article className={styles.item}>
    <div className={styles.itemHead}><span className={`status ${item.severity === "critical" ? "bad" : item.severity === "attention" ? "warn" : item.severity === "positive" ? "good" : "neutral"}`}>{badge(item)}</span></div>
    <h3>{item.title}</h3>
    <p>{item.summary}</p>
    {item.metric && <div className={styles.metric}><small>{item.metric.label}</small><strong>{metric(item, currency)}</strong></div>}
    <p className={styles.meta}>Source: {item.evidence.source_tables.join(", ") || "LEXA saved records"} · {item.evidence.record_count} saved rows{item.evidence.as_of_date ? ` · as of ${item.evidence.as_of_date}` : ""}{item.evidence.refreshed_at ? ` · refreshed ${item.evidence.refreshed_at.replace("T", " ").slice(0, 16)}` : ""}</p>
    {item.limitations.slice(0, 2).map(limit => <p className={styles.meta} key={limit}>Limit: {limit}</p>)}
    <div className={styles.links}><Link className="button button-soft button-small" href={item.evidence.href}>{item.evidence.label || item.action_label}</Link><Link className="button button-soft button-small" href={item.action_href}>{item.action_label}</Link></div>
  </article>;
}

export default function DailyBriefPage() {
  const [brief, setBrief] = useState<DailyBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setBrief(await getDailyBrief()); }
    catch (cause) { setBrief(null); setError(cause instanceof Error ? cause.message : "LEXA couldn't load the daily brief. Try again."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return <AppShell title="Daily business brief" eyebrow="LEXA intelligence">
    <main className={`workspace ${styles.page}`} style={{ maxWidth: 1240 }}>
      <div className="workspace-header">
        <div><span className="workspace-breadcrumb">LEXA · BUSINESS INTELLIGENCE</span><h1>Your business, at a glance.</h1><p>A practical summary of what may need attention today, based on the saved records LEXA can verify.</p></div>
        <div className="header-actions"><Link href="/intelligence" className="button button-soft">All business insights</Link><button className="button button-soft" type="button" onClick={() => void load()} disabled={loading}>{loading ? "Refreshing…" : "Refresh brief"}</button></div>
      </div>
      {error && <div className="notice notice-error" role="alert">{error}<p>Missing or stale information is not treated as zero. Your saved business records have not been changed.</p><button type="button" className="button button-soft" onClick={() => void load()} disabled={loading}>Try again</button></div>}
      {loading && <div className="empty-state compact" role="status">Checking sales, stock and recorded balances…</div>}
      {!loading && brief && <>
        <section className={styles.summary} aria-labelledby="brief-headline">
          <div className={styles.summaryHead}><div><span className="section-label">{brief.as_of_date} · {brief.currency_code} · SEVEN-DAY VIEW</span><h2 id="brief-headline">{brief.headline}</h2><p>Reporting period: {brief.period.from_date} – {brief.period.to_date}. This brief uses deterministic rules, not an external AI provider.</p></div><span className={`status ${brief.status === "attention" ? "warn" : brief.status === "partial" || brief.status === "unavailable" ? "neutral" : "good"}`}>{brief.status === "attention" ? "Review needed" : brief.status === "partial" ? "Some data needs checking" : brief.status === "unavailable" ? "Unavailable" : "Ready"}</span></div>
          <div className={styles.counts}>
            <div className={styles.count}><span>Needs review</span><strong>{brief.counts.action_items}</strong></div>
            <div className={styles.count}><span>Information</span><strong>{brief.counts.information_items}</strong></div>
            <div className={styles.count}><span>Data-quality warnings</span><strong>{brief.counts.data_quality_items}</strong></div>
            <div className={styles.count}><span>Insights checked</span><strong>{brief.counts.insights_considered}</strong></div>
          </div>
          {brief.last_successful_refresh_at && <p className={styles.disclaimer}>Last successful analytics refresh: {brief.last_successful_refresh_at.replace("T", " ").slice(0, 16)} UTC.</p>}
        </section>
        <section className={`workspace-section ${styles.section}`} aria-labelledby="brief-actions-title"><div className="section-head"><div><span className="section-label">PRIORITY ITEMS</span><h2 id="brief-actions-title">What to check first</h2><p>These are prompts for your team to review—not automated transactions.</p></div></div>{brief.action_items.length ? <div className={styles.list}>{brief.action_items.map(item => <Card key={item.rule_id} item={item} currency={brief.currency_code} />)}</div> : <div className={styles.empty}>No urgent rule-based alerts were raised from the available source data. This is not a guarantee that every record is correct.</div>}</section>
        <section className={`workspace-section ${styles.section}`} aria-labelledby="brief-info-title"><div className="section-head"><div><span className="section-label">BUSINESS INDICATORS</span><h2 id="brief-info-title">Other useful signals</h2></div></div>{brief.information_items.length ? <div className={styles.list}>{brief.information_items.map(item => <Card key={item.rule_id} item={item} currency={brief.currency_code} />)}</div> : <div className={styles.empty}>No additional confirmed indicators were returned for this period.</div>}</section>
        <section className={`workspace-section ${styles.section}`} aria-labelledby="brief-quality-title"><div className="section-head"><div><span className="section-label">DATA QUALITY</span><h2 id="brief-quality-title">Information that needs a refresh</h2><p>LEXA separates these warnings from the current action list.</p></div></div>{brief.data_quality.length ? <div className={styles.list}>{brief.data_quality.map(item => <Card key={item.rule_id} item={item} currency={brief.currency_code} />)}</div> : <div className={styles.empty}>No stale or unavailable insight was reported by this brief.</div>}</section>
        <p className={styles.disclaimer}>LEXA is a decision-support tool. Review source records before taking action. This brief cannot create a purchase order, post an expense or journal, change stock, initiate a payment, or send business data to a model provider. Missing data is never presented as zero.</p>
      </>}
    </main>
  </AppShell>;
}
