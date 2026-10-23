"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../components/app-shell";
import { localDateISO, localMonthStartISO } from "../../lib/date.mjs";
import { resolveBusinessInsightQuestion } from "../../lib/business-insight-question.mjs";
import { buildBusinessInsightAnswer } from "../../lib/business-insight-answer.mjs";
import {
  getAnalyticsOverview,
  getBusinessInsights,
  getBusinessProfile,
  getInventoryReplenishmentRecommendations,
  getInventorySummary,
  type AnalyticsOverview,
  type BusinessInsight,
  type BusinessInsightFocus,
  type BusinessInsightsResponse,
  type BusinessProfile,
  type InventorySummary,
  type ReplenishmentRecommendation,
  userFacingError,
} from "../../lib/api";

function formatMoney(value: string | number | undefined, currency: string | null) {
  const amount = Number(value);
  if (!currency || value === undefined || !Number.isFinite(amount)) return "Unavailable";
  try {
    return new Intl.NumberFormat("en-UG", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
  } catch {
    return `${currency} ${amount.toLocaleString("en-UG", { maximumFractionDigits: 0 })}`;
  }
}

function safeError(reason: unknown) {
  return userFacingError(reason, "This information could not be loaded. Please try again.");
}

function insightStatusLabel(status: BusinessInsight["status"]) {
  const labels: Record<BusinessInsight["status"], string> = {
    available: "Review suggested", partial: "Partial evidence", no_finding: "No flag found",
    unavailable: "Unavailable", stale: "Refresh needed",
  };
  return labels[status];
}

function insightStatusClass(severity: BusinessInsight["severity"]) {
  if (severity === "critical") return "bad";
  if (severity === "attention") return "warn";
  if (severity === "positive") return "good";
  return "neutral";
}

function displayInsightMetric(insight: BusinessInsight, currency: string | null) {
  if (!insight.metric) return "Unavailable";
  if (insight.metric.unit === "money") return formatMoney(insight.metric.value, insight.metric.currency_code || currency);
  if (insight.metric.unit === "percent") return `${Number(insight.metric.value).toFixed(2)}%`;
  return `${Number(insight.metric.value).toLocaleString("en-UG")} ${insight.metric.unit === "items" ? "items" : ""}`.trim();
}

export default function IntelligencePage() {
  const [profile, setProfile] = useState<BusinessProfile | null>(null);
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [businessInsights, setBusinessInsights] = useState<BusinessInsightsResponse | null>(null);
  const [insightFocus, setInsightFocus] = useState<"all" | "sales" | "margin" | "stock" | "balances">("all");
  const [question, setQuestion] = useState("");
  const [questionMessage, setQuestionMessage] = useState("");
  const [questionStatus, setQuestionStatus] = useState<"supported" | "guardrail" | "unsupported" | "">("");
  const [questionFocus, setQuestionFocus] = useState<BusinessInsightFocus | null>(null);
  const [inventory, setInventory] = useState<InventorySummary | null>(null);
  const [recommendations, setRecommendations] = useState<ReplenishmentRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState<string[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setErrors([]);
    const issues: string[] = [];
    const [profileResult, inventoryResult, recommendationsResult] = await Promise.allSettled([
      getBusinessProfile(),
      getInventorySummary(),
      getInventoryReplenishmentRecommendations(),
    ]);

    const currentProfile = profileResult.status === "fulfilled" ? profileResult.value : null;
    setProfile(currentProfile);
    if (profileResult.status === "rejected") issues.push(`Business details: ${safeError(profileResult.reason)}`);

    if (inventoryResult.status === "fulfilled") setInventory(inventoryResult.value);
    else { setInventory(null); issues.push(`Stock overview: ${safeError(inventoryResult.reason)}`); }

    if (recommendationsResult.status === "fulfilled") setRecommendations(recommendationsResult.value.items ?? []);
    else { setRecommendations([]); issues.push(`Restock suggestions: ${safeError(recommendationsResult.reason)}`); }

    if (currentProfile?.currency_code && /^[A-Z]{3}$/.test(currentProfile.currency_code)) {
      const fromDate = localMonthStartISO();
      const toDate = localDateISO();
      const [overviewResult, insightsResult] = await Promise.allSettled([
        getAnalyticsOverview(fromDate, toDate, currentProfile.currency_code),
        getBusinessInsights(fromDate, toDate, currentProfile.currency_code),
      ]);
      if (overviewResult.status === "fulfilled") setOverview(overviewResult.value);
      else { setOverview(null); issues.push(`Sales overview: ${safeError(overviewResult.reason)}`); }
      if (insightsResult.status === "fulfilled") setBusinessInsights(insightsResult.value);
      else { setBusinessInsights(null); issues.push(`Business insights: ${safeError(insightsResult.reason)}`); }
    } else {
      setOverview(null);
      setBusinessInsights(null);
      issues.push("Add your business currency in Settings to see money values correctly.");
    }
    setErrors(issues);
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);
  const currency = profile?.currency_code?.trim().toUpperCase() || null;
  const totals = overview?.totals;
  const orderedRecommendations = [...recommendations].sort((a, b) => Number(b.reorder_quantity) - Number(a.reorder_quantity)).slice(0, 8);
  const visibleInsights = (businessInsights?.insights ?? []).filter((item) => {
    if (insightFocus === "all") return true;
    if (insightFocus === "sales") return item.id === "sales-movement";
    if (insightFocus === "margin") return item.id === "gross-margin-movement";
    if (insightFocus === "stock") return item.id === "stock-risk";
    return item.id === "working-capital-balances";
  });
  const questionAnswer = questionStatus === "supported" && questionFocus && businessInsights && !loading
    ? buildBusinessInsightAnswer(questionFocus, businessInsights.insights)
    : null;

  return <AppShell title="Business insights" eyebrow="Helpful next steps">
    <main className="workspace" style={{ maxWidth: 1400 }}>
      <div className="workspace-header">
        <div>
          <span className="workspace-breadcrumb">LEXA · YOUR BUSINESS</span>
          <h1>Business insights</h1>
          <p>A clear view of sales, stock and items that may need attention, using the latest saved records.</p>
        </div>
        <div className="header-actions">
          <Link href="/reports" className="button button-soft">Open reports</Link>
          <button type="button" className="button button-soft" onClick={() => void load()} disabled={loading}>{loading ? "Updating…" : "Refresh"}</button>
        </div>
      </div>

      {errors.length > 0 && <div className="notice notice-error" role="status"><strong>Some information is unavailable.</strong><ul>{errors.map(issue => <li key={issue}>{issue}</li>)}</ul><button type="button" className="button button-soft" onClick={() => void load()} disabled={loading}>Try again</button></div>}

      <div className="metric-strip">
        <div><span>Net sales this month</span><strong>{loading ? "Loading…" : formatMoney(totals?.net_sales, currency)}</strong><small>{overview ? `${overview.from_date} – ${overview.to_date}` : "No confirmed figure available"}</small></div>
        <div><span>Payments collected</span><strong>{loading ? "Loading…" : formatMoney(totals?.payments_collected, currency)}</strong><small>For the current month</small></div>
        <div><span>Low-stock items</span><strong>{loading ? "Loading…" : inventory ? inventory.low_stock_rows.toLocaleString() : "Unavailable"}</strong><small>Based on current stock records</small></div>
        <div><span>Out of stock</span><strong>{loading ? "Loading…" : inventory ? inventory.out_of_stock_rows.toLocaleString() : "Unavailable"}</strong><small>Items with no available stock</small></div>
      </div>


      <section className="workspace-section">
        <div className="section-head"><div><span className="section-label">EXPLAINABLE · READ-ONLY</span><h2>What may need your attention?</h2><p>These checks use saved LEXA records and visible rules. They are prompts for review, not predictions or automatic actions.</p></div><Link href="/reports" className="button button-soft">Open source reports</Link></div>
        {businessInsights?.last_successful_refresh_at && <p className="muted">Last successful analytics refresh: {businessInsights.last_successful_refresh_at.replace("T", " ").slice(0, 16)} UTC · {businessInsights.currency_code} · {businessInsights.period.from_date} – {businessInsights.period.to_date}</p>}
        <form className="insight-question" onSubmit={(event) => {
          event.preventDefault();
          const result = resolveBusinessInsightQuestion(question);
          setQuestionMessage(result.message);
          setQuestionStatus(result.status);
          setQuestionFocus(result.focus);
          setInsightFocus(result.focus ?? "all");
        }}>
          <label htmlFor="business-insight-question">Ask about your saved business figures</label>
          <div className="insight-question-row">
            <input id="business-insight-question" type="text" value={question} onChange={(event) => { setQuestion(event.target.value); setQuestionMessage(""); setQuestionStatus(""); setQuestionFocus(null); setInsightFocus("all"); }} maxLength={240} placeholder="e.g. Why did sales change? Is stock running low?" aria-describedby="business-insight-question-help" />
            <button type="submit" className="button button-dark">Answer</button>
          </div>
          <small id="business-insight-question-help">Supported now: sales movement, gross margin, stock risk, current receivables and supplier balances. Answers use local rules and saved metrics; this question is not sent to an AI provider.</small>
          {questionMessage && <p className={`insight-question-message ${questionStatus === "guardrail" || questionStatus === "unsupported" ? "is-warning" : ""}`} role="status">{questionMessage}</p>}
        </form>
        {questionStatus === "supported" && questionFocus && <section className="insight-answer" aria-labelledby="insight-answer-title" aria-live="polite" aria-atomic="true">
          {loading ? <p role="status">Checking the saved figures for your answer…</p> : !businessInsights ? <><h3 id="insight-answer-title">Answer unavailable</h3><p>LEXA could not verify the saved insight data just now. Refresh the page data before relying on a figure; missing information is not zero.</p></> : questionAnswer ? <>
            <div className="insight-answer-head"><div><span className="section-label">ANSWER FROM SAVED RECORDS</span><h3 id="insight-answer-title">{questionAnswer.title}</h3></div><span className={`status ${questionAnswer.insight ? insightStatusClass(questionAnswer.insight.severity) : "neutral"}`}>{questionAnswer.insight ? insightStatusLabel(questionAnswer.insight.status) : "Overview"}</span></div>
            <p className="insight-answer-summary">{questionAnswer.summary}</p>
            {questionAnswer.insight?.metric && <div className="insight-answer-metric"><small>{questionAnswer.insight.metric.label}</small><strong>{displayInsightMetric(questionAnswer.insight, currency)}</strong></div>}
            {questionAnswer.insight?.comparison && <p className="insight-answer-comparison"><strong>{questionAnswer.insight.comparison.label}:</strong> {questionAnswer.insight.comparison.unit === "money" ? formatMoney(questionAnswer.insight.comparison.previous_value, currency) : `${questionAnswer.insight.comparison.previous_value}${questionAnswer.insight.comparison.unit === "percentage_points" ? "%" : ""}`} previous value · Change {questionAnswer.insight.comparison.unit === "money" ? formatMoney(questionAnswer.insight.comparison.change_value, currency) : `${Number(questionAnswer.insight.comparison.change_value) > 0 ? "+" : ""}${questionAnswer.insight.comparison.change_value}${questionAnswer.insight.comparison.unit === "percentage_points" ? " percentage points" : ""}`}{questionAnswer.insight.comparison.change_percent !== null ? ` (${Number(questionAnswer.insight.comparison.change_percent) > 0 ? "+" : ""}${questionAnswer.insight.comparison.change_percent}%)` : ""}</p>}
            {questionAnswer.insight && <div className="insight-answer-footnote"><p><strong>Period:</strong> {questionAnswer.insight.period.from_date} – {questionAnswer.insight.period.to_date}</p><p><strong>Source:</strong> {questionAnswer.insight.source.tables.join(", ")} · {questionAnswer.insight.source.record_count} saved rows{questionAnswer.insight.source.as_of_date ? ` · as of ${questionAnswer.insight.source.as_of_date}` : ""}{questionAnswer.insight.source.refreshed_at ? ` · refreshed ${questionAnswer.insight.source.refreshed_at.replace("T", " ").slice(0, 16)}` : ""}</p><p><strong>Calculation:</strong> {questionAnswer.insight.methodology}</p>{questionAnswer.insight.limitations.slice(0, 2).map(limit => <p key={limit}><strong>Limit:</strong> {limit}</p>)}<Link className="button button-soft button-small" href={questionAnswer.insight.evidence.href}>{questionAnswer.insight.evidence.label}</Link></div>}
            {questionAnswer.state === "overview" && <p className="insight-answer-footnote">Reporting period: {businessInsights.period.from_date} – {businessInsights.period.to_date} · Currency: {businessInsights.currency_code}{businessInsights.last_successful_refresh_at ? ` · Last successful refresh ${businessInsights.last_successful_refresh_at.replace("T", " ").slice(0, 16)} UTC` : " · Refresh time unavailable"}</p>}
          </> : <p>No answer could be assembled from the saved response. LEXA has not substituted zero for missing information.</p>}
        </section>}
        {businessInsights && <div className="filter-row" role="group" aria-label="Filter business insights">
          {[{id:"all",label:"All insights"},{id:"sales",label:"Sales movement"},{id:"margin",label:"Gross margin"},{id:"stock",label:"Stock risk"},{id:"balances",label:"Customer & supplier balances"}].map(option => <button key={option.id} type="button" className={`button button-small ${insightFocus===option.id?"button-dark":"button-soft"}`} aria-pressed={insightFocus===option.id} onClick={()=>setInsightFocus(option.id as typeof insightFocus)}>{option.label}</button>)}
        </div>}
        {!businessInsights && !loading && <div className="empty-state compact"><strong>Business insights are unavailable</strong><span>LEXA could not verify the saved reporting data. Open the underlying reports and try again after analytics has refreshed.</span><button type="button" className="button button-soft" onClick={()=>void load()} disabled={loading}>Try again</button></div>}
        {loading && <p role="status">Checking saved sales, cost and stock records…</p>}
        {!loading && businessInsights && visibleInsights.length === 0 && <div className="empty-state compact"><strong>No insight for this filter</strong><span>Choose another question or review the saved reports.</span></div>}
        {!loading && businessInsights && visibleInsights.length > 0 && <div className="foundation-grid">
          {visibleInsights.map(item => <article key={item.id} className="panel foundation-panel">
            <div className="panel-head"><div><span className={`status ${insightStatusClass(item.severity)}`}>{insightStatusLabel(item.status)}</span><h3>{item.title}</h3></div></div>
            <p>{item.summary}</p>
            {item.metric && <div className="insight-value"><small>{item.metric.label}</small><strong>{displayInsightMetric(item, currency)}</strong></div>}
            {item.comparison && <p className="muted">Previous period: {item.comparison.unit === "money" ? formatMoney(item.comparison.previous_value, currency) : `${item.comparison.previous_value}${item.comparison.unit === "percentage_points" ? "%" : ""}`} · Change: {item.comparison.unit === "money" ? formatMoney(item.comparison.change_value, currency) : `${Number(item.comparison.change_value)>0?"+":""}${item.comparison.change_value}${item.comparison.unit === "percentage_points" ? " percentage points" : ""}`}{item.comparison.change_percent !== null ? ` (${Number(item.comparison.change_percent)>0?"+":""}${item.comparison.change_percent}%)` : ""}</p>}
            {item.details && item.id === "stock-risk" && <p className="muted">Out of stock: {item.details.out_of_stock ?? "—"} · Low cover: {item.details.low_cover ?? "—"} · No sales in 30 days: {item.details.slow_moving ?? "—"}</p>}
            {item.details && item.id === "working-capital-balances" && <p className="muted">Customer receivables: {formatMoney(item.details.customer_receivables, currency)} · Past due: {formatMoney(item.details.overdue_receivables, currency)} · Supplier payables: {formatMoney(item.details.supplier_payables, currency)} · Supplier credits: {formatMoney(item.details.supplier_credit, currency)}</p>}
            {item.examples && item.examples.length > 0 && <ul>{item.examples.slice(0,3).map(example => <li key={`${example.location_id}-${example.variant_id}`}>{example.product_name} · {example.variant_name} ({example.location_name}): available {Number(example.available).toLocaleString("en-UG")}{example.days_cover !== null ? `, ${Number(example.days_cover).toFixed(1)} days of cover` : ", days of cover unavailable"}</li>)}</ul>}
            <p className="muted"><strong>How it is calculated:</strong> {item.methodology}</p>
            <p className="muted"><strong>Source:</strong> {item.source.tables.join(", ")} · {item.source.record_count} saved rows{item.source.as_of_date ? ` · as of ${item.source.as_of_date}` : ""}{item.source.refreshed_at ? ` · refreshed ${item.source.refreshed_at.replace("T", " ").slice(0, 16)}` : ""}</p>
            {item.limitations.map(limit => <p className="muted" key={limit}>Limit: {limit}</p>)}
            <div className="insight-evidence-links"><Link href={item.evidence.href} className="button button-soft button-small">{item.evidence.label}</Link>{item.evidence_links?.map(link => <Link key={`${item.id}-${link.href}`} href={link.href} className="button button-soft button-small">{link.label}</Link>)}</div>
          </article>)}
        </div>}
        <p className="muted">This view uses deterministic rules only. No external AI provider receives customer or business records, and none of these insights can post a transaction, adjust stock or create a purchase order.</p>
      </section>

      <section className="workspace-section">
        <div className="section-head"><div><span className="section-label">STOCK NEEDS ATTENTION</span><h2>Restock suggestions</h2><p>Suggestions are a guide for your team. They do not place orders automatically.</p></div><Link href="/inventory" className="button button-soft">Review stock</Link></div>
        {loading && <p role="status">Checking stock needs…</p>}
        {!loading && orderedRecommendations.length === 0 && <div className="empty-state compact"><strong>No restock suggestions to show</strong><span>There are no current suggestions, or the stock rules have not been set up yet.</span><Link href="/inventory" className="button button-soft">Open inventory</Link></div>}
        {!loading && orderedRecommendations.length > 0 && <div className="table-wrap"><table><thead><tr><th>Item</th><th>Location</th><th>In stock</th><th>Suggested restock</th><th>Why this is suggested</th></tr></thead><tbody>{orderedRecommendations.map(row => <tr key={`${row.location_id}-${row.variant_id}`}><td><strong>{row.product_name}</strong><small>{row.variant_name}{row.sku ? ` · Code ${row.sku}` : ""}</small></td><td>{row.location_name}</td><td>{Number(row.available).toLocaleString("en-UG")}</td><td><strong>{Number(row.reorder_quantity).toLocaleString("en-UG")}</strong><small>{formatMoney(row.estimated_reorder_value, currency)}</small></td><td>{row.reason_code.replaceAll("_", " ").toLowerCase()}</td></tr>)}</tbody></table></div>}
      </section>

      <section className="workspace-section">
        <div className="section-head"><div><span className="section-label">QUICK ACTIONS</span><h2>Where to go next</h2><p>Open the part of LEXA that can help you act on what you see.</p></div></div>
        <div className="foundation-grid">
          <Link className="panel foundation-panel" href="/sales"><div className="panel-head"><div><h2>Record a sale</h2><p>Serve customers and record payments.</p></div><span aria-hidden="true">→</span></div></Link>
          <Link className="panel foundation-panel" href="/purchasing"><div className="panel-head"><div><h2>Manage suppliers</h2><p>Review purchase orders, deliveries and supplier balances.</p></div><span aria-hidden="true">→</span></div></Link>
          <Link className="panel foundation-panel" href="/reports"><div className="panel-head"><div><h2>View reports</h2><p>Explore sales, customers and stock performance.</p></div><span aria-hidden="true">→</span></div></Link>
        </div>
      </section>
    </main>
  </AppShell>;
}
