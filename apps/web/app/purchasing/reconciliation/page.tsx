"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../../components/app-shell";
import { restoreSession, userFacingError } from "../../../lib/api";

type Reconciliation = {
  status: "ok" | "mismatch";
  scope: string;
  checks: Record<string, number | string | null | Array<Record<string, unknown>>>;
  stock_mismatches: Array<Record<string, unknown>>;
  supplier_mismatches: Array<Record<string, unknown>>;
  purchase_inventory_value_by_currency: Array<{ currency_code: string; inventory_stock_cost: string; inventory_journal_value: string; difference: string }>;
  currency_note: string;
  read_only: true;
};

async function loadPurchasingReconciliation(token: string): Promise<Reconciliation> {
  const response = await fetch("/api/lexa/api/v1/purchasing/reconciliation", {
    method: "GET", credentials: "include", cache: "no-store",
    headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload && typeof payload === "object" && "detail" in payload ? (payload as { detail?: unknown }).detail : null;
    const message = detail && typeof detail === "object" && "message" in detail
      ? String((detail as { message?: unknown }).message || "")
      : typeof detail === "string" ? detail : "LEXA could not complete the purchasing reconciliation.";
    throw new Error(message);
  }
  return payload as Reconciliation;
}

function metricLabel(key: string) {
  return key.replaceAll("_", " ").replace(/\b[a-z]/g, value => value.toUpperCase());
}

export default function PurchasingReconciliationPage() {
  const [result, setResult] = useState<Reconciliation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshedAt, setRefreshedAt] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const session = await restoreSession();
      if (!session) throw new Error("Your sign-in may have expired. Sign in again to view purchasing reconciliation.");
      const next = await loadPurchasingReconciliation(session.access_token);
      setResult(next); setRefreshedAt(new Date().toLocaleString("en-UG"));
    } catch (cause) {
      setError(userFacingError(cause, "LEXA could not load purchasing reconciliation."));
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const checks = result?.checks || {};
  const details = [
    { title: "Stock quantity vs ledger", key: "stock_balance_ledger_mismatches" },
    { title: "Posted receipts missing journal", key: "posted_receipts_missing_journals" },
    { title: "Supplier entries missing journal", key: "supplier_ledger_entries_missing_journals" },
    { title: "Unbalanced posted journals", key: "unbalanced_posted_journals" },
    { title: "Supplier subledger vs GL", key: "supplier_subledger_gl_mismatches" },
    { title: "Unmapped purchase stock moves", key: "unmapped_purchase_inventory_transactions" },
  ];

  return <AppShell title="Purchasing reconciliation" eyebrow="Inventory · supplier balances · accounting">
    <section className="panel" style={{ padding: "1.25rem", maxWidth: 1180 }}>
      <div className="panel-head">
        <div><p className="eyebrow">READ-ONLY CONTROL REPORT</p><h2>Do stock, supplier balances and journals agree?</h2></div>
        <button type="button" className="button button-soft button-small" onClick={() => void refresh()} disabled={loading}>{loading ? "Checking…" : "Refresh reconciliation"}</button>
      </div>
      <p>This report does not repair or change records. It checks inventory quantities against the stock ledger, posted purchase receipts against journals, supplier balances against accounts payable and advances, journal balancing, and purchase stock-cost flow by currency.</p>
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {loading && <p role="status">Checking stock and accounting records…</p>}
      {!loading && result && <>
        <div className={`notice ${result.status === "ok" ? "notice-success" : "notice-error"}`} role="status">
          <strong>{result.status === "ok" ? "Reconciliation passed" : "Differences need review"}</strong>
          <span> {result.scope}. Read-only. Last checked: {refreshedAt || "just now"}.</span>
        </div>
        <div className="summary-grid" style={{ marginTop: "1rem" }}>
          {details.map(item => <article className="summary-card" key={item.key}>
            <p className="eyebrow">{item.title}</p><strong>{String(checks[item.key] ?? "—")}</strong>
          </article>)}
        </div>
        <h3 style={{ marginTop: "1.5rem" }}>Purchase inventory cost by currency</h3>
        <p>{result.currency_note}</p>
        {result.purchase_inventory_value_by_currency.length === 0 ? <div className="empty-inline">No posted purchase inventory or journal values were available to compare.</div> : <div className="mini-register">
          {result.purchase_inventory_value_by_currency.map(row => <div className="workflow-row" key={row.currency_code}>
            <div><strong>{row.currency_code}</strong><small>Purchases less supplier returns and reversals</small></div>
            <div className="balance-stack"><small>Stock-cost flow</small><b>{row.inventory_stock_cost}</b></div>
            <div className="balance-stack"><small>Inventory journal flow</small><b>{row.inventory_journal_value}</b></div>
            <div className="balance-stack"><small>Difference</small><b>{row.difference}</b></div>
          </div>)}
        </div>}
        {result.stock_mismatches.length > 0 && <><h3 style={{ marginTop: "1.5rem" }}>Stock quantity differences</h3><div className="mini-register">{result.stock_mismatches.map((row, index) => <div className="workflow-row" key={`${String(row.location_id)}-${String(row.variant_id)}-${index}`}><div><strong>{String(row.variant_id)}</strong><small>Location {String(row.location_id)}</small></div><span>Balance: {String(row.balance_quantity)}</span><span>Ledger: {String(row.ledger_quantity)}</span></div>)}</div></>}
        {result.supplier_mismatches.length > 0 && <><h3 style={{ marginTop: "1.5rem" }}>Supplier balance differences</h3><div className="mini-register">{result.supplier_mismatches.map((row, index) => <div className="workflow-row" key={`${String(row.supplier_party_id)}-${String(row.currency_code)}-${index}`}><div><strong>{String(row.supplier_party_id)}</strong><small>{String(row.currency_code)}</small></div><span>Supplier ledger: {String(row.supplier_ledger_net)}</span><span>Accounting: {String(row.accounting_net)}</span><span>Difference: {String(row.difference)}</span></div>)}</div></>}
      </>}
      <div style={{ display: "flex", gap: ".75rem", flexWrap: "wrap", marginTop: "1.5rem" }}>
        <Link className="text-link" href="/purchasing">Return to purchasing</Link>
        <Link className="text-link" href="/purchasing/approval-limits">Manage approval limits</Link>
      </div>
    </section>
  </AppShell>;
}
