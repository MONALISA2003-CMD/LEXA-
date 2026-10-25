"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../../components/app-shell";
import { getBusinessProfile, restoreSession, userFacingError } from "../../../lib/api";

type ApprovalLimit = {
  id: string;
  role_name: string;
  currency_code: string;
  max_approval_amount: string;
  created_at?: string | null;
  updated_at?: string | null;
};
type ApprovalPolicyResponse = { items: ApprovalLimit[]; eligible_roles: string[] };

async function purchasingJson<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/lexa/api/v1${path}`, {
    credentials: "include",
    cache: "no-store",
    ...init,
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers || {}),
    },
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload && typeof payload === "object" && "detail" in payload
      ? (payload as { detail?: unknown }).detail : null;
    const message = detail && typeof detail === "object" && "message" in detail
      ? String((detail as { message?: unknown }).message || "")
      : typeof detail === "string" ? detail : "LEXA could not save the approval limit. Review the role and try again.";
    throw new Error(message);
  }
  return payload as T;
}

function money(value: string, currency: string) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return `${currency} ${value}`;
  try {
    return new Intl.NumberFormat("en-UG", { style: "currency", currency, maximumFractionDigits: 2 }).format(amount);
  } catch {
    return `${currency} ${amount.toLocaleString("en-UG", { maximumFractionDigits: 2 })}`;
  }
}

export default function PurchasingApprovalLimitsPage() {
  const [token, setToken] = useState("");
  const [items, setItems] = useState<ApprovalLimit[]>([]);
  const [eligibleRoles, setEligibleRoles] = useState<string[]>([]);
  const [roleName, setRoleName] = useState("Manager");
  const [currencyCode, setCurrencyCode] = useState("");
  const [amount, setAmount] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const selectedLimit = useMemo(
    () => items.find(item => item.role_name === roleName && item.currency_code === currencyCode),
    [items, roleName, currencyCode],
  );

  async function load() {
    setLoading(true);
    setError("");
    try {
      const session = await restoreSession();
      if (!session) throw new Error("Your sign-in may have expired. Sign in again to manage purchasing approval limits.");
      setToken(session.access_token);
      const [profile, policy] = await Promise.all([
        getBusinessProfile(),
        purchasingJson<ApprovalPolicyResponse>("/purchasing/approval-limits", session.access_token),
      ]);
      setCurrencyCode(current => current || (profile?.currency_code || "").toUpperCase());
      setEligibleRoles(policy.eligible_roles || []);
      setItems(policy.items || []);
      if (policy.eligible_roles?.length && !policy.eligible_roles.includes(roleName)) setRoleName(policy.eligible_roles[0]);
    } catch (cause) {
      setError(userFacingError(cause, "LEXA could not load approval policy settings."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    if (!token) { setError("Sign in again before saving an approval limit."); return; }
    const currency = currencyCode.trim().toUpperCase();
    if (!/^[A-Z]{3}$/.test(currency)) { setError("Enter the three-letter currency used by this business and supplier order."); return; }
    const parsed = Number(amount);
    if (!Number.isFinite(parsed) || parsed < 0) { setError("Enter a non-negative approval amount."); return; }
    setSaving(true);
    try {
      const saved = await purchasingJson<ApprovalLimit>("/purchasing/approval-limits", token, {
        method: "PUT",
        body: JSON.stringify({ role_name: roleName, currency_code: currency, max_approval_amount: parsed.toFixed(2) }),
      });
      setItems(previous => [saved, ...previous.filter(item => !(item.role_name === saved.role_name && item.currency_code === saved.currency_code))].sort((a, b) => a.role_name.localeCompare(b.role_name) || a.currency_code.localeCompare(b.currency_code)));
      setCurrencyCode(currency);
      setNotice(`${saved.role_name} approval limit saved for ${saved.currency_code}.`);
    } catch (cause) {
      setError(userFacingError(cause, "LEXA could not save this approval limit. No change was confirmed."));
    } finally {
      setSaving(false);
    }
  }

  return <AppShell title="Purchasing approval limits" eyebrow="Purchasing controls">
    <section className="panel" style={{ padding: "1.25rem", maxWidth: 1040 }}>
      <div className="panel-head">
        <div>
          <p className="eyebrow">ROLE-BASED PURCHASE AUTHORIZATION</p>
          <h2>Control who can approve purchase orders</h2>
        </div>
      </div>
      <p>Approval limits apply to the purchase-order total and the exact currency selected. LEXA does not convert currencies automatically. Owner and Administrator roles are the explicit override roles; other roles must have a configured limit and cannot approve above it.</p>
      <p>For a member with more than one purchasing-approval role, the strictest applicable limit applies. A missing currency-specific rule fails closed instead of granting an unlimited approval.</p>
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {notice && <div className="notice notice-success" role="status">{notice}</div>}

      <form className="embedded-form" onSubmit={save}>
        <h3>Set a role limit</h3>
        {loading ? <p role="status">Loading workspace approval rules…</p> : eligibleRoles.length === 0 ? <p>No non-administrator roles currently have purchase-order approval permission. Review role permissions before creating a limit.</p> : <>
          <div className="form-grid">
            <label>Approver role
              <select value={roleName} onChange={event => { setRoleName(event.target.value); setAmount(""); }} required>
                {eligibleRoles.map(role => <option key={role} value={role}>{role}</option>)}
              </select>
            </label>
            <label>Currency code
              <input aria-label="Approval currency code" value={currencyCode} onChange={event => setCurrencyCode(event.target.value.toUpperCase().slice(0, 3))} minLength={3} maxLength={3} pattern="[A-Za-z]{3}" placeholder="Business currency" required />
            </label>
          </div>
          <label>Maximum purchase order total
            <input aria-label="Maximum purchase approval amount" type="number" min="0" step="0.01" value={amount} onChange={event => setAmount(event.target.value)} required placeholder="Enter an approval limit" />
          </label>
          {selectedLimit && <p>Current limit: <strong>{money(selectedLimit.max_approval_amount, selectedLimit.currency_code)}</strong></p>}
          <button className="button button-dark" type="submit" disabled={saving}>{saving ? "Saving limit…" : "Save approval limit"}</button>
        </>}
      </form>

      <div className="mini-register" style={{ marginTop: "1.5rem" }}>
        <div className="list-head"><div><p className="eyebrow">CURRENT POLICY</p><h3>Configured approval limits</h3></div><button type="button" className="button button-soft button-small" onClick={() => void load()} disabled={loading || saving}>Refresh</button></div>
        {loading ? <p role="status">Loading…</p> : items.length === 0 ? <div className="empty-inline">No approval limits have been configured. Non-administrator approvals will be blocked until a limit is saved.</div> : items.map(item => <div className="workflow-row" key={item.id}>
          <div><strong>{item.role_name}</strong><small>Currency: {item.currency_code}</small></div>
          <div className="balance-stack"><small>Maximum approval</small><b>{money(item.max_approval_amount, item.currency_code)}</b></div>
          <button className="button button-soft button-small" type="button" onClick={() => { setRoleName(item.role_name); setCurrencyCode(item.currency_code); setAmount(item.max_approval_amount); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Edit limit</button>
        </div>)}
      </div>
      <div style={{ marginTop: "1.25rem" }}>
        <Link className="text-link" href="/purchasing">Return to purchasing →</Link>
      </div>
    </section>
  </AppShell>;
}
