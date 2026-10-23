"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  createTaxConfiguration,
  createTaxRate,
  getEfrisConfig,
  getFiscalDocuments,
  getTaxConfigurations,
  getTaxRates,
  updateEfrisConfig,
  type EfrisConfig,
  type FiscalDocument,
  type TaxConfiguration,
  type TaxRate,
} from "../../lib/api";
import { AppShell } from "../../components/app-shell";
import { localDateISO } from "../../lib/date.mjs";

const fiscalStatusLabel = (value: string) => ({
  NOT_REGISTERED: "Not registered",
  PENDING: "Waiting for setup",
  ACTIVE: "Active",
  SUSPENDED: "Paused",
  DRAFT: "Draft",
  SUBMITTED: "Sent to URA",
  ACCEPTED: "Accepted by URA",
  REJECTED: "Not accepted by URA",
  FAILED: "Needs attention",
  CANCELLED: "Cancelled",
}[value] || value.replaceAll("_", " ").toLowerCase());

const fiscalDocumentLabel = (value: string) => ({
  INVOICE: "Invoice",
  CREDIT_NOTE: "Credit note",
  RECEIPT: "Receipt",
  DEBIT_NOTE: "Debit note",
}[value] || value.replaceAll("_", " ").toLowerCase());

const errorMessage = (reason: unknown, fallback: string) =>
  reason instanceof Error && reason.message ? reason.message : fallback;

export default function CompliancePage() {
  const [config, setConfig] = useState<EfrisConfig | null>(null);
  const [docs, setDocs] = useState<FiscalDocument[]>([]);
  const [taxRates, setTaxRates] = useState<TaxRate[]>([]);
  const [taxConfigs, setTaxConfigs] = useState<TaxConfiguration[]>([]);
  const [busy, setBusy] = useState(true);
  const [savingEfris, setSavingEfris] = useState(false);
  const [savingRate, setSavingRate] = useState(false);
  const [savingRule, setSavingRule] = useState(false);
  const [message, setMessage] = useState("");
  const [messageTone, setMessageTone] = useState<"status" | "error">("status");
  const [configLoaded, setConfigLoaded] = useState(false);
  const [docsLoaded, setDocsLoaded] = useState(false);
  const [taxRatesLoaded, setTaxRatesLoaded] = useState(false);
  const [taxConfigsLoaded, setTaxConfigsLoaded] = useState(false);
  const [rateDraft, setRateDraft] = useState({
    code: "",
    name: "",
    rate_percent: "",
    inclusive: false,
    effective_from: localDateISO(),
    effective_to: "",
  });
  const [ruleDraft, setRuleDraft] = useState({
    name: "",
    tax_rate_id: "",
    effective_from: localDateISO(),
    effective_to: "",
  });

  async function load() {
    setBusy(true);
    const [c, d, r, tc] = await Promise.allSettled([
      getEfrisConfig(),
      getFiscalDocuments(),
      getTaxRates(),
      getTaxConfigurations(),
    ]);
    const failures: string[] = [];
    if (c.status === "fulfilled") {
      setConfig(c.value);
      setConfigLoaded(true);
    } else {
      setConfig(null);
      setConfigLoaded(false);
      failures.push("EFRIS setup");
    }
    if (d.status === "fulfilled") {
      setDocs(d.value);
      setDocsLoaded(true);
    } else {
      setDocs([]);
      setDocsLoaded(false);
      failures.push("official documents");
    }
    if (r.status === "fulfilled") {
      setTaxRates(r.value);
      setTaxRatesLoaded(true);
    } else {
      setTaxRates([]);
      setTaxRatesLoaded(false);
      failures.push("tax rates");
    }
    if (tc.status === "fulfilled") {
      setTaxConfigs(tc.value);
      setTaxConfigsLoaded(true);
    } else {
      setTaxConfigs([]);
      setTaxConfigsLoaded(false);
      failures.push("tax rules");
    }
    if (failures.length) {
      setMessage(`${failures.join(", ")} could not be loaded. Refresh to try again.`);
      setMessageTone("error");
    } else {
      setMessage("");
      setMessageTone("status");
    }
    setBusy(false);
  }

  useEffect(() => { void load(); }, []);

  async function saveEfris() {
    if (!config || savingEfris) return;
    setSavingEfris(true);
    setMessage("");
    try {
      setConfig(await updateEfrisConfig({
        enabled: config.enabled,
        integration_mode: config.integration_mode,
        tin: config.tin,
        legal_name: config.legal_name,
        effective_date: config.effective_date,
      }));
      setMessage("EFRIS details saved. Registration status still depends on a verified URA workflow.");
      setMessageTone("status");
    } catch (reason) {
      setMessage(errorMessage(reason, "EFRIS details could not be saved."));
      setMessageTone("error");
    } finally {
      setSavingEfris(false);
    }
  }

  async function saveTaxRate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (savingRate) return;
    const percent = Number(rateDraft.rate_percent);
    if (!Number.isFinite(percent) || percent < 0 || percent > 100) {
      setMessage("Enter a tax percentage between 0 and 100.");
      setMessageTone("error");
      return;
    }
    if (rateDraft.effective_to && rateDraft.effective_to < rateDraft.effective_from) {
      setMessage("The tax rate end date cannot be before its start date.");
      setMessageTone("error");
      return;
    }
    setSavingRate(true);
    setMessage("");
    try {
      await createTaxRate({
        code: rateDraft.code.trim(),
        name: rateDraft.name.trim(),
        rate_percent: String(percent),
        inclusive: rateDraft.inclusive,
        effective_from: rateDraft.effective_from,
        effective_to: rateDraft.effective_to || null,
      });
      setRateDraft({ code: "", name: "", rate_percent: "", inclusive: false, effective_from: localDateISO(), effective_to: "" });
      await load();
      setMessage("Tax rate saved. Review it and apply it to a default tax rule only when confirmed for this business.");
      setMessageTone("status");
    } catch (reason) {
      setMessage(errorMessage(reason, "The tax rate was not saved. Review your access and the details, then try again."));
      setMessageTone("error");
    } finally {
      setSavingRate(false);
    }
  }

  async function saveDefaultRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (savingRule) return;
    if (!taxRates.some(rate => rate.id === ruleDraft.tax_rate_id)) {
      setMessage("Choose one of the saved tax rates before creating a rule.");
      setMessageTone("error");
      return;
    }
    if (ruleDraft.effective_to && ruleDraft.effective_to < ruleDraft.effective_from) {
      setMessage("The tax rule end date cannot be before its start date.");
      setMessageTone("error");
      return;
    }
    setSavingRule(true);
    setMessage("");
    try {
      await createTaxConfiguration({
        name: ruleDraft.name.trim(),
        tax_rate_id: ruleDraft.tax_rate_id,
        scope_type: "DEFAULT",
        scope_id: null,
        effective_from: ruleDraft.effective_from,
        effective_to: ruleDraft.effective_to || null,
      });
      setRuleDraft({ name: "", tax_rate_id: "", effective_from: localDateISO(), effective_to: "" });
      await load();
      setMessage("Default tax rule saved. Check its effective dates and priority before using it in a live sale.");
      setMessageTone("status");
    } catch (reason) {
      setMessage(errorMessage(reason, "The default tax rule was not saved. Check your permission and the selected tax rate."));
      setMessageTone("error");
    } finally {
      setSavingRule(false);
    }
  }

  return (
    <AppShell title="Tax and official receipts" eyebrow="Tax records and EFRIS">
      <main className="workspace" style={{ maxWidth: 1500 }}>
        <div className="workspace-header">
          <div>
            <span className="workspace-breadcrumb">LEXA · COMPLIANCE</span>
            <h1>Tax and official receipts</h1>
            <p>Manage business tax rules separately from payment records. LEXA marks an e-document accepted only after a genuine URA response.</p>
          </div>
          <div className="header-actions">
            <Link className="button button-soft" href="/">Back</Link>
            <button type="button" className="button button-soft" onClick={() => void load()} disabled={busy}>Refresh</button>
          </div>
        </div>
        {message && <div className="inline-message" role={messageTone === "error" ? "alert" : "status"} aria-live={messageTone === "error" ? "assertive" : "polite"}>{message}</div>}

        <section className="workspace-section">
          <div className="section-head">
            <div>
              <span className="section-label">EFRIS SETUP</span>
              <h2>Official receipt setup</h2>
              <p>Connection status remains pending until a real URA-approved connector is configured and verified.</p>
            </div>
          </div>
          {configLoaded && config ? (
            <div className="command-form">
              <label htmlFor="efris-enabled">Use EFRIS for this business
                <select id="efris-enabled" value={config.enabled ? "true" : "false"} onChange={event => setConfig({ ...config, enabled: event.target.value === "true" })}>
                  <option value="false">Disabled</option><option value="true">Enabled</option>
                </select>
              </label>
              <label htmlFor="efris-mode">How EFRIS will be used
                <select id="efris-mode" value={config.integration_mode} onChange={event => setConfig({ ...config, integration_mode: event.target.value })}>
                  <option value="MANUAL">Record details manually</option>
                  <option value="PENDING_INTEGRATION">Not connected yet</option>
                  <option value="SYSTEM_TO_SYSTEM">System-to-system (requires an approved, verified connector)</option>
                </select>
              </label>
              <label htmlFor="efris-registration-status">URA registration status
                <input id="efris-registration-status" value={fiscalStatusLabel(config.registration_status)} readOnly aria-readonly="true" />
                <small>This status is set by a verified integration process, not by a manual selection.</small>
              </label>
              <label htmlFor="efris-tin">Tax Identification Number (TIN)
                <input id="efris-tin" value={config.tin || ""} maxLength={80} onChange={event => setConfig({ ...config, tin: event.target.value || null })} />
              </label>
              <label htmlFor="efris-legal-name">Legal name
                <input id="efris-legal-name" value={config.legal_name || ""} maxLength={250} onChange={event => setConfig({ ...config, legal_name: event.target.value || null })} />
              </label>
              <button type="button" className="primary" onClick={() => void saveEfris()} disabled={busy || savingEfris || !config}>{savingEfris ? "Saving…" : "Save EFRIS details"}</button>
            </div>
          ) : !busy ? <p role="status">EFRIS configuration is unavailable or could not be loaded. Refresh to try again.</p> : <p role="status">Loading EFRIS configuration…</p>}
        </section>

        <section className="workspace-section">
          <div className="section-head">
            <div>
              <span className="section-label">TAX SETUP</span>
              <h2>{taxRatesLoaded && taxConfigsLoaded ? `${taxRates.length} rates · ${taxConfigs.length} tax rules` : "Tax setup status unavailable"}</h2>
              <p>Only save values confirmed for this business. This form does not determine what tax rate your business is legally required to use.</p>
            </div>
          </div>

          <div className="table-wrap">
            <table>
              <thead><tr><th>Tax code</th><th>Tax name</th><th>Rate</th><th>Included in price</th><th>Applies from</th><th>Status</th></tr></thead>
              <tbody>
                {taxRates.map(rate => <tr key={rate.id}><td>{rate.code}</td><td>{rate.name}</td><td>{rate.rate_percent}%</td><td>{rate.inclusive ? "Yes" : "No"}</td><td>{rate.effective_from}{rate.effective_to ? ` → ${rate.effective_to}` : " onward"}</td><td>{fiscalStatusLabel(rate.status)}</td></tr>)}
                {!busy && taxRatesLoaded && taxRates.length === 0 && <tr><td colSpan={6}>No tax rates are saved yet. Add only a rate verified for your business.</td></tr>}
                {!busy && !taxRatesLoaded && <tr><td colSpan={6}>Tax rates could not be loaded. Refresh this page to try again.</td></tr>}
              </tbody>
            </table>
          </div>

          <div className="foundation-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))", marginTop: 18 }}>
            <form className="command-form" onSubmit={saveTaxRate}>
              <div><h3>Add a tax rate</h3><p>Create a rate record first. Use the exact code, percentage, inclusivity and dates confirmed for this business.</p></div>
              <label htmlFor="tax-rate-code">Tax code<input id="tax-rate-code" value={rateDraft.code} onChange={event => setRateDraft({ ...rateDraft, code: event.target.value })} maxLength={50} required /></label>
              <label htmlFor="tax-rate-name">Tax rate name<input id="tax-rate-name" value={rateDraft.name} onChange={event => setRateDraft({ ...rateDraft, name: event.target.value })} maxLength={160} required /></label>
              <label htmlFor="tax-rate-percent">Rate (%)<input id="tax-rate-percent" type="number" min="0" max="100" step="0.01" value={rateDraft.rate_percent} onChange={event => setRateDraft({ ...rateDraft, rate_percent: event.target.value })} required /></label>
              <label htmlFor="tax-rate-inclusive">Price treatment
                <select id="tax-rate-inclusive" value={rateDraft.inclusive ? "inclusive" : "exclusive"} onChange={event => setRateDraft({ ...rateDraft, inclusive: event.target.value === "inclusive" })}>
                  <option value="exclusive">Tax added to price (exclusive)</option><option value="inclusive">Tax already included in price (inclusive)</option>
                </select>
              </label>
              <div className="form-grid">
                <label htmlFor="tax-rate-from">Effective from<input id="tax-rate-from" type="date" value={rateDraft.effective_from} onChange={event => setRateDraft({ ...rateDraft, effective_from: event.target.value })} required /></label>
                <label htmlFor="tax-rate-to">Effective to (optional)<input id="tax-rate-to" type="date" min={rateDraft.effective_from || undefined} value={rateDraft.effective_to} onChange={event => setRateDraft({ ...rateDraft, effective_to: event.target.value })} /></label>
              </div>
              <button type="submit" className="button button-dark" disabled={busy || savingRate}>{savingRate ? "Saving tax rate…" : "Save tax rate"}</button>
            </form>

            <form className="command-form" onSubmit={saveDefaultRule}>
              <div><h3>Configure a default tax rule</h3><p>Link a saved rate to the default scope. Product- or category-specific rules need a separate scope choice and are not created by this form.</p></div>
              <label htmlFor="tax-rule-name">Rule name<input id="tax-rule-name" value={ruleDraft.name} onChange={event => setRuleDraft({ ...ruleDraft, name: event.target.value })} maxLength={160} required /></label>
              <label htmlFor="tax-rule-rate">Saved tax rate
                <select id="tax-rule-rate" value={ruleDraft.tax_rate_id} onChange={event => setRuleDraft({ ...ruleDraft, tax_rate_id: event.target.value })} required>
                  <option value="">Choose a saved rate</option>
                  {taxRates.map(rate => <option key={rate.id} value={rate.id}>{rate.code} · {rate.name} · {rate.rate_percent}% ({fiscalStatusLabel(rate.status)})</option>)}
                </select>
              </label>
              <div className="form-grid">
                <label htmlFor="tax-rule-from">Effective from<input id="tax-rule-from" type="date" value={ruleDraft.effective_from} onChange={event => setRuleDraft({ ...ruleDraft, effective_from: event.target.value })} required /></label>
                <label htmlFor="tax-rule-to">Effective to (optional)<input id="tax-rule-to" type="date" min={ruleDraft.effective_from || undefined} value={ruleDraft.effective_to} onChange={event => setRuleDraft({ ...ruleDraft, effective_to: event.target.value })} /></label>
              </div>
              <button type="submit" className="button button-dark" disabled={busy || savingRule || taxRates.length === 0}>{savingRule ? "Saving tax rule…" : "Save default tax rule"}</button>
              {taxRates.length === 0 && <small>Add a tax rate before creating a default rule.</small>}
            </form>
          </div>

          <div className="table-wrap" style={{ marginTop: 20 }}>
            <table>
              <thead><tr><th>Rule name</th><th>Scope</th><th>Tax code</th><th>Rate</th><th>Inclusive</th><th>Effective period</th><th>Status</th></tr></thead>
              <tbody>
                {taxConfigs.map(rule => <tr key={rule.id}><td>{rule.name}</td><td>{rule.scope_type.replaceAll("_", " ")}</td><td>{rule.tax_code}</td><td>{rule.rate_percent}%</td><td>{rule.inclusive ? "Yes" : "No"}</td><td>{rule.effective_from}{rule.effective_to ? ` → ${rule.effective_to}` : " onward"}</td><td>{fiscalStatusLabel(rule.status)}</td></tr>)}
                {!busy && taxConfigsLoaded && taxConfigs.length === 0 && <tr><td colSpan={7}>No tax rules are saved yet. Add a default rule only after confirming which saved rate should apply by default.</td></tr>}
                {!busy && !taxConfigsLoaded && <tr><td colSpan={7}>Tax rules could not be loaded. Refresh this page to try again.</td></tr>}
              </tbody>
            </table>
          </div>
          <p style={{ color: "#77849a", fontSize: 11, marginTop: 12 }}>Tax rules have effective dates. Past sales keep the tax amount recorded when each sale was completed. Check rule overlap and priority with your administrator before relying on a live checkout.</p>
        </section>

        <section className="workspace-section">
          <div className="section-head"><div><span className="section-label">FISCAL DOCUMENTS</span><h2>{docsLoaded ? `${docs.length} official documents` : "Official documents unavailable"}</h2></div></div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Date</th><th>Document</th><th>Status</th><th>Official receipt number</th><th>Verification code</th></tr></thead>
              <tbody>
                {docs.map(document => <tr key={document.id}><td>{document.issue_date}</td><td>{fiscalDocumentLabel(document.document_type)}</td><td>{fiscalStatusLabel(document.status)}</td><td>{document.fdn || "Not issued"}</td><td>{document.verification_code || "Not issued"}</td></tr>)}
                {!busy && docsLoaded && docs.length === 0 && <tr><td colSpan={5}>No official fiscal documents have been recorded yet. A LEXA payment receipt is not the same as an accepted EFRIS document.</td></tr>}
                {!busy && !docsLoaded && <tr><td colSpan={5}>Official document history could not be loaded. Refresh this page to try again.</td></tr>}
              </tbody>
            </table>
          </div>
          <p style={{ color: "#77849a", fontSize: 11, marginTop: 12 }}>LEXA only shows official receipt numbers and verification details returned by URA. It never makes them up.</p>
        </section>
      </main>
    </AppShell>
  );
}
