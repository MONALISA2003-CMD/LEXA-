"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { AppShell } from "../../components/app-shell";
import {
  approveAdjustment, approveStockCount, approveTransfer, completeTransfer, createAdjustment, createLocation,
  createStockCount, createTransfer, createWarehouse, dispatchTransfer, getAdjustments, getBranches,
  getInventoryBalances, getInventoryIntegrity, getInventoryLedger, getLocations, getStockCounts, getTransfers,
  getVariantOptions, getWarehouses, postAdjustment, postStockCount, receiveTransfer, submitStockCount,
  updateCountLines, type Branch, type InventoryAdjustment, type InventoryBalance, type InventoryLedger,
  type Location, type StockCount, type Transfer, type VariantOption, type Warehouse,
} from "../../lib/api";

type Tab = "Stock" | "Ledger" | "Adjustments" | "Counts" | "Transfers" | "Locations";
type LineDraft = { variantId: string; quantity: string; unitCost?: string };

const tabs: Tab[] = ["Stock", "Ledger", "Adjustments", "Counts", "Transfers", "Locations"];
const money = (value: string | number) => new Intl.NumberFormat("en-UG", { style: "currency", currency: "UGX", maximumFractionDigits: 0 }).format(Number(value));
const qty = (value: string | number) => new Intl.NumberFormat("en-UG", { maximumFractionDigits: 3 }).format(Number(value));
const short = (value: string) => `${value.slice(0, 8)}…`;

function statusTone(status: string) {
  if (["POSTED", "COMPLETED", "RECEIVED", "APPROVED"].includes(status)) return "good";
  if (["SUBMITTED", "PARTIALLY_RECEIVED", "DISPATCHED"].includes(status)) return "warn";
  if (["DRAFT", "COUNTING"].includes(status)) return "neutral";
  return "neutral";
}

export default function InventoryPage() {
  const [tab, setTab] = useState<Tab>("Stock");
  const [locations, setLocations] = useState<Location[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [variants, setVariants] = useState<VariantOption[]>([]);
  const [balances, setBalances] = useState<InventoryBalance[]>([]);
  const [ledger, setLedger] = useState<InventoryLedger[]>([]);
  const [adjustments, setAdjustments] = useState<InventoryAdjustment[]>([]);
  const [counts, setCounts] = useState<StockCount[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [integrity, setIntegrity] = useState("checking");
  const [search, setSearch] = useState("");
  const [locationFilter, setLocationFilter] = useState("");
  const [ledgerType, setLedgerType] = useState("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const [adjustLocation, setAdjustLocation] = useState("");
  const [adjustReason, setAdjustReason] = useState("COUNT_CORRECTION");
  const [adjustNotes, setAdjustNotes] = useState("");
  const [adjustLines, setAdjustLines] = useState<LineDraft[]>([{ variantId: "", quantity: "", unitCost: "" }]);

  const [countLocation, setCountLocation] = useState("");
  const [countScope, setCountScope] = useState("");
  const [countVariantIds, setCountVariantIds] = useState<string[]>([]);
  const [selectedCountId, setSelectedCountId] = useState("");
  const [countValues, setCountValues] = useState<Record<string, string>>({});

  const [transferFrom, setTransferFrom] = useState("");
  const [transferTo, setTransferTo] = useState("");
  const [transferNotes, setTransferNotes] = useState("");
  const [transferLines, setTransferLines] = useState<LineDraft[]>([{ variantId: "", quantity: "" }]);

  const [warehouseName, setWarehouseName] = useState("");
  const [warehouseCode, setWarehouseCode] = useState("");
  const [warehouseBranch, setWarehouseBranch] = useState("");
  const [locationName, setLocationName] = useState("");
  const [locationCode, setLocationCode] = useState("");
  const [locationWarehouse, setLocationWarehouse] = useState("");

  const variantMap = useMemo(() => new Map(variants.map((x) => [x.id, x])), [variants]);
  const locationMap = useMemo(() => new Map(locations.map((x) => [x.id, x])), [locations]);
  const warehouseMap = useMemo(() => new Map(warehouses.map((x) => [x.id, x])), [warehouses]);
  const selectedCount = useMemo(() => counts.find((x) => x.id === selectedCountId) || null, [counts, selectedCountId]);

  async function load() {
    setBusy(true); setError("");
    try {
      const [l, w, b, v, bal, led, adj, cnt, tr, check] = await Promise.all([
        getLocations(), getWarehouses(), getBranches(), getVariantOptions(),
        getInventoryBalances({ location_id: locationFilter || undefined, q: search || undefined }),
        getInventoryLedger({ location_id: locationFilter || undefined, transaction_type: ledgerType || undefined }),
        getAdjustments(), getStockCounts(), getTransfers(), getInventoryIntegrity(),
      ]);
      setLocations(l); setWarehouses(w); setBranches(b); setVariants(v); setBalances(bal); setLedger(led); setAdjustments(adj); setCounts(cnt); setTransfers(tr); setIntegrity(check.status);
      if (!adjustLocation && l[0]) setAdjustLocation(l[0].id);
      if (!countLocation && l[0]) setCountLocation(l[0].id);
      if (!transferFrom && l[0]) setTransferFrom(l[0].id);
      if (!transferTo && l[1]) setTransferTo(l[1].id);
      if (!locationWarehouse && w[0]) setLocationWarehouse(w[0].id);
      if (!selectedCountId && cnt[0]) setSelectedCountId(cnt[0].id);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to load inventory."); }
    finally { setBusy(false); }
  }

  useEffect(() => { const timer = setTimeout(() => void load(), 200); return () => clearTimeout(timer); }, [locationFilter, search, ledgerType]);
  useEffect(() => {
    const query = new URLSearchParams(window.location.search).get("q");
    if (query) setSearch(query);
  }, []);

  function updateLine(setter: (value: LineDraft[]) => void, lines: LineDraft[], index: number, field: keyof LineDraft, value: string) {
    setter(lines.map((line, i) => i === index ? { ...line, [field]: value } : line));
  }

  async function submitAdjustment(event: FormEvent) {
    event.preventDefault();
    const lines = adjustLines.filter((line) => line.variantId && Number(line.quantity) !== 0).map((line) => ({ variant_id: line.variantId, quantity_delta: line.quantity, unit_cost: line.unitCost || "0" }));
    if (!adjustLocation || !lines.length) { setMessage("Select a location and at least one non-zero adjustment line."); return; }
    setBusy(true);
    try { await createAdjustment({ location_id: adjustLocation, reason_code: adjustReason, notes: adjustNotes || null, lines }); setAdjustLines([{ variantId: "", quantity: "", unitCost: "" }]); setAdjustNotes(""); setMessage("Adjustment created as a draft. Approval is required before posting."); setTab("Adjustments"); await load(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Could not create the adjustment."); } finally { setBusy(false); }
  }

  async function runAdjustmentAction(id: string, action: "approve" | "post") {
    setBusy(true);
    try { if (action === "approve") await approveAdjustment(id); else await postAdjustment(id); setMessage(action === "approve" ? "Adjustment approved. It is ready to post." : "Adjustment posted to the inventory ledger."); await load(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Inventory action could not be completed."); } finally { setBusy(false); }
  }

  async function createCount(event: FormEvent) {
    event.preventDefault(); if (!countLocation || countVariantIds.length === 0) { setMessage("Choose a location and one or more variants to count."); return; }
    setBusy(true);
    try { const created = await createStockCount({ location_id: countLocation, scope_description: countScope || null, variant_ids: countVariantIds }); setSelectedCountId(created.id); setCountVariantIds([]); setCountScope(""); setMessage("Stock count opened. Enter physical quantities before submission."); setTab("Counts"); await load(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Could not create the stock count."); } finally { setBusy(false); }
  }

  async function saveCountLines() {
    if (!selectedCount) return;
    const lines = selectedCount.lines.filter((line) => countValues[line.variant_id] !== undefined && countValues[line.variant_id] !== "").map((line) => ({ variant_id: line.variant_id, counted_quantity: countValues[line.variant_id] }));
    if (!lines.length) { setMessage("Enter at least one counted quantity."); return; }
    setBusy(true);
    try { await updateCountLines(selectedCount.id, { lines }); setMessage("Counted quantities saved. Review variances before submission."); await load(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Could not save counted quantities."); } finally { setBusy(false); }
  }

  async function runCountAction(id: string, action: "submit" | "approve" | "post") {
    setBusy(true);
    try { if (action === "submit") await submitStockCount(id); if (action === "approve") await approveStockCount(id); if (action === "post") await postStockCount(id); setMessage(action === "submit" ? "Stock count submitted for approval." : action === "approve" ? "Stock count approved." : "Stock count posted; variances are now ledger corrections."); await load(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Stock count action could not be completed."); } finally { setBusy(false); }
  }

  async function submitTransfer(event: FormEvent) {
    event.preventDefault();
    const lines = transferLines.filter((line) => line.variantId && Number(line.quantity) > 0).map((line) => ({ variant_id: line.variantId, quantity: line.quantity }));
    if (!transferFrom || !transferTo || transferFrom === transferTo || !lines.length) { setMessage("Choose different source/destination locations and at least one quantity."); return; }
    setBusy(true);
    try { const created = await createTransfer({ source_location_id: transferFrom, destination_location_id: transferTo, notes: transferNotes || null, lines }); setTransferLines([{ variantId: "", quantity: "" }]); setTransferNotes(""); setMessage("Transfer created as draft. Approval and dispatch happen before destination receipt."); setTab("Transfers"); await load(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Could not create the transfer."); } finally { setBusy(false); }
  }

  async function runTransferAction(id: string, action: "approve" | "dispatch" | "receive" | "complete") {
    setBusy(true);
    try {
      if (action === "approve") await approveTransfer(id);
      if (action === "dispatch") await dispatchTransfer(id);
      if (action === "complete") await completeTransfer(id);
      if (action === "receive") {
        const transfer = transfers.find((item) => item.id === id);
        if (!transfer) throw new Error("Transfer not found.");
        const lines = transfer.lines.filter((line) => Number(line.dispatched_quantity) > Number(line.received_quantity)).map((line) => ({ variant_id: line.variant_id, counted_quantity: String(Number(line.dispatched_quantity) - Number(line.received_quantity)) }));
        if (!lines.length) throw new Error("There is nothing remaining to receive on this transfer.");
        await receiveTransfer(id, { lines });
      }
      setMessage(action === "receive" ? "Transfer receipt recorded at the destination." : `Transfer ${action} completed.`); await load();
    } catch (e) { setMessage(e instanceof Error ? e.message : "Transfer action could not be completed."); } finally { setBusy(false); }
  }

  async function submitWarehouse(event: FormEvent) {
    event.preventDefault(); if (!warehouseName.trim() || !warehouseCode.trim()) return;
    setBusy(true);
    try { const created = await createWarehouse({ name: warehouseName.trim(), code: warehouseCode.trim().toUpperCase(), branch_id: warehouseBranch || null }); setWarehouseName(""); setWarehouseCode(""); setMessage(`Warehouse ${created.name} created.`); await load(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Could not create warehouse."); } finally { setBusy(false); }
  }

  async function submitLocation(event: FormEvent) {
    event.preventDefault(); if (!locationName.trim() || !locationCode.trim() || !locationWarehouse) return;
    setBusy(true);
    try { const created = await createLocation({ name: locationName.trim(), code: locationCode.trim().toUpperCase(), warehouse_id: locationWarehouse }); setLocationName(""); setLocationCode(""); setMessage(`Location ${created.name} created.`); await load(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Could not create location."); } finally { setBusy(false); }
  }

  const total = balances.reduce((sum, row) => sum + Number(row.stock_value), 0);
  const low = balances.filter((row) => Number(row.available) > 0 && Number(row.available) <= 5).length;
  const out = balances.filter((row) => Number(row.available) <= 0).length;
  const mismatch = integrity === "mismatch";

  return <AppShell title="Inventory" eyebrow="Operations">
    <div className="module-toolbar"><div><strong>Stock control</strong><span>Historical ledger · projected balances · controlled operational workflows</span></div><div className="toolbar-actions"><button className="button button-soft" onClick={() => void load()} disabled={busy}>Refresh</button><button className="button button-dark" onClick={() => setTab("Adjustments")}>+ Inventory action</button></div></div>
    {message && <div className="notice">{message}</div>}{error && <div className="notice notice-error">{error}</div>}
    <div className="metric-strip"><div><span>Stock value</span><strong>{money(total)}</strong><small>Projected from posted inventory state</small></div><div><span>Locations</span><strong>{locations.length}</strong><small>{warehouses.length} warehouses</small></div><div><span>Low stock</span><strong>{low}</strong><small>Available quantity ≤ 5</small></div><div><span>Out of stock</span><strong>{out}</strong><small>Available quantity ≤ 0</small></div></div>

    <section className="panel"><div className="module-tabs">{tabs.map((name) => <button key={name} className={tab===name?"active":""} onClick={()=>setTab(name)}>{name}</button>)}</div>

      {tab === "Stock" && <><div className="panel-head"><div><h2>Current stock</h2><p>On-hand, reservations and available stock are projections backed by the authoritative inventory ledger.</p></div><div className="filter-row"><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search product or SKU"/><select value={locationFilter} onChange={e=>setLocationFilter(e.target.value)}><option value="">All locations</option>{locations.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></div></div><div className="data-table-wrap"><table className="data-table"><thead><tr><th>Item</th><th>Location</th><th>On hand</th><th>Available</th><th>Avg. cost</th><th>Value</th><th>Updated</th></tr></thead><tbody>{balances.map(row=><tr key={row.id}><td><strong>{variantMap.get(row.variant_id)?.name || short(row.variant_id)}</strong><small>{variantMap.get(row.variant_id)?.sku || "Variant"}</small></td><td>{locationMap.get(row.location_id)?.name || short(row.location_id)}</td><td>{qty(row.on_hand)}</td><td className={Number(row.available)<=0?"number-danger":Number(row.available)<=5?"number-warning":""}>{qty(row.available)}</td><td>{money(row.average_cost)}</td><td>{money(row.stock_value)}</td><td>{new Date(row.updated_at).toLocaleString("en-GB")}</td></tr>)}{!balances.length&&!busy&&<tr><td colSpan={7}><div className="empty-state"><strong>No stock rows</strong><span>Stock appears here as inventory balances are established.</span></div></td></tr>}</tbody></table></div><div className={`integrity-line ${mismatch?"integrity-bad":""}`}><span className={`status-dot ${mismatch?"warning":""}`}/>{mismatch?"Inventory integrity mismatch detected. Investigate before using balance projections.":`Ledger integrity ${integrity} · ${balances.length} visible balance rows`}<button onClick={()=>void load()}>Recheck</button></div></>}

      {tab === "Ledger" && <><div className="panel-head"><div><h2>Inventory ledger</h2><p>Immutable history of stock-affecting movements. Corrections are new transactions, not edits.</p></div><div className="filter-row"><select value={locationFilter} onChange={e=>setLocationFilter(e.target.value)}><option value="">All locations</option>{locations.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select><select value={ledgerType} onChange={e=>setLedgerType(e.target.value)}><option value="">All movement types</option><option>ADJUSTMENT</option><option>COUNT_RECONCILIATION</option><option>TRANSFER_OUT</option><option>TRANSFER_IN</option><option>PURCHASE</option><option>SALE</option><option>SALE_RETURN</option></select></div></div><div className="data-table-wrap"><table className="data-table"><thead><tr><th>Time</th><th>Item</th><th>Location</th><th>Movement</th><th>Quantity</th><th>Unit cost</th><th>Balance after</th><th>Source</th></tr></thead><tbody>{ledger.map(row=><tr key={row.id}><td>{new Date(row.occurred_at).toLocaleString("en-GB")}</td><td><strong>{variantMap.get(row.variant_id)?.name || short(row.variant_id)}</strong><small>{variantMap.get(row.variant_id)?.sku || "Variant"}</small></td><td>{locationMap.get(row.location_id)?.name || short(row.location_id)}</td><td><span className="status-pill status-muted">{row.transaction_type}</span></td><td className={Number(row.quantity_delta)<0?"number-danger":"number-good"}>{Number(row.quantity_delta)>0?"+":""}{qty(row.quantity_delta)}</td><td>{money(row.unit_cost)}</td><td>{qty(row.balance_after)}</td><td>{row.reference_type?`${row.reference_type} ${row.reference_id?short(row.reference_id):""}`:"—"}</td></tr>)}{!ledger.length&&!busy&&<tr><td colSpan={8}><div className="empty-state"><strong>No ledger movements</strong><span>Posted stock movements will become the historical record here.</span></div></td></tr>}</tbody></table></div></>}

      {tab === "Adjustments" && <div className="operations-layout"><form className="operation-form" onSubmit={submitAdjustment}><div><p className="eyebrow">CONTROLLED ADJUSTMENT</p><h3>Create an adjustment</h3><p>Draft → Approved → Posted. Positive quantities require an explicit unit cost.</p></div><label>Location<select value={adjustLocation} onChange={e=>setAdjustLocation(e.target.value)} required>{locations.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label>Reason<select value={adjustReason} onChange={e=>setAdjustReason(e.target.value)}><option>COUNT_CORRECTION</option><option>DAMAGE</option><option>LOSS</option><option>FOUND</option><option>OPENING_BALANCE</option><option>OTHER</option></select></label><label>Notes<textarea value={adjustNotes} onChange={e=>setAdjustNotes(e.target.value)} rows={2} placeholder="Why did the physical stock differ?"/></label><div className="line-editor"><div className="line-editor-head"><strong>Lines</strong><button type="button" className="button button-soft button-small" onClick={()=>setAdjustLines([...adjustLines,{variantId:"",quantity:"",unitCost:""}])}>+ Add line</button></div>{adjustLines.map((line,i)=><div className="editor-row" key={i}><select value={line.variantId} onChange={e=>updateLine(setAdjustLines,adjustLines,i,"variantId",e.target.value)} required><option value="">Item</option>{variants.map(v=><option key={v.id} value={v.id}>{v.product_name} · {v.name} · {v.sku}</option>)}</select><input type="number" step="0.001" value={line.quantity} onChange={e=>updateLine(setAdjustLines,adjustLines,i,"quantity",e.target.value)} placeholder="± Qty" required/><input type="number" min="0" step="0.01" value={line.unitCost||""} onChange={e=>updateLine(setAdjustLines,adjustLines,i,"unitCost",e.target.value)} placeholder="Unit cost"/><button type="button" className="row-remove" onClick={()=>setAdjustLines(adjustLines.filter((_,idx)=>idx!==i))} aria-label="Remove line">×</button></div>)}</div><button className="button button-dark" disabled={busy}>Create draft adjustment</button></form><div className="operation-list"><div className="list-head"><div><p className="eyebrow">ADJUSTMENT REGISTER</p><h3>Recent adjustments</h3></div></div>{adjustments.length?adjustments.map(item=><div className="workflow-row" key={item.id}><div><strong>{item.reason_code} · {short(item.id)}</strong><small>{locationMap.get(item.location_id)?.name||short(item.location_id)} · {item.lines.length} line(s)</small></div><span className={`status ${statusTone(item.status)}`}>{item.status}</span><div className="row-actions">{item.status==="DRAFT"&&<button className="button button-soft button-small" onClick={()=>void runAdjustmentAction(item.id,"approve")} disabled={busy}>Approve</button>}{item.status==="APPROVED"&&<button className="button button-dark button-small" onClick={()=>void runAdjustmentAction(item.id,"post")} disabled={busy}>Post</button>}</div></div>):<div className="empty-inline">No adjustments created yet.</div>}</div></div>}

      {tab === "Counts" && <div className="operations-layout"><div><form className="operation-form" onSubmit={createCount}><div><p className="eyebrow">PHYSICAL COUNT</p><h3>Open a stock count</h3><p>Count the physical quantity against the system expectation. Every line must be counted before submission.</p></div><label>Location<select value={countLocation} onChange={e=>setCountLocation(e.target.value)} required>{locations.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label>Scope<input value={countScope} onChange={e=>setCountScope(e.target.value)} placeholder="e.g. electronics shelf A"/></label><div className="variant-picker"><strong>Variants to count</strong>{variants.map(v=><label key={v.id} className="check-line"><input type="checkbox" checked={countVariantIds.includes(v.id)} onChange={e=>setCountVariantIds(current=>e.target.checked?[...current,v.id]:current.filter(id=>id!==v.id))}/><span>{v.product_name} · {v.name} <small>{v.sku}</small></span></label>)}</div><button className="button button-dark" disabled={busy}>Open count</button></form><div className="operation-list"><div className="list-head"><div><p className="eyebrow">COUNT REGISTER</p><h3>Stock counts</h3></div><select value={selectedCountId} onChange={e=>setSelectedCountId(e.target.value)}><option value="">Select count</option>{counts.map(x=><option key={x.id} value={x.id}>{short(x.id)} · {x.status}</option>)}</select></div>{counts.map(item=><button type="button" className={`workflow-row workflow-row-button ${selectedCountId===item.id?"selected":""}`} key={item.id} onClick={()=>setSelectedCountId(item.id)}><div><strong>{short(item.id)} · {item.scope_description||"Count"}</strong><small>{locationMap.get(item.location_id)?.name||short(item.location_id)} · {item.lines.length} line(s)</small></div><span className={`status ${statusTone(item.status)}`}>{item.status}</span></button>)}</div></div><div className="operation-detail">{selectedCount?<><div className="list-head"><div><p className="eyebrow">COUNT REVIEW</p><h3>{short(selectedCount.id)}</h3><small>{locationMap.get(selectedCount.location_id)?.name||short(selectedCount.location_id)} · {selectedCount.status}</small></div></div><div className="count-grid">{selectedCount.lines.map(line=>{const counted=countValues[line.variant_id] ?? line.counted_quantity ?? ""; const variance=counted===""?null:Number(counted)-Number(line.expected_quantity); return <div className="count-row" key={line.id}><div><strong>{variantMap.get(line.variant_id)?.name||short(line.variant_id)}</strong><small>{variantMap.get(line.variant_id)?.sku||"Variant"}</small></div><span>Expected {qty(line.expected_quantity)}</span><input type="number" min="0" step="0.001" value={counted} onChange={e=>setCountValues(values=>({...values,[line.variant_id]:e.target.value}))} disabled={selectedCount.status!=="COUNTING"} placeholder="Counted"/><span className={variance===null?"":variance<0?"number-danger":"number-warning"}>{variance===null?"—":`${variance>0?"+":""}${qty(variance)}`}</span></div>})}</div>{selectedCount.status==="COUNTING"&&<div className="row-actions"><button className="button button-soft" onClick={()=>void saveCountLines()} disabled={busy}>Save quantities</button><button className="button button-dark" onClick={()=>void runCountAction(selectedCount.id,"submit")} disabled={busy}>Submit for approval</button></div>}{selectedCount.status==="SUBMITTED"&&<button className="button button-dark" onClick={()=>void runCountAction(selectedCount.id,"approve")} disabled={busy}>Approve count</button>}{selectedCount.status==="APPROVED"&&<button className="button button-dark" onClick={()=>void runCountAction(selectedCount.id,"post")} disabled={busy}>Post count & reconcile</button>}</>:<div className="module-placeholder"><span>◎</span><strong>Select a stock count</strong><p>Open a count from the left register to review expected quantity, enter physical counts and resolve variances.</p></div>}</div></div>}

      {tab === "Transfers" && <div className="operations-layout"><form className="operation-form" onSubmit={submitTransfer}><div><p className="eyebrow">LOCATION TRANSFER</p><h3>Move stock between locations</h3><p>Draft → Approved → Dispatched → Received → Completed. Dispatch reduces source stock; receipt increases destination stock.</p></div><div className="form-grid"><label>From<select value={transferFrom} onChange={e=>setTransferFrom(e.target.value)} required>{locations.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label>To<select value={transferTo} onChange={e=>setTransferTo(e.target.value)} required>{locations.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label></div><label>Notes<textarea value={transferNotes} onChange={e=>setTransferNotes(e.target.value)} rows={2} placeholder="Reason or dispatch note"/></label><div className="line-editor"><div className="line-editor-head"><strong>Items</strong><button type="button" className="button button-soft button-small" onClick={()=>setTransferLines([...transferLines,{variantId:"",quantity:""}])}>+ Add item</button></div>{transferLines.map((line,i)=><div className="editor-row" key={i}><select value={line.variantId} onChange={e=>updateLine(setTransferLines,transferLines,i,"variantId",e.target.value)} required><option value="">Item</option>{variants.map(v=><option key={v.id} value={v.id}>{v.product_name} · {v.name} · {v.sku}</option>)}</select><input type="number" min="0.001" step="0.001" value={line.quantity} onChange={e=>updateLine(setTransferLines,transferLines,i,"quantity",e.target.value)} placeholder="Quantity" required/><button type="button" className="row-remove" onClick={()=>setTransferLines(transferLines.filter((_,idx)=>idx!==i))} aria-label="Remove line">×</button></div>)}</div><button className="button button-dark" disabled={busy}>Create transfer</button></form><div className="operation-list"><div className="list-head"><div><p className="eyebrow">TRANSFER REGISTER</p><h3>Recent transfers</h3></div></div>{transfers.length?transfers.map(item=><div className="workflow-row" key={item.id}><div><strong>{short(item.id)} · {locationMap.get(item.source_location_id)?.name||short(item.source_location_id)} → {locationMap.get(item.destination_location_id)?.name||short(item.destination_location_id)}</strong><small>{item.lines.length} line(s) · {item.notes||"No notes"}</small></div><span className={`status ${statusTone(item.status)}`}>{item.status}</span><div className="row-actions">{item.status==="DRAFT"&&<button className="button button-soft button-small" onClick={()=>void runTransferAction(item.id,"approve")} disabled={busy}>Approve</button>}{item.status==="APPROVED"&&<button className="button button-dark button-small" onClick={()=>void runTransferAction(item.id,"dispatch")} disabled={busy}>Dispatch</button>}{(item.status==="DISPATCHED"||item.status==="PARTIALLY_RECEIVED")&&<button className="button button-dark button-small" onClick={()=>void runTransferAction(item.id,"receive")} disabled={busy}>Receive</button>}{item.status==="RECEIVED"&&<button className="button button-dark button-small" onClick={()=>void runTransferAction(item.id,"complete")} disabled={busy}>Complete</button>}</div></div>):<div className="empty-inline">No transfers created yet.</div>}</div></div>}

      {tab === "Locations" && <div className="operations-layout"><form className="operation-form" onSubmit={submitWarehouse}><div><p className="eyebrow">WAREHOUSE</p><h3>Create warehouse</h3><p>Warehouses group operational locations. Branch assignment is optional in the current organization contract.</p></div><label>Name<input value={warehouseName} onChange={e=>setWarehouseName(e.target.value)} placeholder="Main warehouse" required/></label><label>Code<input value={warehouseCode} onChange={e=>setWarehouseCode(e.target.value)} placeholder="WH-KLA-01" required/></label><label>Branch<select value={warehouseBranch} onChange={e=>setWarehouseBranch(e.target.value)}><option value="">No branch assignment</option>{branches.map(x=><option key={x.id} value={x.id}>{x.name} · {x.code}</option>)}</select></label><button className="button button-dark" disabled={busy}>Create warehouse</button></form><form className="operation-form" onSubmit={submitLocation}><div><p className="eyebrow">LOCATION</p><h3>Create inventory location</h3><p>Locations are the concrete stock positions used by balances, transfers and counts.</p></div><label>Warehouse<select value={locationWarehouse} onChange={e=>setLocationWarehouse(e.target.value)} required><option value="">Select warehouse</option>{warehouses.map(x=><option key={x.id} value={x.id}>{x.name} · {x.code}</option>)}</select></label><label>Name<input value={locationName} onChange={e=>setLocationName(e.target.value)} placeholder="Main floor" required/></label><label>Code<input value={locationCode} onChange={e=>setLocationCode(e.target.value)} placeholder="LOC-01" required/></label><button className="button button-dark" disabled={busy}>Create location</button></form><div className="operation-list full-width"><div className="list-head"><div><p className="eyebrow">LOCATION REGISTER</p><h3>{locations.length} locations</h3></div></div>{locations.map(item=><div className="workflow-row" key={item.id}><div><strong>{item.name}</strong><small>{item.code} · Warehouse {warehouseMap.get(item.warehouse_id)?.name||short(item.warehouse_id)}</small></div><span className="status good">{item.status}</span></div>)}{!locations.length&&<div className="empty-inline">No locations yet.</div>}</div></div>}
    </section>
  </AppShell>;
}