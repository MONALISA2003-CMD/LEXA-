"use client";

import { useEffect, useMemo, useState } from "react";
import { getHealth, getProducts, getReadiness, login, register, type ApiHealth, type ApiReadiness, type Product } from "../lib/api";

const modules = [
  { name: "Overview", desc: "Business command center" },
  { name: "Products", desc: "Catalog, variants, SKUs and prices" },
  { name: "Inventory", desc: "Stock ledger, balances and movements" },
  { name: "Sales", desc: "POS, payments and returns" },
  { name: "Purchasing", desc: "Suppliers, orders and receiving" },
  { name: "Transfers", desc: "Move stock between locations" },
  { name: "Reports", desc: "Operational and financial analytics" },
  { name: "LEXA Brain", desc: "Analysis, recommendations and controlled actions" },
];

export default function HomePage() {
  const [health, setHealth] = useState<ApiHealth | null>(null);
  const [readiness, setReadiness] = useState<ApiReadiness | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState("Overview");
  const [products, setProducts] = useState<Product[]>([]);
  const [query, setQuery] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authError, setAuthError] = useState<string | null>(null);
  const [authBusy, setAuthBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [tenantId, setTenantId] = useState("");
  const [tenantName, setTenantName] = useState("");

  async function refresh() {
    try {
      const [h, r] = await Promise.all([getHealth(), getReadiness()]);
      setHealth(h); setReadiness(r); setError(null);
    } catch (err) {
      setHealth(null); setReadiness(null);
      setError(err instanceof Error ? err.message : "Unable to reach the LEXA API.");
    }
  }

  async function loadProducts(search = query) {
    if (!token) return;
    try {
      const page = await getProducts(search, undefined);
      setProducts(page.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load products.");
    }
  }

  useEffect(() => { refresh(); const saved = window.sessionStorage.getItem("lexa_access_token"); if (saved) setToken(saved); }, []);
  useEffect(() => { if (token && active === "Products") loadProducts(); }, [token, active]);

  const apiState = useMemo(() => {
    if (health && readiness?.status === "ready") return "Online & database ready";
    if (health) return "API online";
    return "Not connected";
  }, [health, readiness]);

  async function submitAuth(event: React.FormEvent) {
    event.preventDefault(); setAuthError(null); setAuthBusy(true);
    try {
      if (authMode === "register") {
        const created = await register({ email, password, tenant_name: tenantName });
        setTenantId(created.tenant_id);
        const session = await login({ email, password, tenant_id: created.tenant_id });
        window.sessionStorage.setItem("lexa_access_token", session.access_token);
        setToken(session.access_token); setAuthOpen(false);
      } else {
        const session = await login({ email, password, tenant_id: tenantId });
        window.sessionStorage.setItem("lexa_access_token", session.access_token);
        setToken(session.access_token); setAuthOpen(false);
      }
    } catch (err) { setAuthError(err instanceof Error ? err.message : "Authentication failed."); }
    finally { setAuthBusy(false); }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">L</span><div><strong>LEXA</strong><small>Business Operating System</small></div></div>
        <nav aria-label="Main navigation">{modules.map(item => <button key={item.name} className={`nav-item ${active === item.name ? "active" : ""}`} onClick={() => setActive(item.name)}><span>{item.name}</span></button>)}</nav>
        <div className="sidebar-note"><strong>Production architecture</strong><p>Tenant-aware transactions, PostgreSQL source of truth, auditable workflows and controlled automation.</p></div>
      </aside>

      <section className="workspace">
        <header className="topbar"><div><p className="eyebrow">LEXA / {active.toUpperCase()}</p><h1>{active === "Overview" ? "Business command center" : active}</h1></div><div className="top-actions"><button className="secondary" onClick={refresh}>Refresh</button><button className="primary" onClick={() => setAuthOpen(true)}>{token ? "Workspace session" : "Sign in"}</button></div></header>

        <div className="connection-strip"><span className={`pulse ${health ? "good" : "bad"}`} /><div><strong>{apiState}</strong><span>Frontend proxy → Render API → Neon PostgreSQL</span></div>{error && <span className="connection-error">{error}</span>}</div>

        {active === "Overview" && <>
          <section className="hero-grid">
            <article className="hero-card"><span className="tag">LIVE SYSTEM</span><h2>Operate the business. Then let intelligence build on the truth.</h2><p>LEXA is a multi-purpose, multi-tenant operating system. Different businesses and unrelated product categories use the same reliable transaction foundation without sharing tenant data.</p><div className="architecture"><span>Catalog</span><b>→</b><span>Inventory</span><b>→</b><span>Sales</span><b>→</b><span>Events</span><b>→</b><span>Analytics</span><b>→</b><span>Brain</span></div></article>
            <article className="metric-card"><span>API</span><strong>{health ? "Healthy" : "Offline"}</strong><small>{health?.environment ?? "Connection unavailable"}</small></article>
            <article className="metric-card"><span>DATABASE</span><strong>{readiness?.dependencies?.database === "ok" ? "Ready" : "Unavailable"}</strong><small>Render → Neon</small></article>
            <article className="metric-card"><span>SESSION</span><strong>{token ? "Authenticated" : "Not signed in"}</strong><small>Tenant workspace access</small></article>
          </section>

          <section className="section"><div className="section-head"><div><p className="eyebrow">OPERATING MODULES</p><h2>Workspaces</h2></div></div><div className="cards-grid">{modules.slice(1).map(item => <button className="module-card" key={item.name} onClick={() => setActive(item.name)}><h3>{item.name}</h3><p>{item.desc}</p><span>Open workspace →</span></button>)}</div></section>
        </>}

        {active === "Products" && <section className="section"><div className="section-head"><div><p className="eyebrow">CATALOG</p><h2>Products</h2><p className="section-sub">Live tenant catalog from the LEXA API.</p></div><div className="search"><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search products" /><button onClick={() => loadProducts()}>Search</button></div></div>{!token ? <div className="empty"><strong>Sign in to access your tenant catalog.</strong><p>Products are never shown from invented demo records. Once authenticated, this screen reads the tenant's actual catalog.</p><button className="primary" onClick={() => setAuthOpen(true)}>Sign in</button></div> : <div className="table-wrap"><table><thead><tr><th>Product</th><th>Type</th><th>Status</th><th>Variants</th></tr></thead><tbody>{products.length ? products.map(p => <tr key={p.id}><td><strong>{p.name}</strong><small>{p.description || "No description"}</small></td><td>{p.product_type}</td><td>{p.status}</td><td>{p.has_variants ? "Yes" : "No"}</td></tr>) : <tr><td colSpan={4}><div className="empty-inline">No products found in this tenant.</div></td></tr>}</tbody></table></div>}</section>}

        {active !== "Overview" && active !== "Products" && <section className="module-page"><span className="tag">WORKSPACE</span><h2>{active}</h2><p>{modules.find(m => m.name === active)?.desc}</p><div className="notice"><strong>This is a real LEXA workspace boundary.</strong><p>The module will connect to its transactional API as that domain is implemented. No fake business records are presented as live data.</p></div></section>}
      </section>

      {authOpen && <div className="modal-backdrop" onClick={() => setAuthOpen(false)}><div className="modal" onClick={e => e.stopPropagation()}><div className="modal-head"><div><p className="eyebrow">WORKSPACE ACCESS</p><h2>{authMode === "login" ? "Sign in to LEXA" : "Create a LEXA workspace"}</h2></div><button className="close" onClick={() => setAuthOpen(false)}>×</button></div><div className="tabs"><button className={authMode === "login" ? "selected" : ""} onClick={() => setAuthMode("login")}>Sign in</button><button className={authMode === "register" ? "selected" : ""} onClick={() => setAuthMode("register")}>Create workspace</button></div><form onSubmit={submitAuth}><label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} required /></label><label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} minLength={12} required /><small>Minimum 12 characters.</small></label>{authMode === "register" ? <label>Business / workspace name<input value={tenantName} onChange={e => setTenantName(e.target.value)} required /></label> : <label>Tenant ID<input value={tenantId} onChange={e => setTenantId(e.target.value)} placeholder="Your tenant UUID" required /></label>}{authError && <div className="form-error">{authError}</div>}<button className="primary full" disabled={authBusy}>{authBusy ? "Working…" : authMode === "login" ? "Sign in" : "Create and sign in"}</button></form></div></div>}
    </main>
  );
}
