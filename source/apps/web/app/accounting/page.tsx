"use client";

import { Fragment, FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../components/app-shell";
import { SalesTrendChart } from "../../components/dashboard-charts";
import { localDateISO, localMonthStartISO } from "../../lib/date.mjs";
import {
  closeReconciliation,
  createExpense,
  createPaymentChannel,
  createReconciliation,
  deactivatePaymentChannel,
  getAccountingAccounts,
  getAnalyticsOverview,
  getAnalyticsProductSummary,
  getBalanceSheet,
  getBusinessProfile,
  getCommerceDashboard,
  getExpenses,
  getExpenseHistory,
  getIncomeStatement,
  getPaymentChannels,
  getReceivables,
  getReconciliations,
  getSupplierBalances,
  payReceivable,
  postExpense,
  refreshAnalytics,
  resolveReconciliationLine,
  reverseExpense,
  setReconciliationActual,
  voidExpense,
  type AccountingAccount,
  type AnalyticsOverview,
  type AnalyticsProductSummary,
  type CommerceDashboard,
  type ExpenseHistoryEvent,
  type ExpenseRecord,
  type PaymentChannel,
  type Receivable,
  type Reconciliation,
  type ReconciliationLine,
  type SupplierBalance,
} from "../../lib/api";

type Tab = "Summary" | "Expenses" | "Customer balances" | "End-of-day check" | "Payment methods" | "Financial reports";
const tabs: Tab[] = ["Summary", "Expenses", "Customer balances", "End-of-day check", "Payment methods", "Financial reports"];

function today() { return localDateISO(); }
function monthStart() { return localMonthStartISO(); }
function money(value: string | number | null | undefined, code: string | null | undefined) {
  if (!code || !/^[A-Z]{3}$/.test(code)) return "Currency unavailable";
  const n = Number(value ?? 0);
  if (!Number.isFinite(n)) return "Unavailable";
  try { return new Intl.NumberFormat("en-UG", { style: "currency", currency: code, maximumFractionDigits: 0 }).format(n); }
  catch { return `${code} ${n.toLocaleString("en-UG", { maximumFractionDigits: 0 })}`; }
}
function typeLabel(value: string) {
  const map: Record<string, string> = { CASH: "Cash", MOBILE_MONEY: "Mobile money", BANK: "Bank", CARD: "Card", CHEQUE: "Cheque", OTHER: "Other" };
  return map[value] || value.replaceAll("_", " ").toLowerCase();
}
function statusLabel(value: string) {
  const map: Record<string, string> = {
    DRAFT: "Needs review", POSTED: "Included in records", VOIDED: "Cancelled before recording", REVERSED: "Corrected",
    OPEN: "Not finished", PARTIALLY_PAID: "Partly paid", PAID: "Paid", CLOSED: "Completed",
    RECONCILIATION_PENDING: "Amounts still needed", VARIANCE_DETECTED: "Difference to review", UNDER_REVIEW: "Being reviewed",
    RECONCILED: "Checked", RESOLVED: "Resolved", ACKNOWLEDGED: "Reviewed",
  };
  return map[value] || value.replaceAll("_", " ").toLowerCase();
}
function errorMessage(error: unknown, fallback: string) {
  const raw = error instanceof Error ? error.message : "";
  if (!raw || /UndefinedTable|UndefinedColumn|ProgrammingError|OperationalError|psycopg|sqlalchemy|Traceback|relation .* does not exist|column .* does not exist|public\.[a-z_]+|SELECT .* FROM|INSERT INTO/i.test(raw)) return fallback;
  return raw.length > 220 ? fallback : raw;
}
function statusClass(value: string) { return value === "POSTED" || value === "CLOSED" || value === "RESOLVED" ? "status status-good" : value === "REVERSED" || value === "VOIDED" ? "status status-muted" : "status"; }

export default function AccountingPage() {
  const [tab, setTab] = useState<Tab>("Summary");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [currencyCode, setCurrencyCode] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<CommerceDashboard | null>(null);
  const [channels, setChannels] = useState<PaymentChannel[]>([]);
  const [receivables, setReceivables] = useState<Receivable[]>([]);
  const [reconciliations, setReconciliations] = useState<Reconciliation[]>([]);
  const [expenses, setExpenses] = useState<ExpenseRecord[]>([]);
  const [expenseHistory, setExpenseHistory] = useState<Record<string, ExpenseHistoryEvent[]>>({});
  const [expandedExpenseId, setExpandedExpenseId] = useState("");
  const [historyLoadingId, setHistoryLoadingId] = useState("");
  const [accounts, setAccounts] = useState<AccountingAccount[]>([]);
  const [supplierBalances, setSupplierBalances] = useState<SupplierBalance[]>([]);
  const [report, setReport] = useState<AnalyticsOverview | null>(null);
  const [productSummary, setProductSummary] = useState<AnalyticsProductSummary[]>([]);
  const [incomeRows, setIncomeRows] = useState<Array<{ account_id: string; code: string; name: string; account_type: string; amount: string }>>([]);
  const [balanceRows, setBalanceRows] = useState<Array<{ account_id: string; code: string; name: string; account_type: string; amount: string }>>([]);
  const [fromDate, setFromDate] = useState(monthStart());
  const [toDate, setToDate] = useState(today());
  const [reportBusy, setReportBusy] = useState(false);

  const [channelName, setChannelName] = useState("");
  const [channelType, setChannelType] = useState("CASH");
  const [channelProvider, setChannelProvider] = useState("");

  const [expenseDate, setExpenseDate] = useState(today());
  const [expenseReference, setExpenseReference] = useState("");
  const [expenseDescription, setExpenseDescription] = useState("");
  const [expenseAccountId, setExpenseAccountId] = useState("");
  const [expenseChannelId, setExpenseChannelId] = useState("");
  const [expenseSubtotal, setExpenseSubtotal] = useState("");
  const [expenseTax, setExpenseTax] = useState("0");
  const [correctingExpenseId, setCorrectingExpenseId] = useState("");
  const [correctionReason, setCorrectionReason] = useState("");

  const [payingReceivableId, setPayingReceivableId] = useState("");
  const [receivableAmount, setReceivableAmount] = useState("");
  const [receivableChannelId, setReceivableChannelId] = useState("");
  const [receivableReference, setReceivableReference] = useState("");
  const [receivableDate, setReceivableDate] = useState(today());

  const [selectedReconciliationId, setSelectedReconciliationId] = useState("");
  const [actuals, setActuals] = useState<Record<string, string>>({});
  const [actualNotes, setActualNotes] = useState<Record<string, string>>({});
  const [reviewingLineId, setReviewingLineId] = useState("");
  const [reviewReason, setReviewReason] = useState("");

  const activeChannels = useMemo(() => channels.filter(c => c.active && c.currency_code === currencyCode), [channels, currencyCode]);
  const expenseAccounts = useMemo(() => accounts.filter(a => a.account_type === "EXPENSE" && a.status === "ACTIVE" && a.allow_posting), [accounts]);
  const selectedReconciliation = useMemo(() => reconciliations.find(r => r.id === selectedReconciliationId) || null, [reconciliations, selectedReconciliationId]);
  const openReceivables = useMemo(() => receivables.filter(r => Number(r.balance) > 0), [receivables]);
  const totalReceivables = useMemo(() => openReceivables.reduce((sum, r) => sum + Number(r.balance || 0), 0), [openReceivables]);
  const totalSupplierPayables = useMemo(() => supplierBalances.filter(r => r.currency_code === currencyCode).reduce((sum, r) => sum + Number(r.payable || 0), 0), [supplierBalances, currencyCode]);
  const relevantExpenses = useMemo(() => expenses.filter(e => e.currency_code === currencyCode), [expenses, currencyCode]);
  const recordedExpenses = useMemo(() => relevantExpenses.filter(e => e.status === "POSTED"), [relevantExpenses]);
  const reportCurrency = report?.currency_code || currencyCode;
  const productCogs = useMemo(() => productSummary.reduce((sum, p) => sum + Number(p.cogs || 0), 0), [productSummary]);
  const productMargin = useMemo(() => productSummary.reduce((sum, p) => sum + Number(p.gross_margin || 0), 0), [productSummary]);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const profile = await getBusinessProfile().catch(() => null);
      const code = profile?.currency_code && /^[A-Z]{3}$/i.test(profile.currency_code) ? profile.currency_code.toUpperCase() : null;
      setCurrencyCode(code);
      const results = await Promise.allSettled([
        getCommerceDashboard(today()), getPaymentChannels(), getReceivables(), getReconciliations(),
        getExpenses(), getAccountingAccounts(), getSupplierBalances(),
      ]);
      const labels = ["today's summary", "payment methods", "customer balances", "end-of-day checks", "expenses", "expense categories", "supplier balances"];
      const failures: string[] = [];
      if (results[0].status === "fulfilled") setDashboard(results[0].value); else failures.push(labels[0]);
      if (results[1].status === "fulfilled") setChannels(results[1].value); else failures.push(labels[1]);
      if (results[2].status === "fulfilled") setReceivables(results[2].value); else failures.push(labels[2]);
      if (results[3].status === "fulfilled") {
        setReconciliations(results[3].value);
        setSelectedReconciliationId(current => current && results[3].value.some(r => r.id === current) ? current : results[3].value[0]?.id || "");
      } else failures.push(labels[3]);
      if (results[4].status === "fulfilled") setExpenses(results[4].value); else failures.push(labels[4]);
      if (results[5].status === "fulfilled") {
        setAccounts(results[5].value);
        setExpenseAccountId(current => current || results[5].value.find(a => a.account_type === "EXPENSE" && a.status === "ACTIVE" && a.allow_posting)?.id || "");
      } else failures.push(labels[5]);
      if (results[6].status === "fulfilled") setSupplierBalances(results[6].value); else failures.push(labels[6]);
      if (code) {
        const analytics = await Promise.allSettled([getAnalyticsOverview(fromDate, toDate, code), getAnalyticsProductSummary(fromDate, toDate, code, 100), getIncomeStatement(fromDate, toDate), getBalanceSheet(toDate)]);
        if (analytics[0].status === "fulfilled") setReport(analytics[0].value); else setReport(null);
        if (analytics[1].status === "fulfilled") setProductSummary(analytics[1].value); else setProductSummary([]);
        if (analytics[2].status === "fulfilled") setIncomeRows(analytics[2].value); else setIncomeRows([]);
        if (analytics[3].status === "fulfilled") setBalanceRows(analytics[3].value); else setBalanceRows([]);
      } else {
        setReport(null); setProductSummary([]); setIncomeRows([]); setBalanceRows([]);
      }
      if (!code) failures.push("business currency");
      if (failures.length === results.length + (code ? 0 : 1)) setError("Finance information could not be loaded. Check your access or connection, then refresh.");
      else if (failures.length) setMessage(`Some information is not available: ${failures.join(", ")}. Other sections can still be used.`);
    } catch (reason) {
      setError(errorMessage(reason, "Finance information could not be loaded. Try again."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); /* initial page load only */ // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreatePaymentMethod(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currencyCode) { setError("Set your business currency before adding a payment method."); return; }
    setSaving(true); setError(""); setMessage("");
    try {
      await createPaymentChannel({ name: channelName.trim(), channel_type: channelType, provider: channelProvider.trim() || undefined, currency_code: currencyCode });
      setChannelName(""); setChannelProvider("");
      setMessage("Payment method added. Staff can now select it when recording money received.");
      await load();
    } catch (reason) { setError(errorMessage(reason, "The payment method was not saved. Check the details and try again.")); }
    finally { setSaving(false); }
  }

  async function handleDeactivate(channel: PaymentChannel) {
    if (!window.confirm(`Stop using “${channel.name}” for new records? Past payments will remain in your history.`)) return;
    setSaving(true); setError(""); setMessage("");
    try {
      await deactivatePaymentChannel(channel.id, "Deactivated from Finance settings");
      setMessage(`${channel.name} is no longer available for new payments. Past records are unchanged.`);
      await load();
    } catch (reason) { setError(errorMessage(reason, "This payment method could not be deactivated. Try again.")); }
    finally { setSaving(false); }
  }

  async function toggleExpenseHistory(expense: ExpenseRecord) {
    if (expandedExpenseId === expense.id) { setExpandedExpenseId(""); return; }
    setExpandedExpenseId(expense.id);
    if (expenseHistory[expense.id]) return;
    setHistoryLoadingId(expense.id); setError("");
    try {
      const events = await getExpenseHistory(expense.id);
      setExpenseHistory(current => ({ ...current, [expense.id]: events }));
    } catch (reason) {
      setExpandedExpenseId("");
      setError(errorMessage(reason, "The expense history could not be loaded. Try again."));
    } finally { setHistoryLoadingId(""); }
  }

  function expenseHistoryLabel(eventType: string) {
    const labels: Record<string, string> = {
      EXPENSE_DRAFT_CREATED: "Draft saved",
      EXPENSE_POSTED: "Added to business records",
      EXPENSE_DRAFT_CANCELLED: "Draft cancelled",
      EXPENSE_REVERSED: "Expense corrected",
    };
    return labels[eventType] || "Record updated";
  }

  async function handleCreateExpense(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currencyCode) { setError("Set your business currency before recording an expense."); return; }
    if (!expenseAccountId || !expenseChannelId) { setError("Choose an expense category and how the money was paid."); return; }
    const subtotal = Number(expenseSubtotal); const tax = Number(expenseTax || 0);
    if (!Number.isFinite(subtotal) || subtotal < 0 || !Number.isFinite(tax) || tax < 0 || subtotal + tax <= 0) { setError("Enter an amount greater than zero. Tax must be zero or more."); return; }
    setSaving(true); setError(""); setMessage("");
    try {
      const created = await createExpense({ expense_date: expenseDate, reference: expenseReference.trim(), description: expenseDescription.trim(), expense_account_id: expenseAccountId, payment_channel_id: expenseChannelId, currency_code: currencyCode, subtotal: String(subtotal), tax_amount: String(tax) });
      setExpenseReference(""); setExpenseDescription(""); setExpenseSubtotal(""); setExpenseTax("0");
      setMessage(`Expense saved as a draft (${money(created.total, created.currency_code || currencyCode)}). Review it below and add it to the business records when correct.`);
      await load(); setTab("Expenses");
    } catch (reason) { setError(errorMessage(reason, "The expense was not saved. Check the details and try again.")); }
    finally { setSaving(false); }
  }

  async function handlePostExpense(expense: ExpenseRecord) {
    if (!window.confirm(`Add “${expense.description}” (${money(expense.total, expense.currency_code)}) to the business records?`)) return;
    setSaving(true); setError(""); setMessage("");
    try {
      await postExpense(expense.id);
      setExpenseHistory(current => { const next = { ...current }; delete next[expense.id]; return next; });
      setExpandedExpenseId("");
      setMessage("Expense added to the business records."); await load();
    }
    catch (reason) { setError(errorMessage(reason, "The expense could not be recorded. Check the details and try again.")); }
    finally { setSaving(false); }
  }

  async function handleVoidExpense(expense: ExpenseRecord) {
    if (!window.confirm("Cancel this draft? It has not been included in the business records.")) return;
    setSaving(true); setError(""); setMessage("");
    try {
      await voidExpense(expense.id, "Draft cancelled before being added to business records");
      setExpenseHistory(current => { const next = { ...current }; delete next[expense.id]; return next; });
      setExpandedExpenseId("");
      setMessage("Draft expense cancelled. It was not included in the business records."); await load();
    }
    catch (reason) { setError(errorMessage(reason, "The draft could not be cancelled.")); }
    finally { setSaving(false); }
  }

  async function handleReverseExpense(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!correctingExpenseId || correctionReason.trim().length < 5) { setError("Explain why this expense needs correcting (at least five characters)."); return; }
    setSaving(true); setError(""); setMessage("");
    try {
      const correctedId = correctingExpenseId;
      await reverseExpense(correctedId, correctionReason.trim());
      setExpenseHistory(current => { const next = { ...current }; delete next[correctedId]; return next; });
      setExpandedExpenseId("");
      setMessage("The expense record was corrected. The earlier entry remains available in its history."); setCorrectingExpenseId(""); setCorrectionReason(""); await load();
    }
    catch (reason) { setError(errorMessage(reason, "This expense could not be corrected. Review the record and try again.")); }
    finally { setSaving(false); }
  }

  function openPaymentForm(row: Receivable) {
    setPayingReceivableId(current => current === row.id ? "" : row.id);
    setReceivableAmount(row.balance);
    setReceivableChannelId(activeChannels[0]?.id || "");
    setReceivableReference(""); setReceivableDate(today());
    setError(""); setMessage("");
  }

  async function handleReceivablePayment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const row = openReceivables.find(r => r.id === payingReceivableId);
    if (!row) return;
    const amount = Number(receivableAmount);
    if (!Number.isFinite(amount) || amount <= 0 || amount > Number(row.balance) + 0.0001) { setError("Enter an amount greater than zero and no higher than the amount still owed."); return; }
    if (!receivableChannelId) { setError("Choose how the customer paid."); return; }
    setSaving(true); setError(""); setMessage("");
    try {
      await payReceivable(row.id, { payment_channel_id: receivableChannelId, amount: String(amount), business_date: receivableDate, reference: receivableReference.trim() || undefined });
      setMessage("Customer payment recorded. The amount still owed has been updated."); setPayingReceivableId(""); await load();
    } catch (reason) { setError(errorMessage(reason, "The payment was not recorded. Check the details and try again.")); }
    finally { setSaving(false); }
  }

  async function handleStartDayCheck() {
    setSaving(true); setError(""); setMessage("");
    try {
      const created = await createReconciliation({ business_date: today() });
      setSelectedReconciliationId(created.id);
      setMessage(created.status === "CLOSED"
        ? "Today's end-of-day check is already complete. You can review its saved figures."
        : "Today's end-of-day check is ready. Enter the actual receipts for each payment method.");
      await load(); setSelectedReconciliationId(created.id);
    } catch (reason) { setError(errorMessage(reason, "The end-of-day check could not be opened.")); }
    finally { setSaving(false); }
  }

  async function handleSaveActual(line: ReconciliationLine) {
    const amount = actuals[line.line_id] ?? (line.actual_amount == null ? "" : String(line.actual_amount));
    if (!amount.trim() || !Number.isFinite(Number(amount)) || Number(amount) < 0) { setError("Enter an actual amount of zero or more before saving."); return; }
    setSaving(true); setError(""); setMessage("");
    try { await setReconciliationActual(line.line_id, { actual_amount: amount, notes: actualNotes[line.line_id]?.trim() || undefined }); setMessage("The actual amount has been saved."); await load(); }
    catch (reason) { setError(errorMessage(reason, "The amount could not be saved.")); }
    finally { setSaving(false); }
  }

  function beginReview(line: ReconciliationLine) {
    setReviewingLineId(line.line_id);
    setReviewReason(actualNotes[line.line_id] || line.line_notes || "Checked against the business receipt records.");
    setError("");
    setMessage("");
  }

  async function handleAcknowledge(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reviewingLineId || reviewReason.trim().length < 3) {
      setError("Add a short note explaining what was checked before marking this difference as reviewed.");
      return;
    }
    const line = selectedReconciliation?.lines.find(item => item.line_id === reviewingLineId);
    if (!line) { setError("This line is no longer available. Refresh the page and try again."); return; }
    const actual = actuals[line.line_id] ?? (line.actual_amount == null ? "" : String(line.actual_amount));
    if (!actual.trim() || !Number.isFinite(Number(actual)) || Number(actual) < 0) {
      setError("Enter and save the actual amount before marking the difference as reviewed.");
      return;
    }
    if (line.actual_amount == null || Math.abs(Number(line.actual_amount) - Number(actual)) > 0.0001) {
      setError("Save the actual amount first, then review the difference.");
      return;
    }
    setSaving(true); setError(""); setMessage("");
    try {
      await resolveReconciliationLine(line.line_id, { status: "ACKNOWLEDGED", notes: reviewReason.trim() });
      setMessage("The difference is marked as reviewed. The recorded amounts have not been changed.");
      setReviewingLineId(""); setReviewReason("");
      await load();
    } catch (reason) { setError(errorMessage(reason, "This difference could not be marked as reviewed.")); }
    finally { setSaving(false); }
  }

  async function handleCloseDay() {
    if (!selectedReconciliation) return;
    if (!window.confirm("Finish this end-of-day check? Make sure every payment method has an actual amount and any differences have been reviewed.")) return;
    setSaving(true); setError(""); setMessage("");
    try { await closeReconciliation(selectedReconciliation.id); setMessage("End-of-day check completed."); await load(); }
    catch (reason) { setError(errorMessage(reason, "This check cannot be completed yet. Fill in missing amounts and review any differences.")); }
    finally { setSaving(false); }
  }

  async function loadReports(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!fromDate || !toDate || fromDate > toDate) { setError("Choose a valid date range. The start date must be before the end date."); return; }
    if (!currencyCode) { setError("Business currency is not available. Check your business settings."); return; }
    setReportBusy(true); setError(""); setMessage("");
    try {
      const refreshed = await refreshAnalytics(fromDate, toDate).catch(() => null);
      const [overview, products, income, balance] = await Promise.all([
        getAnalyticsOverview(fromDate, toDate, currencyCode), getAnalyticsProductSummary(fromDate, toDate, currencyCode, 100),
        getIncomeStatement(fromDate, toDate), getBalanceSheet(toDate),
      ]);
      setReport(overview); setProductSummary(products); setIncomeRows(income); setBalanceRows(balance);
      setMessage(refreshed ? "Report figures have been refreshed from saved business records." : "Report figures are loaded. If figures appear out of date, check the Business reports page and refresh its calculations.");
    } catch (reason) { setError(errorMessage(reason, "The report could not be refreshed.")); }
    finally { setReportBusy(false); }
  }

  return <AppShell title="Finance" eyebrow="Money in and out">
    <main className="workspace" style={{ maxWidth: 1480 }}>
      <div className="workspace-header">
        <div>
          <span className="workspace-breadcrumb">LEXA · FINANCE</span>
          <h1>Finance</h1>
          <p>Keep track of money received, money spent, customer balances and what you still owe suppliers.</p>
        </div>
        <div className="header-actions">
          <button type="button" className="button button-soft" onClick={() => void load()} disabled={loading || saving}>Refresh</button>
          <Link className="button button-soft" href="/reports">Business reports</Link>
        </div>
      </div>

      <div className="notice" role="note">LEXA records the payment method you select. It does not move money or confirm payments with MTN, Airtel or a bank. Never enter PINs, passwords, one-time codes or account sign-in details in LEXA.</div>
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {message && !error && <div className="notice" role="status">{message}</div>}
      {!currencyCode && <div className="notice notice-error" role="status">Business currency is unavailable. Set it in <Link href="/settings">Settings</Link> before recording money.</div>}

      <nav className="module-tabs" aria-label="Finance sections">
        {tabs.map(item => <button key={item} type="button" className={tab === item ? "active" : ""} onClick={() => { setTab(item); setError(""); setMessage(""); }}>{item}</button>)}
      </nav>

      {loading && <p role="status" className="muted">Loading your money records…</p>}

      {tab === "Summary" && <>
        <section className="metric-strip" aria-label="Today's finance summary">
          <div><span>Sales today</span><strong>{dashboard ? money(dashboard.sales.sales, currencyCode) : "Unavailable"}</strong></div>
          <div><span>Money recorded as received today</span><strong>{dashboard ? money(dashboard.sales.collected, currencyCode) : "Unavailable"}</strong></div>
          <div><span>Customers still owe</span><strong>{dashboard ? money(dashboard.outstanding_receivables, currencyCode) : money(totalReceivables, currencyCode)}</strong></div>
          <div><span>Supplier bills still to pay</span><strong>{money(totalSupplierPayables, currencyCode)}</strong></div>
        </section>
        <div className="two-column">
          <section className="workspace-section">
            <div className="section-head"><div><span className="section-label">MONEY SPENT</span><h2>Recent expenses</h2><p>Only expenses added to the business records count here.</p></div><button type="button" className="button button-soft" onClick={() => setTab("Expenses")}>View expenses</button></div>
            <div className="workflow-list">{recordedExpenses.slice(0, 5).map(expense => <div className="workflow-row" key={expense.id}><div><strong>{expense.description}</strong><small>{expense.expense_date} · {expense.reference} · {expense.payment_channel_name || "Payment method not available"}</small></div><span>{money(expense.total, expense.currency_code)}</span></div>)}{!recordedExpenses.length && <p className="empty-inline">No expenses have been added to the business records yet.</p>}</div>
          </section>
          <section className="workspace-section">
            <div className="section-head"><div><span className="section-label">CUSTOMERS</span><h2>Balances to follow up</h2><p>Amounts still owed by customers.</p></div><button type="button" className="button button-soft" onClick={() => setTab("Customer balances")}>View balances</button></div>
            <div className="workflow-list">{openReceivables.slice(0, 5).map(row => <div className="workflow-row" key={row.id}><div><strong>{row.customer_name}</strong><small>Sale recorded {String(row.created_at).slice(0, 10)}</small></div><span>{money(row.balance, currencyCode)}</span></div>)}{!openReceivables.length && <p className="empty-inline">No customer balances are currently outstanding.</p>}</div>
          </section>
        </div>
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">QUICK ACTIONS</span><h2>What would you like to do?</h2></div></div><div className="foundation-grid">
          <button type="button" className="panel foundation-panel" onClick={() => setTab("Expenses")}><div className="panel-head"><div><h2>Record an expense</h2><p>Enter money already spent by the business.</p></div><span aria-hidden="true">→</span></div></button>
          <button type="button" className="panel foundation-panel" onClick={() => setTab("Customer balances")}><div className="panel-head"><div><h2>Record a customer payment</h2><p>Update an amount a customer still owes.</p></div><span aria-hidden="true">→</span></div></button>
          <button type="button" className="panel foundation-panel" onClick={() => setTab("End-of-day check")}><div className="panel-head"><div><h2>Check today's receipts</h2><p>Compare LEXA's records with cash counted and statements checked by your team.</p></div><span aria-hidden="true">→</span></div></button>
          <Link className="panel foundation-panel" href="/purchasing"><div className="panel-head"><div><h2>Supplier bills and payments</h2><p>Review bills, payments and balances due to suppliers.</p></div><span aria-hidden="true">→</span></div></Link>
        </div></section>
      </>}

      {tab === "Expenses" && <>
        <section className="workspace-section">
          <div className="section-head"><div><span className="section-label">RECORD MONEY SPENT</span><h2>Add an expense</h2><p>This form is for money already paid by the business. For an unpaid supplier invoice, use <Link href="/purchasing">Supplier bills</Link> so it appears in the correct balance.</p></div></div>
          {expenseAccounts.length === 0 && <div className="notice notice-error">Expense categories are not set up yet. Finish business setup or ask the business owner to review finance settings.</div>}
          {activeChannels.length === 0 && <div className="notice notice-error">Add an active payment method before recording an expense. <button type="button" className="button button-soft" onClick={() => setTab("Payment methods")}>Set up payment methods</button></div>}
          <form onSubmit={handleCreateExpense}>
            <div className="form-grid">
              <label htmlFor="expense-date">Date paid<input id="expense-date" type="date" value={expenseDate} max={today()} onChange={e => setExpenseDate(e.target.value)} required /></label>
              <label htmlFor="expense-reference">Receipt or reference<input id="expense-reference" value={expenseReference} onChange={e => setExpenseReference(e.target.value)} maxLength={120} placeholder="e.g. receipt number" required /></label>
              <label htmlFor="expense-category">Expense category<select id="expense-category" value={expenseAccountId} onChange={e => setExpenseAccountId(e.target.value)} required><option value="">Choose category</option>{expenseAccounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
            </div>
            <div className="form-grid" style={{ marginTop: 14 }}>
              <label htmlFor="expense-description">What was the money spent on?<input id="expense-description" value={expenseDescription} onChange={e => setExpenseDescription(e.target.value)} maxLength={1000} placeholder="e.g. shop electricity" required /></label>
              <label htmlFor="expense-paid-by">Paid using<select id="expense-paid-by" value={expenseChannelId} onChange={e => setExpenseChannelId(e.target.value)} required><option value="">Choose payment method</option>{activeChannels.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
              <label htmlFor="expense-subtotal">Amount before tax<input id="expense-subtotal" type="number" min="0" step="0.01" value={expenseSubtotal} onChange={e => setExpenseSubtotal(e.target.value)} required /></label>
            </div>
            <div className="form-grid" style={{ marginTop: 14 }}>
              <label htmlFor="expense-tax">Tax amount, if any<input id="expense-tax" type="number" min="0" step="0.01" value={expenseTax} onChange={e => setExpenseTax(e.target.value)} /></label>
              <div><span className="muted">Total expense</span><strong style={{ display: "block", marginTop: 10 }}>{money((Number(expenseSubtotal) || 0) + (Number(expenseTax) || 0), currencyCode)}</strong></div>
              <div className="muted">Saving creates a draft only. You can review it before adding it to the business records.</div>
            </div>
            <div className="header-actions" style={{ justifyContent: "flex-end", marginTop: 18 }}><button type="submit" className="button button-dark" disabled={saving || !currencyCode || !expenseAccounts.length || !activeChannels.length}>{saving ? "Saving…" : "Save expense draft"}</button></div>
          </form>
        </section>
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">EXPENSE HISTORY</span><h2>Expenses</h2><p>Drafts do not affect official totals until they are added. Cancelled drafts and corrected entries remain visible for traceability.</p></div></div>
          <div className="table-wrap"><table><thead><tr><th>Date</th><th>Expense</th><th>Paid using</th><th>Total</th><th>Status</th><th>Next step</th></tr></thead><tbody>
            {relevantExpenses.map(expense => <tr key={expense.id}><td>{expense.expense_date}</td><td><b>{expense.description}</b><small>{expense.reference} · {expense.expense_account_name}</small></td><td>{expense.payment_channel_name || "Unavailable"}</td><td>{money(expense.total, expense.currency_code)}</td><td><span className={statusClass(expense.status)}>{statusLabel(expense.status)}</span></td><td>
              {expense.status === "DRAFT" && <div className="row-actions wrap-actions"><button type="button" className="button button-dark button-small" disabled={saving} onClick={() => void handlePostExpense(expense)}>Add to business records</button><button type="button" className="button button-soft button-small" disabled={saving} onClick={() => void handleVoidExpense(expense)}>Cancel draft</button></div>}
              {expense.status === "POSTED" && <button type="button" className="button button-soft button-small" disabled={saving} onClick={() => { setCorrectingExpenseId(expense.id); setCorrectionReason(""); }}>Correct this expense</button>}
              {expense.status === "REVERSED" && <small>Corrected. The earlier entry is kept for history.</small>}
              {expense.status === "VOIDED" && <small>Kept for history</small>}
              <button type="button" className="button button-soft button-small" disabled={historyLoadingId === expense.id} onClick={() => void toggleExpenseHistory(expense)}>{historyLoadingId === expense.id ? "Loading history…" : expandedExpenseId === expense.id ? "Hide history" : "View history"}</button>
              {expandedExpenseId === expense.id && <div className="compact-form" style={{ marginTop: 10 }}>
                {(expenseHistory[expense.id] || []).map((event, index) => <div key={`${event.event_type}-${event.occurred_at}-${index}`}><strong>{expenseHistoryLabel(event.event_type)}</strong><small>{new Date(event.occurred_at).toLocaleString("en-UG")}{event.actor_email ? ` · By ${event.actor_email}` : ""}</small>{event.reason && <p className="muted">Reason: {event.reason}</p>}</div>)}
                {!expenseHistory[expense.id]?.length && <p className="muted">No history details are available for this expense.</p>}
              </div>}
              {correctingExpenseId === expense.id && <form className="compact-form" onSubmit={handleReverseExpense}><p className="muted">This corrects the business record. It does not mean money was returned.</p><label>Why does this need correcting?<textarea rows={2} value={correctionReason} onChange={e => setCorrectionReason(e.target.value)} minLength={5} required /></label><div className="row-actions"><button type="submit" className="button button-dark button-small" disabled={saving}>Save correction</button><button type="button" className="button button-soft button-small" onClick={() => setCorrectingExpenseId("")}>Keep as is</button></div></form>}
            </td></tr>)}
            {!relevantExpenses.length && <tr><td colSpan={6}>No expenses are recorded in this currency yet. Use the form above to add one.</td></tr>}
          </tbody></table></div>
        </section>
      </>}

      {tab === "Customer balances" && <section className="workspace-section">
        <div className="section-head"><div><span className="section-label">MONEY CUSTOMERS OWE</span><h2>Customer balances</h2><p>Record a payment when a customer settles some or all of an earlier sale. LEXA updates the remaining balance.</p></div><strong>{money(totalReceivables, currencyCode)} outstanding</strong></div>
        <div className="table-wrap"><table><thead><tr><th>Customer</th><th>Sale date</th><th>Original amount</th><th>Paid so far</th><th>Still owed</th><th>Action</th></tr></thead><tbody>
          {openReceivables.map(row => <tr key={row.id}><td><b>{row.customer_name}</b><small>Sale reference {row.sale_id.slice(0, 8)}</small></td><td>{String(row.created_at).slice(0, 10)}</td><td>{money(row.original_amount, currencyCode)}</td><td>{money(row.paid_amount, currencyCode)}</td><td>{money(row.balance, currencyCode)}</td><td><button type="button" className="button button-soft button-small" onClick={() => openPaymentForm(row)}>{payingReceivableId === row.id ? "Close form" : "Record payment"}</button>
            {payingReceivableId === row.id && <form className="compact-form" onSubmit={handleReceivablePayment}>
              <label>Amount received ({currencyCode})<input type="number" min="0.01" max={row.balance} step="0.01" value={receivableAmount} onChange={e => setReceivableAmount(e.target.value)} required /></label>
              <label>How did the customer pay?<select value={receivableChannelId} onChange={e => setReceivableChannelId(e.target.value)} required><option value="">Choose payment method</option>{activeChannels.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
              <label>Date received<input type="date" value={receivableDate} max={today()} onChange={e => setReceivableDate(e.target.value)} required /></label>
              <label>Receipt or transaction reference (optional)<input value={receivableReference} onChange={e => setReceivableReference(e.target.value)} maxLength={120} placeholder="Receipt or transaction ID" /></label>
              <p className="muted">Enter the reference only—never a PIN, password or one-time confirmation code. LEXA records what you enter; it does not confirm this payment with a bank or mobile-money provider.</p>
              <button type="submit" className="button button-dark button-small" disabled={saving}>{saving ? "Saving…" : "Save payment"}</button>
            </form>}
          </td></tr>)}
          {!openReceivables.length && <tr><td colSpan={6}>No customer balances are outstanding right now.</td></tr>}
        </tbody></table></div>
      </section>}

      {tab === "End-of-day check" && <>
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">COMPARE RECORDS WITH ACTUAL RECEIPTS</span><h2>End-of-day check</h2><p>Compare payments recorded in LEXA with the receipts your team counted or found in statements. This checks receipts less recorded refunds, not the balance left in a till or bank account after money is spent. LEXA does not connect to or verify wallets or bank accounts.</p></div><button type="button" className="button button-dark" disabled={saving} onClick={() => void handleStartDayCheck()}>Open today's check</button></div>
          {reconciliations.length > 0 && <div className="form-grid"><label htmlFor="day-check-select">Choose business day<select id="day-check-select" value={selectedReconciliationId} onChange={e => setSelectedReconciliationId(e.target.value)}>{reconciliations.map(r => <option key={r.id} value={r.id}>{r.business_date} · {statusLabel(r.status)}</option>)}</select></label><div><span className="muted">Check status</span><strong style={{ display: "block", marginTop: 8 }}>{selectedReconciliation ? statusLabel(selectedReconciliation.status) : "Not selected"}</strong></div><div><span className="muted">Payment methods</span><strong style={{ display: "block", marginTop: 8 }}>{selectedReconciliation?.lines.length || 0}</strong></div></div>}
        </section>
        {selectedReconciliation && <section className="workspace-section"><div className="section-head"><div><span className="section-label">PAYMENT METHOD TOTALS</span><h2>{selectedReconciliation.business_date}</h2><p>Enter the actual receipts for each method (after refunds, before expenses). A positive difference means more was counted than recorded; a negative difference means less. Save each amount, then explain any difference before finishing.</p></div>{selectedReconciliation.status !== "CLOSED" && <button type="button" className="button button-dark" disabled={saving} onClick={() => void handleCloseDay()}>Finish end-of-day check</button>}</div>
          <div className="table-wrap"><table><thead><tr><th>Payment method</th><th>LEXA recorded</th><th>Actual amount</th><th>Difference</th><th>Review</th></tr></thead><tbody>
            {selectedReconciliation.lines.map(line => { const actual = actuals[line.line_id] ?? (line.actual_amount == null ? "" : String(line.actual_amount)); const difference = actual === "" ? null : Number(actual) - Number(line.expected_amount); const reviewed = line.line_status === "ACKNOWLEDGED" || line.line_status === "RESOLVED" || line.line_status === "CLOSED"; const actualSaved = line.actual_amount !== null && line.actual_amount !== undefined && actual !== "" && Math.abs(Number(line.actual_amount) - Number(actual)) <= 0.0001; return <Fragment key={line.line_id}><tr><td><b>{line.channel_name}</b><small>{typeLabel(line.channel_type)}</small></td><td>{money(line.expected_amount, currencyCode)}</td><td><div style={{ minWidth: 180 }}><input aria-label={`Actual receipts for ${line.channel_name}`} type="number" min="0" step="0.01" value={actual} disabled={selectedReconciliation.status === "CLOSED"} onChange={e => setActuals(s => ({ ...s, [line.line_id]: e.target.value }))} placeholder="Enter actual receipts"/><input aria-label={`Note for ${line.channel_name}`} value={actualNotes[line.line_id] ?? line.line_notes ?? ""} disabled={selectedReconciliation.status === "CLOSED"} onChange={e => setActualNotes(s => ({ ...s, [line.line_id]: e.target.value }))} placeholder="Note (optional)" style={{ marginTop: 5 }}/><button type="button" className="button button-soft button-small" style={{ marginTop: 5 }} disabled={saving || selectedReconciliation.status === "CLOSED"} onClick={() => void handleSaveActual(line)}>Save actual receipts</button></div></td><td>{difference === null ? "Not entered" : <strong className={Math.abs(difference) > 0.0001 ? "number-warning" : ""}>{money(difference, currencyCode)}</strong>}</td><td>{reviewed ? <span className="status status-good">Reviewed</span> : difference !== null && Math.abs(difference) > 0.0001 ? <button type="button" className="button button-soft button-small" disabled={saving || selectedReconciliation.status === "CLOSED" || !actualSaved} onClick={() => beginReview(line)}>Review difference</button> : difference === 0 ? <span className="status status-good">Matches</span> : <span className="status">Needs amount</span>}</td></tr>{reviewingLineId === line.line_id && selectedReconciliation.status !== "CLOSED" && <tr key={`${line.line_id}-review`}><td colSpan={5}><form className="compact-form" onSubmit={handleAcknowledge}><label>What did you check to explain this difference?<textarea rows={2} value={reviewReason} onChange={e => setReviewReason(e.target.value)} minLength={3} maxLength={1000} required placeholder="e.g. Checked the mobile-money statement and found a delayed receipt." /></label><p className="muted">This note records the review only. It does not change the amounts.</p><div className="row-actions"><button type="submit" className="button button-dark button-small" disabled={saving}>{saving ? "Saving…" : "Save review"}</button><button type="button" className="button button-soft button-small" disabled={saving} onClick={() => { setReviewingLineId(""); setReviewReason(""); }}>Cancel</button></div></form></td></tr>}</Fragment>; })}
            {!selectedReconciliation.lines.length && <tr><td colSpan={5}>No active payment methods were available when this check was opened.</td></tr>}
          </tbody></table></div>
          {selectedReconciliation.status === "CLOSED" && <div className="notice" role="status">This end-of-day check is complete. Its recorded figures are kept for history.</div>}
        </section>}
        {!reconciliations.length && <section className="workspace-section"><p className="empty-inline">No end-of-day checks yet. Open today's check to start comparing recorded receipts.</p></section>}
      </>}

      {tab === "Payment methods" && <>
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">HOW YOUR BUSINESS RECEIVES MONEY</span><h2>Payment methods</h2><p>Create names that your staff will recognize, such as Cash, MTN Line 1, Airtel Line 1, Stanbic or Centenary Bank.</p></div></div>
          <div className="notice" role="note">LEXA only records what your team enters. Do not enter phone or bank account numbers, PINs, passwords, one-time codes, API keys or other sign-in details.</div>
          <form className="command-form" onSubmit={handleCreatePaymentMethod}>
            <label>Payment method name<input value={channelName} onChange={e => setChannelName(e.target.value)} placeholder="e.g. MTN Line 1 or Stanbic" maxLength={160} required /></label>
            <div className="form-grid"><label>Type<select value={channelType} onChange={e => setChannelType(e.target.value)}><option value="CASH">Cash</option><option value="MOBILE_MONEY">Mobile money</option><option value="BANK">Bank</option><option value="CARD">Card</option><option value="CHEQUE">Cheque</option><option value="OTHER">Other</option></select></label><label>Institution or service (optional)<input value={channelProvider} onChange={e => setChannelProvider(e.target.value)} placeholder="e.g. MTN" maxLength={100}/></label></div>
            <p className="muted">Currency: {currencyCode || "Unavailable"}. All methods on this page use your business currency.</p>
            <button type="submit" className="button button-dark" disabled={saving || !currencyCode}>{saving ? "Saving…" : "Add payment method"}</button>
          </form>
        </section>
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">YOUR PAYMENT METHODS</span><h2>{channels.length} method{channels.length === 1 ? "" : "s"}</h2><p>Stopping a method prevents new entries from using it. Existing payments and reports are kept.</p></div></div>
          <div className="workflow-list">{channels.map(channel => <div className="workflow-row" key={channel.id}><div><strong>{channel.name}</strong><small>{typeLabel(channel.channel_type)}{channel.provider ? ` · ${channel.provider}` : ""} · {channel.currency_code}</small></div><span className={channel.active ? "status status-good" : "status status-muted"}>{channel.active ? "Available" : "Inactive"}</span>{channel.active && <button type="button" className="button button-soft button-small" disabled={saving} onClick={() => void handleDeactivate(channel)}>Stop using</button>}</div>)}{!channels.length && <p className="empty-inline">No payment methods have been set up yet. Add at least Cash or the methods your business uses.</p>}</div>
        </section>
      </>}

      {tab === "Financial reports" && <>
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">CHOOSE A REPORTING PERIOD</span><h2>Income, spending and cash movement</h2><p>Figures are grouped by your business currency. Money recorded as received is shown separately from sales.</p></div></div>
          <form onSubmit={loadReports}><div className="form-grid"><label htmlFor="finance-from">From<input id="finance-from" type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} required /></label><label htmlFor="finance-to">To<input id="finance-to" type="date" value={toDate} onChange={e => setToDate(e.target.value)} required /></label><div><span className="muted">Reporting currency</span><strong style={{ display: "block", marginTop: 10 }}>{currencyCode || "Unavailable"}</strong></div></div><div className="header-actions" style={{ justifyContent: "flex-end", marginTop: 16 }}><Link className="button button-soft" href="/reports">Open detailed business reports</Link><button type="submit" className="button button-dark" disabled={reportBusy || !currencyCode}>{reportBusy ? "Updating figures…" : "Update report figures"}</button></div></form>
        </section>
        {report && <>
          <section className="workspace-section"><div className="section-head"><div><span className="section-label">DAY BY DAY</span><h2>Sales and money recorded</h2><p>Sales and recorded payments are shown separately. This is not a bank balance.</p></div></div><SalesTrendChart daily={report.daily || []} startDate={report.from_date || fromDate} endDate={report.to_date || toDate} currencyCode={reportCurrency} /></section>
          <section className="metric-strip"><div><span>Sales before returns</span><strong>{money(report.totals.sales_total, reportCurrency)}</strong></div><div><span>Sales after returns</span><strong>{money(report.totals.net_sales, reportCurrency)}</strong></div><div><span>Money recorded as received</span><strong>{money(report.totals.payments_collected, reportCurrency)}</strong></div><div><span>Expenses paid</span><strong>{money(report.totals.expenses_total, reportCurrency)}</strong></div><div><span>Expense corrections recorded (accounting only)</span><strong>{money(report.totals.expense_reversals_total, reportCurrency)}</strong><small>Correction records are not proof that money came back.</small></div><div><span>Net recorded money movement</span><strong>{money(report.totals.net_cash_movement, reportCurrency)}</strong><small>Recorded receipts minus refunds and expense amounts originally recorded as paid. A correction does not prove money returned; this is not a bank balance.</small></div><div><span>New customer balances from credit sales</span><strong>{money(report.totals.credit_created, reportCurrency)}</strong></div></section>
          <div className="header-actions" aria-label="Open supporting records" style={{ justifyContent: "flex-start", flexWrap: "wrap" }}>
            <Link className="button button-soft button-small" href="/sales">View sales and payments</Link>
            <button type="button" className="button button-soft button-small" onClick={() => setTab("Expenses")}>View expenses</button>
            <button type="button" className="button button-soft button-small" onClick={() => setTab("End-of-day check")}>Check receipts</button>
            <button type="button" className="button button-soft button-small" onClick={() => setTab("Customer balances")}>View customer balances</button>
            <Link className="button button-soft button-small" href="/purchasing">View supplier bills</Link>
          </div>
          <section className="workspace-section"><div className="section-head"><div><span className="section-label">PRODUCT COSTS</span><h2>Sales after product costs</h2><p>This is sales after returns minus the recorded cost of the products sold. It does not subtract staff, rent, transport or other running costs.</p></div></div><div className="metric-strip"><div><span>Cost of products sold</span><strong>{money(productCogs, reportCurrency)}</strong></div><div><span>Sales left after product costs</span><strong>{money(productMargin, reportCurrency)}</strong></div></div><div className="table-wrap"><table><thead><tr><th>Product</th><th>Units sold</th><th>Sales after returns</th><th>Product cost</th><th>Sales left after product cost</th></tr></thead><tbody>{productSummary.map((item, i) => <tr key={`${item.variant_id}-${i}`}><td><b>{item.product_name || "Product"}</b><small>{item.variant_name || item.sku || ""}</small></td><td>{Number(item.units_sold).toLocaleString("en-UG")}</td><td>{money(item.net_sales, item.currency_code)}</td><td>{money(item.cogs, item.currency_code)}</td><td>{money(item.gross_margin, item.currency_code)}</td></tr>)}{!productSummary.length && <tr><td colSpan={5}>No product cost figures are available for this period. Refresh the figures or choose another period.</td></tr>}</tbody></table></div></section>
        </>}
        <div className="two-column"><section className="workspace-section"><div className="section-head"><div><span className="section-label">INCOME AND SPENDING</span><h2>Recorded financial records</h2><p>Amounts come from saved business records for the selected dates.</p></div></div><div className="table-wrap"><table><thead><tr><th>Name</th><th>Category</th><th>Amount</th></tr></thead><tbody>{incomeRows.map(row => <tr key={row.account_id}><td>{row.name}</td><td>{row.account_type === "REVENUE" ? "Income" : "Expense"}</td><td>{money(row.amount, currencyCode)}</td></tr>)}{!incomeRows.length && <tr><td colSpan={3}>No financial records yet are available for this period.</td></tr>}</tbody></table></div></section>
          <section className="workspace-section"><div className="section-head"><div><span className="section-label">WHAT THE BUSINESS OWNS AND OWES</span><h2>Financial position as of {toDate}</h2><p>Based on financial entries saved in the business records.</p></div></div><div className="table-wrap"><table><thead><tr><th>Name</th><th>Category</th><th>Amount</th></tr></thead><tbody>{balanceRows.map(row => <tr key={row.account_id}><td>{row.name}</td><td>{({ ASSET: "Owned by the business", LIABILITY: "Owed by the business", EQUITY: "Owner's share" } as Record<string, string>)[row.account_type] || row.account_type}</td><td>{money(row.amount, currencyCode)}</td></tr>)}{!balanceRows.length && <tr><td colSpan={3}>No figures are available for this date.</td></tr>}</tbody></table></div></section></div>
        <section className="workspace-section"><div className="section-head"><div><span className="section-label">RELATED WORK</span><h2>Follow up on the underlying records</h2></div></div><div className="foundation-grid"><Link className="panel foundation-panel" href="/sales"><div className="panel-head"><div><h2>Sales and customer payments</h2><p>Open a sale and see its recorded payments, returns and balance.</p></div><span>→</span></div></Link><Link className="panel foundation-panel" href="/purchasing"><div className="panel-head"><div><h2>Supplier bills and payments</h2><p>Review supplier bills, payments and amounts still payable.</p></div><span>→</span></div></Link><Link className="panel foundation-panel" href="/reports"><div className="panel-head"><div><h2>Business reports</h2><p>Review performance by product, customer and branch.</p></div><span>→</span></div></Link></div></section>
      </>}
    </main>
  </AppShell>;
}
