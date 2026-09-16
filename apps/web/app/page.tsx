"use client";

import { useEffect, useMemo, useState } from "react";
import {
  approveAdjustment, approveStockCount, approveTransfer, completeTransfer, createAdjustment, createLocation, createWarehouse,
  createStockCount, createTransfer, dispatchTransfer, getAdjustments, getHealth, getInventoryBalances,
  getInventoryIntegrity, getInventoryLedger, getLocations, getReadiness, getStockCounts, getTransfers, getVariantOptions,
  login, postAdjustment, postStockCount, receiveTransfer, register, submitStockCount, updateCountLines,
  type ApiHealth, type ApiReadiness, type InventoryAdjustment, type InventoryBalance, type InventoryLedger,
  type Location, type StockCount, type Transfer, type VariantOption,
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

function money(value: string | number) { return new Intl.NumberFormat("en-UG", { style: "currency", currency: "UGX", maximumFractionDigits: 0 }).format(Number(value)); }
function qty(value: string | number) { return new Intl.NumberFormat("en-UG", { maximumFractionDigits: 3 }).format(Number(value)); }
function date(value: string) { return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
function short(id: string) { return `${id.slice(0, 8)}…`; }

export default function HomePage() {
  const [health, setHealth] = useState<ApiHealth | null>(null);
  const [readiness, setReadiness] = useState<ApiReadiness | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState("Overview");
  const [token, setToken] = useState<string | null>(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authError, setAuthError] = useState<string | null>(null);
  const [authBusy, setAuthBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
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

  async function refreshSystem() {
    try { const [h, r] = await Promise.all([getHealth(), getReadiness()]); setHealth(h); setReadiness(r); setError(null); }
    catch (e) { setHealth(null); setReadiness(null); setError(e instanceof Error ? e.message : "Unable to reach LEXA."); }
  }
  async function refreshInventory() {
    if (!token) return;
    setInvBusy(true); setInvMessage(null);
    try {
      const [loc, vars, bal, led, integ, adj, cnt, tr] = await Promise.all([getLocations(), getVariantOptions(), getInventoryBalances({ location_id: locationFilter || undefined, q: stockSearch || undefined }), getInventoryLedger({ location_id: locationFilter || undefined }), getInventoryIntegrity(), getAdjustments(), getStockCounts(), getTransfers()]);
      setLocations(loc); setVariants(vars); setBalances(bal); setLedger(led); setIntegrity(integ); setAdjustments(adj); setCounts(cnt); setTransfers(tr);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to load inventory."); }
    finally { setInvBusy(false); }
  }
  useEffect(() => { refreshSystem(); const saved = window.sessionStorage.getItem("lexa_access_token"); if (saved) setToken(saved); }, []);
  useEffect(() => { if (token && active === "Inventory") refreshInventory(); }, [token, active, invTab, locationFilter]);

  const variantMap = useMemo(() => new Map(variants.map(v => [v.id, v])), [variants]);
  const locationMap = useMemo(() => new Map(locations.map(l => [l.id, l])), [locations]);
  const inventoryStats = useMemo(() => {
    const totalUnits = balances.reduce((s, b) => s + Number(b.on_hand), 0);
    const value = balances.reduce((s, b) => s + Number(b.stock_value), 0);
    const low = balances.filter(b => Number(b.available) > 0 && Number(b.available) <= 5).length;
    const out = balances.filter(b => Number(b.available) <= 0).length;
    return { totalUnits, value, low, out };
  }, [balances]);

  async function submitAuth(event: React.FormEvent) {
    event.preventDefault(); setAuthError(null); setAuthBusy(true);
    try {
      let tid = tenantId;
      if (authMode === "register") { const created = await register({ email, password, tenant_name: tenantName }); tid = created.tenant_id; setTenantId(tid); }
      const session = await login({ email, password, tenant_id: tid });
      window.sessionStorage.setItem("lexa_access_token", session.access_token); setToken(session.access_token); setAuthOpen(false); setActive("Overview");
    } catch (e) { setAuthError(e instanceof Error ? e.message : "Authentication failed."); }
    finally { setAuthBusy(false); }
  }
  function signOut() { window.sessionStorage.removeItem("lexa_access_token"); setToken(null); setBalances([]); setLocations([]); setVariants([]); setActive("Overview"); }
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

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">L</span><div><strong>LEXA</strong><small>Business Operating System</small></div></div>
        <nav aria-label="Main navigation">{modules.map(item => <button key={item.name} className={`nav-item ${active === item.name ? "active" : ""}`} onClick={() => setActive(item.name)}><span>{item.name}</span></button>)}</nav>
        <div className="sidebar-note"><strong>One platform. Many businesses.</strong><p>Tenant-isolated operations for different business models, categories and workflows.</p></div>
      </aside>
      <section className="workspace">
        <header className="topbar"><div><p className="eyebrow">LEXA / {active.toUpperCase()}</p><h1>{active === "Overview" ? "Business command center" : active}</h1></div><div className="top-actions"><button className="secondary" onClick={active === "Inventory" ? refreshInventory : refreshSystem}>Refresh</button>{token ? <button className="secondary" onClick={signOut}>Sign out</button> : <button className="primary" onClick={() => setAuthOpen(true)}>Sign in</button>}</div></header>
        <div className="connection-strip"><span className={`pulse ${health ? "good" : "bad"}`} /><div><strong>{health ? "LEXA services online" : "Connection unavailable"}</strong><span>{readiness?.dependencies?.database === "ok" ? "Business database ready" : "Checking business services"}</span></div>{error && <span className="connection-error">{error}</span>}</div>

        {active === "Overview" && <>
          <section className="hero-grid"><article className="hero-card"><span className="tag">OPERATING SYSTEM</span><h2>Run the business on trusted operational data.</h2><p>LEXA is a real multi-purpose, multi-tenant SaaS platform. Each tenant operates its own business data, workflows and permissions while sharing the same product foundation.</p><div className="architecture"><span>Catalog</span><b>→</b><span>Inventory</span><b>→</b><span>Sales</span><b>→</b><span>Purchasing</span><b>→</b><span>Analytics</span><b>→</b><span>Intelligence</span></div></article><article className="metric-card"><span>SERVICES</span><strong>{health ? "Online" : "Offline"}</strong><small>LEXA API</small></article><article className="metric-card"><span>DATA</span><strong>{readiness?.dependencies?.database === "ok" ? "Ready" : "Checking"}</strong><small>Transactional database</small></article><article className="metric-card"><span>WORKSPACE</span><strong>{token ? "Active" : "Guest"}</strong><small>{token ? "Tenant session" : "Sign in to operate"}</small></article></section>
          <section className="section"><div className="section-head"><div><p className="eyebrow">WORKSPACES</p><h2>Operate every part of the business</h2></div></div><div className="cards-grid">{modules.slice(1).map(item => <button className="module-card" key={item.name} onClick={() => setActive(item.name)}><h3>{item.name}</h3><p>{item.desc}</p><span>Open →</span></button>)}</div></section>
        </>}

        {active === "Inventory" && <InventoryWorkspace token={token} invTab={invTab} setInvTab={setInvTab} locations={locations} variants={variants} balances={balances} ledger={ledger} adjustments={adjustments} counts={counts} transfers={transfers} locationMap={locationMap} variantMap={variantMap} stats={inventoryStats} integrity={integrity} busy={invBusy} message={invMessage} setMessage={setInvMessage} search={stockSearch} setSearch={setStockSearch} locationFilter={locationFilter} setLocationFilter={setLocationFilter} onRefresh={refreshInventory} onAdjustment={submitAdjustment} approveAdjustment={approveAdjustment} postAdjustment={postAdjustment} approveStockCount={approveStockCount} submitStockCount={submitStockCount} postStockCount={postStockCount} approveTransfer={approveTransfer} dispatchTransfer={dispatchTransfer} receiveTransfer={receiveTransfer} completeTransfer={completeTransfer} adjustLocation={adjustLocation} setAdjustLocation={setAdjustLocation} adjustVariant={adjustVariant} setAdjustVariant={setAdjustVariant} adjustQty={adjustQty} setAdjustQty={setAdjustQty} adjustCost={adjustCost} setAdjustCost={setAdjustCost} adjustReason={adjustReason} setAdjustReason={setAdjustReason} act={act} onTransfer={submitTransfer} transferFrom={transferFrom} setTransferFrom={setTransferFrom} transferTo={transferTo} setTransferTo={setTransferTo} transferVariant={transferVariant} setTransferVariant={setTransferVariant} transferQty={transferQty} setTransferQty={setTransferQty} onCount={submitCount} countLocation={countLocation} setCountLocation={setCountLocation} countVariantIds={countVariantIds} setCountVariantIds={setCountVariantIds} selectedCount={selectedCount} setSelectedCount={setSelectedCount} countValues={countValues} setCountValues={setCountValues} saveCount={saveCount} newWarehouseName={newWarehouseName} setNewWarehouseName={setNewWarehouseName} newWarehouseCode={newWarehouseCode} setNewWarehouseCode={setNewWarehouseCode} newLocationName={newLocationName} setNewLocationName={setNewLocationName} newLocationCode={newLocationCode} setNewLocationCode={setNewLocationCode} createWarehouse={createWarehouse} createLocation={createLocation} />}
        {active !== "Overview" && active !== "Inventory" && <section className="module-page"><span className="tag">WORKSPACE</span><h2>{active}</h2><p>{modules.find(m => m.name === active)?.desc}</p><div className="notice"><strong>Real product domain</strong><p>This workspace is part of the LEXA operating model. Its transactional capabilities will be connected to the same tenant-safe domain layer rather than populated with fake records.</p></div></section>}
      </section>

      {authOpen && <div className="modal-backdrop" onClick={() => setAuthOpen(false)}><div className="modal" onClick={e => e.stopPropagation()}><div className="modal-head"><div><p className="eyebrow">WORKSPACE ACCESS</p><h2>{authMode === "login" ? "Sign in to LEXA" : "Create a workspace"}</h2></div><button className="close" onClick={() => setAuthOpen(false)}>×</button></div><div className="tabs"><button className={authMode === "login" ? "selected" : ""} onClick={() => setAuthMode("login")}>Sign in</button><button className={authMode === "register" ? "selected" : ""} onClick={() => setAuthMode("register")}>Create workspace</button></div><form onSubmit={submitAuth}><label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} required /></label><label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} minLength={12} required /><small>Minimum 12 characters.</small></label>{authMode === "register" ? <label>Business name<input value={tenantName} onChange={e => setTenantName(e.target.value)} required /></label> : <label>Workspace ID<input value={tenantId} onChange={e => setTenantId(e.target.value)} required /></label>}{authError && <div className="form-error">{authError}</div>}<button className="primary full" disabled={authBusy}>{authBusy ? "Working…" : authMode === "login" ? "Sign in" : "Create workspace"}</button></form></div></div>}
    </main>
  );
}

type InvProps = any;
function InventoryWorkspace(p: InvProps) {
  if (!p.token) return <section className="module-page"><span className="tag">INVENTORY</span><h2>Your inventory workspace</h2><p>Sign in to work with the tenant's actual stock data.</p><div className="notice"><strong>No demo inventory is shown.</strong><p>LEXA will only display products, quantities and movements that belong to the authenticated tenant.</p><p className="section-sub">Use the Sign in button in the top bar to open your tenant workspace.</p></div></section>;
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

function StockTab(p:InvProps) { return <><div className="section-head compact"><div><h2>Stock by location</h2><p className="section-sub">On hand, reserved, available, inbound and weighted-average cost.</p></div><div className="filters"><input placeholder="Search SKU or product" value={p.search} onChange={e=>p.setSearch(e.target.value)} onKeyDown={e=>e.key==="Enter"&&p.onRefresh()} /><select value={p.locationFilter} onChange={e=>p.setLocationFilter(e.target.value)}><option value="">All locations</option>{p.locations.map((l:Location)=><option key={l.id} value={l.id}>{l.name}</option>)}</select></div></div><div className="table-wrap"><table><thead><tr><th>Product / SKU</th><th>Location</th><th>On hand</th><th>Available</th><th>Inbound</th><th>Avg. cost</th><th>Value</th></tr></thead><tbody>{p.balances.length?p.balances.map((b:InventoryBalance)=><tr key={b.id}><td><strong>{p.variantMap.get(b.variant_id)?.product_name || short(b.variant_id)}</strong><small>{p.variantMap.get(b.variant_id)?.sku || b.variant_id}</small></td><td>{p.locationMap.get(b.location_id)?.name || short(b.location_id)}</td><td>{qty(b.on_hand)}</td><td><span className={Number(b.available)<=0?"status danger":Number(b.available)<=5?"status warn":"status good"}>{qty(b.available)}</span></td><td>{qty(b.inbound)}</td><td>{money(b.average_cost)}</td><td>{money(b.stock_value)}</td></tr>):<tr><td colSpan={7}><div className="empty-inline">No inventory balances found for this tenant.</div></td></tr>}</tbody></table></div></> }
function LedgerTab(p:InvProps) { return <><div className="section-head compact"><div><h2>Inventory ledger</h2><p className="section-sub">Immutable movements with running balance snapshots.</p></div></div><div className="table-wrap"><table><thead><tr><th>Date</th><th>Movement</th><th>Product</th><th>Location</th><th>Quantity</th><th>Cost</th><th>Balance</th><th>Reference</th></tr></thead><tbody>{p.ledger.length?p.ledger.map((x:InventoryLedger)=><tr key={x.id}><td>{date(x.occurred_at)}</td><td><span className="movement">{x.transaction_type.replaceAll("_"," ")}</span></td><td>{p.variantMap.get(x.variant_id)?.sku || short(x.variant_id)}</td><td>{p.locationMap.get(x.location_id)?.name || short(x.location_id)}</td><td className={Number(x.quantity_delta)<0?"negative":"positive"}>{Number(x.quantity_delta)>0?"+":""}{qty(x.quantity_delta)}</td><td>{money(x.unit_cost)}</td><td>{qty(x.balance_after)}</td><td>{x.reference_type||"—"}</td></tr>):<tr><td colSpan={8}><div className="empty-inline">No ledger movements yet. Receive or adjust stock to create the first movement.</div></td></tr>}</tbody></table></div></> }
function AdjustmentsTab(p:InvProps) { return <><div className="split-panel"><form className="command-form" onSubmit={p.onAdjustment}><div><p className="eyebrow">NEW ADJUSTMENT</p><h3>Controlled stock adjustment</h3><p>Every posted adjustment becomes an immutable ledger movement.</p></div><label>Location<select value={p.adjustLocation} onChange={e=>p.setAdjustLocation(e.target.value)} required><option value="">Select location</option>{p.locations.map((l:Location)=><option key={l.id} value={l.id}>{l.name}</option>)}</select></label><label>Product / SKU<select value={p.adjustVariant} onChange={e=>p.setAdjustVariant(e.target.value)} required><option value="">Select product</option>{p.variants.map((v:VariantOption)=><option key={v.id} value={v.id}>{v.product_name} · {v.sku}</option>)}</select></label><div className="form-grid"><label>Quantity change<input type="number" step="0.001" value={p.adjustQty} onChange={e=>p.setAdjustQty(e.target.value)} placeholder="+10 or -2" required /></label><label>Unit cost<input type="number" step="0.01" min="0" value={p.adjustCost} onChange={e=>p.setAdjustCost(e.target.value)} placeholder="UGX" /></label></div><label>Reason<select value={p.adjustReason} onChange={e=>p.setAdjustReason(e.target.value)}><option>COUNT_CORRECTION</option><option>DAMAGE</option><option>LOSS</option><option>FOUND</option><option>OPENING_BALANCE</option><option>OTHER</option></select></label><button className="primary" type="submit">Create adjustment</button></form><div className="workflow-list"><p className="eyebrow">PENDING & HISTORY</p>{p.adjustments.length?p.adjustments.map((a:InventoryAdjustment)=><div className="workflow-row" key={a.id}><div><strong>{a.reason_code}</strong><small>{short(a.id)} · {a.lines.length} line{a.lines.length===1?"":"s"}</small></div><span className={`status ${a.status==="POSTED"?"good":a.status==="APPROVED"?"warn":"neutral"}`}>{a.status}</span><div className="row-actions">{a.status==="DRAFT"&&<button onClick={()=>p.act(()=>p.approveAdjustment(a.id),"Adjustment approved")}>Approve</button>}{a.status==="APPROVED"&&<button onClick={()=>p.act(()=>p.postAdjustment(a.id),"Adjustment posted")}>Post</button>}</div></div>):<div className="empty-inline">No adjustments have been created.</div>}</div></div></> }
function CountsTab(p:InvProps) { return <><div className="split-panel"><form className="command-form" onSubmit={p.onCount}><div><p className="eyebrow">STOCK COUNT</p><h3>Start a physical count</h3><p>LEXA snapshots expected quantities, then reconciles only the variance.</p></div><label>Location<select value={p.countLocation} onChange={e=>p.setCountLocation(e.target.value)} required><option value="">Select location</option>{p.locations.map((l:Location)=><option key={l.id} value={l.id}>{l.name}</option>)}</select></label><label>Products to count<select multiple value={p.countVariantIds} onChange={e=>p.setCountVariantIds(Array.from(e.target.selectedOptions).map(o=>o.value))} required>{p.variants.map((v:VariantOption)=><option key={v.id} value={v.id}>{v.product_name} · {v.sku}</option>)}</select><small>Use Ctrl/⌘ to select multiple products on desktop.</small></label><button className="primary" type="submit">Start count</button></form><div className="workflow-list"><p className="eyebrow">COUNT WORKFLOW</p>{p.counts.length?p.counts.map((c:StockCount)=><div className="workflow-row" key={c.id}><div><strong>{p.locationMap.get(c.location_id)?.name||short(c.location_id)}</strong><small>{short(c.id)} · {c.lines.length} items</small></div><span className={`status ${c.status==="POSTED"?"good":c.status==="APPROVED"?"warn":"neutral"}`}>{c.status}</span><div className="row-actions"><button onClick={()=>{p.setSelectedCount(c);p.setCountValues(Object.fromEntries(c.lines.map((l:any)=>[l.variant_id,l.counted_quantity??""])));}}>Open</button>{c.status==="COUNTING"&&<button onClick={()=>p.act(()=>p.submitStockCount(c.id),"Count submitted")}>Submit</button>}{c.status==="SUBMITTED"&&<button onClick={()=>p.act(()=>p.approveStockCount(c.id),"Count approved")}>Approve</button>}{c.status==="APPROVED"&&<button onClick={()=>p.act(()=>p.postStockCount(c.id),"Count posted")}>Post</button>}</div></div>):<div className="empty-inline">No stock counts yet.</div>}</div></div>{p.selectedCount&&<div className="count-editor"><div className="section-head compact"><div><p className="eyebrow">COUNT {short(p.selectedCount.id)}</p><h3>Enter physical quantities</h3></div><button className="secondary" onClick={()=>p.setSelectedCount(null)}>Close</button></div>{p.selectedCount.lines.map((l:any)=><div className="count-line" key={l.id}><div><strong>{p.variantMap.get(l.variant_id)?.product_name||short(l.variant_id)}</strong><small>{p.variantMap.get(l.variant_id)?.sku||l.variant_id} · Expected {qty(l.expected_quantity)}</small></div><input type="number" min="0" step="0.001" value={p.countValues[l.variant_id]??""} onChange={e=>p.setCountValues({...p.countValues,[l.variant_id]:e.target.value})} disabled={p.selectedCount.status!=="COUNTING"} /><span>{l.counted_quantity==null?"Not counted":`Variance ${qty(l.variance_quantity||"0")}`}</span></div>)}{p.selectedCount.status==="COUNTING"&&<button className="primary" onClick={p.saveCount}>Save counted quantities</button>}</div>}</> }
function TransfersTab(p:InvProps) { return <><div className="split-panel"><form className="command-form" onSubmit={p.onTransfer}><div><p className="eyebrow">TRANSFER STOCK</p><h3>Move inventory between locations</h3><p>Dispatch decreases source stock; receipt increases destination stock.</p></div><div className="form-grid"><label>From<select value={p.transferFrom} onChange={e=>p.setTransferFrom(e.target.value)} required><option value="">Source</option>{p.locations.map((l:Location)=><option key={l.id} value={l.id}>{l.name}</option>)}</select></label><label>To<select value={p.transferTo} onChange={e=>p.setTransferTo(e.target.value)} required><option value="">Destination</option>{p.locations.map((l:Location)=><option key={l.id} value={l.id}>{l.name}</option>)}</select></label></div><label>Product / SKU<select value={p.transferVariant} onChange={e=>p.setTransferVariant(e.target.value)} required><option value="">Select product</option>{p.variants.map((v:VariantOption)=><option key={v.id} value={v.id}>{v.product_name} · {v.sku}</option>)}</select></label><label>Quantity<input type="number" min="0.001" step="0.001" value={p.transferQty} onChange={e=>p.setTransferQty(e.target.value)} required /></label><button className="primary" type="submit">Create transfer</button></form><div className="workflow-list"><p className="eyebrow">TRANSFER PIPELINE</p>{p.transfers.length?p.transfers.map((t:Transfer)=><div className="workflow-row" key={t.id}><div><strong>{p.locationMap.get(t.source_location_id)?.name||short(t.source_location_id)} → {p.locationMap.get(t.destination_location_id)?.name||short(t.destination_location_id)}</strong><small>{short(t.id)} · {t.lines.length} items</small></div><span className={`status ${t.status==="COMPLETED"?"good":t.status==="APPROVED"||t.status==="RECEIVED"?"warn":"neutral"}`}>{t.status}</span><div className="row-actions">{t.status==="DRAFT"&&<button onClick={()=>p.act(()=>p.approveTransfer(t.id),"Transfer approved")}>Approve</button>}{t.status==="APPROVED"&&<button onClick={()=>p.act(()=>p.dispatchTransfer(t.id),"Transfer dispatched")}>Dispatch</button>}{(t.status==="DISPATCHED"||t.status==="PARTIALLY_RECEIVED")&&<button onClick={()=>p.act(()=>p.receiveTransfer(t.id,{lines:t.lines.map((l:any)=>({variant_id:l.variant_id,counted_quantity:String(Number(l.dispatched_quantity)-Number(l.received_quantity))}))}),"Transfer received")}>Receive</button>}{t.status==="RECEIVED"&&<button onClick={()=>p.act(()=>p.completeTransfer(t.id),"Transfer completed")}>Complete</button>}</div></div>):<div className="empty-inline">No transfers have been created.</div>}</div></div></> }
function LocationsTab(p:InvProps) {
  const create = async (e:React.FormEvent) => { e.preventDefault(); try { const w=await p.createWarehouse({name:p.newWarehouseName,code:p.newWarehouseCode}); await p.createLocation({name:p.newLocationName,code:p.newLocationCode,warehouse_id:w.id}); p.setNewWarehouseName("");p.setNewWarehouseCode("");p.setNewLocationName("");p.setNewLocationCode("");p.setMessage("Warehouse and location created successfully."); p.onRefresh(); } catch(e) { p.setMessage(e instanceof Error?e.message:"Unable to create location"); } };
  return <div><div className="section-head compact"><div><h2>Inventory locations</h2><p className="section-sub">Stock is always attached to a tenant-owned location.</p></div></div><div className="location-setup"><form onSubmit={create}><div><p className="eyebrow">QUICK SETUP</p><h3>Add a warehouse and stock location</h3><p>Create the physical place where LEXA will track inventory.</p></div><div className="form-grid"><label>Warehouse name<input value={p.newWarehouseName} onChange={(e:any)=>p.setNewWarehouseName(e.target.value)} required /></label><label>Warehouse code<input value={p.newWarehouseCode} onChange={(e:any)=>p.setNewWarehouseCode(e.target.value)} required /></label></div><div className="form-grid"><label>Location name<input value={p.newLocationName} onChange={(e:any)=>p.setNewLocationName(e.target.value)} required /></label><label>Location code<input value={p.newLocationCode} onChange={(e:any)=>p.setNewLocationCode(e.target.value)} required /></label></div><button className="primary">Create location</button></form></div><div className="cards-grid location-grid">{p.locations.length?p.locations.map((l:Location)=><article className="location-card" key={l.id}><span className="tag">LOCATION</span><h3>{l.name}</h3><p>{l.code}</p><small>{l.status} · {short(l.id)}</small></article>):<div className="empty"><strong>No locations configured.</strong><p>Use the setup form above to create the first stock location.</p></div>}</div></div> }
