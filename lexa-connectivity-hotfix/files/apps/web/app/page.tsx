"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  approveAdjustment, approveStockCount, approveTransfer, completeTransfer, createAdjustment, createLocation, createWarehouse,
  createStockCount, createTransfer, dispatchTransfer, getAdjustments, getHealth, getInventoryBalances,
  getInventoryIntegrity, getInventoryLedger, getLocations, getReadiness, getStockCounts, getTransfers, getVariantOptions,
  openDevSession, postAdjustment, postStockCount, receiveTransfer, submitStockCount, updateCountLines,
  createProduct, createVariant, getCatalogWorkspace, getBrands, getCategories, getPriceLists, getProducts, getUnits, getVariants,
  type ApiHealth, type ApiReadiness, type Brand, type Category, type InventoryAdjustment, type InventoryBalance, type InventoryLedger,
  type Location, type PriceList, type Product, type StockCount, type Transfer, type Unit, type Variant, type VariantOption,
} from "../lib/api";

const modules = [
  { name: "Overview", desc: "Business command center" },
  { name: "Products", desc: "Catalog, variants, SKUs and prices" },
  { name: "Inventory", desc: "Stock, movements, counts and transfers" },
  { name: "Sales", desc: "POS, payments and returns" },
  { name: "Purchasing", desc: "Suppliers, orders and receiving" },
  { name: "Customers", desc: "Customer relationships and credit" },
  { name: "Reports", desc: "Operational and financial insight" },
  { name: "LEXA Intelligence", desc: "Analysis, recommendations and controlled actions" },
];
const invTabs = ["Stock", "Ledger", "Adjustments", "Counts", "Transfers", "Locations"];
const OPEN_DEV_MODE = process.env.NEXT_PUBLIC_LEXA_OPEN_MODE !== "false";

function money(value: string | number) { return new Intl.NumberFormat("en-UG", { style: "currency", currency: "UGX", maximumFractionDigits: 0 }).format(Number(value)); }
function qty(value: string | number) { return new Intl.NumberFormat("en-UG", { maximumFractionDigits: 3 }).format(Number(value)); }
function date(value: string) { return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
function short(id: string) { return `${id.slice(0, 8)}…`; }

export default function HomePage() {
  const [health, setHealth] = useState<ApiHealth | null>(null);
  const [readiness, setReadiness] = useState<ApiReadiness | null>(null);
  const [, setError] = useState<string | null>(null);
  const [active, setActive] = useState("Overview");
  const [token, setToken] = useState<string | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [tenantId, setTenantId] = useState("");
  const [tenantName, setTenantName] = useState("");
  const [invTab, setInvTab] = useState("Stock");
  const [locations, setLocations] = useState<Location[]>([]);
  const [variants, setVariants] = useState<VariantOption[]>([]);
  const [balances, setBalances] = useState<InventoryBalance[]>([]);
  const [ledger, setLedger] = useState<InventoryLedger[]>([]);
  const [integrity, setIntegrity] = useState<{status:string;checked:number;mismatches:any[]}>({status:"checking",checked:0,mismatches:[]});
  const [adjustments, setAdjustments] = useState<InventoryAdjustment[]>([]);
  const [counts, setCounts] = useState<StockCount[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [invBusy, setInvBusy] = useState(false);
  const [invMessage, setInvMessage] = useState<string | null>(null);
  const [stockSearch, setStockSearch] = useState("");
  const [locationFilter, setLocationFilter] = useState("");
  const [adjustLocation, setAdjustLocation] = useState("");
  const [adjustVariant, setAdjustVariant] = useState("");
  const [adjustQty, setAdjustQty] = useState("");
  const [adjustCost, setAdjustCost] = useState("");
  const [adjustReason, setAdjustReason] = useState("COUNT_CORRECTION");
  const [transferFrom, setTransferFrom] = useState("");
  const [transferTo, setTransferTo] = useState("");
  const [transferVariant, setTransferVariant] = useState("");
  const [transferQty, setTransferQty] = useState("");
  const [countLocation, setCountLocation] = useState("");
  const [countVariantIds, setCountVariantIds] = useState<string[]>([]);
  const [selectedCount, setSelectedCount] = useState<StockCount | null>(null);
  const [countValues, setCountValues] = useState<Record<string, string>>({});
  const [newWarehouseName, setNewWarehouseName] = useState("");
  const [newWarehouseCode, setNewWarehouseCode] = useState("");
  const [newLocationName, setNewLocationName] = useState("");
  const [newLocationCode, setNewLocationCode] = useState("");
  const [catalogProducts, setCatalogProducts] = useState<Product[]>([]);
  const [catalogCategories, setCatalogCategories] = useState<Category[]>([]);
  const [catalogBrands, setCatalogBrands] = useState<Brand[]>([]);
  const [catalogUnits, setCatalogUnits] = useState<Unit[]>([]);
  const [catalogPriceLists, setCatalogPriceLists] = useState<PriceList[]>([]);
  const [catalogVariants, setCatalogVariants] = useState<Variant[]>([]);
  const [catalogBusy, setCatalogBusy] = useState(false);
  const [catalogMessage, setCatalogMessage] = useState<string | null>(null);
  const [catalogSearch, setCatalogSearch] = useState("");
  const [newProductName, setNewProductName] = useState("");
  const [newProductCategory, setNewProductCategory] = useState("");
  const [newProductBrand, setNewProductBrand] = useState("");
  const [newVariantProduct, setNewVariantProduct] = useState("");
  const [newVariantName, setNewVariantName] = useState("");
  const [newVariantSku, setNewVariantSku] = useState("");
  const [newVariantUnit, setNewVariantUnit] = useState("");

  async function refreshSystem() {
    try { const [h, r] = await Promise.all([getHealth(), getReadiness()]); setHealth(h); setReadiness(r); setError(null); }
    catch (e) { setHealth(null); setReadiness(null); setError(e instanceof Error ? e.message : "Unable to reach LEXA."); }
  }
  async function refreshInventory() {
    if (!token) return;
    setInvBusy(true); setInvMessage(null);
    const results = await Promise.allSettled([
      getLocations(),
      getVariantOptions(),
      getInventoryBalances({ location_id: locationFilter || undefined, q: stockSearch || undefined }),
      getInventoryLedger({ location_id: locationFilter || undefined }),
      getInventoryIntegrity(),
      getAdjustments(),
      getStockCounts(),
      getTransfers(),
    ]);
    const [loc, vars, bal, led, integ, adj, cnt, tr] = results;
    if (loc.status === "fulfilled") setLocations(loc.value);
    if (vars.status === "fulfilled") setVariants(vars.value);
    if (bal.status === "fulfilled") setBalances(bal.value);
    if (led.status === "fulfilled") setLedger(led.value);
    if (integ.status === "fulfilled") setIntegrity(integ.value);
    if (adj.status === "fulfilled") setAdjustments(adj.value);
    if (cnt.status === "fulfilled") setCounts(cnt.value);
    if (tr.status === "fulfilled") setTransfers(tr.value);
    const failed = results.filter(x => x.status === "rejected").length;
    if (failed) setInvMessage("Some inventory areas are still being prepared. You can continue reviewing the workspace.");
    setInvBusy(false);
  }
  const catalogAbort = useRef<AbortController | null>(null);
  async function refreshCatalog() {
    if (!token) return;
    catalogAbort.current?.abort();
    const controller = new AbortController();
    catalogAbort.current = controller;
    setCatalogBusy(true); setCatalogMessage(null);
    try {
      const workspace = await getCatalogWorkspace({ q: catalogSearch.trim(), limit: 40 }, controller.signal);
      setCatalogProducts(workspace.items);
      setCatalogCategories(workspace.references.categories);
      setCatalogBrands(workspace.references.brands);
      setCatalogUnits(workspace.references.units);
      setCatalogPriceLists(workspace.references.price_lists);
      setCatalogVariants(workspace.items.flatMap(p => p.variants.map(v => ({ id:v.id, tenant_id:p.tenant_id, product_id:p.id, name:v.name, sku:v.sku, base_unit_id:v.id, track_inventory:v.track_inventory, allow_fractional_quantity:false, status:v.status, metadata:{} }))));
      if (!newProductCategory && workspace.references.categories[0]) setNewProductCategory(workspace.references.categories[0].id);
      if (!newVariantProduct && workspace.items[0]) setNewVariantProduct(workspace.items[0].id);
      if (!newVariantUnit && workspace.references.units[0]) setNewVariantUnit(workspace.references.units[0].id);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setCatalogMessage(e instanceof Error ? e.message : "Unable to load catalog.");
    } finally { if (!controller.signal.aborted) setCatalogBusy(false); }
  }

  useEffect(() => {
    let cancelled = false;
    async function boot() {
      // System probes and the development session must warm in parallel.
      // Waiting for /ready first made a cold Render instance block the entire
      // workspace bootstrap path even when /auth/dev-session could succeed.
      void refreshSystem();
      const saved = window.sessionStorage.getItem("lexa_access_token");
      const savedWorkspace = window.sessionStorage.getItem("lexa_workspace_id");
      const savedWorkspaceName = window.sessionStorage.getItem("lexa_workspace_name");
      if (saved && savedWorkspace) {
        if (!cancelled) { setToken(saved); setTenantId(savedWorkspace); setTenantName(savedWorkspaceName || "LEXA Workspace"); }
        return;
      }
      if (!OPEN_DEV_MODE || cancelled) return;
      try {
        let session = null as Awaited<ReturnType<typeof openDevSession>> | null;
        let lastError: unknown = null;
        const delays = [0, 900, 2200, 5000];
        for (const delay of delays) {
          if (delay) await new Promise(resolve => window.setTimeout(resolve, delay));
          if (cancelled) return;
          try {
            session = await openDevSession();
            break;
          } catch (e) {
            lastError = e;
          }
        }
        if (!session) throw lastError instanceof Error ? lastError : new Error("Workspace session unavailable");
        if (cancelled) return;
        window.sessionStorage.setItem("lexa_access_token", session.access_token);
        window.sessionStorage.setItem("lexa_workspace_id", session.tenant_id);
        window.sessionStorage.setItem("lexa_workspace_name", session.tenant_name);
        setToken(session.access_token); setTenantId(session.tenant_id); setTenantName(session.tenant_name);
        void refreshSystem();
      } catch (e) {
        if (!cancelled) setCatalogMessage(e instanceof Error ? e.message : "LEXA is preparing your workspace.");
      }
    }
    boot();
    return () => { cancelled = true; };
  }, []);
  useEffect(() => { if (token && active === "Inventory") refreshInventory(); }, [token, active, invTab, locationFilter]);
  useEffect(() => { if (!token || active !== "Products") return; const t = window.setTimeout(() => void refreshCatalog(), catalogSearch.trim() ? 280 : 0); return () => window.clearTimeout(t); }, [token, active, catalogSearch]);

  const variantMap = useMemo(() => new Map(variants.map(v => [v.id, v])), [variants]);
  const locationMap = useMemo(() => new Map(locations.map(l => [l.id, l])), [locations]);
  const inventoryStats = useMemo(() => {
    const totalUnits = balances.reduce((s, b) => s + Number(b.on_hand), 0);
    const value = balances.reduce((s, b) => s + Number(b.stock_value), 0);
    const low = balances.filter(b => Number(b.available) > 0 && Number(b.available) <= 5).length;
    const out = balances.filter(b => Number(b.available) <= 0).length;
    return { totalUnits, value, low, out };
  }, [balances]);

  async function submitProduct(e: React.FormEvent) {
    e.preventDefault(); setCatalogMessage(null);
    try { const p = await createProduct({ name:newProductName, category_id:newProductCategory, brand_id:newProductBrand || null }); setCatalogMessage(`Product ${short(p.id)} created.`); setNewProductName(""); await refreshCatalog(); }
    catch (e) { setCatalogMessage(e instanceof Error ? e.message : "Product creation failed."); }
  }
  async function submitVariant(e: React.FormEvent) {
    e.preventDefault(); setCatalogMessage(null);
    try { const v = await createVariant({ product_id:newVariantProduct, name:newVariantName, sku:newVariantSku, base_unit_id:newVariantUnit }); setCatalogMessage(`SKU ${v.sku} created.`); setNewVariantName(""); setNewVariantSku(""); await refreshCatalog(); }
    catch (e) { setCatalogMessage(e instanceof Error ? e.message : "Variant creation failed."); }
  }

  function resetPreview() {
    window.sessionStorage.removeItem("lexa_access_token");
    window.sessionStorage.removeItem("lexa_workspace_id");
    window.sessionStorage.removeItem("lexa_workspace_name");
    setToken(null); setTenantId(""); setTenantName("");
    setBalances([]); setLocations([]); setVariants([]); setCatalogProducts([]); setCatalogVariants([]);
    setActive("Overview"); setMobileMenuOpen(false);
    if (OPEN_DEV_MODE) {
      void openDevSession().then(session => {
        window.sessionStorage.setItem("lexa_access_token", session.access_token);
        window.sessionStorage.setItem("lexa_workspace_id", session.tenant_id);
        window.sessionStorage.setItem("lexa_workspace_name", session.tenant_name);
        setToken(session.access_token); setTenantId(session.tenant_id); setTenantName(session.tenant_name);
      });
    }
  }
  function clearInvMessage() { setInvMessage(null); setError(null); }

  async function submitAdjustment(e: React.FormEvent) {
    e.preventDefault(); clearInvMessage();
    try { const r = await createAdjustment({ location_id: adjustLocation, reason_code: adjustReason, lines: [{ variant_id: adjustVariant, quantity_delta: adjustQty, unit_cost: adjustCost || "0" }] }); setInvMessage(`Adjustment ${short(r.id)} created. Approve and post it to change stock.`); setAdjustQty(""); await refreshInventory(); }
    catch (e) { setInvMessage(e instanceof Error ? e.message : "Adjustment failed."); }
  }
  async function act(fn: () => Promise<{id:string;status:string}>, success: string) { clearInvMessage(); try { const r = await fn(); setInvMessage(`${success} · ${short(r.id)}`); await refreshInventory(); } catch (e) { setInvMessage(e instanceof Error ? e.message : "Action failed."); } }
  async function submitTransfer(e: React.FormEvent) {
    e.preventDefault(); clearInvMessage();
    try { const r = await createTransfer({ source_location_id: transferFrom, destination_location_id: transferTo, lines: [{ variant_id: transferVariant, quantity: transferQty }] }); setInvMessage(`Transfer ${short(r.id)} created. Approve then dispatch.`); setTransferQty(""); await refreshInventory(); }
    catch (e) { setInvMessage(e instanceof Error ? e.message : "Transfer failed."); }
  }
  async function submitCount(e: React.FormEvent) {
    e.preventDefault(); clearInvMessage();
    try { const r = await createStockCount({ location_id: countLocation, variant_ids: countVariantIds }); setInvMessage(`Stock count ${short(r.id)} started. Enter counted quantities below.`); await refreshInventory(); const created = (await getStockCounts()).find(x => x.id === r.id); if (created) { setSelectedCount(created); setCountValues(Object.fromEntries(created.lines.map(l => [l.variant_id, l.counted_quantity ?? ""]))); } }
    catch (e) { setInvMessage(e instanceof Error ? e.message : "Stock count failed."); }
  }
  async function saveCount() {
    if (!selectedCount) return; clearInvMessage();
    try { await updateCountLines(selectedCount.id, { lines: selectedCount.lines.map(l => ({ variant_id: l.variant_id, counted_quantity: countValues[l.variant_id] ?? null })) }); setInvMessage(`Count ${short(selectedCount.id)} saved.`); await refreshInventory(); const fresh = (await getStockCounts()).find(x => x.id === selectedCount.id); if (fresh) setSelectedCount(fresh); }
    catch (e) { setInvMessage(e instanceof Error ? e.message : "Unable to save count."); }
  }

  const logo = <img className="lexa-logo" src="/lexa-wordmark.png" alt="LEXA" />;
  const mark = <img className="lexa-mark" src="/lexa-mark.png" alt="" aria-hidden="true" />;
  const activeDescription = modules.find(item => item.name === active)?.desc || "Business operations";

  if (!token && !OPEN_DEV_MODE) {
    return (
      <main className="public-page">
        <header className="public-header">
          <a href="#top" className="public-brand" aria-label="LEXA home">{logo}</a>
          <nav className="public-nav" aria-label="Primary navigation">
            <a href="#platform">Platform</a><a href="#capabilities">Capabilities</a><a href="#intelligence">Intelligence</a>
          </nav>
          <button className="button button-dark" onClick={() => setActive("Overview")}>Open workspace</button>
        </header>

        <section className="public-hero" id="top">
          <div className="hero-copy">
            <div className="hero-kicker"><span className="kicker-dot" /> Business operating system</div>
            <h1>Run your business from one intelligent place.</h1>
            <p>LEXA brings products, inventory, sales, purchasing, customers, reporting and business intelligence into a single workspace built for growing businesses.</p>
            <div className="hero-actions"><button className="button button-dark button-large" onClick={() => setActive("Overview")}>Create your workspace</button><a className="text-link" href="#platform">See how it works <span>→</span></a></div>
            <div className="hero-trust"><span>One workspace</span><span>Clear operations</span><span>Built to scale</span></div>
          </div>
          <div className="hero-visual" aria-label="LEXA workspace preview">
            <div className="preview-window">
              <div className="preview-top"><div className="preview-brand">{mark}<span>LEXA</span></div><span className="preview-status"><i /> Workspace ready</span></div>
              <div className="preview-grid">
                <div className="preview-side"><span className="side-active">Overview</span><span>Products</span><span>Inventory</span><span>Sales</span><span>Purchasing</span><span>Reports</span></div>
                <div className="preview-main"><div className="preview-title"><span>Business command center</span><b>Today</b></div><div className="preview-metrics"><div><small>Products</small><strong>Catalog</strong><em>Organise your range</em></div><div><small>Inventory</small><strong>Stock</strong><em>Track every movement</em></div><div><small>Sales</small><strong>Orders</strong><em>Keep revenue visible</em></div></div><div className="preview-chart"><div className="chart-head"><span>Business activity</span><small>Live workspace</small></div><div className="bars"><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /></div></div></div>
              </div>
            </div>
            <div className="floating-card floating-card-a"><span>Stock control</span><strong>Everything in one view</strong></div>
            <div className="floating-card floating-card-b"><span>LEXA Intelligence</span><strong>Turn data into action</strong></div>
          </div>
        </section>

        <section className="platform-section" id="platform">
          <div className="section-intro"><span className="section-label">THE PLATFORM</span><h2>Everything your team needs to keep the business moving.</h2><p>Each area works together so your people can act from the same information, instead of stitching separate tools together.</p></div>
          <div className="capability-grid" id="capabilities">
            {modules.slice(1, 7).map((item, index) => <article className="capability-card" key={item.name}><span className="capability-index">0{index + 1}</span><h3>{item.name}</h3><p>{item.desc}.</p><span className="capability-arrow">↗</span></article>)}
          </div>
        </section>

        <section className="intelligence-section" id="intelligence">
          <div className="intelligence-copy"><span className="section-label">LEXA INTELLIGENCE</span><h2>From business data to useful decisions.</h2><p>LEXA is designed to help teams see what is happening, understand why it matters and act with confidence. Intelligence sits alongside day to day operations rather than apart from them.</p><div className="intelligence-points"><span><b>01</b> Understand performance</span><span><b>02</b> Spot opportunities and risks</span><span><b>03</b> Turn insight into action</span></div></div>
          <div className="intelligence-card"><div className="intelligence-top"><span>{mark}</span><div><strong>LEXA Intelligence</strong><small>Your business, clearly explained.</small></div></div><div className="insight"><span>INSIGHT</span><strong>Inventory movement is changing across your active locations.</strong><p>See the products, locations and time periods behind the change.</p></div><div className="insight-row"><span>Business signal</span><b>Ready for review</b></div><div className="insight-row"><span>Next step</span><b>Open Inventory</b></div></div>
        </section>

        <section className="public-cta"><div><span className="section-label">LEXA</span><h2>Give your business one place to operate.</h2><p>Create a workspace and bring the day to day together.</p></div><button className="button button-light button-large" onClick={() => setActive("Overview")}>Create your workspace</button></section>
        <footer className="public-footer"><div className="footer-brand">{logo}</div><p>Business operations, connected.</p><span>© {new Date().getFullYear()} LEXA</span></footer>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <aside className={`sidebar ${mobileMenuOpen ? "open" : ""}`}>
        <div className="sidebar-brand"><a href="#" className="sidebar-brand-link" onClick={(e) => { e.preventDefault(); setActive("Overview"); setMobileMenuOpen(false); }}><img className="lexa-sidebar-mark" src="/lexa-mark.png" alt="LEXA" /><span>LEXA</span></a><button className="mobile-close" onClick={() => setMobileMenuOpen(false)} aria-label="Close menu">×</button></div>
        <div className="sidebar-workspace"><span className="workspace-avatar">{tenantName ? tenantName.slice(0, 1).toUpperCase() : "L"}</span><div><strong>{tenantName || "Your workspace"}</strong><small>Business workspace</small></div></div>
        <nav className="sidebar-nav" aria-label="Workspace navigation">{modules.map(item => <button key={item.name} className={`sidebar-item ${active === item.name ? "active" : ""}`} onClick={() => { setActive(item.name); setMobileMenuOpen(false); }}><span className="sidebar-icon"><NavIcon name={item.name} /></span><span className="sidebar-text"><b>{item.name}</b><small>{item.desc}</small></span></button>)}</nav>
        <div className="sidebar-bottom"><div className="sidebar-note"><span className="note-dot" /><div><strong>{health && readiness?.status === "ready" ? "Workspace ready" : "Getting things ready"}</strong><p>{health && readiness?.status === "ready" ? "Your business tools are ready to use." : "Your workspace is loading."}</p></div></div><button className="sidebar-account" onClick={resetPreview}><span className="avatar-small">L</span><span><b>Preview workspace</b><small>Reset workspace</small></span></button></div>
      </aside>

      <section className="workspace">
        <header className="workspace-header"><button className="mobile-menu" onClick={() => setMobileMenuOpen(true)} aria-label="Open menu">☰</button><div><span className="workspace-breadcrumb">LEXA · {active}</span><h1>{active === "Overview" ? "Business command center" : active}</h1><p>{activeDescription}</p></div><div className="header-actions"><span className="preview-badge">Preview</span><button className="button button-soft" onClick={active === "Inventory" ? refreshInventory : active === "Products" ? refreshCatalog : refreshSystem}>Refresh</button></div></header>
        <div className={`workspace-banner ${health && readiness?.status === "ready" ? "positive" : "attention"}`}><span className="banner-icon">{health && readiness?.status === "ready" ? "✓" : "i"}</span><div><strong>{health && readiness?.status === "ready" ? "Everything is ready" : "Your workspace is taking a moment to connect"}</strong><p>{health && readiness?.status === "ready" ? "You can move between your business areas and keep work moving." : "Refresh in a moment. Your workspace and information remain safe."}</p></div></div>

        {active === "Overview" && <>
          <section className="command-hero"><div><span className="section-label">YOUR WORKSPACE</span><h2>One place for the work that keeps your business moving.</h2><p>Use the areas below to manage products, stock, sales, purchasing, customers and reports. LEXA keeps the pieces connected as your business grows.</p><div className="hero-quick-actions"><button className="button button-dark" onClick={() => setActive("Products")}>Manage products</button><button className="button button-soft" onClick={() => setActive("Inventory")}>Open inventory</button></div></div><div className="command-orbit"><div className="orbit-core">{mark}<span>LEXA</span></div><div className="orbit-item orbit-a">Products</div><div className="orbit-item orbit-b">Inventory</div><div className="orbit-item orbit-c">Sales</div><div className="orbit-item orbit-d">Insights</div></div></section>
          <section className="workspace-section"><div className="section-head"><div><span className="section-label">YOUR BUSINESS</span><h2>Workspaces that stay connected</h2></div></div><div className="module-grid">{modules.slice(1).map(item => <button className="module-tile" key={item.name} onClick={() => setActive(item.name)}><span className="tile-icon"><NavIcon name={item.name} /></span><div><h3>{item.name}</h3><p>{item.desc}.</p></div><span className="tile-arrow">→</span></button>)}</div></section>
          <section className="workspace-section two-column"><div className="insight-panel"><span className="section-label">LEXA INTELLIGENCE</span><h2>Insight beside the work.</h2><p>As your workspace grows, intelligence can help your team understand movement, spot patterns and prepare the next action.</p><button className="button button-dark" onClick={() => setActive("LEXA Intelligence")}>Open Intelligence</button></div><div className="trust-panel"><span className="section-label">BUILT AROUND YOUR BUSINESS</span><div className="trust-items"><div><strong>Shared information</strong><span>Keep teams working from the same business picture.</span></div><div><strong>Clear permissions</strong><span>Give each person the right access for their role.</span></div><div><strong>Ready to grow</strong><span>Add products, locations and workflows as you expand.</span></div></div></div></section>
        </>}
        {active === "Inventory" && <InventoryWorkspace token={token} invTab={invTab} setInvTab={setInvTab} locations={locations} variants={variants} balances={balances} ledger={ledger} adjustments={adjustments} counts={counts} transfers={transfers} locationMap={locationMap} variantMap={variantMap} stats={inventoryStats} integrity={integrity} busy={invBusy} message={invMessage} setMessage={setInvMessage} search={stockSearch} setSearch={setStockSearch} locationFilter={locationFilter} setLocationFilter={setLocationFilter} onRefresh={refreshInventory} onAdjustment={submitAdjustment} approveAdjustment={approveAdjustment} postAdjustment={postAdjustment} approveStockCount={approveStockCount} submitStockCount={submitStockCount} postStockCount={postStockCount} approveTransfer={approveTransfer} dispatchTransfer={dispatchTransfer} receiveTransfer={receiveTransfer} completeTransfer={completeTransfer} adjustLocation={adjustLocation} setAdjustLocation={setAdjustLocation} adjustVariant={adjustVariant} setAdjustVariant={setAdjustVariant} adjustQty={adjustQty} setAdjustQty={setAdjustQty} adjustCost={adjustCost} setAdjustCost={setAdjustCost} adjustReason={adjustReason} setAdjustReason={setAdjustReason} act={act} onTransfer={submitTransfer} transferFrom={transferFrom} setTransferFrom={setTransferFrom} transferTo={transferTo} setTransferTo={setTransferTo} transferVariant={transferVariant} setTransferVariant={setTransferVariant} transferQty={transferQty} setTransferQty={setTransferQty} onCount={submitCount} countLocation={countLocation} setCountLocation={setCountLocation} countVariantIds={countVariantIds} setCountVariantIds={setCountVariantIds} selectedCount={selectedCount} setSelectedCount={setSelectedCount} countValues={countValues} setCountValues={setCountValues} saveCount={saveCount} newWarehouseName={newWarehouseName} setNewWarehouseName={setNewWarehouseName} newWarehouseCode={newWarehouseCode} setNewWarehouseCode={setNewWarehouseCode} newLocationName={newLocationName} setNewLocationName={setNewLocationName} newLocationCode={newLocationCode} setNewLocationCode={setNewLocationCode} createWarehouse={createWarehouse} createLocation={createLocation} />}
        {active === "Products" && <CatalogWorkspace token={token} products={catalogProducts} categories={catalogCategories} brands={catalogBrands} units={catalogUnits} variants={catalogVariants} priceLists={catalogPriceLists} busy={catalogBusy} message={catalogMessage} search={catalogSearch} setSearch={setCatalogSearch} onRefresh={refreshCatalog} newProductName={newProductName} setNewProductName={setNewProductName} newProductCategory={newProductCategory} setNewProductCategory={setNewProductCategory} newProductBrand={newProductBrand} setNewProductBrand={setNewProductBrand} onProduct={submitProduct} newVariantProduct={newVariantProduct} setNewVariantProduct={setNewVariantProduct} newVariantName={newVariantName} setNewVariantName={setNewVariantName} newVariantSku={newVariantSku} setNewVariantSku={setNewVariantSku} newVariantUnit={newVariantUnit} setNewVariantUnit={setNewVariantUnit} onVariant={submitVariant} />}
        {active !== "Overview" && active !== "Inventory" && active !== "Products" && <section className="module-page"><div className="module-hero-icon"><NavIcon name={active} /></div><span className="section-label">LEXA WORKSPACE</span><h2>{active}</h2><p>{activeDescription}.</p><div className="module-ready-card"><div><strong>{active === "LEXA Intelligence" ? "See more in less time." : "Built for practical work."}</strong><p>{active === "Sales" ? "Keep sales, payments and returns together." : active === "Purchasing" ? "Keep suppliers, orders and receiving organised." : active === "Customers" ? "Keep relationships, notes and credit visible." : active === "Reports" ? "Bring operational and financial insight together." : "Your workspace keeps the next step close at hand."}</p></div><button className="button button-dark" onClick={() => setActive("Overview")}>Back to overview</button></div></section>}
      </section>

      <nav className="mobile-nav" aria-label="Mobile navigation">{modules.slice(0, 4).map(item => <button key={item.name} className={active === item.name ? "active" : ""} onClick={() => setActive(item.name)}><NavIcon name={item.name} /><span>{item.name}</span></button>)}<button onClick={() => setMobileMenuOpen(true)}><span className="more-icon">•••</span><span>More</span></button></nav>
    </main>
  );
}

function NavIcon({ name }: { name: string }) {
  const common = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  if (name === "Overview") return <svg {...common}><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>;
  if (name === "Products") return <svg {...common}><path d="M5 7.5 12 4l7 3.5v9L12 20l-7-3.5z"/><path d="M5 7.5 12 11l7-3.5M12 11v9"/></svg>;
  if (name === "Inventory") return <svg {...common}><path d="M4 8h16M6 4h12M6 12h12M6 16h12M6 20h8"/></svg>;
  if (name === "Sales") return <svg {...common}><path d="M4 18V8l8-4 8 4v10"/><path d="M7 18h10M9 14h6M9 10h6"/></svg>;
  if (name === "Purchasing") return <svg {...common}><path d="M5 6h14l-1 13H6z"/><path d="M9 6a3 3 0 0 1 6 0M8 11h8"/></svg>;
  if (name === "Customers") return <svg {...common}><circle cx="9" cy="8" r="3"/><path d="M3 20c0-3 2.5-5 6-5s6 2 6 5M16 6.5a3 3 0 1 1 0 5.8"/></svg>;
  if (name === "Reports") return <svg {...common}><path d="M5 19V9M12 19V5M19 19v-7"/></svg>;
  return <svg {...common}><path d="M12 3 14 8l5 .5-3.7 3.2 1.1 5.1-4.4-2.8-4.4 2.8 1.1-5.1L5 8.5 10 8z"/><circle cx="12" cy="12" r="2"/></svg>;
}

type CatalogProps = any;
function CatalogWorkspace(p: CatalogProps) {
  if (!p.token) return <section className="module-page"><span className="tag">CATALOG</span><h2>Your product catalog</h2><p>Your workspace is being prepared.</p><div className="notice"><strong>Getting your catalog ready.</strong><p>Your product tools will appear here as soon as the workspace is connected.</p></div></section>;
  return <>
    <section className="inventory-summary"><div><span className="eyebrow">CATALOG CONTROL</span><h2>Products and SKUs</h2><p>Product identity that becomes the foundation for inventory, sales and purchasing.</p></div><div className="inventory-actions"><button className="secondary" onClick={p.onRefresh}>{p.busy ? "Refreshing…" : "Refresh catalog"}</button></div></section>
    {p.message && <div className="inline-message">{p.message}</div>}
    <section className="stat-grid"><div className="stat-card"><span>PRODUCTS</span><strong>{p.products.length}</strong><small>Active catalog records loaded</small></div><div className="stat-card"><span>SKUS</span><strong>{p.variants.length}</strong><small>Variant identities loaded</small></div><div className="stat-card"><span>CATEGORIES</span><strong>{p.categories.length}</strong><small>Workspace categories</small></div><div className="stat-card"><span>PRICE LISTS</span><strong>{p.priceLists.length}</strong><small>Commercial pricing sets</small></div></section>
    <section className="split-panel"><form className="command-form" onSubmit={p.onProduct}><div><p className="eyebrow">NEW PRODUCT</p><h3>Create product identity</h3><p>Product identity is separated from SKU identity.</p></div><label>Name<input value={p.newProductName} onChange={e=>p.setNewProductName(e.target.value)} required /></label><label>Category<select value={p.newProductCategory} onChange={e=>p.setNewProductCategory(e.target.value)} required><option value="">Select category</option>{p.categories.map((x:Category)=><option key={x.id} value={x.id}>{x.name} · {x.code}</option>)}</select></label><label>Brand<select value={p.newProductBrand} onChange={e=>p.setNewProductBrand(e.target.value)}><option value="">No brand</option>{p.brands.map((x:Brand)=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label><button className="primary">Create product</button></form><form className="command-form" onSubmit={p.onVariant}><div><p className="eyebrow">NEW SKU</p><h3>Add sellable variant</h3><p>Each SKU must belong to a product and valid unit.</p></div><label>Product<select value={p.newVariantProduct} onChange={e=>p.setNewVariantProduct(e.target.value)} required><option value="">Select product</option>{p.products.map((x:Product)=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label>Variant name<input value={p.newVariantName} onChange={e=>p.setNewVariantName(e.target.value)} required /></label><label>SKU<input value={p.newVariantSku} onChange={e=>p.setNewVariantSku(e.target.value)} required /></label><label>Base unit<select value={p.newVariantUnit} onChange={e=>p.setNewVariantUnit(e.target.value)} required><option value="">Select unit</option>{p.units.map((x:Unit)=><option key={x.id} value={x.id}>{x.name} ({x.symbol})</option>)}</select></label><button className="primary">Create SKU</button></form></section>
    <section className="section"><div className="section-head compact"><div><h2>Catalog records</h2><p className="section-sub">Search your live product catalog.</p></div><input placeholder="Search products" value={p.search} onChange={e=>p.setSearch(e.target.value)} /></div><div className="table-wrap"><table><thead><tr><th>Product</th><th>Status</th><th>Variants / SKUs</th><th>Category</th><th>Brand</th></tr></thead><tbody>{p.products.length?p.products.map((x:Product)=>{const vars=p.variants.filter((v:Variant)=>v.product_id===x.id);const cat=p.categories.find((c:Category)=>c.id===x.category_id);const brand=p.brands.find((b:Brand)=>b.id===x.brand_id);return <tr key={x.id}><td><strong>{x.name}</strong><small>{short(x.id)}</small></td><td><span className="status good">{x.status}</span></td><td>{vars.length?vars.map((v:Variant)=><span key={v.id} className="movement">{v.sku}</span>):"No SKU yet"}</td><td>{cat?.name||short(x.category_id)}</td><td>{brand?.name||"—"}</td></tr>}):<tr><td colSpan={5}><div className="empty-inline">No products found in this workspace.</div></td></tr>}</tbody></table></div></section>
  </>;
}

type InvProps = any;

function InventoryWorkspace(p: InvProps) {
  if (!p.token) return <section className="module-page"><span className="tag">INVENTORY</span><h2>Your inventory workspace</h2><p>Your workspace is being prepared.</p><div className="notice"><strong>Getting inventory ready.</strong><p>Your stock, movements and locations will appear here as soon as the workspace is connected.</p></div></section>;
  return <>
    <section className="inventory-summary"><div><span className="eyebrow">INVENTORY CONTROL</span><h2>Stock operations</h2><p>Ledger-backed inventory with location-aware balances, controlled adjustments, counts and transfers.</p></div><div className="inventory-actions"><button className="secondary" onClick={p.onRefresh}>{p.busy ? "Refreshing…" : "Refresh data"}</button></div></section>
    <section className="stat-grid"><div className="stat-card"><span>ON HAND</span><strong>{qty(p.stats.totalUnits)}</strong><small>Across loaded locations</small></div><div className="stat-card"><span>STOCK VALUE</span><strong>{money(p.stats.value)}</strong><small>Weighted-average basis</small></div><div className="stat-card"><span>LOW STOCK</span><strong>{p.stats.low}</strong><small>Available ≤ 5 units</small></div><div className="stat-card"><span>OUT OF STOCK</span><strong>{p.stats.out}</strong><small>Available ≤ 0</small></div><div className="stat-card"><span>LEDGER INTEGRITY</span><strong>{p.integrity.status === "ok" ? "OK" : p.integrity.status === "checking" ? "Checking" : "Review"}</strong><small>{p.integrity.checked} balance records checked</small></div></section>
    {p.message && <div className="inline-message">{p.message}</div>}
    <section className="section inventory-section"><div className="inventory-tabs">{invTabs.map((t:string)=><button key={t} className={p.invTab===t?"selected":""} onClick={()=>p.setInvTab(t)}>{t}</button>)}</div>
      {p.invTab === "Stock" && <StockTab {...p} />}
      {p.invTab === "Ledger" && <LedgerTab {...p} />}
      {p.invTab === "Adjustments" && <AdjustmentsTab {...p} />}
      {p.invTab === "Counts" && <CountsTab {...p} />}
      {p.invTab === "Transfers" && <TransfersTab {...p} />}
      {p.invTab === "Locations" && <LocationsTab {...p} />}
    </section>
  </>;
}

function StockTab(p:InvProps) { return <><div className="section-head compact"><div><h2>Stock by location</h2><p className="section-sub">On hand, reserved, available, inbound and weighted-average cost.</p></div><div className="filters"><input placeholder="Search SKU or product" value={p.search} onChange={e=>p.setSearch(e.target.value)} onKeyDown={e=>e.key==="Enter"&&p.onRefresh()} /><select value={p.locationFilter} onChange={e=>p.setLocationFilter(e.target.value)}><option value="">All locations</option>{p.locations.map((l:Location)=><option key={l.id} value={l.id}>{l.name}</option>)}</select></div></div><div className="table-wrap"><table><thead><tr><th>Product / SKU</th><th>Location</th><th>On hand</th><th>Available</th><th>Inbound</th><th>Avg. cost</th><th>Value</th></tr></thead><tbody>{p.balances.length?p.balances.map((b:InventoryBalance)=><tr key={b.id}><td><strong>{p.variantMap.get(b.variant_id)?.product_name || short(b.variant_id)}</strong><small>{p.variantMap.get(b.variant_id)?.sku || b.variant_id}</small></td><td>{p.locationMap.get(b.location_id)?.name || short(b.location_id)}</td><td>{qty(b.on_hand)}</td><td><span className={Number(b.available)<=0?"status danger":Number(b.available)<=5?"status warn":"status good"}>{qty(b.available)}</span></td><td>{qty(b.inbound)}</td><td>{money(b.average_cost)}</td><td>{money(b.stock_value)}</td></tr>):<tr><td colSpan={7}><div className="empty-inline">No inventory balances found in this workspace.</div></td></tr>}</tbody></table></div></> }
function LedgerTab(p:InvProps) { return <><div className="section-head compact"><div><h2>Inventory ledger</h2><p className="section-sub">Immutable movements with running balance snapshots.</p></div></div><div className="table-wrap"><table><thead><tr><th>Date</th><th>Movement</th><th>Product</th><th>Location</th><th>Quantity</th><th>Cost</th><th>Balance</th><th>Reference</th></tr></thead><tbody>{p.ledger.length?p.ledger.map((x:InventoryLedger)=><tr key={x.id}><td>{date(x.occurred_at)}</td><td><span className="movement">{x.transaction_type.replaceAll("_"," ")}</span></td><td>{p.variantMap.get(x.variant_id)?.sku || short(x.variant_id)}</td><td>{p.locationMap.get(x.location_id)?.name || short(x.location_id)}</td><td className={Number(x.quantity_delta)<0?"negative":"positive"}>{Number(x.quantity_delta)>0?"+":""}{qty(x.quantity_delta)}</td><td>{money(x.unit_cost)}</td><td>{qty(x.balance_after)}</td><td>{x.reference_type||"—"}</td></tr>):<tr><td colSpan={8}><div className="empty-inline">No ledger movements yet. Receive or adjust stock to create the first movement.</div></td></tr>}</tbody></table></div></> }
function AdjustmentsTab(p:InvProps) { return <><div className="split-panel"><form className="command-form" onSubmit={p.onAdjustment}><div><p className="eyebrow">NEW ADJUSTMENT</p><h3>Controlled stock adjustment</h3><p>Every posted adjustment becomes an immutable ledger movement.</p></div><label>Location<select value={p.adjustLocation} onChange={e=>p.setAdjustLocation(e.target.value)} required><option value="">Select location</option>{p.locations.map((l:Location)=><option key={l.id} value={l.id}>{l.name}</option>)}</select></label><label>Product / SKU<select value={p.adjustVariant} onChange={e=>p.setAdjustVariant(e.target.value)} required><option value="">Select product</option>{p.variants.map((v:VariantOption)=><option key={v.id} value={v.id}>{v.product_name} · {v.sku}</option>)}</select></label><div className="form-grid"><label>Quantity change<input type="number" step="0.001" value={p.adjustQty} onChange={e=>p.setAdjustQty(e.target.value)} placeholder="+10 or -2" required /></label><label>Unit cost<input type="number" step="0.01" min="0" value={p.adjustCost} onChange={e=>p.setAdjustCost(e.target.value)} placeholder="UGX" /></label></div><label>Reason<select value={p.adjustReason} onChange={e=>p.setAdjustReason(e.target.value)}><option>COUNT_CORRECTION</option><option>DAMAGE</option><option>LOSS</option><option>FOUND</option><option>OPENING_BALANCE</option><option>OTHER</option></select></label><button className="primary" type="submit">Create adjustment</button></form><div className="workflow-list"><p className="eyebrow">PENDING & HISTORY</p>{p.adjustments.length?p.adjustments.map((a:InventoryAdjustment)=><div className="workflow-row" key={a.id}><div><strong>{a.reason_code}</strong><small>{short(a.id)} · {a.lines.length} line{a.lines.length===1?"":"s"}</small></div><span className={`status ${a.status==="POSTED"?"good":a.status==="APPROVED"?"warn":"neutral"}`}>{a.status}</span><div className="row-actions">{a.status==="DRAFT"&&<button onClick={()=>p.act(()=>p.approveAdjustment(a.id),"Adjustment approved")}>Approve</button>}{a.status==="APPROVED"&&<button onClick={()=>p.act(()=>p.postAdjustment(a.id),"Adjustment posted")}>Post</button>}</div></div>):<div className="empty-inline">No adjustments have been created.</div>}</div></div></> }
function CountsTab(p:InvProps) { return <><div className="split-panel"><form className="command-form" onSubmit={p.onCount}><div><p className="eyebrow">STOCK COUNT</p><h3>Start a physical count</h3><p>LEXA snapshots expected quantities, then reconciles only the variance.</p></div><label>Location<select value={p.countLocation} onChange={e=>p.setCountLocation(e.target.value)} required><option value="">Select location</option>{p.locations.map((l:Location)=><option key={l.id} value={l.id}>{l.name}</option>)}</select></label><label>Products to count<select multiple value={p.countVariantIds} onChange={e=>p.setCountVariantIds(Array.from(e.target.selectedOptions).map(o=>o.value))} required>{p.variants.map((v:VariantOption)=><option key={v.id} value={v.id}>{v.product_name} · {v.sku}</option>)}</select><small>Use Ctrl/⌘ to select multiple products on desktop.</small></label><button className="primary" type="submit">Start count</button></form><div className="workflow-list"><p className="eyebrow">COUNT WORKFLOW</p>{p.counts.length?p.counts.map((c:StockCount)=><div className="workflow-row" key={c.id}><div><strong>{p.locationMap.get(c.location_id)?.name||short(c.location_id)}</strong><small>{short(c.id)} · {c.lines.length} items</small></div><span className={`status ${c.status==="POSTED"?"good":c.status==="APPROVED"?"warn":"neutral"}`}>{c.status}</span><div className="row-actions"><button onClick={()=>{p.setSelectedCount(c);p.setCountValues(Object.fromEntries(c.lines.map((l:any)=>[l.variant_id,l.counted_quantity??""])));}}>Open</button>{c.status==="COUNTING"&&<button onClick={()=>p.act(()=>p.submitStockCount(c.id),"Count submitted")}>Submit</button>}{c.status==="SUBMITTED"&&<button onClick={()=>p.act(()=>p.approveStockCount(c.id),"Count approved")}>Approve</button>}{c.status==="APPROVED"&&<button onClick={()=>p.act(()=>p.postStockCount(c.id),"Count posted")}>Post</button>}</div></div>):<div className="empty-inline">No stock counts yet.</div>}</div></div>{p.selectedCount&&<div className="count-editor"><div className="section-head compact"><div><p className="eyebrow">COUNT {short(p.selectedCount.id)}</p><h3>Enter physical quantities</h3></div><button className="secondary" onClick={()=>p.setSelectedCount(null)}>Close</button></div>{p.selectedCount.lines.map((l:any)=><div className="count-line" key={l.id}><div><strong>{p.variantMap.get(l.variant_id)?.product_name||short(l.variant_id)}</strong><small>{p.variantMap.get(l.variant_id)?.sku||l.variant_id} · Expected {qty(l.expected_quantity)}</small></div><input type="number" min="0" step="0.001" value={p.countValues[l.variant_id]??""} onChange={e=>p.setCountValues({...p.countValues,[l.variant_id]:e.target.value})} disabled={p.selectedCount.status!=="COUNTING"} /><span>{l.counted_quantity==null?"Not counted":`Variance ${qty(l.variance_quantity||"0")}`}</span></div>)}{p.selectedCount.status==="COUNTING"&&<button className="primary" onClick={p.saveCount}>Save counted quantities</button>}</div>}</> }
function TransfersTab(p:InvProps) { return <><div className="split-panel"><form className="command-form" onSubmit={p.onTransfer}><div><p className="eyebrow">TRANSFER STOCK</p><h3>Move inventory between locations</h3><p>Dispatch decreases source stock; receipt increases destination stock.</p></div><div className="form-grid"><label>From<select value={p.transferFrom} onChange={e=>p.setTransferFrom(e.target.value)} required><option value="">Source</option>{p.locations.map((l:Location)=><option key={l.id} value={l.id}>{l.name}</option>)}</select></label><label>To<select value={p.transferTo} onChange={e=>p.setTransferTo(e.target.value)} required><option value="">Destination</option>{p.locations.map((l:Location)=><option key={l.id} value={l.id}>{l.name}</option>)}</select></label></div><label>Product / SKU<select value={p.transferVariant} onChange={e=>p.setTransferVariant(e.target.value)} required><option value="">Select product</option>{p.variants.map((v:VariantOption)=><option key={v.id} value={v.id}>{v.product_name} · {v.sku}</option>)}</select></label><label>Quantity<input type="number" min="0.001" step="0.001" value={p.transferQty} onChange={e=>p.setTransferQty(e.target.value)} required /></label><button className="primary" type="submit">Create transfer</button></form><div className="workflow-list"><p className="eyebrow">TRANSFER PIPELINE</p>{p.transfers.length?p.transfers.map((t:Transfer)=><div className="workflow-row" key={t.id}><div><strong>{p.locationMap.get(t.source_location_id)?.name||short(t.source_location_id)} → {p.locationMap.get(t.destination_location_id)?.name||short(t.destination_location_id)}</strong><small>{short(t.id)} · {t.lines.length} items</small></div><span className={`status ${t.status==="COMPLETED"?"good":t.status==="APPROVED"||t.status==="RECEIVED"?"warn":"neutral"}`}>{t.status}</span><div className="row-actions">{t.status==="DRAFT"&&<button onClick={()=>p.act(()=>p.approveTransfer(t.id),"Transfer approved")}>Approve</button>}{t.status==="APPROVED"&&<button onClick={()=>p.act(()=>p.dispatchTransfer(t.id),"Transfer dispatched")}>Dispatch</button>}{(t.status==="DISPATCHED"||t.status==="PARTIALLY_RECEIVED")&&<button onClick={()=>p.act(()=>p.receiveTransfer(t.id,{lines:t.lines.map((l:any)=>({variant_id:l.variant_id,counted_quantity:String(Number(l.dispatched_quantity)-Number(l.received_quantity))}))}),"Transfer received")}>Receive</button>}{t.status==="RECEIVED"&&<button onClick={()=>p.act(()=>p.completeTransfer(t.id),"Transfer completed")}>Complete</button>}</div></div>):<div className="empty-inline">No transfers have been created.</div>}</div></div></> }
function LocationsTab(p:InvProps) {
  const create = async (e:React.FormEvent) => { e.preventDefault(); try { const w=await p.createWarehouse({name:p.newWarehouseName,code:p.newWarehouseCode}); await p.createLocation({name:p.newLocationName,code:p.newLocationCode,warehouse_id:w.id}); p.setNewWarehouseName("");p.setNewWarehouseCode("");p.setNewLocationName("");p.setNewLocationCode("");p.setMessage("Warehouse and location created successfully."); p.onRefresh(); } catch(e) { p.setMessage(e instanceof Error?e.message:"Unable to create location"); } };
  return <div><div className="section-head compact"><div><h2>Inventory locations</h2><p className="section-sub">Stock is always attached to a workspace location.</p></div></div><div className="location-setup"><form onSubmit={create}><div><p className="eyebrow">QUICK SETUP</p><h3>Add a warehouse and stock location</h3><p>Create the physical place where LEXA will track inventory.</p></div><div className="form-grid"><label>Warehouse name<input value={p.newWarehouseName} onChange={(e:any)=>p.setNewWarehouseName(e.target.value)} required /></label><label>Warehouse code<input value={p.newWarehouseCode} onChange={(e:any)=>p.setNewWarehouseCode(e.target.value)} required /></label></div><div className="form-grid"><label>Location name<input value={p.newLocationName} onChange={(e:any)=>p.setNewLocationName(e.target.value)} required /></label><label>Location code<input value={p.newLocationCode} onChange={(e:any)=>p.setNewLocationCode(e.target.value)} required /></label></div><button className="primary">Create location</button></form></div><div className="cards-grid location-grid">{p.locations.length?p.locations.map((l:Location)=><article className="location-card" key={l.id}><span className="tag">LOCATION</span><h3>{l.name}</h3><p>{l.code}</p><small>{l.status} · {short(l.id)}</small></article>):<div className="empty"><strong>No locations configured.</strong><p>Use the setup form above to create the first stock location.</p></div>}</div></div> }
