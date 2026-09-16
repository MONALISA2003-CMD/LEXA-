"use client";

import { useEffect, useMemo, useState } from "react";
import { API_URL, getHealth, getReadiness, type ApiHealth, type ApiReadiness } from "../lib/api";

const modules = [
  { name: "Overview", desc: "Business command center", state: "Preview" },
  { name: "Products", desc: "Catalog, variants, SKUs and prices", state: "Built" },
  { name: "Inventory", desc: "Stock ledger, balances and movements", state: "Next" },
  { name: "Sales", desc: "POS, payments and returns", state: "Next" },
  { name: "Purchasing", desc: "Suppliers, orders and receiving", state: "Planned" },
  { name: "Transfers", desc: "Move stock between locations", state: "Planned" },
  { name: "Reports", desc: "Operational and financial analytics", state: "Planned" },
  { name: "LEXA Brain", desc: "Analysis, recommendations and actions", state: "Planned" },
];

const previewProducts = [
  { name: "Samsung Galaxy A-series", sku: "PREVIEW-SKU-001", stock: "—", price: "—" },
  { name: "Tecno smartphone", sku: "PREVIEW-SKU-002", stock: "—", price: "—" },
  { name: "Infinix smartphone", sku: "PREVIEW-SKU-003", stock: "—", price: "—" },
];

export default function HomePage() {
  const [health, setHealth] = useState<ApiHealth | null>(null);
  const [readiness, setReadiness] = useState<ApiReadiness | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState("Overview");

  async function refresh() {
    try {
      const [h, r] = await Promise.all([getHealth(), getReadiness()]);
      setHealth(h);
      setReadiness(r);
      setError(null);
    } catch (err) {
      setHealth(null);
      setReadiness(null);
      setError(err instanceof Error ? err.message : "Unable to reach the LEXA API.");
    }
  }

  useEffect(() => { refresh(); }, []);

  const apiState = useMemo(() => {
    if (health && readiness?.status === "ready") return "Online & ready";
    if (health) return "API online";
    return "Not connected";
  }, [health, readiness]);

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">L</span><div><strong>LEXA</strong><small>Business OS</small></div></div>
        <nav aria-label="Main navigation">
          {modules.map((item) => (
            <button key={item.name} className={`nav-item ${active === item.name ? "active" : ""}`} onClick={() => setActive(item.name)}>
              <span>{item.name}</span><em>{item.state}</em>
            </button>
          ))}
        </nav>
        <div className="sidebar-note"><strong>Implementation mode</strong><p>Core workflows are being built before production login enforcement.</p></div>
      </aside>

      <section className="workspace">
        <header className="topbar"><div><p className="eyebrow">LEXA / {active.toUpperCase()}</p><h1>{active === "Overview" ? "Business command center" : active}</h1></div><button className="refresh" onClick={refresh}>Refresh connection</button></header>

        <div className="connection-strip">
          <span className={`pulse ${health ? "good" : "bad"}`} />
          <div><strong>{apiState}</strong><span>{API_URL || "NEXT_PUBLIC_API_URL is not configured"}</span></div>
          {error && <span className="connection-error">{error}</span>}
        </div>

        {active === "Overview" && <>
          <section className="hero-grid">
            <article className="hero-card"><span className="tag">BUILD PREVIEW</span><h2>From transactions to intelligence.</h2><p>LEXA is being built from the trustworthy transaction layer upward: catalog → inventory → sales → events → analytics → Brain.</p><div className="progress"><span style={{ width: "32%" }} /></div><small>Foundation + catalog in progress · inventory is the next major workflow</small></article>
            <article className="metric-card"><span>API</span><strong>{health ? "Healthy" : "—"}</strong><small>{health?.environment ?? "Waiting for connection"}</small></article>
            <article className="metric-card"><span>DATABASE</span><strong>{readiness?.dependencies?.database === "ok" ? "Ready" : "—"}</strong><small>Render → Neon readiness</small></article>
            <article className="metric-card"><span>REDIS</span><strong>Planned</strong><small>Worker/queue layer</small></article>
          </section>

          <section className="section"><div className="section-head"><div><p className="eyebrow">VISIBLE WORK</p><h2>What you can review now</h2></div><span className="preview-badge">Preview data is clearly marked</span></div>
            <div className="cards-grid">{modules.slice(1, 5).map((item) => <button className="module-card" key={item.name} onClick={() => setActive(item.name)}><div><h3>{item.name}</h3><p>{item.desc}</p></div><span>{item.state}</span></button>)}</div>
          </section>

          <section className="section"><div className="section-head"><div><p className="eyebrow">CATALOG UI</p><h2>Product workspace preview</h2></div></div>
            <div className="table-wrap"><table><thead><tr><th>Product</th><th>SKU</th><th>Inventory</th><th>Price</th></tr></thead><tbody>{previewProducts.map(p => <tr key={p.sku}><td><strong>{p.name}</strong><small>Preview record — not live database data</small></td><td>{p.sku}</td><td>{p.stock}</td><td>{p.price}</td></tr>)}</tbody></table></div>
          </section>
        </>}

        {active !== "Overview" && <section className="module-page"><span className="tag">{modules.find(m => m.name === active)?.state.toUpperCase()}</span><h2>{active}</h2><p>{modules.find(m => m.name === active)?.desc}</p><div className="notice"><strong>This workspace is being implemented.</strong><p>The navigation and visual workflow are now exposed so you can give feedback before we connect the underlying business transactions.</p></div>{active === "Products" && <div className="table-wrap"><table><thead><tr><th>Product</th><th>SKU</th><th>Status</th></tr></thead><tbody>{previewProducts.map(p => <tr key={p.sku}><td>{p.name}</td><td>{p.sku}</td><td><span className="preview-badge">Preview</span></td></tr>)}</tbody></table></div>}</section>}
      </section>
    </main>
  );
}
