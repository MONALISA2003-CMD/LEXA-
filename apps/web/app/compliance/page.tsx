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

const statusLabel = (value: string) => ({
  NOT_REGISTERED: "Not registered",
  PENDING: "Awaiting URA confirmation",
  ACTIVE: "Active",
  SUSPENDED: "Suspended",
  DRAFT: "Draft",
  SUBMITTED: "Submitted to URA",
  ACCEPTED: "Accepted by URA",
  REJECTED: "Rejected by URA",
  FAILED: "Requires attention",
  CANCELLED: "Cancelled",
}[value] || value.replaceAll("_", " ").toLowerCase());

const documentLabel = (value: string) => ({
  INVOICE: "E-invoice",
  CREDIT_NOTE: "E-credit note",
  RECEIPT: "E-receipt",
  DEBIT_NOTE: "E-debit note",
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
  const [savingUraPreset, setSavingUraPreset] = useState("");
  const [message, setMessage] = useState("");
  const [messageTone, setMessageTone] = useState<"status" | "error">("status");
  const [configLoaded, setConfigLoaded] = useState(false);
  const [docsLoaded, setDocsLoaded] = useState(false);
  const [ratesLoaded, setRatesLoaded] = useState(false);
  const [rulesLoaded, setRulesLoaded] = useState(false);
  const [rateDraft, setRateDraft] = useState({
    code: "", name: "", rate_percent: "", inclusive: false,
    effective_from: localDateISO(), effective_to: "",
  });
  const [ruleDraft, setRuleDraft] = useState({
    name: "", tax_rate_id: "", effective_from: localDateISO(), effective_to: "",
  });

  async function load() {
    setBusy(true);
    const [c, d, r, tc] = await Promise.allSettled([
      getEfrisConfig(), getFiscalDocuments(), getTaxRates(), getTaxConfigurations(),
    ]);
    const failures: string[] = [];
    if (c.status === "fulfilled") { setConfig(c.value); setConfigLoaded(true); }
    else { setConfig(null); setConfigLoaded(false); failures.push("EFRIS settings"); }
    if (d.status === "fulfilled") { setDocs(d.value); setDocsLoaded(true); }
    else { setDocs([]); setDocsLoaded(false); failures.push("fiscal documents"); }
    if (r.status === "fulfilled") { setTaxRates(r.value); setRatesLoaded(true); }
    else { setTaxRates([]); setRatesLoaded(false); failures.push("tax rates"); }
    if (tc.status === "fulfilled") { setTaxConfigs(tc.value); setRulesLoaded(true); }
    else { setTaxConfigs([]); setRulesLoaded(false); failures.push("tax rules"); }
    if (failures.length) {
      setMessage(`${failures.join(", ")} could not be loaded. Refresh to retry.`);
      setMessageTone("error");
    } else { setMessage(""); setMessageTone("status"); }
    setBusy(false);
  }

  useEffect(() => { void load(); }, []);

  async function saveEfris() {
    if (!config || savingEfris) return;
    if (config.integration_mode === "SYSTEM_TO_SYSTEM" && (!config.tin?.trim() || !config.legal_name?.trim())) {
      setMessage("Enter the registered TIN and legal business name before saving system-to-system setup.");
      setMessageTone("error");
      return;
    }
    setSavingEfris(true); setMessage("");
    try {
      const saved = await updateEfrisConfig({
        enabled: config.enabled,
        integration_mode: config.integration_mode,
        tin: config.tin?.trim() || null,
        legal_name: config.legal_name?.trim() || null,
        effective_date: config.effective_date || null,
      });
      setConfig(saved);
      setMessage("EFRIS business details saved. Live fiscalisation remains pending until a genuine URA-approved connection confirms registration.");
      setMessageTone("status");
    } catch (reason) {
      setMessage(errorMessage(reason, "EFRIS details could not be saved.")); setMessageTone("error");
    } finally { setSavingEfris(false); }
  }

  async function addUraReferenceRate(kind: "standard" | "zero") {
    if (savingUraPreset) return;
    const preset = kind === "standard"
      ? { code: "UG_VAT_STANDARD_18", name: "Uganda VAT — standard-rated supply (verify eligibility)", rate_percent: "18" }
      : { code: "UG_VAT_ZERO_RATED_0", name: "Uganda VAT — zero-rated supply (verify eligibility)", rate_percent: "0" };
    if (taxRates.some(rate => rate.code.toUpperCase() === preset.code)) {
      setMessage(`${preset.code} already exists. Check its effective dates and status in the tax-rate table.`);
      setMessageTone("status");
      return;
    }
    setSavingUraPreset(kind); setMessage("");
    try {
      await createTaxRate({ ...preset, inclusive: false, effective_from: localDateISO(), effective_to: null });
      await load();
      setMessage(`${preset.rate_percent}% URA reference rate added. It has not been assigned as a default rule; apply it only to supplies confirmed as eligible for that treatment.`);
      setMessageTone("status");
    } catch (reason) {
      setMessage(errorMessage(reason, "The URA reference rate could not be added. Check permissions and existing tax codes."));
      setMessageTone("error");
    } finally { setSavingUraPreset(""); }
  }

  async function saveTaxRate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (savingRate) return;
    const percent = Number(rateDraft.rate_percent);
    if (!Number.isFinite(percent) || percent < 0 || percent > 100) {
      setMessage("Enter a percentage from 0 to 100."); setMessageTone("error"); return;
    }
    if (rateDraft.effective_to && rateDraft.effective_to < rateDraft.effective_from) {
      setMessage("Tax rate end date cannot be before its start date."); setMessageTone("error"); return;
    }
    setSavingRate(true); setMessage("");
    try {
      await createTaxRate({
        code: rateDraft.code.trim(), name: rateDraft.name.trim(), rate_percent: String(percent),
        inclusive: rateDraft.inclusive, effective_from: rateDraft.effective_from,
        effective_to: rateDraft.effective_to || null,
      });
      setRateDraft({ code: "", name: "", rate_percent: "", inclusive: false, effective_from: localDateISO(), effective_to: "" });
      await load(); setMessage("Tax rate saved. Confirm its legal applicability and effective dates before assigning it to sales."); setMessageTone("status");
    } catch (reason) {
      setMessage(errorMessage(reason, "The tax rate was not saved. Check the code, access and dates.")); setMessageTone("error");
    } finally { setSavingRate(false); }
  }

  async function saveDefaultRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (savingRule) return;
    if (!taxRates.some(rate => rate.id === ruleDraft.tax_rate_id)) {
      setMessage("Choose a saved tax rate first."); setMessageTone("error"); return;
    }
    if (ruleDraft.effective_to && ruleDraft.effective_to < ruleDraft.effective_from) {
      setMessage("Tax rule end date cannot be before its start date."); setMessageTone("error"); return;
    }
    setSavingRule(true); setMessage("");
    try {
      await createTaxConfiguration({
        name: ruleDraft.name.trim(), tax_rate_id: ruleDraft.tax_rate_id,
        scope_type: "DEFAULT", scope_id: null, effective_from: ruleDraft.effective_from,
        effective_to: ruleDraft.effective_to || null,
      });
      setRuleDraft({ name: "", tax_rate_id: "", effective_from: localDateISO(), effective_to: "" });
      await load(); setMessage("Default rule saved. Confirm it is suitable for every product covered by the default scope before checkout."); setMessageTone("status");
    } catch (reason) {
      setMessage(errorMessage(reason, "The default tax rule could not be saved.")); setMessageTone("error");
    } finally { setSavingRule(false); }
  }

  return (
    <AppShell title="URA, tax and official receipts" eyebrow="Compliance and fiscal documents">
      <main className="workspace" style={{ maxWidth: 1500 }}>
        <div className="workspace-header">
          <div>
            <span className="workspace-breadcrumb">LEXA · UGANDA COMPLIANCE</span>
            <h1>URA, tax and official receipts</h1>
            <p>Maintain the taxpayer details, tax treatment and fiscal document records your business actually uses.</p>
          </div>
          <div className="header-actions">
            <Link className="button button-soft" href="/">Back</Link>
            <button type="button" className="button button-soft" onClick={() => void load()} disabled={busy}>Refresh</button>
          </div>
        </div>
        {message && <div className="inline-message" role={messageTone === "error" ? "alert" : "status"} aria-live={messageTone === "error" ? "assertive" : "polite"}>{message}</div>}

        <section className="workspace-section">
          <div className="section-head"><div>
            <span className="section-label">URA / EFRIS CONNECTION</span>
            <h2>Official receipt configuration</h2>
            <p>Configure the taxpayer identity and intended connection method. Only a real URA-approved connector can confirm registration or issue a verified URA fiscal document.</p>
          </div></div>
          {configLoaded && config ? <>
            <div className="command-form">
              <label htmlFor="efris-enabled">EFRIS for this business
                <select id="efris-enabled" value={config.enabled ? "true" : "false"} onChange={event => setConfig({ ...config, enabled: event.target.value === "true" })}>
                  <option value="false">Not enabled in LEXA</option><option value="true">Enabled / preparing setup</option>
                </select>
              </label>
              <label htmlFor="efris-mode">Issuing method
                <select id="efris-mode" value={config.integration_mode} onChange={event => setConfig({ ...config, integration_mode: event.target.value })}>
                  <option value="MANUAL">Manual reference only</option>
                  <option value="PENDING_INTEGRATION">Awaiting connector setup</option>
                  <option value="SYSTEM_TO_SYSTEM">System-to-system integration</option>
                </select>
              </label>
              <label htmlFor="efris-status">URA registration status
                <input id="efris-status" value={statusLabel(config.registration_status)} readOnly aria-readonly="true" />
                <small>Controlled by verified integration; it cannot be activated from this form.</small>
              </label>
              <label htmlFor="efris-tin">URA Tax Identification Number (TIN)
                <input id="efris-tin" value={config.tin || ""} maxLength={80} autoComplete="off" onChange={event => setConfig({ ...config, tin: event.target.value || null })} placeholder="Enter the registered business TIN" />
              </label>
              <label htmlFor="efris-legal-name">Registered legal business name
                <input id="efris-legal-name" value={config.legal_name || ""} maxLength={250} onChange={event => setConfig({ ...config, legal_name: event.target.value || null })} placeholder="As registered with URA" />
              </label>
              <label htmlFor="efris-effective-date">EFRIS registration effective date
                <input id="efris-effective-date" type="date" value={config.effective_date || ""} onChange={event => setConfig({ ...config, effective_date: event.target.value || null })} />
                <small>Use the date approved or confirmed for your business, not an assumed date.</small>
              </label>
              <button type="button" className="primary" onClick={() => void saveEfris()} disabled={busy || savingEfris}>{savingEfris ? "Saving…" : "Save URA / EFRIS details"}</button>
            </div>
            <div style={{ marginTop: 16 }}>
              <p><strong>URA registration:</strong> sign in through the official URA portal, open EFRIS and complete the first-time registration or required integration process. System-to-system access requires URA’s integration process and approved connection credentials; selecting the option above does not establish that connection.</p>
              <p><a href="https://ura.go.ug/en/efris/efris-registration/" target="_blank" rel="noreferrer">Open official URA EFRIS registration guidance</a> · <a href="https://ura.go.ug/en/efris/" target="_blank" rel="noreferrer">EFRIS overview and taxpayer guidance</a></p>
            </div>
          </> : !busy ? <p role="status">EFRIS settings are unavailable. Refresh the page or contact your administrator.</p> : <p role="status">Loading URA configuration…</p>}
        </section>

        <section className="workspace-section">
          <div className="section-head"><div>
            <span className="section-label">URA TAX REFERENCE</span>
            <h2>{ratesLoaded && rulesLoaded ? `${taxRates.length} tax rates · ${taxConfigs.length} active and historical rules` : "Tax configuration"}</h2>
            <p>URA currently describes standard-rated supplies at 18% and eligible zero-rated supplies at 0%. Exempt supplies are a separate legal category; do not classify every supply by rate alone.</p>
          </div></div>
          <div className="header-actions" style={{ marginBottom: 16 }}>
            <button type="button" className="button button-soft" onClick={() => void addUraReferenceRate("standard")} disabled={busy || Boolean(savingUraPreset)}>{savingUraPreset === "standard" ? "Adding…" : "Add 18% standard-rate reference"}</button>
            <button type="button" className="button button-soft" onClick={() => void addUraReferenceRate("zero")} disabled={busy || Boolean(savingUraPreset)}>{savingUraPreset === "zero" ? "Adding…" : "Add 0% zero-rate reference"}</button>
          </div>
          <p style={{ color: "#77849a", fontSize: 12 }}>These actions save reusable tax-rate records only. They do not create a default tax rule or automatically apply a rate to products. Confirm eligibility with your tax adviser or URA before applying a treatment.</p>
          <div className="table-wrap">
            <table><thead><tr><th>Tax code</th><th>Tax treatment</th><th>Rate</th><th>Price includes tax</th><th>Effective period</th><th>Status</th></tr></thead>
              <tbody>{taxRates.map(rate => <tr key={rate.id}><td>{rate.code}</td><td>{rate.name}</td><td>{rate.rate_percent}%</td><td>{rate.inclusive ? "Yes" : "No"}</td><td>{rate.effective_from}{rate.effective_to ? ` → ${rate.effective_to}` : " onward"}</td><td>{statusLabel(rate.status)}</td></tr>)}
                {!busy && ratesLoaded && taxRates.length === 0 && <tr><td colSpan={6}>No tax rates are saved yet. Add an official reference or create a rate confirmed for your business.</td></tr>}
                {!busy && !ratesLoaded && <tr><td colSpan={6}>Tax rates could not be loaded. Refresh to retry.</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="foundation-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))", marginTop: 18 }}>
            <form className="command-form" onSubmit={saveTaxRate}>
              <div><h3>Add a tax rate</h3><p>Creating a tax rate does not determine what tax rate your business is legally required to use. Confirm its applicability and treatment with URA or your tax adviser before use.</p></div>
              <label htmlFor="tax-code">Tax code<input id="tax-code" value={rateDraft.code} onChange={event => setRateDraft({ ...rateDraft, code: event.target.value })} maxLength={50} required /></label>
              <label htmlFor="tax-name">Rate name<input id="tax-name" value={rateDraft.name} onChange={event => setRateDraft({ ...rateDraft, name: event.target.value })} maxLength={160} required /></label>
              <label htmlFor="tax-percent">Rate (%)<input id="tax-percent" type="number" min="0" max="100" step="0.01" value={rateDraft.rate_percent} onChange={event => setRateDraft({ ...rateDraft, rate_percent: event.target.value })} required /></label>
              <label htmlFor="tax-inclusive">Price treatment<select id="tax-inclusive" value={rateDraft.inclusive ? "inclusive" : "exclusive"} onChange={event => setRateDraft({ ...rateDraft, inclusive: event.target.value === "inclusive" })}><option value="exclusive">Tax added to price</option><option value="inclusive">Tax included in price</option></select></label>
              <div className="form-grid">
                <label htmlFor="tax-from">Effective from<input id="tax-from" type="date" value={rateDraft.effective_from} onChange={event => setRateDraft({ ...rateDraft, effective_from: event.target.value })} required /></label>
                <label htmlFor="tax-to">Effective to (optional)<input id="tax-to" type="date" min={rateDraft.effective_from || undefined} value={rateDraft.effective_to} onChange={event => setRateDraft({ ...rateDraft, effective_to: event.target.value })} /></label>
              </div>
              <button type="submit" className="button button-dark" disabled={busy || savingRate}>{savingRate ? "Saving rate…" : "Save tax rate"}</button>
            </form>
            <form className="command-form" onSubmit={saveDefaultRule}>
              <div><h3>Configure a default tax rule</h3><p>A default affects the products covered by the default scope. Do not use it where products need different tax treatments.</p></div>
              <label htmlFor="rule-name">Rule name<input id="rule-name" value={ruleDraft.name} onChange={event => setRuleDraft({ ...ruleDraft, name: event.target.value })} maxLength={160} required /></label>
              <label htmlFor="rule-rate">Saved tax rate<select id="rule-rate" value={ruleDraft.tax_rate_id} onChange={event => setRuleDraft({ ...ruleDraft, tax_rate_id: event.target.value })} required><option value="">Choose a saved rate</option>{taxRates.map(rate => <option key={rate.id} value={rate.id}>{rate.code} · {rate.name} · {rate.rate_percent}%</option>)}</select></label>
              <div className="form-grid">
                <label htmlFor="rule-from">Effective from<input id="rule-from" type="date" value={ruleDraft.effective_from} onChange={event => setRuleDraft({ ...ruleDraft, effective_from: event.target.value })} required /></label>
                <label htmlFor="rule-to">Effective to (optional)<input id="rule-to" type="date" min={ruleDraft.effective_from || undefined} value={ruleDraft.effective_to} onChange={event => setRuleDraft({ ...ruleDraft, effective_to: event.target.value })} /></label>
              </div>
              <button type="submit" className="button button-dark" disabled={busy || savingRule || !taxRates.length}>{savingRule ? "Saving rule…" : "Save default tax rule"}</button>
              <small>Confirm the intended scope, product eligibility and effective dates before checkout.</small>
            </form>
          </div>
          <div className="table-wrap" style={{ marginTop: 20 }}>
            <table><thead><tr><th>Rule</th><th>Scope</th><th>Tax code</th><th>Rate</th><th>Inclusive</th><th>Effective period</th><th>Status</th></tr></thead>
              <tbody>{taxConfigs.map(rule => <tr key={rule.id}><td>{rule.name}</td><td>{rule.scope_type.replaceAll("_", " ")}</td><td>{rule.tax_code}</td><td>{rule.rate_percent}%</td><td>{rule.inclusive ? "Yes" : "No"}</td><td>{rule.effective_from}{rule.effective_to ? ` → ${rule.effective_to}` : " onward"}</td><td>{statusLabel(rule.status)}</td></tr>)}
                {!busy && rulesLoaded && taxConfigs.length === 0 && <tr><td colSpan={7}>No tax rules configured yet.</td></tr>}
                {!busy && !rulesLoaded && <tr><td colSpan={7}>Tax rules could not be loaded. Refresh to retry.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>

        <section className="workspace-section">
          <div className="section-head"><div><span className="section-label">OFFICIAL FISCAL RECORDS</span><h2>{docsLoaded ? `${docs.length} fiscal documents` : "Fiscal document status unavailable"}</h2><p>Only a verified URA response can supply an official fiscal document number (FDN), verification code or QR reference.</p></div></div>
          <div className="table-wrap"><table><thead><tr><th>Issue date</th><th>Document</th><th>Status</th><th>URA document number</th><th>Verification code</th></tr></thead>
            <tbody>{docs.map(doc => <tr key={doc.id}><td>{doc.issue_date}</td><td>{documentLabel(doc.document_type)}</td><td>{statusLabel(doc.status)}</td><td>{doc.fdn || "Not issued"}</td><td>{doc.verification_code || "Not issued"}</td></tr>)}
              {!busy && docsLoaded && docs.length === 0 && <tr><td colSpan={5}>No official fiscal documents have been recorded yet. A verified URA fiscal document has not been returned; a LEXA payment receipt is not automatically an EFRIS receipt.</td></tr>}
              {!busy && !docsLoaded && <tr><td colSpan={5}>Fiscal documents could not be loaded. Refresh to retry.</td></tr>}
            </tbody>
          </table></div>
          <p style={{ color: "#77849a", fontSize: 12, marginTop: 12 }}>Do not print or describe a LEXA payment slip as an official EFRIS receipt until the document is accepted and its URA-issued identifiers are available.</p>
        </section>
      </main>
    </AppShell>
  );
}
