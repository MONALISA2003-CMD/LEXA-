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
    <p className={styles.meta}>Based on {item.evidence.record_count} saved {item.evidence.record_count === 1 ? "record" : "records"}{item.evidence.as_of_date ? ` · information through ${item.evidence.as_of_date}` : ""}{item.evidence.refreshed_at ? ` · last updated ${item.evidence.refreshed_at.replace("T", " ").slice(0, 16)}` : ""}.</p>
    {item.limitations.slice(0, 2).map(limit => <p className={styles.meta} key={limit}>Note: {limit}</p>)}
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
    catch (cause) { setBrief(null); setError(cause instanceof Error ? cause.message : "LEXA couldn't load the daily overview. Check your business details and try again."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return <AppShell title="Daily overview" eyebrow="BUSINESS OVERVIEW">
    <main className={`workspace ${styles.page}`} style={{ maxWidth: 1240 }}>
      <div className="workspace-header">
        <div><span className="workspace-breadcrumb">LEXA · BUSINESS OVERVIEW</span><h1>Your business, at a glance.</h1><p>A practical summary of what may need attention today, based on the saved records LEXA can verify.</p></div>
        <div className="header-actions"><Link href="/intelligence" className="button button-soft">Other business insights</Link><button className="button button-soft" type="button" onClick={() => void load()} disabled={loading}>{loading ? "Refreshing…" : "Refresh overview"}</button></div>
      </div>
      {error && <div className="notice notice-error" role="alert">{error}<p>Missing or stale information is not treated as zero. Your saved business records have not been changed.</p><button type="button" className="button button-soft" onClick={() => void load()} disabled={loading}>Try again</button></div>}
      {loading && <div className="empty-state compact" role="status">Checking sales, stock and recorded balances…</div>}
      {!loading && brief && <>
        <section className={styles.summary} aria-labelledby="brief-headline">
          <div className={styles.summaryHead}><div><span className="section-label">{brief.as_of_date} · {brief.currency_code} · SEVEN-DAY VIEW</span><h2 id="brief-headline">{brief.headline}</h2><p>Reporting period: {brief.period.from_date} – {brief.period.to_date}. This overview is based on the business records available to LEXA.</p></div><span className={`status ${brief.status === "attention" ? "warn" : brief.status === "partial" || brief.status === "unavailable" ? "neutral" : "good"}`}>{brief.status === "attention" ? "Review needed" : brief.status === "partial" ? "Some data needs checking" : brief.status === "unavailable" ? "Unavailable" : "Ready"}</span></div>
          <div className={styles.counts}>
            <div className={styles.count}><span>Needs review</span><strong>{brief.counts.action_items}</strong></div>
            <div className={styles.count}><span>Information</span><strong>{brief.counts.information_items}</strong></div>
            <div className={styles.count}><span>Information to check</span><strong>{brief.counts.data_quality_items}</strong></div>
            <div className={styles.count}><span>Checks completed</span><strong>{brief.counts.insights_considered}</strong></div>
          </div>
          {brief.last_successful_refresh_at && <p className={styles.disclaimer}>Last updated: {new Date(brief.last_successful_refresh_at).toLocaleString("en-UG", { dateStyle: "medium", timeStyle: "short" })}.</p>}
        </section>
        <section className={`workspace-section ${styles.section}`} aria-labelledby="brief-actions-title"><div className="section-head"><div><span className="section-label">ITEMS TO REVIEW</span><h2 id="brief-actions-title">What to check first</h2><p>These are prompts for your team to review—not automated transactions.</p></div></div>{brief.action_items.length ? <div className={styles.list}>{brief.action_items.map(item => <Card key={item.rule_id} item={item} currency={brief.currency_code} />)}</div> : <div className={styles.empty}>No urgent issues were found in the records available for this period. Check the original records when you need to confirm a detail.</div>}</section>
        <section className={`workspace-section ${styles.section}`} aria-labelledby="brief-info-title"><div className="section-head"><div><span className="section-label">BUSINESS INDICATORS</span><h2 id="brief-info-title">Other useful signals</h2></div></div>{brief.information_items.length ? <div className={styles.list}>{brief.information_items.map(item => <Card key={item.rule_id} item={item} currency={brief.currency_code} />)}</div> : <div className={styles.empty}>There are no other confirmed business updates for this period.</div>}</section>
        <section className={`workspace-section ${styles.section}`} aria-labelledby="brief-quality-title"><div className="section-head"><div><span className="section-label">INFORMATION QUALITY</span><h2 id="brief-quality-title">Information to check or update</h2><p>These items are shown separately from the tasks that may need your attention.</p></div></div>{brief.data_quality.length ? <div className={styles.list}>{brief.data_quality.map(item => <Card key={item.rule_id} item={item} currency={brief.currency_code} />)}</div> : <div className={styles.empty}>No outdated or unavailable information was reported.</div>}</section>
        <p className={styles.disclaimer}>Use this overview to guide your next steps, then check the original business records before acting. This page does not create orders, record expenses, change stock or make payments. Missing information is never treated as zero.</p>
      </>}
    </main>
  </AppShell>;
}
