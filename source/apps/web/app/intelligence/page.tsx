"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../components/app-shell";
import { localDateISO, localMonthStartISO } from "../../lib/date.mjs";
import {
  getAnalyticsOverview,
  getBusinessProfile,
  getInventoryReplenishmentRecommendations,
  getInventorySummary,
  type AnalyticsOverview,
  type BusinessProfile,
  type InventorySummary,
  type ReplenishmentRecommendation,
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
  return reason instanceof Error ? reason.message : "This information could not be loaded. Please try again.";
}

export default function IntelligencePage() {
  const [profile, setProfile] = useState<BusinessProfile | null>(null);
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
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
      try {
        setOverview(await getAnalyticsOverview(localMonthStartISO(), localDateISO(), currentProfile.currency_code));
      } catch (reason) {
        setOverview(null);
        issues.push(`Sales overview: ${safeError(reason)}`);
      }
    } else {
      setOverview(null);
      issues.push("Add your business currency in Settings to see money values correctly.");
    }
    setErrors(issues);
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);
  const currency = profile?.currency_code?.trim().toUpperCase() || null;
  const totals = overview?.totals;
  const orderedRecommendations = [...recommendations].sort((a, b) => Number(b.reorder_quantity) - Number(a.reorder_quantity)).slice(0, 8);

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
        <div className="section-head"><div><span className="section-label">STOCK NEEDS ATTENTION</span><h2>Restock suggestions</h2><p>Suggestions are a guide for your team. They do not place orders automatically.</p></div><Link href="/inventory" className="button button-soft">Review stock</Link></div>
        {loading && <p role="status">Checking stock needs…</p>}
        {!loading && orderedRecommendations.length === 0 && <div className="empty-state compact"><strong>No restock suggestions to show</strong><span>There are no current suggestions, or the stock rules have not been set up yet.</span><Link href="/inventory" className="button button-soft">Open inventory</Link></div>}
        {!loading && orderedRecommendations.length > 0 && <div className="table-wrap"><table><thead><tr><th>Item</th><th>Location</th><th>Available</th><th>Suggested order</th><th>Reason</th></tr></thead><tbody>{orderedRecommendations.map(row => <tr key={`${row.location_id}-${row.variant_id}`}><td><strong>{row.product_name}</strong><small>{row.variant_name}{row.sku ? ` · ${row.sku}` : ""}</small></td><td>{row.location_name}</td><td>{Number(row.available).toLocaleString("en-UG")}</td><td><strong>{Number(row.reorder_quantity).toLocaleString("en-UG")}</strong><small>{formatMoney(row.estimated_reorder_value, currency)}</small></td><td>{row.reason_code.replaceAll("_", " ").toLowerCase()}</td></tr>)}</tbody></table></div>}
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
