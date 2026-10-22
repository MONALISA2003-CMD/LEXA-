"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { AppShell } from "../../components/app-shell";
import {
  acceptSupplierBillVariance, approvePurchaseOrder, approvePurchaseReturn, cancelPurchaseOrder, cancelPurchaseReceipt,
  cancelPurchaseReturn, closePurchaseOrder, createPurchaseOrder, createPurchaseReceipt, createPurchaseReturn,
  createPurchasingSupplier, createSupplierBill, createSupplierPayment, updatePurchasingSupplier,
  getBranches, getBusinessProfile, getLocations, getPurchaseOrder, getPurchaseOrders, getPurchaseReceipt,
  getPurchaseReceipts, getPurchaseReturns, getPurchasingSummary, getPurchasingSuppliers, getSupplierBalances,
  getSupplierBills, getSupplierCosts, getSupplierLedger, getSupplierPayments, getVariantOptions, getWarehouses,
  postPurchaseReceipt, postPurchaseReturn, postSupplierBill, postSupplierPayment, setSupplierCost, submitPurchaseOrder,
  voidSupplierBill, voidSupplierPayment,
  type Branch, type Location, type PurchaseOrder, type PurchaseReceipt, type PurchaseReturn, type SupplierBalance,
  type SupplierBill, type SupplierLedgerEntry, type PurchasingSupplier, type PurchasingSupplierCost, type SupplierPayment,
  type VariantOption, type Warehouse,
  userFacingError,
} from "../../lib/api";

type Tab = "Suppliers" | "Purchase orders" | "Receiving" | "Supplier returns" | "Bills & payments" | "Balances";
type DraftLine = { variant_id: string; ordered_quantity: string; unit_cost: string; tax_rate: string; description: string };
type ReceiveDraftLine = { purchase_order_line_id: string; received_quantity: string; unit_cost: string; difference_reason: string };
type ReturnDraftLine = { purchase_receipt_line_id: string; quantity: string; reason: string };
type PaymentAllocationDraft = { bill_id: string; amount: string };

const tabs: Tab[] = ["Suppliers", "Purchase orders", "Receiving", "Supplier returns", "Bills & payments", "Balances"];
const today = () => new Date().toISOString().slice(0, 10);
const qty = (value: string | number | null | undefined) => new Intl.NumberFormat("en-UG", { maximumFractionDigits: 3 }).format(Number(value || 0));
const money = (value: string | number | null | undefined, currency: string | null) => {
  if (!currency || !/^[A-Z]{3}$/.test(currency)) return "Business currency not set";
  try { return new Intl.NumberFormat("en-UG", { style: "currency", currency, maximumFractionDigits: 2 }).format(Number(value || 0)); }
  catch { return `${currency} ${Number(value || 0).toLocaleString("en-UG")}`; }
};
const statusClass = (status: string) => ["POSTED", "APPROVED", "OPEN", "FULLY_RECEIVED", "ACTIVE", "PAID"].includes(status) ? "good" : ["SUBMITTED", "PARTIALLY_RECEIVED", "REQUESTED", "DRAFT", "OVERDUE"].includes(status) ? "warn" : "neutral";
const statusLabel = (status: string) => ({ DRAFT: "Draft", SUBMITTED: "Waiting for approval", APPROVED: "Approved", OPEN: "Ready to receive", PARTIALLY_RECEIVED: "Partly received", FULLY_RECEIVED: "Fully received", RECEIVED: "Received", POSTED: "Recorded", REQUESTED: "Waiting for approval", CLOSED: "Closed", CANCELLED: "Cancelled", VOIDED: "Cancelled", ACTIVE: "Available", INACTIVE: "Not available", PAID: "Paid", PARTIALLY_PAID: "Partly paid", OVERDUE: "Overdue", REVERSED: "Corrected" }[status] || status.replaceAll("_", " ").toLowerCase());
const matchStatusLabel = (status?: string | null) => ({ MATCHED: "Matches the receipt", VARIANCE: "Needs review", WAITING_RECEIPT: "Waiting for receipt", NOT_LINKED: "No delivery linked" }[status || ""] || (status ? status.replaceAll("_", " ").toLowerCase() : "Not checked"));
const costTypeLabel = (code: string) => ({ FREIGHT: "Delivery", HANDLING: "Handling", DUTY: "Duty or customs", INSURANCE: "Insurance", OTHER: "Other" }[code] || "Other cost");
const costSharingLabel = (method: string) => ({ BY_VALUE: "Based on item value", BY_QUANTITY: "Based on quantity", EQUALLY: "Equal share" }[method] || "Saved method");
const balanceHistoryLabel = (entry: SupplierLedgerEntry) => {
  const kind = `${entry.entry_type} ${entry.source_type}`.toUpperCase();
  if (kind.includes("BILL")) return /REVERSE|VOID|CANCEL/.test(kind) ? "Supplier bill corrected" : "Supplier bill";
  if (kind.includes("PAYMENT")) return /REVERSE|VOID|CANCEL/.test(kind) ? "Supplier payment corrected" : "Supplier payment";
  if (kind.includes("RETURN") || kind.includes("CREDIT")) return "Supplier return credit";
  return "Supplier balance change";
};
const errorText = (e: unknown, fallback: string) => {
  const raw = userFacingError(e, "");
  if (!raw || /UndefinedTable|UndefinedColumn|ProgrammingError|OperationalError|psycopg|sqlalchemy|Traceback|relation .* does not exist|column .* does not exist|public\.[a-z_]+|SELECT .* FROM|INSERT INTO|UPDATE .* SET/i.test(raw)) return fallback;
  return raw.length > 220 ? fallback : raw;
};

export default function PurchasingPage() {
  const [tab, setTab] = useState<Tab>("Suppliers");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [businessCurrency, setBusinessCurrency] = useState<string | null>(null);
  const [summary, setSummary] = useState<Record<string, string | number>>({});
  const [suppliers, setSuppliers] = useState<PurchasingSupplier[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [receipts, setReceipts] = useState<PurchaseReceipt[]>([]);
  const [returns, setReturns] = useState<PurchaseReturn[]>([]);
  const [bills, setBills] = useState<SupplierBill[]>([]);
  const [payments, setPayments] = useState<SupplierPayment[]>([]);
  const [balances, setBalances] = useState<SupplierBalance[]>([]);
  const [supplierCosts, setSupplierCosts] = useState<PurchasingSupplierCost[]>([]);
  const [history, setLedger] = useState<SupplierLedgerEntry[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [variants, setVariants] = useState<VariantOption[]>([]);

  const [supplierName, setSupplierName] = useState("");
  const [supplierCode, setSupplierCode] = useState("");
  const [supplierEmail, setSupplierEmail] = useState("");
  const [supplierPhone, setSupplierPhone] = useState("");
  const [supplierTerms, setSupplierTerms] = useState("30");
  const [supplierCurrency, setSupplierCurrency] = useState("UGX");
  const [supplierLocation, setSupplierLocation] = useState("");
  const [supplierTaxNumber, setSupplierTaxNumber] = useState("");
  const [selectedSupplierId, setSelectedSupplierId] = useState("");
  const [supplierEditName, setSupplierEditName] = useState("");
  const [supplierEditEmail, setSupplierEditEmail] = useState("");
  const [supplierEditPhone, setSupplierEditPhone] = useState("");
  const [supplierEditTerms, setSupplierEditTerms] = useState("30");
  const [supplierEditCurrency, setSupplierEditCurrency] = useState("UGX");
  const [supplierEditLocation, setSupplierEditLocation] = useState("");
  const [supplierEditTaxNumber, setSupplierEditTaxNumber] = useState("");
  const [supplierEditNotes, setSupplierEditNotes] = useState("");
  const [supplierEditStatus, setSupplierEditStatus] = useState<"ACTIVE"|"INACTIVE"|"ARCHIVED">("ACTIVE");
  const [costVariant, setCostVariant] = useState("");
  const [costAmount, setCostAmount] = useState("");
  const [costMinimum, setCostMinimum] = useState("1");
  const [costLeadTime, setCostLeadTime] = useState("7");

  const [poSupplier, setPoSupplier] = useState("");
  const [poBranch, setPoBranch] = useState("");
  const [poLocation, setPoLocation] = useState("");
  const [poDate, setPoDate] = useState(today());
  const [poExpectedDate, setPoExpectedDate] = useState("");
  const [poNotes, setPoNotes] = useState("");
  const [poLines, setPoLines] = useState<DraftLine[]>([{ variant_id: "", ordered_quantity: "1", unit_cost: "", tax_rate: "0", description: "" }]);
  const [selectedOrderId, setSelectedOrderId] = useState("");
  const [orderDetail, setOrderDetail] = useState<PurchaseOrder | null>(null);
  const [receiveLines, setReceiveLines] = useState<ReceiveDraftLine[]>([]);
  const [receiveNotes, setReceiveNotes] = useState("");
  const [landedCosts, setLandedCosts] = useState<Array<{cost_code:string;description:string;amount:string;currency_code:string;allocation_method:"BY_VALUE"|"BY_QUANTITY"|"EQUALLY";reference:string}>>([]);
  const [landedCode, setLandedCode] = useState("FREIGHT");
  const [landedDescription, setLandedDescription] = useState("");
  const [landedAmount, setLandedAmount] = useState("");
  const [landedMethod, setLandedMethod] = useState<"BY_VALUE"|"BY_QUANTITY"|"EQUALLY">("BY_VALUE");
  const [selectedReceiptId, setSelectedReceiptId] = useState("");
  const [receiptDetail, setReceiptDetail] = useState<PurchaseReceipt | null>(null);
  const [returnReceiptDetail, setReturnReceiptDetail] = useState<PurchaseReceipt | null>(null);

  const [returnReceiptId, setReturnReceiptId] = useState("");
  const [returnReason, setReturnReason] = useState("DAMAGED_GOODS");
  const [returnNotes, setReturnNotes] = useState("");
  const [returnLines, setReturnLines] = useState<ReturnDraftLine[]>([]);

  const [billSupplier, setBillSupplier] = useState("");
  const [billNumber, setBillNumber] = useState("");
  const [billDate, setBillDate] = useState(today());
  const [billDueDate, setBillDueDate] = useState("");
  const [billPoId, setBillPoId] = useState("");
  const [billReceiptId, setBillReceiptId] = useState("");
  const [billSubtotal, setBillSubtotal] = useState("");
  const [billTax, setBillTax] = useState("0");
  const [billCharges, setBillCharges] = useState("0");
  const [billNotes, setBillNotes] = useState("");
  const [billVarianceReasons, setBillVarianceReasons] = useState<Record<string,string>>({});
  const [paymentSupplier, setPaymentSupplier] = useState("");
  const [paymentNumber, setPaymentNumber] = useState("");
  const [paymentDate, setPaymentDate] = useState(today());
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("BANK_TRANSFER");
  const [paymentReference, setPaymentReference] = useState("");
  const [paymentAllocations, setPaymentAllocations] = useState<PaymentAllocationDraft[]>([{ bill_id: "", amount: "" }]);
  const [historySupplierId, setLedgerSupplierId] = useState("");

  const variantMap = useMemo(() => new Map(variants.map((v) => [v.id, v])), [variants]);
  const supplierMap = useMemo(() => new Map(suppliers.map((s) => [s.supplier_party_id, s])), [suppliers]);
  const warehousesById = useMemo(() => new Map(warehouses.map((w) => [w.id, w])), [warehouses]);
  const branchLocations = useMemo(() => locations.filter((loc) => {
    const warehouse = warehousesById.get(loc.warehouse_id);
    return !poBranch || warehouse?.branch_id === poBranch;
  }), [locations, warehousesById, poBranch]);
  const selectedOrder = orders.find((o) => o.id === selectedOrderId) || null;
  const selectedReturnReceipt = receipts.find((r) => r.id === returnReceiptId) || null;

  const load = useCallback(async () => {
    setLoading(true); setError("");
    const results = await Promise.allSettled([
      getPurchasingSummary(), getPurchasingSuppliers(), getPurchaseOrders(), getPurchaseReceipts(), getPurchaseReturns(),
      getSupplierBills(), getSupplierPayments(), getSupplierBalances(), getBranches(), getLocations(), getWarehouses(),
      getVariantOptions(), getBusinessProfile(),
    ] as const);
    const names = ["summary", "suppliers", "purchase orders", "receipts", "supplier returns", "supplier bills", "supplier payments", "supplier balances", "branches", "locations", "warehouses", "variants", "business profile"];
    const failures = results.flatMap((r, i) => r.status === "rejected" ? [`${names[i]}: ${errorText(r.reason, "failed to load")}`] : []);
    const value = (i: number) => results[i].status === "fulfilled" ? results[i].value : null;
    if (value(0)) setSummary(value(0) as Record<string, string | number>);
    const nextSuppliers = (value(1) as PurchasingSupplier[] | null) || [];
    const nextBranches = (value(8) as Branch[] | null) || [];
    const nextLocations = (value(9) as Location[] | null) || [];
    const nextWarehouses = (value(10) as Warehouse[] | null) || [];
    if (value(1)) setSuppliers(nextSuppliers);
    if (value(2)) setOrders(value(2) as PurchaseOrder[]);
    if (value(3)) setReceipts(value(3) as PurchaseReceipt[]);
    if (value(4)) setReturns(value(4) as PurchaseReturn[]);
    if (value(5)) setBills(value(5) as SupplierBill[]);
    if (value(6)) setPayments(value(6) as SupplierPayment[]);
    if (value(7)) setBalances(value(7) as SupplierBalance[]);
    if (value(8)) setBranches(value(8) as Branch[]);
    if (value(9)) setLocations(value(9) as Location[]);
    if (value(10)) setWarehouses(value(10) as Warehouse[]);
    if (value(11)) setVariants(value(11) as VariantOption[]);
    const profile = value(12) as { currency_code?: string } | null;
    setBusinessCurrency(profile?.currency_code && /^[A-Z]{3}$/i.test(profile.currency_code) ? profile.currency_code.toUpperCase() : null);
    if (profile?.currency_code && /^[A-Z]{3}$/i.test(profile.currency_code)) setSupplierCurrency(profile.currency_code.toUpperCase());
    setPoSupplier(current => current || nextSuppliers[0]?.supplier_party_id || "");
    setBillSupplier(current => current || nextSuppliers[0]?.supplier_party_id || "");
    setPaymentSupplier(current => current || nextSuppliers[0]?.supplier_party_id || "");
    setSelectedSupplierId(current => current || nextSuppliers[0]?.supplier_party_id || "");
    setPoBranch(current => current || nextBranches[0]?.id || "");
    setPoLocation(current => current || nextLocations.find(loc => nextWarehouses.some(w => w.id === loc.warehouse_id && w.branch_id === nextBranches[0]?.id))?.id || nextLocations[0]?.id || "");
    if (failures.length) setError(`Some purchasing panels could not load. ${failures.join(" · ")}`);
    setLoading(false);
  // Load once per page session. Selections are preserved on refresh.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!selectedOrderId) { setOrderDetail(null); setReceiveLines([]); return; }
    let active = true;
    void getPurchaseOrder(selectedOrderId).then((data) => {
      if (!active) return;
      setOrderDetail(data);
      setReceiveLines((data.lines || []).map((line) => ({
        purchase_order_line_id: line.id,
        received_quantity: Math.max(0, Number(line.ordered_quantity) - Number(line.received_quantity)).toString(),
        unit_cost: line.unit_cost,
        difference_reason: "",
      })));
    }).catch((e) => { if (active) setError(errorText(e, "Purchase order detail could not be loaded.")); });
    return () => { active = false; };
  }, [selectedOrderId]);
  useEffect(() => {
    if (!selectedReceiptId) { setReceiptDetail(null); return; }
    let active = true;
    void getPurchaseReceipt(selectedReceiptId).then((data) => { if (active) setReceiptDetail(data); }).catch((e) => { if (active) setError(errorText(e, "Receipt detail could not be loaded.")); });
    return () => { active = false; };
  }, [selectedReceiptId]);
  useEffect(() => {
    if (!returnReceiptId) { setReturnLines([]); setReturnReceiptDetail(null); return; }
    let active = true;
    void getPurchaseReceipt(returnReceiptId).then((receipt) => {
      if (!active) return;
      setReturnReceiptDetail(receipt);
      setReturnLines((receipt.lines || []).map((line) => ({ purchase_receipt_line_id: line.id, quantity: "0", reason: "" })));
    }).catch((e) => { if (active) setError(errorText(e, "Receipt lines could not be loaded for return.")); });
    return () => { active = false; };
  }, [returnReceiptId]);
  useEffect(() => {
    if (!selectedSupplierId) { setSupplierCosts([]); return; }
    void getSupplierCosts(selectedSupplierId).then(setSupplierCosts).catch((e) => setError(errorText(e, "Supplier prices could not be loaded.")));
  }, [selectedSupplierId]);
  useEffect(() => {
    if (!historySupplierId) { setLedger([]); return; }
    void getSupplierLedger(historySupplierId).then(setLedger).catch((e) => setError(errorText(e, "Supplier balance history could not be loaded. Please try again.")));
  }, [historySupplierId]);

  async function perform(action: () => Promise<unknown>, success: string, after?: () => void) {
    setBusy(true); setError(""); setMessage("");
    try { await action(); setMessage(success); after?.(); await load(); }
    catch (e) { setError(errorText(e, "The purchasing action could not be completed.")); }
    finally { setBusy(false); }
  }
  function editPoLine(index: number, field: keyof DraftLine, value: string) {
    setPoLines((current) => current.map((line, i) => i === index ? { ...line, [field]: value } : line));
  }
  function editReceiveLine(index: number, field: keyof ReceiveDraftLine, value: string) {
    setReceiveLines((current) => current.map((line, i) => i === index ? { ...line, [field]: value } : line));
  }
  function editReturnLine(index: number, field: keyof ReturnDraftLine, value: string) {
    setReturnLines((current) => current.map((line, i) => i === index ? { ...line, [field]: value } : line));
  }
  function editAllocation(index: number, field: keyof PaymentAllocationDraft, value: string) {
    setPaymentAllocations((current) => current.map((line, i) => i === index ? { ...line, [field]: value } : line));
  }
  function chooseSupplierProfile(id: string) {
    setSelectedSupplierId(id);
    setCostVariant("");
    const supplier = suppliers.find((item) => item.supplier_party_id === id);
    if (!supplier) return;
    setSupplierEditName(supplier.name || "");
    setSupplierEditEmail(supplier.email || "");
    setSupplierEditPhone(supplier.phone || "");
    setSupplierEditTerms(String(supplier.payment_terms_days ?? 0));
    setSupplierEditCurrency(supplier.currency_code || "UGX");
    setSupplierEditLocation(supplier.default_receiving_location_id || "");
    setSupplierEditTaxNumber(supplier.tax_number || "");
    setSupplierEditNotes(supplier.notes || "");
    setSupplierEditStatus((supplier.profile_status || "ACTIVE") as "ACTIVE"|"INACTIVE"|"ARCHIVED");
  }

  async function onCreateSupplier(event: FormEvent) {
    event.preventDefault();
    await perform(async () => {
      const created = await createPurchasingSupplier({ name: supplierName, code: supplierCode || undefined, email: supplierEmail || null, phone: supplierPhone || null, currency_code: supplierCurrency.toUpperCase(), payment_terms_days: Number(supplierTerms), default_receiving_location_id: supplierLocation || null, tax_number: supplierTaxNumber || null });
      setSelectedSupplierId(created.supplier_party_id); setPoSupplier(created.supplier_party_id); setBillSupplier(created.supplier_party_id); setPaymentSupplier(created.supplier_party_id);
      setSupplierName(""); setSupplierCode(""); setSupplierEmail(""); setSupplierPhone(""); setSupplierTaxNumber("");
    }, "Supplier profile created.");
  }
  async function onSetSupplierCost(event: FormEvent) {
    event.preventDefault(); if (!selectedSupplierId || !costVariant || !costAmount) { setError("Choose a supplier, product and positive supplier unit cost."); return; }
    await perform(() => setSupplierCost(selectedSupplierId, { variant_id: costVariant, unit_cost: costAmount, minimum_quantity: costMinimum || "1", currency_code: supplierMap.get(selectedSupplierId)?.currency_code || supplierCurrency, lead_time_days: costLeadTime ? Number(costLeadTime) : null }), "Supplier product cost saved. New cost history is effective-dated.");
  }
  async function onUpdateSupplier(event: FormEvent) {
    event.preventDefault();
    if (!selectedSupplierId || !supplierEditName.trim()) { setError("Select a supplier and provide its trading name."); return; }
    await perform(() => updatePurchasingSupplier(selectedSupplierId, {
      name: supplierEditName.trim(), email: supplierEditEmail.trim() || null, phone: supplierEditPhone.trim() || null,
      payment_terms_days: Number(supplierEditTerms), currency_code: supplierEditCurrency,
      default_receiving_location_id: supplierEditLocation || null, tax_number: supplierEditTaxNumber.trim() || null,
      notes: supplierEditNotes.trim() || null, status: supplierEditStatus,
    }), "Supplier profile and terms updated. Currency cannot change after purchasing activity.");
  }
  async function onCreateOrder(event: FormEvent) {
    event.preventDefault();
    if (!poSupplier || !poBranch || !poLocation) { setError("Select a supplier, branch and receiving location."); return; }
    const lines = poLines.filter((line) => line.variant_id && Number(line.ordered_quantity) > 0 && Number(line.unit_cost) > 0).map((line) => ({ variant_id: line.variant_id, ordered_quantity: line.ordered_quantity, unit_cost: line.unit_cost, tax_rate: line.tax_rate || "0", description: line.description || null }));
    if (!lines.length) { setError("Add at least one product line with quantity and unit cost."); return; }
    await perform(async () => {
      const result = await createPurchaseOrder({ supplier_party_id: poSupplier, branch_id: poBranch, receiving_location_id: poLocation, order_date: poDate, expected_date: poExpectedDate || null, currency_code: supplierMap.get(poSupplier)?.currency_code || businessCurrency || "UGX", notes: poNotes || null, lines });
      setSelectedOrderId(result.id); setTab("Purchase orders"); setPoLines([{ variant_id: "", ordered_quantity: "1", unit_cost: "", tax_rate: "0", description: "" }]); setPoNotes("");
    }, "Purchase order created as a draft. Submit it for approval before receiving stock.");
  }
  async function onCreateReceipt(event: FormEvent) {
    event.preventDefault(); if (!orderDetail) { setError("Select a purchase order first."); return; }
    const lines = receiveLines.filter((line) => Number(line.received_quantity) > 0).map((line) => ({ purchase_order_line_id: line.purchase_order_line_id, received_quantity: line.received_quantity, unit_cost: line.unit_cost || null, difference_reason: line.difference_reason || null }));
    if (!lines.length) { setError("Enter at least one positive received quantity."); return; }
    await perform(async () => {
      const result = await createPurchaseReceipt(orderDetail.id, { notes: receiveNotes || null, lines, landed_costs: landedCosts.map(({cost_code,description,amount,currency_code,allocation_method,reference})=>({cost_code,description,amount,currency_code,allocation_method,reference:reference||null})) });
      setSelectedReceiptId(result.id); setReceiveNotes(""); setLandedCosts([]); setLandedDescription(""); setLandedAmount(""); setTab("Receiving");
    }, "Delivery saved as a draft. Review the quantities and extra costs, then record it to update stock.");
  }
  async function onCreateReturn(event: FormEvent) {
    event.preventDefault();
    const lines = returnLines.filter((line) => Number(line.quantity) > 0).map((line) => ({ purchase_receipt_line_id: line.purchase_receipt_line_id, quantity: line.quantity, reason: line.reason || null }));
    if (!returnReceiptId || !lines.length) { setError("Choose a recorded delivery and enter a quantity above zero for at least one item."); return; }
    await perform(async () => { await createPurchaseReturn({ purchase_receipt_id: returnReceiptId, reason: returnReason, notes: returnNotes || null, lines }); setReturnNotes(""); setTab("Supplier returns"); }, "Supplier return requested. A manager must approve it before stock is reduced and the supplier credit is recorded.");
  }
  async function onCreateBill(event: FormEvent) {
    event.preventDefault(); if (!billSupplier || !billNumber || !billSubtotal) { setError("Choose a supplier and enter the invoice number and subtotal."); return; }
    await perform(() => createSupplierBill({ supplier_party_id: billSupplier, bill_number: billNumber, bill_date: billDate, due_date: billDueDate || null, currency_code: supplierMap.get(billSupplier)?.currency_code || businessCurrency || "UGX", subtotal: billSubtotal, tax_amount: billTax || "0", other_charges: billCharges || "0", purchase_order_id: billPoId || null, purchase_receipt_id: billReceiptId || null, notes: billNotes || null }), "Supplier bill saved as a draft. Record it when the invoice details have been checked.");
    setBillNumber(""); setBillSubtotal(""); setBillTax("0"); setBillCharges("0"); setBillPoId(""); setBillReceiptId(""); setBillNotes("");
  }
  async function onCreatePayment(event: FormEvent) {
    event.preventDefault(); if (!paymentSupplier || !paymentNumber || !paymentAmount) { setError("Choose a supplier and enter the payment number and amount."); return; }
    const allocations = paymentAllocations.filter((x) => x.bill_id && Number(x.amount) > 0).map((x) => ({ bill_id: x.bill_id, amount: x.amount }));
    await perform(() => createSupplierPayment({ supplier_party_id: paymentSupplier, payment_number: paymentNumber, payment_date: paymentDate, currency_code: supplierMap.get(paymentSupplier)?.currency_code || businessCurrency || "UGX", amount: paymentAmount, payment_method: paymentMethod, reference: paymentReference || null, allocations }), "Supplier payment saved as a draft. Check the amounts and reference before recording it.");
    setPaymentNumber(""); setPaymentAmount(""); setPaymentReference(""); setPaymentAllocations([{ bill_id: "", amount: "" }]);
  }

  return <AppShell title="Purchases" eyebrow="Suppliers, orders and stock received">
    <div className="module-page">
      <div className="module-toolbar">
        <div><strong>Purchases and suppliers</strong><span>Keep supplier orders, deliveries, bills, payments and balances together.</span></div>
        <div className="toolbar-actions"><button type="button" className="button button-soft" onClick={() => void load()} disabled={loading || busy}>Refresh</button></div>
      </div>
      {(error || message) && <div className={`notice ${error ? "notice-error" : "notice-success"}`} role={error ? "alert" : "status"}>{error || message}<button type="button" className="notice-dismiss" onClick={() => { setError(""); setMessage(""); }} aria-label="Dismiss message">×</button></div>}
      <div className="metric-grid">
        <div className="metric-card"><span>Active suppliers</span><strong>{summary.active_suppliers ?? "—"}</strong><small>Supplier profiles</small></div>
        <div className="metric-card"><span>Open purchase orders</span><strong>{summary.open_purchase_orders ?? "—"}</strong><small>Approved / partial</small></div>
        <div className="metric-card"><span>Draft receipts</span><strong>{summary.draft_receipts ?? "—"}</strong><small>Not in on-hand yet</small></div>
        <div className="metric-card"><span>Overdue bills</span><strong>{summary.overdue_supplier_bills ?? "—"}</strong><small>Review supplier due dates</small></div>
      </div>
      <section className="panel">
        <div className="module-tabs" role="tablist" aria-label="Purchasing workflows">{tabs.map((name) => <button type="button" role="tab" aria-selected={tab===name} key={name} className={tab===name?"active":""} onClick={()=>setTab(name)}>{name}</button>)}</div>

        {tab === "Suppliers" && <div className="operations-layout">
          <form className="operation-form" onSubmit={onCreateSupplier}>
            <div><p className="eyebrow">SUPPLIERS</p><h3>Add supplier</h3><p>Supplier identity, commercial currency, payment terms and default receiving location.</p></div>
            <label>Supplier / legal trading name<input value={supplierName} onChange={e=>setSupplierName(e.target.value)} required minLength={2} maxLength={250} placeholder="Supplier business name"/></label>
            <div className="form-grid"><label>Supplier code (optional)<input value={supplierCode} onChange={e=>setSupplierCode(e.target.value)} placeholder="SUP-001"/></label><label>Payment terms (days)<input type="number" min="0" max="3650" value={supplierTerms} onChange={e=>setSupplierTerms(e.target.value)} required/></label></div>
            <div className="form-grid"><label>Currency<select value={supplierCurrency} onChange={e=>setSupplierCurrency(e.target.value)}><option value="UGX">UGX — Uganda shilling</option><option value="USD">USD</option><option value="KES">KES</option><option value="EUR">EUR</option><option value="GBP">GBP</option></select></label><label>Tax / registration number<input value={supplierTaxNumber} onChange={e=>setSupplierTaxNumber(e.target.value)} placeholder="Optional"></input></label></div>
            <div className="form-grid"><label>Email<input type="email" value={supplierEmail} onChange={e=>setSupplierEmail(e.target.value)} placeholder="accounts@supplier.example"/></label><label>Phone<input value={supplierPhone} onChange={e=>setSupplierPhone(e.target.value)} placeholder="Contact number"/></label></div>
            <label>Default receiving location<select value={supplierLocation} onChange={e=>setSupplierLocation(e.target.value)}><option value="">Choose at order time</option>{locations.map(loc=><option key={loc.id} value={loc.id}>{loc.name} · {loc.code}</option>)}</select></label>
            <button type="submit" className="button button-dark" disabled={busy}>Create supplier</button>
          </form>
          <div className="operation-list"><div className="list-head"><div><p className="eyebrow">SUPPLIER DETAILS</p><h3>{suppliers.length} suppliers</h3></div></div>
            {loading?<div className="empty-inline">Loading supplier records…</div>:suppliers.length?suppliers.map(s=><button type="button" className={`workflow-row workflow-row-button ${selectedSupplierId===s.supplier_party_id?"selected":""}`} key={s.supplier_party_id} onClick={()=>chooseSupplierProfile(s.supplier_party_id)}><div><strong>{s.name}</strong><small>{s.code||"No code"} · {s.email||s.phone||"No contact recorded"}</small><small>{s.currency_code} · {s.payment_terms_days} day terms · net {money(s.net_balance,s.currency_code)}</small></div><span className={`status ${statusClass(s.profile_status||s.status||"ACTIVE")}`}>{statusLabel(s.profile_status||s.status||"ACTIVE")}</span></button>):<div className="empty-inline">No suppliers yet. Add one to create the first purchase order.</div>}
          </div>
          <form className="operation-form" onSubmit={onSetSupplierCost}><div><p className="eyebrow">SUPPLIER PRICES</p><h3>Record a supplier cost</h3><p>Effective-dated cost reference for reorder and purchase-order preparation. This does not change stock or create an order.</p></div>
            <label>Supplier<select value={selectedSupplierId} onChange={e=>chooseSupplierProfile(e.target.value)} required><option value="">Choose supplier</option>{suppliers.map(s=><option key={s.supplier_party_id} value={s.supplier_party_id}>{s.name}</option>)}</select></label>
            <label>Tracked variant<select value={costVariant} onChange={e=>setCostVariant(e.target.value)} required><option value="">Choose product</option>{variants.map(v=><option key={v.id} value={v.id}>{v.product_name} · {v.name} · {v.sku}</option>)}</select></label>
            <div className="form-grid"><label>Unit cost<input type="number" min="0.000001" step="0.000001" value={costAmount} onChange={e=>setCostAmount(e.target.value)} required/></label><label>Minimum quantity<input type="number" min="0.000001" step="0.001" value={costMinimum} onChange={e=>setCostMinimum(e.target.value)} required/></label></div>
            <label>Expected supplier lead time (days)<input type="number" min="0" max="3650" value={costLeadTime} onChange={e=>setCostLeadTime(e.target.value)}/></label>
            <button type="submit" className="button button-dark" disabled={busy || !selectedSupplierId}>Save supplier cost</button>
            {supplierCosts.length>0&&<div className="mini-register"><strong>Recent effective costs</strong>{supplierCosts.slice(0,5).map(c=><div key={c.id}><span>{c.product_name} · {c.sku}</span><b>{money(c.unit_cost,c.currency_code)}</b><small>min {qty(c.minimum_quantity)} · effective {String(c.effective_from).slice(0,10)}</small></div>)}</div>}
          </form>
          <form className="operation-form" onSubmit={onUpdateSupplier}>
            <div><p className="eyebrow">SUPPLIER TERMS</p><h3>Edit supplier terms</h3><p>Changes are audited. Currency is locked after purchasing activity; suppliers with open work or a non-zero balance cannot be archived.</p></div>
            <label>Supplier<select value={selectedSupplierId} onChange={e=>chooseSupplierProfile(e.target.value)} required><option value="">Choose supplier</option>{suppliers.map(s=><option key={s.supplier_party_id} value={s.supplier_party_id}>{s.name} · {s.currency_code}</option>)}</select></label>
            <label>Trading name<input value={supplierEditName} onChange={e=>setSupplierEditName(e.target.value)} minLength={2} maxLength={250} required/></label>
            <div className="form-grid"><label>Payment terms (days)<input type="number" min="0" max="3650" value={supplierEditTerms} onChange={e=>setSupplierEditTerms(e.target.value)} required/></label><label>Currency<select value={supplierEditCurrency} onChange={e=>setSupplierEditCurrency(e.target.value)}><option value="UGX">UGX</option><option value="USD">USD</option><option value="KES">KES</option><option value="EUR">EUR</option><option value="GBP">GBP</option></select></label></div>
            <div className="form-grid"><label>Email<input type="email" value={supplierEditEmail} onChange={e=>setSupplierEditEmail(e.target.value)}/></label><label>Phone<input value={supplierEditPhone} onChange={e=>setSupplierEditPhone(e.target.value)}/></label></div>
            <label>Default receiving location<select value={supplierEditLocation} onChange={e=>setSupplierEditLocation(e.target.value)}><option value="">Choose at order time</option>{locations.map(loc=><option key={loc.id} value={loc.id}>{loc.name} · {loc.code}</option>)}</select></label>
            <label>Tax / registration number<input value={supplierEditTaxNumber} onChange={e=>setSupplierEditTaxNumber(e.target.value)}/></label>
            <label>Commercial notes<textarea rows={2} value={supplierEditNotes} onChange={e=>setSupplierEditNotes(e.target.value)}/></label>
            <label>Supplier status<select value={supplierEditStatus} onChange={e=>setSupplierEditStatus(e.target.value as "ACTIVE"|"INACTIVE"|"ARCHIVED")}><option value="ACTIVE">Active</option><option value="INACTIVE">Inactive</option><option value="ARCHIVED">Archive (guarded)</option></select></label>
            <button type="submit" className="button button-dark" disabled={busy || !selectedSupplierId}>Save supplier terms</button>
          </form>
        </div>}

        {tab === "Purchase orders" && <div className="operations-layout">
          <form className="operation-form" onSubmit={onCreateOrder}><div><p className="eyebrow">PURCHASE ORDER</p><h3>Create purchase order</h3><p>Prepare an order, send it for approval, then record the delivery. Stock and amounts due change only when the right records are saved.</p></div>
            <label>Supplier<select value={poSupplier} onChange={e=>{const id=e.target.value;setPoSupplier(id);setSelectedSupplierId(id);const s=supplierMap.get(id);if(s?.currency_code)setSupplierCurrency(s.currency_code);if(s?.default_receiving_location_id){const loc=locations.find(x=>x.id===s.default_receiving_location_id);const wh=loc?warehousesById.get(loc.warehouse_id):undefined;if(loc&&(!poBranch||wh?.branch_id===poBranch))setPoLocation(loc.id);}}} required><option value="">Choose supplier</option>{suppliers.filter(s=>(s.profile_status||"ACTIVE")==="ACTIVE").map(s=><option key={s.supplier_party_id} value={s.supplier_party_id}>{s.name} · {s.currency_code}</option>)}</select></label>
            <div className="form-grid"><label>Branch<select value={poBranch} onChange={e=>{setPoBranch(e.target.value);setPoLocation("");}} required><option value="">Choose branch</option>{branches.map(b=><option key={b.id} value={b.id}>{b.name} · {b.code}</option>)}</select></label><label>Receiving location<select value={poLocation} onChange={e=>setPoLocation(e.target.value)} required><option value="">Choose location</option>{branchLocations.map(l=><option key={l.id} value={l.id}>{l.name} · {l.code}</option>)}</select></label></div>
            <div className="form-grid"><label>Order date<input type="date" value={poDate} onChange={e=>setPoDate(e.target.value)} required/></label><label>Expected delivery<input type="date" min={poDate} value={poExpectedDate} onChange={e=>setPoExpectedDate(e.target.value)}/></label></div>
            <div className="line-editor"><div className="line-editor-head"><strong>Order lines</strong><button type="button" className="button button-soft button-small" onClick={()=>setPoLines(x=>[...x,{variant_id:"",ordered_quantity:"1",unit_cost:"",tax_rate:"0",description:""}])}>+ Add line</button></div>
              {poLines.map((line,i)=>{const quote=supplierCosts.filter(c=>c.variant_id===line.variant_id&&!c.effective_to&&c.currency_code===(supplierMap.get(poSupplier)?.currency_code||businessCurrency)&&Number(c.minimum_quantity)<=Number(line.ordered_quantity)).sort((a,b)=>Number(b.minimum_quantity)-Number(a.minimum_quantity))[0];return <div key={i}><div className="editor-row purchase-editor-row"><select aria-label={`Variant line ${i+1}`} value={line.variant_id} onChange={e=>editPoLine(i,"variant_id",e.target.value)} required><option value="">Choose item</option>{variants.map(v=><option key={v.id} value={v.id}>{v.product_name} · {v.name} · {v.sku}</option>)}</select><input aria-label={`Quantity line ${i+1}`} type="number" min="0.000001" step="0.001" value={line.ordered_quantity} onChange={e=>editPoLine(i,"ordered_quantity",e.target.value)} required placeholder="Qty"/><input aria-label={`Cost line ${i+1}`} type="number" min="0.000001" step="0.000001" value={line.unit_cost} onChange={e=>editPoLine(i,"unit_cost",e.target.value)} required placeholder="Unit cost"/><input aria-label={`Tax percent line ${i+1}`} type="number" min="0" max="100" step="0.001" value={line.tax_rate} onChange={e=>editPoLine(i,"tax_rate",e.target.value)} placeholder="Tax %"/><button type="button" className="row-remove" aria-label={`Remove order line ${i+1}`} disabled={poLines.length===1} onClick={()=>setPoLines(x=>x.filter((_,idx)=>idx!==i))}>×</button></div>{line.variant_id&&<small className="inline-hint">{quote?`Supplier price history: ${money(quote.unit_cost,quote.currency_code)} per unit, minimum ${qty(quote.minimum_quantity)}${quote.lead_time_days==null?"":`, lead time ${quote.lead_time_days} days`}. `:"No active supplier price tier matches this variant and quantity. "}{quote&&<button type="button" className="button button-soft button-small" onClick={()=>editPoLine(i,"unit_cost",quote.unit_cost)}>Use supplier price</button>}</small>}</div>})}
            </div><label>Order notes<textarea rows={2} value={poNotes} onChange={e=>setPoNotes(e.target.value)} placeholder="Delivery terms, quotation reference, or instructions"/></label><button type="submit" className="button button-dark" disabled={busy}>Save purchase order draft</button>
          </form>
          <div className="operation-list"><div className="list-head"><div><p className="eyebrow">PURCHASE ORDERS</p><h3>{orders.length} purchase orders</h3></div></div>
            {orders.length?orders.map(o=><button type="button" key={o.id} onClick={()=>setSelectedOrderId(o.id)} className={`workflow-row workflow-row-button ${selectedOrderId===o.id?"selected":""}`}><div><strong>{o.po_number} · {o.supplier_name}</strong><small>{o.branch_name} · {o.receiving_location_name} · {String(o.order_date).slice(0,10)}</small><small>{money(o.total,o.currency_code)} · {qty(o.received_units)} units received</small></div><span className={`status ${statusClass(o.status)}`}>{o.status.replaceAll("_"," ")}</span></button>):<div className="empty-inline">No purchase orders yet.</div>}
          </div>
          <div className="operation-detail"><div className="list-head"><div><p className="eyebrow">ORDER DETAILS</p><h3>{orderDetail?.po_number||selectedOrder?.po_number||"Select an order"}</h3><small>{orderDetail?`${orderDetail.supplier_name} · ${orderDetail.status} · ${money(orderDetail.total,orderDetail.currency_code)}`:"Review lines and status before receiving."}</small></div></div>
            {orderDetail?<><div className="detail-lines">{(orderDetail.lines||[]).map(line=><div className="detail-line" key={line.id}><div><strong>{line.product_name} · {line.variant_name}</strong><small>{line.sku} · ordered {qty(line.ordered_quantity)} · received {qty(line.received_quantity)}</small></div><b>{money(line.line_total,orderDetail.currency_code)}</b></div>)}</div><div className="row-actions wrap-actions">
              {orderDetail.status==="DRAFT"&&<button type="button" className="button button-dark button-small" disabled={busy} onClick={()=>void perform(()=>submitPurchaseOrder(orderDetail.id,"Submitted for approval"),"Purchase order submitted for approval.")}>Submit for approval</button>}
              {orderDetail.status==="SUBMITTED"&&<button type="button" className="button button-dark button-small" disabled={busy} onClick={()=>void perform(()=>approvePurchaseOrder(orderDetail.id,"Approved for receiving"),"Purchase order approved. It can now be received.")}>Approve order</button>}
              {orderDetail.status==="DRAFT"&&<button type="button" className="button button-soft button-small" disabled={busy} onClick={()=>void perform(()=>cancelPurchaseOrder(orderDetail.id,"Cancelled by user"),"Draft order cancelled.")}>Cancel</button>}
              {["OPEN","PARTIALLY_RECEIVED"].includes(orderDetail.status)&&<button type="button" className="button button-soft button-small" disabled={busy} onClick={()=>void perform(()=>closePurchaseOrder(orderDetail.id,"Closed by user"),"Purchase order closed.")}>Close order</button>}
            </div>{["OPEN","PARTIALLY_RECEIVED"].includes(orderDetail.status)&&<form onSubmit={onCreateReceipt} className="embedded-form"><h4>Receive this order</h4><p>Enter the quantity that arrived. Explain any price difference. Add delivery or handling costs before recording the delivery.</p>{receiveLines.map((line,i)=>{const poLine=orderDetail.lines?.find(x=>x.id===line.purchase_order_line_id); const remaining=Math.max(0,Number(poLine?.ordered_quantity||0)-Number(poLine?.received_quantity||0)); return <div className="receipt-line-editor" key={line.purchase_order_line_id}><div><strong>{poLine?.product_name} · {poLine?.variant_name}</strong><small>Still expected {qty(remaining)} · Order price {money(poLine?.unit_cost,orderDetail.currency_code)}</small></div><div className="form-grid"><label>Quantity received<input type="number" min="0" max={remaining} step="0.001" value={line.received_quantity} onChange={e=>editReceiveLine(i,"received_quantity",e.target.value)} /></label><label>Actual cost per item<input type="number" min="0.000001" step="0.000001" value={line.unit_cost} onChange={e=>editReceiveLine(i,"unit_cost",e.target.value)} /></label></div><label>Explain the price difference (required if the cost changed)<input value={line.difference_reason} onChange={e=>editReceiveLine(i,"difference_reason",e.target.value)} placeholder="Reason for price difference"/></label></div>;})}
              <div className="line-editor"><div className="line-editor-head"><strong>Delivery and other purchase costs</strong><button type="button" className="button button-soft button-small" onClick={()=>setLandedCosts(x=>[...x,{cost_code:landedCode,description:landedDescription,amount:landedAmount,currency_code:orderDetail.currency_code,allocation_method:landedMethod,reference:""}])} disabled={!landedDescription.trim()||Number(landedAmount)<=0}>Add cost</button></div><div className="form-grid"><label>Cost type<select value={landedCode} onChange={e=>setLandedCode(e.target.value)}><option value="FREIGHT">Freight</option><option value="HANDLING">Handling</option><option value="DUTY">Duty / customs</option><option value="INSURANCE">Insurance</option><option value="OTHER">Other</option></select></label><label>Share costs by<select value={landedMethod} onChange={e=>setLandedMethod(e.target.value as typeof landedMethod)}><option value="BY_VALUE">By merchandise value</option><option value="BY_QUANTITY">By quantity</option><option value="EQUALLY">Equally per line</option></select></label></div><div className="form-grid"><label>Description<input value={landedDescription} onChange={e=>setLandedDescription(e.target.value)} placeholder="Freight invoice reference"/></label><label>Amount ({orderDetail.currency_code})<input type="number" min="0.01" step="0.01" value={landedAmount} onChange={e=>setLandedAmount(e.target.value)}/></label></div>{landedCosts.map((c,i)=><div className="workflow-row" key={`${c.cost_code}-${i}`}><div><strong>{costTypeLabel(c.cost_code)} · {c.description}</strong><small>{costSharingLabel(c.allocation_method)} · {c.currency_code}</small></div><b>{money(c.amount,c.currency_code)}</b><button type="button" className="row-remove" aria-label="Remove other purchase cost" onClick={()=>setLandedCosts(x=>x.filter((_,idx)=>idx!==i))}>×</button></div>)}</div>
              <label>Receipt notes<textarea rows={2} value={receiveNotes} onChange={e=>setReceiveNotes(e.target.value)} placeholder="Delivery note, damaged items, supplier challan"/></label><button type="submit" className="button button-dark" disabled={busy}>Save draft delivery</button></form>}</>:<div className="empty-inline">Select an order in the register. Only approved and unfinished orders can receive stock.</div>}
          </div>
        </div>}

        {tab === "Receiving" && <div className="operations-layout"><div className="operation-list"><div className="list-head"><div><p className="eyebrow">RECEIVED STOCK</p><h3>{receipts.length} receipts</h3></div></div>{receipts.length?receipts.map(r=><button type="button" key={r.id} onClick={()=>setSelectedReceiptId(r.id)} className={`workflow-row workflow-row-button ${selectedReceiptId===r.id?"selected":""}`}><div><strong>{r.receipt_number} · {r.supplier_name}</strong><small>{r.po_number} · {r.location_name} · {String(r.received_at).slice(0,10)}</small><small>{r.line_count||0} items · delivery and other costs {money(r.landed_cost_total,r.currency_code||businessCurrency)}</small></div><span className={`status ${statusClass(r.status)}`}>{statusLabel(r.status)}</span></button>):<div className="empty-inline">No deliverys. Approve a purchase order, then create a receipt from its detail panel.</div>}</div>
          <div className="operation-detail"><div className="list-head"><div><p className="eyebrow">DELIVERY DETAILS</p><h3>{receiptDetail?.receipt_number||"Select a receipt"}</h3><small>{receiptDetail?`${receiptDetail.po_number} · ${receiptDetail.supplier_name} · ${receiptDetail.status}`:"Stock changes when you confirm a delivery."}</small></div></div>{receiptDetail?<><div className="detail-lines">{(receiptDetail.lines||[]).map(l=><div className="detail-line" key={l.id}><div><strong>{l.product_name} · {l.variant_name}</strong><small>{l.sku} · quantity {qty(l.received_quantity)} · base {money(l.base_unit_cost,receiptDetail.currency_code||businessCurrency)} · share of delivery and other costs {money(l.landed_cost_amount,receiptDetail.currency_code||businessCurrency)}</small></div><b>{money(l.unit_cost,receiptDetail.currency_code||businessCurrency)} / unit</b></div>)}</div>{receiptDetail.landed_costs?.length?<div className="mini-register"><strong>Delivery and other purchase costs</strong>{receiptDetail.landed_costs.map((c,i)=><div key={String(c.id||i)}><span>{costTypeLabel(String(c.cost_code))} · {String(c.description)}</span><b>{money(String(c.amount),String(c.currency_code))}</b><small>Spread across items by {({BY_VALUE:"item value",BY_QUANTITY:"quantity",EQUALLY:"equal share"} as Record<string,string>)[String(c.allocation_method)]||"the saved method"}</small></div>)}</div>:<div className="empty-inline">No other purchase costs recorded for this receipt.</div>}{receiptDetail.status==="DRAFT"&&<div className="row-actions wrap-actions"><button type="button" className="button button-dark" disabled={busy} onClick={()=>void perform(()=>postPurchaseReceipt(receiptDetail.id),"Delivery recorded. Stock quantities and average purchase cost are updated.")}>Confirm delivery and update stock</button><button type="button" className="button button-soft button-small" disabled={busy} onClick={()=>void perform(()=>cancelPurchaseReceipt(receiptDetail.id,"Cancelled before posting"),"Draft delivery cancelled; stock has not changed.",()=>setSelectedReceiptId(""))}>Cancel delivery draft</button></div>}{receiptDetail.status==="POSTED"&&<div className="notice notice-success">Recorded delivery: stock is updated. Record the supplier bill separately to keep track of what you owe.</div>}</>:<div className="empty-inline">Choose a delivery to review product quantities and extra purchase costs before recording it.</div>}</div></div>}

        {tab === "Supplier returns" && <div className="operations-layout"><form className="operation-form" onSubmit={onCreateReturn}><div><p className="eyebrow">SUPPLIER RETURN</p><h3>Record a supplier return</h3><p>You can return only items from a recorded delivery. A manager must approve before stock is reduced and the supplier credit is recorded.</p></div><label>Recorded delivery<select value={returnReceiptId} onChange={e=>setReturnReceiptId(e.target.value)} required><option value="">Choose receipt</option>{receipts.filter(r=>r.status==="POSTED").map(r=><option key={r.id} value={r.id}>{r.receipt_number} · {r.supplier_name} · {r.po_number}</option>)}</select></label>{returnLines.map((line,i)=>{const src=returnReceiptDetail?.lines?.find(x=>x.id===line.purchase_receipt_line_id);return <div className="receipt-line-editor" key={line.purchase_receipt_line_id}><strong>{src?.product_name||src?.variant_name||`Receipt line ${i+1}`}</strong><small>{src?.sku||""} · received {qty(src?.received_quantity)} · inventory unit cost {money(src?.unit_cost,returnReceiptDetail?.currency_code||businessCurrency)} · supplier goods cost {money(src?.base_unit_cost,returnReceiptDetail?.currency_code||businessCurrency)}</small><label>Quantity to return<input type="number" min="0" max={Number(src?.received_quantity||0)} step="0.001" value={line.quantity} onChange={e=>editReturnLine(i,"quantity",e.target.value)}/></label><label>Line reason (optional)<input value={line.reason} onChange={e=>editReturnLine(i,"reason",e.target.value)} placeholder="Damaged in transit"/></label></div>;})}<label>Return reason<input value={returnReason} onChange={e=>setReturnReason(e.target.value)} required minLength={2}/></label><label>Notes<textarea rows={2} value={returnNotes} onChange={e=>setReturnNotes(e.target.value)} placeholder="Supplier RMA / collection arrangements"/></label><button type="submit" className="button button-dark" disabled={busy || !returnReceiptId}>Save return request</button></form>
          <div className="operation-list"><div className="list-head"><div><p className="eyebrow">SUPPLIER RETURNS</p><h3>{returns.length} supplier returns</h3></div></div>{returns.length?returns.map(r=><div className="workflow-row" key={r.id}><div><strong>{r.return_number} · {r.supplier_name}</strong><small>{r.receipt_number} · {r.reason}</small><small>Credit estimate {money(r.return_value,r.currency_code??businessCurrency)}</small></div><span className={`status ${statusClass(r.status)}`}>{statusLabel(r.status)}</span><div className="row-actions">{r.status==="REQUESTED"&&<><button type="button" className="button button-soft button-small" disabled={busy} onClick={()=>void perform(()=>approvePurchaseReturn(r.id),"Supplier return approved. It is ready to be recorded.")}>Approve</button><button type="button" className="button button-soft button-small" disabled={busy} onClick={()=>void perform(()=>cancelPurchaseReturn(r.id,"Cancelled by requester"),"Supplier return request cancelled; reserved return quantity released.")}>Cancel request</button></>}{r.status==="APPROVED"&&<button type="button" className="button button-dark button-small" disabled={busy} onClick={()=>void perform(()=>postPurchaseReturn(r.id),"Supplier return recorded. Stock is reduced and the supplier credit is saved.")}>Record return</button>}</div></div>):<div className="empty-inline">No supplier returns have been recorded yet.</div>}</div>
        </div>}

        {tab === "Bills & payments" && <div className="operations-layout">
          <form className="operation-form" onSubmit={onCreateBill}><div><p className="eyebrow">SUPPLIER BILL</p><h3>Record supplier bill</h3><p>A supplier invoice adds to what your business owes. A delivery alone does not create a bill.</p></div><label>Supplier<select value={billSupplier} onChange={e=>{setBillSupplier(e.target.value);setBillPoId("");setBillReceiptId("");}} required><option value="">Choose supplier</option>{suppliers.map(s=><option key={s.supplier_party_id} value={s.supplier_party_id}>{s.name} · {s.currency_code}</option>)}</select></label><div className="form-grid"><label>Supplier invoice number<input value={billNumber} onChange={e=>setBillNumber(e.target.value)} required placeholder="Supplier's invoice reference"/></label><label>Invoice date<input type="date" value={billDate} onChange={e=>setBillDate(e.target.value)} required/></label></div><div className="form-grid"><label>Due date (optional)<input type="date" min={billDate} value={billDueDate} onChange={e=>setBillDueDate(e.target.value)}/></label><label>Link to order<select value={billPoId} onChange={e=>{setBillPoId(e.target.value);if(billReceiptId&&!receipts.some(r=>r.id===billReceiptId&&r.purchase_order_id===e.target.value))setBillReceiptId("");}}><option value="">No order linked</option>{orders.filter(o=>o.supplier_party_id===billSupplier).map(o=><option key={o.id} value={o.id}>{o.po_number}</option>)}</select></label></div><label>Link to recorded delivery (optional)<select value={billReceiptId} onChange={e=>{setBillReceiptId(e.target.value);const receipt=receipts.find(r=>r.id===e.target.value);if(receipt) setBillPoId(receipt.purchase_order_id);}}><option value="">No delivery linked</option>{receipts.filter(r=>r.status==="POSTED"&&orders.some(o=>o.id===r.purchase_order_id&&o.supplier_party_id===billSupplier)).map(r=><option key={r.id} value={r.id}>{r.receipt_number} · {r.po_number}</option>)}</select></label><div className="form-grid"><label>Subtotal<input type="number" min="0" step="0.01" value={billSubtotal} onChange={e=>setBillSubtotal(e.target.value)} required/></label><label>Tax amount<input type="number" min="0" step="0.01" value={billTax} onChange={e=>setBillTax(e.target.value)}/></label></div><label>Other charges<input type="number" min="0" step="0.01" value={billCharges} onChange={e=>setBillCharges(e.target.value)}/></label><p className="total-line">Bill total <strong>{money(Number(billSubtotal||0)+Number(billTax||0)+Number(billCharges||0),supplierMap.get(billSupplier)?.currency_code||businessCurrency)}</strong></p><label>Notes<textarea rows={2} value={billNotes} onChange={e=>setBillNotes(e.target.value)}/></label><button type="submit" className="button button-dark" disabled={busy}>Save bill draft</button></form>
          <div className="operation-list"><div className="list-head"><div><p className="eyebrow">SUPPLIER BILLS</p><h3>{bills.length} bills</h3></div></div>{bills.map(b=><div className="workflow-row" key={b.id}><div><strong>{b.bill_number} · {b.supplier_name}</strong><small>Due {String(b.due_date).slice(0,10)} · paid {money(b.paid_amount,b.currency_code)} · still due {money(b.allocated_outstanding,b.currency_code)}</small><small>Delivery comparison: {matchStatusLabel(b.match_status)}{b.match_status==="VARIANCE"?` · difference ${money(b.match_difference,b.currency_code)}`:""}{b.match_reason?` · ${b.match_reason}`:""}</small><b>{money(b.total,b.currency_code)}</b></div><span className={`status ${statusClass(b.status)}`}>{statusLabel(b.status)}</span><div className="row-actions wrap-actions">{b.status==="DRAFT"&&<>{(b.match_status==="VARIANCE"||b.match_status==="WAITING_RECEIPT")&&<><input aria-label={`Match special approval reason for ${b.bill_number}`} value={billVarianceReasons[b.id]||""} onChange={e=>setBillVarianceReasons(x=>({...x,[b.id]:e.target.value}))} placeholder={b.match_status==="WAITING_RECEIPT"?"Reason to post before receipt":"Reason to accept mismatch"}/><button type="button" className="button button-soft button-small" disabled={busy||(billVarianceReasons[b.id]||"").trim().length<5} onClick={()=>void perform(()=>acceptSupplierBillVariance(b.id,billVarianceReasons[b.id].trim()),"The bill difference has been reviewed and saved.",()=>setBillVarianceReasons(x=>({...x,[b.id]:""})))}>{b.match_status==="WAITING_RECEIPT"?"Allow bill before delivery":"Accept difference"}</button></>}<button type="button" className="button button-dark button-small" disabled={busy||(b.match_status==="VARIANCE"||b.match_status==="WAITING_RECEIPT")} onClick={()=>void perform(()=>postSupplierBill(b.id),"Supplier bill recorded. The amount due has been updated.")}>Record bill</button><button type="button" className="button button-soft button-small" disabled={busy} onClick={()=>void perform(()=>voidSupplierBill(b.id,"Draft invoice withdrawn"),"Draft supplier bill cancelled.")}>Cancel draft</button></>}</div></div>)}{!bills.length&&<div className="empty-inline">No supplier bills have been recorded yet.</div>}
            <form className="embedded-form" onSubmit={onCreatePayment}><h3>Record payment to supplier</h3><p>Apply a payment to bills for the same supplier and currency. Any amount left over remains available for a future bill.</p><label>Supplier<select value={paymentSupplier} onChange={e=>setPaymentSupplier(e.target.value)} required><option value="">Choose supplier</option>{suppliers.map(s=><option key={s.supplier_party_id} value={s.supplier_party_id}>{s.name} · {s.currency_code}</option>)}</select></label><div className="form-grid"><label>Payment number<input value={paymentNumber} onChange={e=>setPaymentNumber(e.target.value)} required placeholder="e.g. PAY-001"/></label><label>Payment date<input type="date" value={paymentDate} onChange={e=>setPaymentDate(e.target.value)} required/></label></div><div className="form-grid"><label>Amount<input type="number" min="0.01" step="0.01" value={paymentAmount} onChange={e=>setPaymentAmount(e.target.value)} required/></label><label>Method<select value={paymentMethod} onChange={e=>setPaymentMethod(e.target.value)}><option value="BANK_TRANSFER">Bank transfer</option><option value="CASH">Cash</option><option value="MOBILE_MONEY">Mobile money</option><option value="CHEQUE">Cheque</option><option value="CARD">Card</option><option value="OTHER">Other</option></select></label></div><label>Reference<input value={paymentReference} onChange={e=>setPaymentReference(e.target.value)} placeholder="Bank/mobile money reference"/></label><div className="line-editor"><div className="line-editor-head"><strong>Apply payment to bills</strong><button type="button" className="button button-soft button-small" onClick={()=>setPaymentAllocations(a=>[...a,{bill_id:"",amount:""}])}>+ Apply to another bill</button></div>{paymentAllocations.map((a,i)=><div className="editor-row" key={i}><select aria-label={`Choose bill for payment ${i+1}`} value={a.bill_id} onChange={e=>editAllocation(i,"bill_id",e.target.value)}><option value="">Leave unapplied</option>{bills.filter(b=>b.status==="POSTED"&&b.supplier_party_id===paymentSupplier&&b.currency_code===(supplierMap.get(paymentSupplier)?.currency_code||businessCurrency)).map(b=><option key={b.id} value={b.id}>{b.bill_number} · open {money(b.allocated_outstanding,b.currency_code)}</option>)}</select><input aria-label={`Allocated amount ${i+1}`} type="number" min="0" step="0.01" value={a.amount} onChange={e=>editAllocation(i,"amount",e.target.value)} placeholder="Amount to apply"/><button type="button" className="row-remove" aria-label="Remove bill payment" disabled={paymentAllocations.length===1} onClick={()=>setPaymentAllocations(x=>x.filter((_,idx)=>idx!==i))}>×</button></div>)}</div><button type="submit" className="button button-dark" disabled={busy}>Save payment draft</button></form>
            <div className="mini-register"><strong>Supplier payments</strong>{payments.map(p=><div key={p.id}><span>{p.payment_number} · {p.supplier_name}<small>{p.payment_method} · applied to bills {money(p.allocated_amount,p.currency_code)} · still available {money(p.unallocated_amount,p.currency_code)}</small></span><b>{money(p.amount,p.currency_code)}</b><span className={`status ${statusClass(p.status)}`}>{statusLabel(p.status)}</span>{p.status==="DRAFT"&&<><button type="button" className="button button-soft button-small" disabled={busy} onClick={()=>void perform(()=>postSupplierPayment(p.id),"Supplier payment recorded. The amount still owed has been updated.")}>Record payment</button><button type="button" className="button button-soft button-small" disabled={busy} onClick={()=>void perform(()=>voidSupplierPayment(p.id,"Draft payment withdrawn"),"Draft supplier payment cancelled; supplier balances are unchanged.")}>Cancel draft</button></>}</div>)}</div>
          </div>
        </div>}

        {tab === "Balances" && <div className="operations-layout"><div className="operation-list full-width"><div className="list-head"><div><p className="eyebrow">WHAT YOU OWE SUPPLIERS</p><h3>What you owe suppliers</h3><small>Bills increase the amount you owe. Recorded payments and accepted return credits reduce it. Each currency is shown separately.</small></div></div>{balances.length?balances.map(b=><button type="button" className={`workflow-row workflow-row-button ${historySupplierId===b.supplier_party_id?"selected":""}`} key={`${b.supplier_party_id}-${b.currency_code}`} onClick={()=>setLedgerSupplierId(b.supplier_party_id)}><div><strong>{b.supplier_name}</strong><small>{b.entry_count} recorded balance changes · {b.overdue_bills} overdue bill(s) · {b.currency_code}</small><small>Added {money(b.debits,b.currency_code)} · paid or credited {money(b.credits,b.currency_code)}</small></div><div className="balance-stack"><small>Still owed</small><b>{money(b.payable,b.currency_code)}</b><small>Unused payment balance {money(b.supplier_credit,b.currency_code)}</small></div></button>):<div className="empty-inline">No recorded supplier bills, payments or return credits yet. Draft records do not affect supplier balances.</div>}</div>
          <div className="operation-list full-width"><div className="list-head"><div><p className="eyebrow">PAYMENT AND BALANCE HISTORY</p><h3>{supplierMap.get(historySupplierId)?.name||"Select a supplier balance"}</h3></div></div>{history.length?history.map(entry=><div className="workflow-row" key={entry.id}><div><strong>{balanceHistoryLabel(entry)} · {entry.reference || "Reference not added"}</strong><small>{String(entry.occurred_at).slice(0,19).replace("T"," ")}</small></div><div className="balance-stack"><small>Added to amount owed {money(entry.debit_amount,entry.currency_code)}</small><b>Paid or credited {money(entry.credit_amount,entry.currency_code)}</b><small>Balance after change {money(entry.running_balance,entry.currency_code)}</small></div></div>):<div className="empty-inline">Choose a supplier balance to view the balance history.</div>}</div>
        </div>}
      </section>
      <p className="module-footnote">Stock and supplier balances update when you record deliveries, returns, bills and payments. Your team reviews each order; LEXA does not make purchases automatically.</p>
    </div>
  </AppShell>;
}
