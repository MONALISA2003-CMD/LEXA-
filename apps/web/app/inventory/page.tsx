"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { AppShell } from "../../components/app-shell";
import { ResponsiveDataTable } from "../../components/ui";
import {
  approveAdjustment, approveStockCount, approveTransfer, completeTransfer, createAdjustment, createLocation,
  createStockCount, createTransfer, createWarehouse, dispatchTransfer, getAdjustments, getBranches,
  getBusinessProfile, getInventoryAgeing, getInventoryBalances, getInventoryIntegrity, getInventoryLedger, getInventoryMovementHealth, getInventoryReplenishmentPolicies, getInventoryReplenishmentRecommendations, getLocations, getStockCounts, getTransfers, upsertInventoryReplenishmentPolicy,
  getVariantOptions, getWarehouses, postAdjustment, postStockCount, receiveTransfer, submitStockCount,
  updateCountLines, type Branch, type InventoryAdjustment, type InventoryAgeing, type InventoryBalance, type InventoryLedger, type InventoryMovementHealth, type ReplenishmentPolicy, type ReplenishmentRecommendation,
  type Location, type StockCount, type Transfer, type VariantOption, type Warehouse,
  userFacingError,
} from "../../lib/api";

type Tab = "Stock" | "Ledger" | "Adjustments" | "Counts" | "Transfers" | "Locations" | "Stock Health" | "Replenishment" | "Stock Age";
type LineDraft = { variantId: string; quantity: string; unitCost?: string };

const tabs: Tab[] = ["Stock", "Ledger", "Adjustments", "Counts", "Transfers", "Locations", "Stock Health", "Replenishment", "Stock Age"];
const tabLabels: Record<Tab, string> = { Stock: "Stock levels", Ledger: "Stock history", Adjustments: "Stock corrections", Counts: "Stock counts", Transfers: "Move stock", Locations: "Locations", "Stock Health": "Stock checks", Replenishment: "Restock suggestions", "Stock Age": "Age of stock" };
function movementLabel(value: string) {
  const labels: Record<string, string> = { ADJUSTMENT: "Stock correction", COUNT_RECONCILIATION: "Stock count", TRANSFER_OUT: "Moved out", TRANSFER_IN: "Moved in", PURCHASE: "Purchase received", SALE: "Sale", SALE_RETURN: "Sale return" };
  return labels[value] || value.replaceAll("_", " ").toLowerCase();
}
function statusLabel(value: string) {
  const labels: Record<string, string> = { DRAFT: "Draft", APPROVED: "Approved", POSTED: "Recorded", RECEIVED: "Received", PARTIALLY_RECEIVED: "Partly received", DISPATCHED: "On the way", COMPLETED: "Completed", COUNTING: "In progress", SUBMITTED: "Sent for approval", OPEN: "Open", ACTIVE: "Available", INACTIVE: "Not available", DISABLED: "Paused", REQUESTED: "Awaiting approval", CANCELLED: "Cancelled", VOIDED: "Cancelled" };
  return labels[value] || value.replaceAll("_", " ").toLowerCase();
}
function healthLabel(value: string) {
  const labels: Record<string, string> = { OUT_OF_STOCK: "Out of stock", OUT_OF_STOCK_WITH_RECENT_DEMAND: "Out of stock with recent demand", AT_OR_BELOW_CONFIGURED_MINIMUM: "At or below minimum", NO_SALE_90D: "No sale in 90 days", NO_SALE_60D: "No sale in 60 days", NO_SALE_30D: "No sale in 30 days", NO_COMPLETED_SALE_HISTORY: "No completed sale found", HEALTHY: "Stock looks healthy" };
  return labels[value] || value.replaceAll("_", " ").toLowerCase();
}
function restockReasonLabel(value: string) {
  const labels: Record<string, string> = { AT_OR_BELOW_MINIMUM_AVAILABLE: "At or below the minimum level", BELOW_TARGET_STOCK: "Below the preferred stock level", NO_NET_DEMAND_IN_LOOKBACK: "No recent demand after returns", TARGET_STOCK_COVERED: "Enough stock for the expected demand" };
  return labels[value] || value.replaceAll("_", " ").toLowerCase();
}
function restockActionLabel(value: string) {
  const labels: Record<string, string> = { REORDER: "Restock soon", MONITOR: "Keep an eye on this item", STOCK_COVERED: "Stock looks sufficient" };
  return labels[value] || "Review this item";
}
const money = (value: string | number, currencyCode: string | null) => {
  if (!currencyCode || !/^[A-Z]{3}$/.test(currencyCode)) return "Business currency not set";
  try { return new Intl.NumberFormat("en-UG", { style: "currency", currency: currencyCode, maximumFractionDigits: 0 }).format(Number(value)); }
  catch { return `${currencyCode} ${Number(value).toLocaleString("en-UG", { maximumFractionDigits: 0 })}`; }
};
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
  const [businessCurrency, setBusinessCurrency] = useState<string | null>(null);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [variants, setVariants] = useState<VariantOption[]>([]);
  const [balances, setBalances] = useState<InventoryBalance[]>([]);
  const [ledger, setLedger] = useState<InventoryLedger[]>([]);
  const [adjustments, setAdjustments] = useState<InventoryAdjustment[]>([]);
  const [counts, setCounts] = useState<StockCount[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [replenishmentPolicies, setReplenishmentPolicies] = useState<ReplenishmentPolicy[]>([]);
  const [replenishmentRecommendations, setReplenishmentRecommendations] = useState<ReplenishmentRecommendation[]>([]);
  const [ageingRows, setAgeingRows] = useState<InventoryAgeing[]>([]);
  const [movementHealthRows, setMovementHealthRows] = useState<InventoryMovementHealth[]>([]);
  const [movementHealthBusy, setMovementHealthBusy] = useState(false);
  const [movementHealthError, setMovementHealthError] = useState("");
  const [ageingBusy, setAgeingBusy] = useState(false);
  const [ageingError, setAgeingError] = useState("");
  const [replenishmentLocation, setReplenishmentLocation] = useState("");
  const [replenishmentVariant, setReplenishmentVariant] = useState("");
  const [replenishmentLeadDays, setReplenishmentLeadDays] = useState("7");
  const [replenishmentReviewDays, setReplenishmentReviewDays] = useState("7");
  const [replenishmentLookbackDays, setReplenishmentLookbackDays] = useState("30");
  const [replenishmentMinimum, setReplenishmentMinimum] = useState("0");
  const [replenishmentSafety, setReplenishmentSafety] = useState("0");
  const [replenishmentBusy, setReplenishmentBusy] = useState(false);
  const [replenishmentError, setReplenishmentError] = useState("");
  const [integrity, setIntegrity] = useState("checking");
  const [search, setSearch] = useState("");
  const [locationFilter, setLocationFilter] = useState("");
  const [ledgerType, setLedgerType] = useState("");
  const [busy, setBusy] = useState(true);
  const [filtersBusy, setFiltersBusy] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [error, setError] = useState("");
  const [stockError, setStockError] = useState("");
  const firstFilterEffect = useRef(true);
  const stockRequestId = useRef(0);
  const movementHealthRequestId = useRef(0);
  const ageingRequestId = useRef(0);
  const replenishmentRequestId = useRef(0);
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
    const requestId = ++stockRequestId.current;
    setBusy(true); setError(""); setStockError(""); setFiltersBusy(false); setHasLoaded(false);
    try {
      const [profile, l, w, b, v, bal, led, adj, cnt, tr, check] = await Promise.all([
        getBusinessProfile().catch(() => null), getLocations(), getWarehouses(), getBranches(), getVariantOptions(),
        getInventoryBalances({ location_id: locationFilter || undefined, q: search || undefined }),
        getInventoryLedger({ location_id: locationFilter || undefined, transaction_type: ledgerType || undefined }),
        getAdjustments(), getStockCounts(), getTransfers(), getInventoryIntegrity(),
      ]);
      setBusinessCurrency(profile?.currency_code && /^[A-Z]{3}$/i.test(profile.currency_code) ? profile.currency_code.toUpperCase() : null);
      setLocations(l); setWarehouses(w); setBranches(b); setVariants(v); setAdjustments(adj); setCounts(cnt); setTransfers(tr); setIntegrity(check.status); setHasLoaded(true);
      if (requestId === stockRequestId.current) { setBalances(bal); setLedger(led); setStockError(""); }
      if (!adjustLocation && l[0]) setAdjustLocation(l[0].id);
      if (!countLocation && l[0]) setCountLocation(l[0].id);
      if (!transferFrom && l[0]) setTransferFrom(l[0].id);
      if (!transferTo && l[1]) setTransferTo(l[1].id);
      if (!locationWarehouse && w[0]) setLocationWarehouse(w[0].id);
      if (!selectedCountId && cnt[0]) setSelectedCountId(cnt[0].id);
    } catch (e) {
      setError(userFacingError(e, "Unable to load inventory."));
      setHasLoaded(false); setLocations([]); setWarehouses([]); setBranches([]); setVariants([]); setAdjustments([]); setCounts([]); setTransfers([]); setIntegrity("unavailable");
      if (requestId === stockRequestId.current) { setBalances([]); setLedger([]); setStockError(userFacingError(e, "Unable to load inventory balances.")); }
    }
    finally { setBusy(false); }
  }

  // Load workspace/reference data once. Search and filter edits below refresh only
  // the two affected datasets instead of refetching every inventory workflow.
  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (firstFilterEffect.current) { firstFilterEffect.current = false; return; }
    const controller = new AbortController();
    const requestId = ++stockRequestId.current;
    setFiltersBusy(true); setStockError("");
    const timer = window.setTimeout(async () => {
      try {
        const [nextBalances, nextLedger] = await Promise.all([
          getInventoryBalances({ location_id: locationFilter || undefined, q: search.trim() || undefined }, controller.signal),
          getInventoryLedger({ location_id: locationFilter || undefined, transaction_type: ledgerType || undefined }, controller.signal),
        ]);
        if (controller.signal.aborted || requestId !== stockRequestId.current) return;
        setBalances(nextBalances); setLedger(nextLedger); setStockError("");
      } catch (e) {
        if (controller.signal.aborted || requestId !== stockRequestId.current) return;
        setStockError(userFacingError(e, "Unable to refresh the filtered stock data."));
      } finally {
        if (!controller.signal.aborted && requestId === stockRequestId.current) setFiltersBusy(false);
      }
    }, 200);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [locationFilter, search, ledgerType]);
  useEffect(() => {
    const query = new URLSearchParams(window.location.search).get("q");
    if (query) setSearch(query);
  }, []);

  async function loadReplenishment() {
    const requestId = ++replenishmentRequestId.current;
    setReplenishmentBusy(true); setReplenishmentError("");
    try {
      const [policies, recommendations] = await Promise.all([
        getInventoryReplenishmentPolicies(replenishmentLocation || undefined),
        getInventoryReplenishmentRecommendations(replenishmentLocation || undefined),
      ]);
      if (requestId !== replenishmentRequestId.current) return;
      setReplenishmentPolicies(policies); setReplenishmentRecommendations(recommendations.items);
    } catch (e) {
      if (requestId !== replenishmentRequestId.current) return;
      setReplenishmentError(userFacingError(e, "Restock suggestions could not be loaded."));
      setReplenishmentPolicies([]); setReplenishmentRecommendations([]);
    } finally { if (requestId === replenishmentRequestId.current) setReplenishmentBusy(false); }
  }

  async function loadMovementHealth() {
    setMovementHealthBusy(true); setMovementHealthError("");
    try {
      const result = await getInventoryMovementHealth(locationFilter || undefined);
      setMovementHealthRows(result.items);
    } catch (e) {
      setMovementHealthError(userFacingError(e, "Stock checks could not be loaded."));
      setMovementHealthRows([]);
    } finally { setMovementHealthBusy(false); }
  }

  async function loadAgeing() {
    setAgeingBusy(true); setAgeingError("");
    try { const result = await getInventoryAgeing(locationFilter || undefined); setAgeingRows(result.items); }
    catch (e) { setAgeingError(userFacingError(e, "Stock age could not be checked.")); setAgeingRows([]); }
    finally { setAgeingBusy(false); }
  }

  async function saveReplenishmentPolicy(event: FormEvent) {
    event.preventDefault();
    if (!replenishmentLocation || !replenishmentVariant) { setMessage("Choose a location and product first."); return; }
    setReplenishmentBusy(true); setReplenishmentError("");
    try {
      await upsertInventoryReplenishmentPolicy({
        location_id: replenishmentLocation, variant_id: replenishmentVariant,
        lead_time_days: Number(replenishmentLeadDays), review_period_days: Number(replenishmentReviewDays),
        lookback_days: Number(replenishmentLookbackDays), minimum_available: replenishmentMinimum,
        safety_stock: replenishmentSafety, enabled: true,
      });
      setMessage("Restock reminders saved. Suggestions now reflect completed sales and returns.");
      await loadReplenishment();
    } catch (e) {
      setReplenishmentError(userFacingError(e, "Restock reminders could not be saved."));
    } finally { setReplenishmentBusy(false); }
  }

  useEffect(() => { if (tab === "Replenishment") void loadReplenishment(); }, [tab, replenishmentLocation]);
  useEffect(() => { if (tab === "Stock Age") void loadAgeing(); }, [tab, locationFilter]);
  useEffect(() => { if (tab === "Stock Health") void loadMovementHealth(); }, [tab, locationFilter]);

  function updateLine(setter: (value: LineDraft[]) => void, lines: LineDraft[], index: number, field: keyof LineDraft, value: string) {
    setter(lines.map((line, i) => i === index ? { ...line, [field]: value } : line));
  }

  async function submitAdjustment(event: FormEvent) {
    event.preventDefault();
    const lines = adjustLines.filter((line) => line.variantId && Number(line.quantity) !== 0).map((line) => ({ variant_id: line.variantId, quantity_delta: line.quantity, unit_cost: line.unitCost || "0" }));
    if (!adjustLocation || !lines.length) { setMessage("Select a location and at least one non-zero adjustment line."); return; }
    setBusy(true);
    try { await createAdjustment({ location_id: adjustLocation, reason_code: adjustReason, notes: adjustNotes || null, lines }); setAdjustLines([{ variantId: "", quantity: "", unitCost: "" }]); setAdjustNotes(""); setMessage("Adjustment created as a draft. Approval is required before posting."); setTab("Adjustments"); await load(); }
    catch (e) { setMessage(userFacingError(e, "Could not create the adjustment.")); } finally { setBusy(false); }
  }

  async function runAdjustmentAction(id: string, action: "approve" | "post") {
    setBusy(true);
    try { if (action === "approve") await approveAdjustment(id); else await postAdjustment(id); setMessage(action === "approve" ? "Adjustment approved. It is ready to post." : "Stock correction recorded."); await load(); }
    catch (e) { setMessage(userFacingError(e, "Inventory action could not be completed.")); } finally { setBusy(false); }
  }

  async function createCount(event: FormEvent) {
    event.preventDefault(); if (!countLocation || countVariantIds.length === 0) { setMessage("Choose a location and one or more products to count."); return; }
    setBusy(true);
    try { const created = await createStockCount({ location_id: countLocation, scope_description: countScope || null, variant_ids: countVariantIds }); setSelectedCountId(created.id); setCountVariantIds([]); setCountScope(""); setMessage("Stock count opened. Enter physical quantities before submission."); setTab("Counts"); await load(); }
    catch (e) { setMessage(userFacingError(e, "Could not create the stock count.")); } finally { setBusy(false); }
  }

  async function saveCountLines() {
    if (!selectedCount) return;
    const lines = selectedCount.lines.filter((line) => countValues[line.variant_id] !== undefined && countValues[line.variant_id] !== "").map((line) => ({ variant_id: line.variant_id, counted_quantity: countValues[line.variant_id] }));
    if (!lines.length) { setMessage("Enter at least one counted quantity."); return; }
    setBusy(true);
    try { await updateCountLines(selectedCount.id, { lines }); setMessage("Counted quantities saved. Review variances before submission."); await load(); }
    catch (e) { setMessage(userFacingError(e, "Could not save counted quantities.")); } finally { setBusy(false); }
  }

  async function runCountAction(id: string, action: "submit" | "approve" | "post") {
    setBusy(true);
    try { if (action === "submit") await submitStockCount(id); if (action === "approve") await approveStockCount(id); if (action === "post") await postStockCount(id); setMessage(action === "submit" ? "Stock count submitted for approval." : action === "approve" ? "Stock count approved." : "Stock count saved. Any differences are now recorded as stock corrections."); await load(); }
    catch (e) { setMessage(userFacingError(e, "Stock count action could not be completed.")); } finally { setBusy(false); }
  }

  async function submitTransfer(event: FormEvent) {
    event.preventDefault();
    const lines = transferLines.filter((line) => line.variantId && Number(line.quantity) > 0).map((line) => ({ variant_id: line.variantId, quantity: line.quantity }));
    if (!transferFrom || !transferTo || transferFrom === transferTo || !lines.length) { setMessage("Choose different source/destination locations and at least one quantity."); return; }
    setBusy(true);
    try { const created = await createTransfer({ source_location_id: transferFrom, destination_location_id: transferTo, notes: transferNotes || null, lines }); setTransferLines([{ variantId: "", quantity: "" }]); setTransferNotes(""); setMessage("Transfer created as draft. Approval and dispatch happen before destination receipt."); setTab("Transfers"); await load(); }
    catch (e) { setMessage(userFacingError(e, "Could not create the transfer.")); } finally { setBusy(false); }
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
    } catch (e) { setMessage(userFacingError(e, "Transfer action could not be completed.")); } finally { setBusy(false); }
  }

  async function submitWarehouse(event: FormEvent) {
    event.preventDefault(); if (!warehouseName.trim() || !warehouseCode.trim()) return;
    setBusy(true);
    try { const created = await createWarehouse({ name: warehouseName.trim(), code: warehouseCode.trim().toUpperCase(), branch_id: warehouseBranch || null }); setWarehouseName(""); setWarehouseCode(""); setMessage(`Warehouse ${created.name} created.`); await load(); }
    catch (e) { setMessage(userFacingError(e, "Could not create warehouse.")); } finally { setBusy(false); }
  }

  async function submitLocation(event: FormEvent) {
    event.preventDefault(); if (!locationName.trim() || !locationCode.trim() || !locationWarehouse) return;
    setBusy(true);
    try { const created = await createLocation({ name: locationName.trim(), code: locationCode.trim().toUpperCase(), warehouse_id: locationWarehouse }); setLocationName(""); setLocationCode(""); setMessage(`Location ${created.name} created.`); await load(); }
    catch (e) { setMessage(userFacingError(e, "Could not create location.")); } finally { setBusy(false); }
  }

  const total = balances.reduce((sum, row) => sum + Number(row.stock_value), 0);
  const low = balances.filter((row) => Number(row.available) > 0 && Number(row.available) <= 5).length;
  const out = balances.filter((row) => Number(row.available) <= 0).length;
  const mismatch = integrity === "mismatch";
  const metricUnavailable = !hasLoaded || busy || filtersBusy || Boolean(error) || Boolean(stockError);
  const visibleStockError = error || stockError;
  const stockTableState = visibleStockError ? "error" : (!hasLoaded || busy || filtersBusy) ? "loading" : balances.length ? "success" : "empty";

  return <AppShell title="Inventory" eyebrow="Stock across your locations">
    <div className="module-toolbar"><div><strong>Stock overview</strong><span>See what is available, what changed, and which items need attention.</span></div><div className="toolbar-actions"><button className="button button-soft" onClick={() => void load()} disabled={busy}>Refresh</button><button className="button button-dark" onClick={() => setTab("Adjustments")}>+ Stock action</button></div></div>
    {message && <div className="notice">{message}</div>}{visibleStockError && <div className="notice notice-error">{visibleStockError}</div>}
    <div className="metric-strip" aria-label="Inventory summary"><div><span>Stock value</span><strong>{metricUnavailable ? "—" : money(total, businessCurrency)}</strong><small>{metricUnavailable ? "Current total unavailable" : businessCurrency ? `Current cost value · ${businessCurrency}` : "Currency not set; stock value cannot be shown yet"}</small></div><div><span>Locations</span><strong>{metricUnavailable ? "—" : locations.length}</strong><small>{metricUnavailable ? "Not confirmed" : `${warehouses.length} warehouses`}</small></div><div><span>Low stock</span><strong>{metricUnavailable ? "—" : low}</strong><small>Available items: 5 or fewer</small></div><div><span>Out of stock</span><strong>{metricUnavailable ? "—" : out}</strong><small>No items available</small></div></div>

    <section className="panel"><div className="module-tabs">{tabs.map((name) => <button key={name} className={tab===name?"active":""} onClick={()=>setTab(name)}>{tabLabels[name]}</button>)}</div>

      {tab === "Stock" && <><div className="panel-head"><div><h2>Current stock</h2><p>See current stock, what is reserved, and what is available to sell or move.</p></div><div className="filter-row"><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search product name or code"/><select value={locationFilter} onChange={e=>setLocationFilter(e.target.value)}><option value="">All locations</option>{locations.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></div></div><ResponsiveDataTable
        rows={balances}
        getKey={(row) => row.id}
        mobileTitle={(row) => variantMap.get(row.variant_id)?.name || short(row.variant_id)}
        mobileSubtitle={(row) => variantMap.get(row.variant_id)?.sku || "No product code"}
        state={stockTableState}
        stateTitle={visibleStockError ? "Stock balances could not be loaded" : busy || filtersBusy ? "Checking current stock" : "No stock rows"}
        stateDescription={visibleStockError ? "The current inventory state could not be confirmed. Retry before making stock decisions." : busy || filtersBusy ? "Checking stock totals and locations." : "Stock will appear here after inventory balances are established."}
        onRetry={() => void load()}
        columns={[
          { key: "item", label: "Item", hideOnMobile: true, render: (row) => <><strong>{variantMap.get(row.variant_id)?.name || short(row.variant_id)}</strong><small>{variantMap.get(row.variant_id)?.sku || "No product code"}</small></> },
          { key: "location", label: "Location", render: (row) => locationMap.get(row.location_id)?.name || short(row.location_id) },
          { key: "on-hand", label: "On hand", align: "right", render: (row) => qty(row.on_hand) },
          { key: "available", label: "Available", align: "right", render: (row) => <span className={Number(row.available) <= 0 ? "number-danger" : Number(row.available) <= 5 ? "number-warning" : ""}>{qty(row.available)}</span> },
          { key: "cost", label: "Average purchase cost", align: "right", render: (row) => money(row.average_cost, businessCurrency) },
          { key: "value", label: "Value", align: "right", render: (row) => money(row.stock_value, businessCurrency) },
          { key: "updated", label: "Updated", render: (row) => new Date(row.updated_at).toLocaleString("en-GB") },
        ]}
      /><div className={`integrity-line ${mismatch?"integrity-bad":""}`}><span className={`status-dot ${mismatch?"warning":""}`}/>{mismatch?"Stock records do not match. Review recent stock changes before making decisions.":`Stock records checked · ${balances.length} items in view`}<button onClick={()=>void load()}>Check again</button></div></>}

      {tab === "Ledger" && <><div className="panel-head"><div><h2>Stock history</h2><p>See every recorded change to stock. To correct a mistake, add a new correction instead of changing history.</p></div><div className="filter-row"><select value={locationFilter} onChange={e=>setLocationFilter(e.target.value)}><option value="">All locations</option>{locations.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select><select value={ledgerType} onChange={e=>setLedgerType(e.target.value)}><option value="">All stock changes</option><option value="ADJUSTMENT">Stock correction</option><option value="COUNT_RECONCILIATION">Stock count</option><option value="TRANSFER_OUT">Moved out</option><option value="TRANSFER_IN">Moved in</option><option value="PURCHASE">Purchase received</option><option value="SALE">Sale</option><option value="SALE_RETURN">Sale return</option></select></div></div><div className="data-table-wrap"><table className="data-table"><thead><tr><th>Time</th><th>Item</th><th>Location</th><th>Movement</th><th>Quantity</th><th>Unit cost</th><th>Stock after change</th><th>Related record</th></tr></thead><tbody>{ledger.map(row=><tr key={row.id}><td>{new Date(row.occurred_at).toLocaleString("en-GB")}</td><td><strong>{variantMap.get(row.variant_id)?.name || short(row.variant_id)}</strong><small>{variantMap.get(row.variant_id)?.sku || "No product code"}</small></td><td>{locationMap.get(row.location_id)?.name || short(row.location_id)}</td><td><span className="status-pill status-muted">{movementLabel(row.transaction_type)}</span></td><td className={Number(row.quantity_delta)<0?"number-danger":"number-good"}>{Number(row.quantity_delta)>0?"+":""}{qty(row.quantity_delta)}</td><td>{money(row.unit_cost, businessCurrency)}</td><td>{qty(row.balance_after)}</td><td>{row.reference_type?`${movementLabel(row.reference_type)} ${row.reference_id?short(row.reference_id):""}`:"—"}</td></tr>)}{!ledger.length&&!busy&&<tr><td colSpan={8}><div className="empty-state"><strong>No stock changes yet</strong><span>Recorded stock changes will appear here.</span></div></td></tr>}</tbody></table></div></>}

      {tab === "Adjustments" && <div className="operations-layout"><form className="operation-form" onSubmit={submitAdjustment}><div><p className="eyebrow">STOCK CORRECTION</p><h3>Record a stock correction</h3><p>Save a draft, review it, then record the correction. Added stock needs a purchase cost.</p></div><label>Location<select value={adjustLocation} onChange={e=>setAdjustLocation(e.target.value)} required>{locations.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label>Reason<select value={adjustReason} onChange={e=>setAdjustReason(e.target.value)}><option value="COUNT_CORRECTION">Physical count correction</option><option value="DAMAGE">Damaged items</option><option value="LOSS">Missing stock</option><option value="FOUND">Stock found</option><option value="OPENING_BALANCE">Starting stock</option><option value="OTHER">Other</option></select></label><label>Notes<textarea value={adjustNotes} onChange={e=>setAdjustNotes(e.target.value)} rows={2} placeholder="Why did the physical stock differ?"/></label><div className="line-editor"><div className="line-editor-head"><strong>Lines</strong><button type="button" className="button button-soft button-small" onClick={()=>setAdjustLines([...adjustLines,{variantId:"",quantity:"",unitCost:""}])}>+ Add line</button></div>{adjustLines.map((line,i)=><div className="editor-row" key={i}><select value={line.variantId} onChange={e=>updateLine(setAdjustLines,adjustLines,i,"variantId",e.target.value)} required><option value="">Item</option>{variants.map(v=><option key={v.id} value={v.id}>{v.product_name} · {v.name} · {v.sku}</option>)}</select><input type="number" step="0.001" value={line.quantity} onChange={e=>updateLine(setAdjustLines,adjustLines,i,"quantity",e.target.value)} placeholder="Quantity change" required/><input type="number" min="0" step="0.01" value={line.unitCost||""} onChange={e=>updateLine(setAdjustLines,adjustLines,i,"unitCost",e.target.value)} placeholder="Unit cost"/><button type="button" className="row-remove" onClick={()=>setAdjustLines(adjustLines.filter((_,idx)=>idx!==i))} aria-label="Remove line">×</button></div>)}</div><button type="submit" className="button button-dark" disabled={busy}>Save stock correction</button></form><div className="operation-list"><div className="list-head"><div><p className="eyebrow">RECENT STOCK CORRECTIONS</p><h3>Recent adjustments</h3></div></div>{adjustments.length?adjustments.map(item=><div className="workflow-row" key={item.id}><div><strong>{item.reason_code.replaceAll("_", " ").toLowerCase()}</strong><small>{locationMap.get(item.location_id)?.name||short(item.location_id)} · {item.lines.length} line(s)</small></div><span className={`status ${statusTone(item.status)}`}>{statusLabel(item.status)}</span><div className="row-actions">{item.status==="DRAFT"&&<button className="button button-soft button-small" onClick={()=>void runAdjustmentAction(item.id,"approve")} disabled={busy}>Approve</button>}{item.status==="APPROVED"&&<button className="button button-dark button-small" onClick={()=>void runAdjustmentAction(item.id,"post")} disabled={busy}>Record</button>}</div></div>):<div className="empty-inline">No adjustments created yet.</div>}</div></div>}

      {tab === "Counts" && <div className="operations-layout"><div><form className="operation-form" onSubmit={createCount}><div><p className="eyebrow">PHYSICAL COUNT</p><h3>Open a stock count</h3><p>Count the physical quantity against the current stock record. Count every selected product before sending for review.</p></div><label>Location<select value={countLocation} onChange={e=>setCountLocation(e.target.value)} required>{locations.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label>Area to count<input value={countScope} onChange={e=>setCountScope(e.target.value)} placeholder="e.g. electronics shelf A"/></label><div className="variant-picker"><strong>Choose products to count</strong>{variants.map(v=><label key={v.id} className="check-line"><input type="checkbox" checked={countVariantIds.includes(v.id)} onChange={e=>setCountVariantIds(current=>e.target.checked?[...current,v.id]:current.filter(id=>id!==v.id))}/><span>{v.product_name} · {v.name} <small>{v.sku}</small></span></label>)}</div><button type="submit" className="button button-dark" disabled={busy}>Start stock count</button></form><div className="operation-list"><div className="list-head"><div><p className="eyebrow">STOCK COUNT HISTORY</p><h3>Stock counts</h3></div><select value={selectedCountId} onChange={e=>setSelectedCountId(e.target.value)}><option value="">Select count</option>{counts.map(x=><option key={x.id} value={x.id}>{short(x.id)} · {x.status}</option>)}</select></div>{counts.map(item=><button type="button" className={`workflow-row workflow-row-button ${selectedCountId===item.id?"selected":""}`} key={item.id} onClick={()=>setSelectedCountId(item.id)}><div><strong>{short(item.id)} · {item.scope_description||"Count"}</strong><small>{locationMap.get(item.location_id)?.name||short(item.location_id)} · {item.lines.length} line(s)</small></div><span className={`status ${statusTone(item.status)}`}>{statusLabel(item.status)}</span></button>)}</div></div><div className="operation-detail">{selectedCount?<><div className="list-head"><div><p className="eyebrow">COUNT REVIEW</p><h3>{short(selectedCount.id)}</h3><small>{locationMap.get(selectedCount.location_id)?.name||short(selectedCount.location_id)} · {selectedCount.status}</small></div></div><div className="count-grid">{selectedCount.lines.map(line=>{const counted=countValues[line.variant_id] ?? line.counted_quantity ?? ""; const variance=counted===""?null:Number(counted)-Number(line.expected_quantity); return <div className="count-row" key={line.id}><div><strong>{variantMap.get(line.variant_id)?.name||short(line.variant_id)}</strong><small>{variantMap.get(line.variant_id)?.sku||"No product code"}</small></div><span>Expected {qty(line.expected_quantity)}</span><input type="number" min="0" step="0.001" value={counted} onChange={e=>setCountValues(values=>({...values,[line.variant_id]:e.target.value}))} disabled={selectedCount.status!=="COUNTING"} placeholder="Counted"/><span className={variance===null?"":variance<0?"number-danger":"number-warning"}>{variance===null?"—":`${variance>0?"+":""}${qty(variance)}`}</span></div>})}</div>{selectedCount.status==="COUNTING"&&<div className="row-actions"><button className="button button-soft" onClick={()=>void saveCountLines()} disabled={busy}>Save quantities</button><button className="button button-dark" onClick={()=>void runCountAction(selectedCount.id,"submit")} disabled={busy}>Send for review</button></div>}{selectedCount.status==="SUBMITTED"&&<button className="button button-dark" onClick={()=>void runCountAction(selectedCount.id,"approve")} disabled={busy}>Approve stock count</button>}{selectedCount.status==="APPROVED"&&<button className="button button-dark" onClick={()=>void runCountAction(selectedCount.id,"post")} disabled={busy}>Record count and save differences</button>}</>:<div className="module-placeholder"><span>◎</span><strong>Select a stock count</strong><p>Start a stock count from the left register to review expected quantity, enter physical counts and resolve variances.</p></div>}</div></div>}

      {tab === "Transfers" && <div className="operations-layout"><form className="operation-form" onSubmit={submitTransfer}><div><p className="eyebrow">LOCATION TRANSFER</p><h3>Move stock between locations</h3><p>Draft → Approved → Dispatched → Received → Completed. Dispatch reduces source stock; receipt increases destination stock.</p></div><div className="form-grid"><label>From<select value={transferFrom} onChange={e=>setTransferFrom(e.target.value)} required>{locations.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label>To<select value={transferTo} onChange={e=>setTransferTo(e.target.value)} required>{locations.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label></div><label>Notes<textarea value={transferNotes} onChange={e=>setTransferNotes(e.target.value)} rows={2} placeholder="Reason or dispatch note"/></label><div className="line-editor"><div className="line-editor-head"><strong>Items</strong><button type="button" className="button button-soft button-small" onClick={()=>setTransferLines([...transferLines,{variantId:"",quantity:""}])}>+ Add item</button></div>{transferLines.map((line,i)=><div className="editor-row" key={i}><select value={line.variantId} onChange={e=>updateLine(setTransferLines,transferLines,i,"variantId",e.target.value)} required><option value="">Item</option>{variants.map(v=><option key={v.id} value={v.id}>{v.product_name} · {v.name} · {v.sku}</option>)}</select><input type="number" min="0.001" step="0.001" value={line.quantity} onChange={e=>updateLine(setTransferLines,transferLines,i,"quantity",e.target.value)} placeholder="Quantity" required/><button type="button" className="row-remove" onClick={()=>setTransferLines(transferLines.filter((_,idx)=>idx!==i))} aria-label="Remove line">×</button></div>)}</div><button type="submit" className="button button-dark" disabled={busy}>Create transfer</button></form><div className="operation-list"><div className="list-head"><div><p className="eyebrow">TRANSFER REGISTER</p><h3>Recent transfers</h3></div></div>{transfers.length?transfers.map(item=><div className="workflow-row" key={item.id}><div><strong>{short(item.id)} · {locationMap.get(item.source_location_id)?.name||short(item.source_location_id)} → {locationMap.get(item.destination_location_id)?.name||short(item.destination_location_id)}</strong><small>{item.lines.length} line(s) · {item.notes||"No notes"}</small></div><span className={`status ${statusTone(item.status)}`}>{statusLabel(item.status)}</span><div className="row-actions">{item.status==="DRAFT"&&<button className="button button-soft button-small" onClick={()=>void runTransferAction(item.id,"approve")} disabled={busy}>Approve</button>}{item.status==="APPROVED"&&<button className="button button-dark button-small" onClick={()=>void runTransferAction(item.id,"dispatch")} disabled={busy}>Dispatch</button>}{(item.status==="DISPATCHED"||item.status==="PARTIALLY_RECEIVED")&&<button className="button button-dark button-small" onClick={()=>void runTransferAction(item.id,"receive")} disabled={busy}>Receive</button>}{item.status==="RECEIVED"&&<button className="button button-dark button-small" onClick={()=>void runTransferAction(item.id,"complete")} disabled={busy}>Complete</button>}</div></div>):<div className="empty-inline">No transfers created yet.</div>}</div></div>}

      {tab === "Locations" && <div className="operations-layout"><form className="operation-form" onSubmit={submitWarehouse}><div><p className="eyebrow">WAREHOUSE</p><h3>Add a stock room</h3><p>A stock room belongs to one part of your business. Choose its location below.</p></div><label>Name<input value={warehouseName} onChange={e=>setWarehouseName(e.target.value)} placeholder="Main warehouse" required/></label><label>Code<input value={warehouseCode} onChange={e=>setWarehouseCode(e.target.value)} placeholder="WH-KLA-01" required/></label><label>Branch<select value={warehouseBranch} onChange={e=>setWarehouseBranch(e.target.value)}><option value="">No branch assignment</option>{branches.map(x=><option key={x.id} value={x.id}>{x.name} · {x.code}</option>)}</select></label><button type="submit" className="button button-dark" disabled={busy}>Add a stock room</button></form><form className="operation-form" onSubmit={submitLocation}><div><p className="eyebrow">LOCATION</p><h3>Add a stock location</h3><p>A stock location tells your team where items are kept.</p></div><label>Warehouse<select value={locationWarehouse} onChange={e=>setLocationWarehouse(e.target.value)} required><option value="">Select warehouse</option>{warehouses.map(x=><option key={x.id} value={x.id}>{x.name} · {x.code}</option>)}</select></label><label>Name<input value={locationName} onChange={e=>setLocationName(e.target.value)} placeholder="Main floor" required/></label><label>Code<input value={locationCode} onChange={e=>setLocationCode(e.target.value)} placeholder="LOC-01" required/></label><button type="submit" className="button button-dark" disabled={busy}>Create location</button></form><div className="operation-list full-width"><div className="list-head"><div><p className="eyebrow">LOCATION REGISTER</p><h3>{locations.length} locations</h3></div></div>{locations.map(item=><div className="workflow-row" key={item.id}><div><strong>{item.name}</strong><small>{item.code} · Warehouse {warehouseMap.get(item.warehouse_id)?.name||short(item.warehouse_id)}</small></div><span className="status good">{statusLabel(item.status)}</span></div>)}{!locations.length&&<div className="empty-inline">No locations yet.</div>}</div></div>}

      {tab === "Replenishment" && <div className="operations-layout"><form className="operation-form" onSubmit={saveReplenishmentPolicy}><div><p className="eyebrow">RESTOCK SETTINGS</p><h3>Set restock reminders</h3><p>Tell LEXA how long deliveries usually take, how often you check stock and how much extra stock you like to keep. This only gives suggestions; it will not place an order.</p></div><label>Location<select value={replenishmentLocation} onChange={e=>setReplenishmentLocation(e.target.value)} required><option value="">Choose location</option>{locations.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label><label>Product<select value={replenishmentVariant} onChange={e=>setReplenishmentVariant(e.target.value)} required><option value="">Choose item</option>{variants.map(v=><option key={v.id} value={v.id}>{v.product_name} · {v.name} · {v.sku}</option>)}</select></label><div className="form-grid"><label>Delivery time (days)<input type="number" min="0" max="365" value={replenishmentLeadDays} onChange={e=>setReplenishmentLeadDays(e.target.value)} required/></label><label>Check stock every (days)<input type="number" min="1" max="90" value={replenishmentReviewDays} onChange={e=>setReplenishmentReviewDays(e.target.value)} required/></label></div><div className="form-grid"><label>Use sales from last (days)<input type="number" min="7" max="365" value={replenishmentLookbackDays} onChange={e=>setReplenishmentLookbackDays(e.target.value)} required/></label><label>Minimum stock level<input type="number" min="0" step="0.001" value={replenishmentMinimum} onChange={e=>setReplenishmentMinimum(e.target.value)} required/></label></div><label>Extra stock to keep<input type="number" min="0" step="0.001" value={replenishmentSafety} onChange={e=>setReplenishmentSafety(e.target.value)} required/></label><button type="submit" className="button button-dark" disabled={replenishmentBusy}>Save restock reminders</button></form><div className="operation-list"><div className="list-head"><div><p className="eyebrow">WHY THESE ITEMS NEED ATTENTION</p><h3>Items to consider restocking</h3><small>Based on completed sales and returns at the selected stock location.</small></div><button className="button button-soft button-small" onClick={()=>void loadReplenishment()} disabled={replenishmentBusy}>Refresh</button></div>{replenishmentError&&<div className="notice notice-error">{replenishmentError}</div>}{replenishmentBusy?<div className="empty-inline">Checking sales and current stock…</div>:replenishmentRecommendations.length?replenishmentRecommendations.map(item=><div className="workflow-row" key={item.policy_id}><div><strong>{item.product_name} · {item.variant_name}</strong><small>{item.sku||"No product code"} · {item.location_name} · {restockReasonLabel(item.reason_code)}</small><small>Available {qty(item.available)} · on the way {qty(item.inbound)} · usual daily sales {qty(item.average_daily_demand)} · estimated stock remaining {item.days_cover===null?"not available":`${qty(item.days_cover)} days`}</small><small>Preferred level {qty(item.target_stock)} · suggested restock {qty(item.reorder_quantity)} · estimated cost {money(item.estimated_reorder_value, businessCurrency)}</small></div><span className={`status ${item.recommended_action==="REORDER"?"warn":"good"}`}>{restockActionLabel(item.recommended_action)}</span></div>):<div className="empty-inline">No restock suggestions yet. Set reminders for a product and stock location. Suggestions never place orders automatically.</div>}</div><div className="operation-list full-width"><div className="list-head"><div><p className="eyebrow">SAVED RESTOCK REMINDERS</p><h3>{replenishmentPolicies.length} saved reminders</h3></div></div>{replenishmentPolicies.map(policy=><div className="workflow-row" key={policy.id}><div><strong>{policy.product_name} · {policy.variant_name}</strong><small>{policy.location_name} · delivery usually takes {policy.lead_time_days} days · check every {policy.review_period_days} days · use the last {policy.lookback_days} days of sales · extra stock {qty(policy.safety_stock)}</small></div><span className={`status ${policy.enabled?"good":"neutral"}`}>{policy.enabled?"Available":"Paused"}</span></div>)}{!replenishmentPolicies.length&&!replenishmentBusy&&<div className="empty-inline">No restock reminders set for this location yet.</div>}</div></div>}
      {tab === "Stock Health" && <section className="workspace-section">
        <div className="panel-head"><div><p className="eyebrow">STOCK INSIGHTS</p><h2>Items that need attention</h2><p>Find empty shelves, items running low, and products that have not sold recently. Sales and returns are shown separately.</p></div><div className="filter-row"><select aria-label="Stock health location" value={locationFilter} onChange={e=>setLocationFilter(e.target.value)}><option value="">All accessible locations</option>{locations.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select><button type="button" className="button button-soft button-small" onClick={()=>void loadMovementHealth()} disabled={movementHealthBusy}>{movementHealthBusy?"Refreshing…":"Refresh"}</button></div></div>
        {movementHealthError&&<div className="notice notice-error">Stock health is unavailable: {movementHealthError}</div>}
        {movementHealthBusy&&!movementHealthRows.length?<div className="empty-inline">Loading completed sales, returns and inventory balances…</div>:movementHealthRows.length?<div className="data-table-wrap"><table className="data-table"><thead><tr><th>Product / code</th><th>Location</th><th>Status</th><th>On hand</th><th>Reserved</th><th>Available</th><th>Sold in 30 days</th><th>Sold in 90 days</th><th>Last sale</th><th>Days since sale</th><th>Purchase cost value</th></tr></thead><tbody>{movementHealthRows.map(row=><tr key={`${row.location_id}:${row.variant_id}`}><td><strong>{row.product_name} · {row.variant_name}</strong><small>Code: {row.sku||"Not set"}</small></td><td>{row.location_name}</td><td><span className={`status ${row.health_status.startsWith("OUT_OF_STOCK")||row.health_status==="AT_OR_BELOW_CONFIGURED_MINIMUM"||row.health_status==="NO_SALE_90D"||row.health_status==="NO_SALE_60D"?"warn":row.health_status==="NO_SALE_30D"||row.health_status==="NO_COMPLETED_SALE_HISTORY"?"neutral":"good"}`}>{healthLabel(row.health_status)}</span></td><td>{qty(row.on_hand)}</td><td>{qty(row.reserved)}</td><td>{qty(row.available)}</td><td>{qty(row.net_units_sold_30d)} <small>{qty(row.units_returned_30d)} returned</small></td><td>{qty(row.net_units_sold_90d)} <small>{qty(row.units_returned_90d)} returned</small></td><td>{row.last_sale_at?new Date(row.last_sale_at).toLocaleDateString("en-GB"):"No completed sale found"}</td><td>{row.days_since_last_sale===null?"—":row.days_since_last_sale}</td><td>{money(row.stock_value, businessCurrency)}</td></tr>)}</tbody></table></div>:!movementHealthError&&!movementHealthBusy?<div className="empty-state"><strong>No stock checks available</strong><span>No stock records or restock reminders were found for this location. Check that stock has been received or added.</span></div>:null}
        <p className="muted-copy">These checks use recorded sales, returns and current stock. “No completed sale found” means there is no matching sales history; it is not a prediction. Stock value uses purchase cost, not selling price or profit.</p>
      </section>}

      {tab === "Stock Age" && <section className="workspace-section">
        <div className="panel-head"><div><p className="eyebrow">STOCK AGE</p><h2>How long stock has been here</h2><p>Age is estimated from recorded stock changes. Items without enough history are marked as unknown, so treat the result as a guide.</p></div><div className="filter-row"><select aria-label="Stock age location" value={locationFilter} onChange={e=>setLocationFilter(e.target.value)}><option value="">All accessible locations</option>{locations.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select><button className="button button-soft" onClick={()=>void loadAgeing()} disabled={ageingBusy}>{ageingBusy?"Loading…":"Refresh stock age"}</button></div></div>
        {ageingError && <div className="notice notice-error" role="alert">Stock-age data unavailable: {ageingError}</div>}
        {ageingBusy ? <div className="empty-inline">Estimating stock age from the recorded history…</div> : ageingError ? <div className="empty-inline">Stock age is not shown because the saved history could not be checked.</div> : ageingRows.length ? <div className="data-table-wrap"><table className="data-table"><thead><tr><th>Product / location</th><th>On hand</th><th>Over 30 days</th><th>Over 60 days</th><th>Over 90 days</th><th>Unknown age</th><th>Oldest stock we can date</th><th>Stock history</th></tr></thead><tbody>{ageingRows.map(row=><tr key={`${row.location_id}-${row.variant_id}`}><td><strong>{row.product_name} · {row.variant_name}</strong><small>{row.sku||"No product code"} · {row.location_name}</small></td><td>{qty(row.on_hand)}</td><td>{qty(row.aged_over_30)}</td><td>{qty(row.aged_over_60)}</td><td>{qty(row.aged_over_90)}</td><td>{qty(row.unknown_age_quantity)}</td><td>{row.oldest_remaining_age_days === null ? "Unavailable" : `${row.oldest_remaining_age_days} days`}</td><td><span className={`status ${row.reconciliation_gap?"bad":Number(row.unknown_age_quantity)>0?"warn":"good"}`}>{row.reconciliation_gap?"Review difference":Number(row.unknown_age_quantity)>0?"Age unknown":"Record available"}</span></td></tr>)}</tbody></table></div> : <div className="empty-inline">No stock history is available for these locations yet.</div>}
      </section>}

    </section>
  </AppShell>;
}