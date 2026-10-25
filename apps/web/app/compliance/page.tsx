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
  PENDING: "Pending manual review (not submitted by LEXA)",
  ACTIVE: "Active",
  SUSPENDED: "Suspended",
  DRAFT: "Draft",
  SUBMITTED: "Previously marked submitted — not verified by LEXA",
  ACCEPTED: "Previously marked accepted — verify directly with URA",
  REJECTED: "Previously marked rejected — verify directly with URA",
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

const TAX_RULE_EFFECTIVE_DATE = "2026-07-01";
type TaxEstimateType = "VAT" | "PRESUMPTIVE" | "PAYE" | "WHT_SUPPLY" | "WHT_PROFESSIONAL";
type TaxEstimateResult = {
  tax_type?: string; eligible?: boolean; is_estimate?: boolean; currency_code?: string;
  tax_amount?: string | null; total_amount?: string | null; taxable_base?: string | null;
  annual_turnover?: string; monthly_chargeable_income?: string; band?: string;
  rate_percent?: string; formula?: string; note?: string; reasons?: string[];
  no_external_submission?: boolean; reference_date?: string;
};

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
  const [standardVatConfirmed, setStandardVatConfirmed] = useState(false);
  const [standardVatPriceInclusive, setStandardVatPriceInclusive] = useState(false);
  const [taxEstimateType, setTaxEstimateType] = useState<TaxEstimateType>("VAT");
  const [taxEstimateAmount, setTaxEstimateAmount] = useState("");
  const [taxPriceInclusive, setTaxPriceInclusive] = useState(false);
  const [recordsKept, setRecordsKept] = useState(true);
  const [residentTaxpayer, setResidentTaxpayer] = useState(true);
  const [businessSector, setBusinessSector] = useState("GENERAL");
  const [withholdingAgent, setWithholdingAgent] = useState(false);
  const [payeeResidency, setPayeeResidency] = useState<"RESIDENT" | "NON_RESIDENT">("RESIDENT");
  const [employeeResidency, setEmployeeResidency] = useState<"RESIDENT" | "NON_RESIDENT">("RESIDENT");
  const [taxEstimateBusy, setTaxEstimateBusy] = useState(false);
  const [taxEstimateResult, setTaxEstimateResult] = useState<TaxEstimateResult | null>(null);
  const [taxEstimateError, setTaxEstimateError] = useState("");
  const [manualDocType, setManualDocType] = useState<"INVOICE" | "RECEIPT" | "CREDIT_NOTE" | "DEBIT_NOTE">("INVOICE");
  const [manualFdn, setManualFdn] = useState("");
  const [manualDocumentNumber, setManualDocumentNumber] = useState("");
  const [manualVerificationCode, setManualVerificationCode] = useState("");
  const [manualQrCode, setManualQrCode] = useState("");
  const [manualIssueDate, setManualIssueDate] = useState(localDateISO());
  const [manualCurrency, setManualCurrency] = useState("UGX");
  const [manualSaleId, setManualSaleId] = useState("");
  const [savingManualDoc, setSavingManualDoc] = useState(false);
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
    if (c.status === "fulfilled") { setConfig({ ...c.value, integration_mode: "MANUAL" }); setConfigLoaded(true); }
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
    setSavingEfris(true); setMessage("");
    try {
      const saved = await updateEfrisConfig({
        enabled: config.enabled,
        integration_mode: "MANUAL",
        tin: config.tin?.trim() || null,
        legal_name: config.legal_name?.trim() || null,
        effective_date: config.effective_date || null,
      });
      setConfig({ ...saved, integration_mode: "MANUAL" });
      setMessage("Manual EFRIS tracking details saved. LEXA does not connect to URA, submit documents, or verify FDNs; enter official details only after obtaining them from URA.");
      setMessageTone("status");
    } catch (reason) {
      setMessage(errorMessage(reason, "EFRIS details could not be saved.")); setMessageTone("error");
    } finally { setSavingEfris(false); }
  }

  async function addUraReferenceRate(kind: "standard" | "zero") {
    if (savingUraPreset) return;
    if (kind === "standard" && !standardVatConfirmed) {
      setMessage("Confirm that this business is registered or otherwise required to charge standard-rated VAT before activating the default 18% rule.");
      setMessageTone("error");
      return;
    }
    const preset = kind === "standard"
      ? { code: "UG_VAT_STANDARD_18_FY2026_27", name: "Uganda VAT — standard-rated supply, FY 2026/27", rate_percent: "18" }
      : { code: "UG_VAT_ZERO_RATED_0_FY2026_27", name: "Uganda VAT — zero-rated supply, FY 2026/27", rate_percent: "0" };
    let rate = taxRates.find(item => item.code.toUpperCase() === preset.code);
    setSavingUraPreset(kind); setMessage("");
    try {
      if (!rate) {
        rate = await createTaxRate({ ...preset, inclusive: kind === "standard" ? standardVatPriceInclusive : false, effective_from: TAX_RULE_EFFECTIVE_DATE, effective_to: null });
      }
      const desiredInclusive = kind === "standard" ? standardVatPriceInclusive : false;
      const dateIsCovered = rate.status === "ACTIVE"
        && Number(rate.rate_percent) === Number(preset.rate_percent)
        && Boolean(rate.inclusive) === desiredInclusive
        && rate.effective_from <= TAX_RULE_EFFECTIVE_DATE
        && (!rate.effective_to || rate.effective_to >= TAX_RULE_EFFECTIVE_DATE);
      if (!dateIsCovered) {
        setMessage(`${preset.code} already exists but its status, rate, price treatment, or dates do not match your selection. Review the saved rate before using it.`);
        setMessageTone("error");
        await load();
        return;
      }
      if (kind === "standard") {
        const existingDefault = taxConfigs.find(rule => rule.scope_type === "DEFAULT"
          && rule.status === "ACTIVE"
          && rule.effective_from <= TAX_RULE_EFFECTIVE_DATE
          && (!rule.effective_to || rule.effective_to >= TAX_RULE_EFFECTIVE_DATE));
        if (existingDefault && existingDefault.tax_rate_id !== rate!.id) {
          setMessage("An active default tax rule already covers 1 July 2026. LEXA did not add a second overlapping default; review the existing rule first.");
          setMessageTone("error");
          await load();
          return;
        }
        if (!existingDefault) {
          await createTaxConfiguration({
            name: "Owner-confirmed Uganda standard VAT — effective 1 July 2026",
            tax_rate_id: rate.id, scope_type: "DEFAULT", scope_id: null,
            effective_from: TAX_RULE_EFFECTIVE_DATE, effective_to: null,
          });
        }
        await load();
        setMessage("The 18% default rule is saved from 1 July 2026. Checkout will calculate tax from this dated rule. Add product/category overrides for zero-rated or exempt supplies; those are not interchangeable. LEXA did not send anything to URA.");
      } else {
        await load();
        setMessage("The 0% reference rate is saved from 1 July 2026 but has not been applied to any product. Use only for supplies confirmed as zero-rated; exempt supplies need separate treatment.");
      }
      setMessageTone("status");
    } catch (reason) {
      setMessage(errorMessage(reason, "The URA reference rate or rule could not be saved. Check permissions and existing tax codes."));
      setMessageTone("error");
    } finally { setSavingUraPreset(""); }
  }

  async function submitTaxEstimate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (taxEstimateBusy) return;
    const amount = Number(taxEstimateAmount);
    if (!Number.isFinite(amount) || amount < 0) {
      setTaxEstimateError("Enter a valid non-negative amount."); setTaxEstimateResult(null); return;
    }
    setTaxEstimateBusy(true); setTaxEstimateError(""); setTaxEstimateResult(null);
    try {
      const response = await fetch("/api/lexa/api/v1/compliance/tax-estimate", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-Request-ID": crypto.randomUUID() },
        body: JSON.stringify({
          tax_type: taxEstimateType, amount: String(taxEstimateAmount), currency_code: "UGX",
          price_includes_tax: taxPriceInclusive, records_kept: recordsKept,
          resident_taxpayer: residentTaxpayer, business_sector: businessSector,
          withholding_agent: withholdingAgent, payee_residency: payeeResidency, employee_residency: employeeResidency,
        }),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(body?.detail?.message || body?.detail || "The tax estimate could not be calculated.");
      setTaxEstimateResult(body as TaxEstimateResult);
    } catch (reason) {
      setTaxEstimateError(errorMessage(reason, "The tax estimate could not be calculated."));
    } finally { setTaxEstimateBusy(false); }
  }

  async function saveManualFiscalDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (savingManualDoc) return;
    if (!manualFdn.trim()) {
      setMessage("Enter the FDN exactly as shown on the official URA document."); setMessageTone("error"); return;
    }
    setSavingManualDoc(true); setMessage("");
    try {
      const response = await fetch("/api/lexa/api/v1/compliance/manual-fiscal-documents", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-Request-ID": crypto.randomUUID() },
        body: JSON.stringify({
          document_type: manualDocType, issue_date: manualIssueDate,
          currency_code: manualCurrency.trim().toUpperCase(), fdn: manualFdn.trim(),
          document_number: manualDocumentNumber.trim() || null,
          verification_code: manualVerificationCode.trim() || null,
          qr_code: manualQrCode.trim() || null,
          sale_id: manualSaleId.trim() || null,
        }),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(body?.detail?.message || body?.detail || "The manual URA record could not be saved.");
      setManualFdn(""); setManualDocumentNumber(""); setManualVerificationCode(""); setManualQrCode(""); setManualSaleId("");
      await load();
      setMessage("Official URA reference saved as a manual record. LEXA has not contacted URA or verified the FDN; the record remains marked as unverified by LEXA.");
      setMessageTone("status");
    } catch (reason) {
      setMessage(errorMessage(reason, "The manual fiscal-document record could not be saved.")); setMessageTone("error");
    } finally { setSavingManualDoc(false); }
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
            <span className="section-label">UGANDA TAX CALCULATOR · FY 2026/27</span>
            <h2>Automatic tax estimates</h2>
            <p>Calculations run inside LEXA's Python API using the dated URA guidance. They are estimates only and do not file a return or send data to URA.</p>
          </div></div>
          <form className="command-form" onSubmit={submitTaxEstimate}>
            <label htmlFor="tax-estimate-type">What do you want to estimate?
              <select id="tax-estimate-type" value={taxEstimateType} onChange={event => { setTaxEstimateType(event.target.value as TaxEstimateType); setTaxEstimateResult(null); setTaxEstimateError(""); }}>
                <option value="VAT">VAT on a sale amount</option>
                <option value="PRESUMPTIVE">Annual presumptive income tax</option>
                <option value="PAYE">Monthly PAYE (resident or non-resident)</option>
                <option value="WHT_SUPPLY">Withholding tax — taxable supply</option>
                <option value="WHT_PROFESSIONAL">Withholding tax — professional/management service</option>
              </select>
            </label>
            <label htmlFor="tax-estimate-amount">{taxEstimateType === "PRESUMPTIVE" ? "Annual gross turnover (UGX)" : taxEstimateType === "PAYE" ? "Monthly chargeable income (UGX)" : taxEstimateType === "VAT" ? "Sale price or taxable base (UGX)" : "Payment amount (UGX)"}
              <input id="tax-estimate-amount" type="number" min="0" step="0.01" value={taxEstimateAmount} onChange={event => setTaxEstimateAmount(event.target.value)} required />
            </label>
            {taxEstimateType === "PAYE" && <label htmlFor="paye-employee-residency">Employee residency
              <select id="paye-employee-residency" value={employeeResidency} onChange={event => setEmployeeResidency(event.target.value as "RESIDENT" | "NON_RESIDENT")}><option value="RESIDENT">Resident employee — amended FY 2026/27 bands</option><option value="NON_RESIDENT">Non-resident employee — separate URA bands</option></select>
            </label>}
            {taxEstimateType === "VAT" && <label htmlFor="tax-price-inclusive">Price treatment
              <select id="tax-price-inclusive" value={taxPriceInclusive ? "true" : "false"} onChange={event => setTaxPriceInclusive(event.target.value === "true")}><option value="false">VAT added to the entered amount</option><option value="true">VAT already included in the entered amount</option></select>
            </label>}
            {taxEstimateType === "PRESUMPTIVE" && <>
              <label htmlFor="tax-records-kept">Business records
                <select id="tax-records-kept" value={recordsKept ? "true" : "false"} onChange={event => setRecordsKept(event.target.value === "true")}><option value="true">I keep records</option><option value="false">I do not keep records</option></select>
              </label>
              <label htmlFor="tax-resident">Resident taxpayer?
                <select id="tax-resident" value={residentTaxpayer ? "true" : "false"} onChange={event => setResidentTaxpayer(event.target.value === "true")}><option value="true">Yes</option><option value="false">No</option></select>
              </label>
              <label htmlFor="tax-sector">Business sector
                <select id="tax-sector" value={businessSector} onChange={event => setBusinessSector(event.target.value)}>
                  <option value="GENERAL">General trade / other eligible business</option><option value="MEDICAL">Medical</option><option value="DENTAL">Dental</option><option value="ARCHITECTURAL">Architectural</option><option value="ENGINEERING">Engineering</option><option value="ACCOUNTING">Accounting</option><option value="LEGAL">Legal</option><option value="OTHER_PROFESSIONAL">Other professional services</option><option value="PUBLIC_ENTERTAINMENT">Public entertainment</option><option value="PUBLIC_UTILITY">Public utility</option><option value="CONSTRUCTION">Construction</option>
                </select>
              </label>
            </>}
            {(taxEstimateType === "WHT_SUPPLY" || taxEstimateType === "WHT_PROFESSIONAL") && <>
              <label htmlFor="tax-agent">Has URA appointed this business as a withholding-tax agent?
                <select id="tax-agent" value={withholdingAgent ? "true" : "false"} onChange={event => setWithholdingAgent(event.target.value === "true")}><option value="false">No / not confirmed</option><option value="true">Yes — appointment confirmed</option></select>
              </label>
              {taxEstimateType === "WHT_PROFESSIONAL" && <label htmlFor="tax-payee-residency">Payee residency
                <select id="tax-payee-residency" value={payeeResidency} onChange={event => setPayeeResidency(event.target.value as "RESIDENT" | "NON_RESIDENT")}><option value="RESIDENT">Resident</option><option value="NON_RESIDENT">Non-resident</option></select>
              </label>}
            </>}
            <button type="submit" className="primary" disabled={taxEstimateBusy || !taxEstimateAmount.trim()}>{taxEstimateBusy ? "Calculating…" : "Calculate estimate"}</button>
          </form>
          {taxEstimateError && <p role="alert" className="inline-message">{taxEstimateError}</p>}
          {taxEstimateResult && <div className="inline-message" role="status" style={{ marginTop: 12 }}>
            <strong>{taxEstimateResult.eligible === false ? "Eligibility not confirmed" : "Estimated tax"}</strong>
            {taxEstimateResult.tax_amount != null && <p style={{ margin: "8px 0" }}>Tax amount: <strong>{taxEstimateResult.currency_code || "UGX"} {Number(taxEstimateResult.tax_amount).toLocaleString("en-UG", { maximumFractionDigits: 2 })}</strong>{taxEstimateResult.rate_percent ? ` · rate ${taxEstimateResult.rate_percent}%` : ""}</p>}
            {taxEstimateResult.taxable_base != null && <p>Taxable base: UGX {Number(taxEstimateResult.taxable_base).toLocaleString("en-UG", { maximumFractionDigits: 2 })}</p>}
            {taxEstimateResult.total_amount != null && <p>Total including tax: UGX {Number(taxEstimateResult.total_amount).toLocaleString("en-UG", { maximumFractionDigits: 2 })}</p>}
            {taxEstimateResult.band && <p>Band: {taxEstimateResult.band}</p>}
            {taxEstimateResult.formula && <p>Formula: {taxEstimateResult.formula}</p>}
            {taxEstimateResult.reasons?.map(reason => <p key={reason}>{reason}</p>)}
            {taxEstimateResult.note && <p>{taxEstimateResult.note}</p>}
            <small>Reference date: {taxEstimateResult.reference_date || "23 October 2026"}. This is not a filed return or an official tax assessment.</small>
          </div>}
          <p style={{ color: "#77849a", fontSize: 12, marginTop: 12 }}>VAT threshold caution: URA's 23 October 2026 Q&amp;A says UGX 300 million annual taxable turnover; another official government VAT page states UGX 250 million under the 2026 amendment. LEXA highlights this conflict and will not automatically change your VAT status. Verify the current threshold and registration obligation with URA.</p>
          <p style={{ fontSize: 12 }}><a href="https://ura.go.ug/en/ask-ura-commissioner-general-41/" target="_blank" rel="noreferrer">Official URA tax update · 23 October 2026</a> · <a href="https://ura.go.ug/en/changes-to-paye-return-form-following-the-income-tax-amendment-act-2026/" target="_blank" rel="noreferrer">Official PAYE update</a> · <a href="https://ura.go.ug/en/additional-taxpayers-required-to-use-efris/" target="_blank" rel="noreferrer">EFRIS applicability notice</a></p>
        </section>

        <section className="workspace-section">
          <div className="section-head"><div>
            <span className="section-label">URA / EFRIS — MANUAL ONLY</span>
            <h2>Official receipt recordkeeping</h2>
            <p>LEXA stores your records and calculates tax from saved rules. A real URA-approved connector is not installed; LEXA does not connect to URA, submit e-invoices, issue an FDN, or verify an official document.</p>
          </div></div>
          {configLoaded && config ? <>
            <div className="command-form">
              <label htmlFor="efris-enabled">Manual EFRIS recordkeeping
                <select id="efris-enabled" value={config.enabled ? "true" : "false"} onChange={event => setConfig({ ...config, enabled: event.target.value === "true", integration_mode: "MANUAL" })}>
                  <option value="false">Not tracking EFRIS records here</option><option value="true">Track manually in LEXA</option>
                </select>
                <small>This setting never enables an EFRIS connection.</small>
              </label>
              <label htmlFor="efris-mode">LEXA mode
                <input id="efris-mode" value="Manual records only — no connection" readOnly aria-readonly="true" />
              </label>
              <label htmlFor="efris-status">URA registration status
                <input id="efris-status" value={statusLabel(config.registration_status)} readOnly aria-readonly="true" />
                <small>LEXA does not verify this status. Confirm it directly in your URA account.</small>
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
              <p><strong>Official workflow:</strong> use the URA portal or URA-approved EFRIS route directly. After URA issues the document, enter its FDN and other identifiers in the manual record form below. LEXA never marks an entry as verified merely because a user typed it.</p>
              <p><a href="https://ura.go.ug/en/efris/efris-registration/" target="_blank" rel="noreferrer">Open official URA EFRIS registration guidance</a> · <a href="https://ura.go.ug/en/efris/" target="_blank" rel="noreferrer">EFRIS overview and taxpayer guidance</a></p>
            </div>
          </> : !busy ? <p role="status">EFRIS settings are unavailable. Refresh the page or contact your administrator.</p> : <p role="status">Loading URA configuration…</p>}
        </section>

        <section className="workspace-section">
          <div className="section-head"><div>
            <span className="section-label">URA TAX REFERENCE</span>
            <h2>{ratesLoaded && rulesLoaded ? `${taxRates.length} tax rates · ${taxConfigs.length} active and historical rules` : "Tax configuration"}</h2>
            <p>The standard VAT rate is 18%. Dated rules are resolved on the server at checkout. Zero-rated and exempt supplies must not be treated as if they were the same.</p>
          </div></div>
          <label style={{ display: "flex", alignItems: "flex-start", gap: 10, margin: "10px 0 14px" }}>
            <input type="checkbox" checked={standardVatConfirmed} onChange={event => setStandardVatConfirmed(event.target.checked)} style={{ marginTop: 4 }} />
            <span><strong>Confirm VAT applicability</strong><small>I have checked this business's VAT registration or legal obligation and want LEXA to activate the 18% standard-rate default for supplies covered by that rule. I will add product/category overrides for different treatments.</small></span>
          </label>
          <label htmlFor="vat-price-treatment" style={{ maxWidth: 520 }}>How prices are usually entered
            <select id="vat-price-treatment" value={standardVatPriceInclusive ? "inclusive" : "exclusive"} onChange={event => setStandardVatPriceInclusive(event.target.value === "inclusive")}>
              <option value="exclusive">Add 18% VAT to the saved price</option>
              <option value="inclusive">Saved price already includes VAT</option>
            </select>
            <small>This choice is saved in the tax-rate rule. If products differ, create product/category overrides instead of using one default.</small>
          </label>
          <div className="header-actions" style={{ marginBottom: 16 }}>
            <button type="button" className="button button-soft" onClick={() => void addUraReferenceRate("standard")} disabled={busy || Boolean(savingUraPreset) || !standardVatConfirmed}>{savingUraPreset === "standard" ? "Applying rule…" : "Apply 18% default VAT rule from 1 July 2026"}</button>
            <button type="button" className="button button-soft" onClick={() => void addUraReferenceRate("zero")} disabled={busy || Boolean(savingUraPreset)}>{savingUraPreset === "zero" ? "Adding…" : "Add 0% zero-rate reference only"}</button>
          </div>
          <p style={{ color: "#77849a", fontSize: 12 }}>The 18% rule uses the effective date 1 July 2026 and the selected inclusive/exclusive pricing treatment; it auto-calculates at checkout once activated. The zero-rate reference is never applied as a default. LEXA does not infer exemption, zero-rating, or VAT registration from turnover.</p>
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
                <label htmlFor="tax-from">Effective from<input id="tax-from" type="date" value={rateDraft.effective_from} onChange={event => setRateDraft({ ...rateDraft, effective_from: event.target.value })} required /><small>Apply the legal effective date for the selected treatment; 2026/27 amendments generally commence 1 July 2026.</small></label>
                <label htmlFor="tax-to">Effective to (optional)<input id="tax-to" type="date" min={rateDraft.effective_from || undefined} value={rateDraft.effective_to} onChange={event => setRateDraft({ ...rateDraft, effective_to: event.target.value })} /></label>
              </div>
              <button type="submit" className="button button-dark" disabled={busy || savingRate}>{savingRate ? "Saving rate…" : "Save tax rate"}</button>
            </form>
            <form className="command-form" onSubmit={saveDefaultRule}>
              <div><h3>Configure a default tax rule</h3><p>Do not create a default tax rule until you have confirmed the business registration, product scope, and applicable tax treatment. A default affects every product covered by its scope; do not use it where products need different tax treatments.</p></div>
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
          <div className="section-head"><div>
            <span className="section-label">OFFICIAL URA DOCUMENT — MANUAL ENTRY</span>
            <h2>Record a document issued by URA</h2>
            <p>First obtain the invoice or receipt using the official URA process. Enter the FDN and identifiers here so LEXA can keep the reference with your records.</p>
          </div></div>
          <form className="command-form" onSubmit={saveManualFiscalDocument}>
            <div className="form-grid">
              <label htmlFor="manual-doc-type">Document type
                <select id="manual-doc-type" value={manualDocType} onChange={event => setManualDocType(event.target.value as "INVOICE" | "RECEIPT" | "CREDIT_NOTE" | "DEBIT_NOTE")}><option value="INVOICE">E-invoice</option><option value="RECEIPT">E-receipt</option><option value="CREDIT_NOTE">E-credit note</option><option value="DEBIT_NOTE">E-debit note</option></select>
              </label>
              <label htmlFor="manual-issue-date">Issue date<input id="manual-issue-date" type="date" value={manualIssueDate} onChange={event => setManualIssueDate(event.target.value)} required /></label>
            </div>
            <div className="form-grid">
              <label htmlFor="manual-currency">Document currency<input id="manual-currency" value={manualCurrency} onChange={event => setManualCurrency(event.target.value.toUpperCase())} minLength={3} maxLength={3} pattern="[A-Za-z]{3}" required /></label>
              <label htmlFor="manual-fdn">URA FDN<input id="manual-fdn" value={manualFdn} onChange={event => setManualFdn(event.target.value)} maxLength={40} autoComplete="off" required placeholder="Copy from the official URA document" /></label>
            </div>
            <div className="form-grid">
              <label htmlFor="manual-doc-number">Document number (optional)<input id="manual-doc-number" value={manualDocumentNumber} onChange={event => setManualDocumentNumber(event.target.value)} maxLength={100} /></label>
              <label htmlFor="manual-verification-code">Verification code (optional)<input id="manual-verification-code" value={manualVerificationCode} onChange={event => setManualVerificationCode(event.target.value)} maxLength={160} autoComplete="off" /></label>
            </div>
            <label htmlFor="manual-qr">QR text or reference (optional)<input id="manual-qr" value={manualQrCode} onChange={event => setManualQrCode(event.target.value)} maxLength={4000} /></label>
            <label htmlFor="manual-sale-id">Completed sale ID (optional)<input id="manual-sale-id" value={manualSaleId} onChange={event => setManualSaleId(event.target.value)} placeholder="Link the document to a saved sale UUID" /></label>
            <button type="submit" className="primary" disabled={savingManualDoc || !manualFdn.trim()}>{savingManualDoc ? "Saving manual record…" : "Save official URA reference"}</button>
          </form>
          <p style={{ color: "#77849a", fontSize: 12, marginTop: 12 }}>A new entry is stored as a manual, unverified record. LEXA does not call URA, does not submit or validate the document, and does not change the status to “accepted” just because information was entered.</p>
        </section>

        <section className="workspace-section">
          <div className="section-head"><div><span className="section-label">OFFICIAL FISCAL RECORDS</span><h2>{docsLoaded ? `${docs.length} fiscal documents` : "Fiscal document status unavailable"}</h2><p>Manual entries are shown for recordkeeping and are not verified by LEXA. Check their FDN and QR directly through URA.</p></div></div>
          <div className="table-wrap"><table><thead><tr><th>Issue date</th><th>Document</th><th>Status</th><th>URA document number</th><th>Verification code</th></tr></thead>
            <tbody>{docs.map(doc => <tr key={doc.id}><td>{doc.issue_date}</td><td>{documentLabel(doc.document_type)}</td><td>{statusLabel(doc.status)}</td><td>{doc.fdn || "Not issued"}</td><td>{doc.verification_code || "Not issued"}</td></tr>)}
              {!busy && docsLoaded && docs.length === 0 && <tr><td colSpan={5}>No official fiscal documents have been recorded yet. A verified URA fiscal document has not been returned; a LEXA payment receipt is not automatically an EFRIS receipt.</td></tr>}
              {!busy && !docsLoaded && <tr><td colSpan={5}>Fiscal documents could not be loaded. Refresh to retry.</td></tr>}
            </tbody>
          </table></div>
          <p style={{ color: "#77849a", fontSize: 12, marginTop: 12 }}>A payment record in LEXA is not an EFRIS receipt. Manual entries must be checked in the official URA portal; the table does not imply LEXA verified or submitted them.</p>
        </section>
      </main>
    </AppShell>
  );
}
