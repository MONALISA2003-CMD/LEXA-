"use client";

import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "../../components/app-shell";
import styles from "./page.module.css";
import { getCachedSession, restoreSession, type AuthResponse } from "../../lib/api";

type Provider = { id: string; label: string; tier: string; model: string; configured: boolean; enabled?: boolean };
type ProviderList = { enabled?: boolean; execution_available?: boolean; providers: Provider[]; maximum_prompt_characters: number };
type AssistResult = { provider: string; model: string; answer: string; used_business_summary: boolean; advisory_only: true };
type Area = "general" | "sales" | "stock" | "purchasing" | "finance" | "customers";

const areas: { value: Area; label: string }[] = [
  { value: "general", label: "Everyday business decisions" },
  { value: "sales", label: "Sales and customers" },
  { value: "stock", label: "Stock and replenishment" },
  { value: "purchasing", label: "Purchasing and suppliers" },
  { value: "finance", label: "Finance and reconciliation" },
  { value: "customers", label: "Customer follow-up" },
];

function readApiMessage(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      const message = (detail as { message?: unknown }).message;
      if (typeof message === "string" && message.trim()) return message;
    }
    if (typeof detail === "string" && detail.trim()) return detail;
  }
  return fallback;
}

export default function AiAssistantPage() {
  const [session, setSession] = useState<AuthResponse | null>(() => getCachedSession());
  const [providers, setProviders] = useState<Provider[]>([]);
  const [selectedProvider, setSelectedProvider] = useState("");
  const [executionAvailable, setExecutionAvailable] = useState(false);
  const [area, setArea] = useState<Area>("general");
  const [question, setQuestion] = useState("");
  const [includeSummary, setIncludeSummary] = useState(false);
  const [loadingProviders, setLoadingProviders] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AssistResult | null>(null);
  const [sessionReady, setSessionReady] = useState(Boolean(getCachedSession()));

  const loadProviders = useCallback(async (auth: AuthResponse) => {
    setLoadingProviders(true);
    try {
      const response = await fetch("/api/lexa/api/v1/ai/providers", {
        method: "GET", cache: "no-store", credentials: "include",
        headers: { Authorization: `Bearer ${auth.access_token}`, Accept: "application/json" },
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(readApiMessage(payload, "LEXA couldn't check the AI connection."));
      const data = payload as ProviderList;
      const rows = Array.isArray(data.providers) ? data.providers : [];
      setProviders(rows);
      setExecutionAvailable(data.execution_available === true);
      setSelectedProvider((current) => current && rows.some((row) => row.id === current && row.configured) ? current : (rows.find((row) => row.configured)?.id || ""));
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "LEXA couldn't check the AI connection.");
    } finally {
      setLoadingProviders(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const boot = async () => {
      try {
        let auth = getCachedSession();
        if (!auth) auth = await restoreSession();
        if (!active) return;
        if (!auth) {
          setError("Your sign-in session has expired. Sign in again to continue.");
          setLoadingProviders(false);
          return;
        }
        setSession(auth);
        setSessionReady(true);
        await loadProviders(auth);
      } catch (cause) {
        if (active) {
          setError(cause instanceof Error ? cause.message : "Sign in again to continue.");
          setLoadingProviders(false);
        }
      }
    };
    void boot();
    return () => { active = false; };
  }, [loadProviders]);

  const configuredProviders = useMemo(() => providers.filter((provider) => provider.configured), [providers]);
  const currentProvider = providers.find((provider) => provider.id === selectedProvider);
  const canAsk = executionAvailable && configuredProviders.length > 0 && Boolean(selectedProvider);

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) { setError("Sign in again to continue."); return; }
    if (!canAsk) { setError("AI responses are not enabled yet. Your question has not been sent to a provider."); return; }
    const prompt = question.trim();
    if (!prompt) { setError("Enter a business question first."); return; }
    setSending(true); setError(""); setResult(null);
    try {
      const response = await fetch("/api/lexa/api/v1/ai/assist", {
        method: "POST", cache: "no-store", credentials: "include",
        headers: { Authorization: `Bearer ${session.access_token}`, "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ provider: selectedProvider, area, prompt, include_business_summary: includeSummary }),
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(readApiMessage(payload, "LEXA couldn't prepare guidance just now."));
      setResult(payload as AssistResult);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "LEXA couldn't prepare guidance just now.");
    } finally { setSending(false); }
  }

  return <AppShell title="AI business assistant" eyebrow="LEXA intelligence">
    <main className={`workspace ${styles.page}`} style={{ maxWidth: 1160 }}>
      <div className="workspace-header">
        <div>
          <span className="workspace-breadcrumb">LEXA · BUSINESS GUIDANCE</span>
          <h1>Guidance that fits your business.</h1>
          <p>Explore options, investigate changes and make a practical plan for sales, stock, purchasing or finance. LEXA does not change saved records or complete transactions for you.</p>
        </div>
      </div>

      <section className={`workspace-section ${styles.section}`} aria-labelledby="assistant-form-title">
        <div className="section-head"><div><span className="section-label">BUSINESS SUPPORT</span><h2 id="assistant-form-title">What would you like help with?</h2><p>When AI is enabled, LEXA uses only the provider approved for the request. It will not silently switch to another provider or a paid service.</p></div></div>
        {error && <div className="notice notice-error" role="alert">{error}</div>}
        {!loadingProviders && configuredProviders.length === 0 && <div className="notice" role="status"><strong>AI assistance isn't connected yet.</strong><p>No AI provider is configured on the LEXA server. A workspace administrator can arrange the connection after reviewing privacy and cost settings. API keys must stay on the server—never add them to this website or to a <code>NEXT_PUBLIC_</code> variable.</p></div>}
        {!loadingProviders && configuredProviders.length > 0 && !executionAvailable && <div className="notice" role="status"><strong>AI responses are temporarily paused.</strong><p>LEXA is finishing the privacy and safety checks for external AI requests. Your question will not be sent to a provider until this is enabled.</p></div>}

        <form onSubmit={ask} className={styles.form}>
          <div className={styles.formGrid}>
            <label className={styles.field}><span>AI provider</span>
              <select value={selectedProvider} onChange={(event) => setSelectedProvider(event.target.value)} disabled={loadingProviders || sending || !canAsk} required>
                <option value="">{loadingProviders ? "Checking connection…" : "No provider available"}</option>
                {configuredProviders.map((provider) => <option key={provider.id} value={provider.id}>{provider.label}</option>)}
              </select>
              {currentProvider && <small>{currentProvider.tier}</small>}
            </label>
            <label className={styles.field}><span>Business area</span>
              <select value={area} onChange={(event) => setArea(event.target.value as Area)} disabled={sending}>
                {areas.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
          </div>
          <label className={styles.field}><span>Your business question</span>
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={5} maxLength={8000} disabled={sending} required placeholder="For example: Help me investigate why sales and gross margin fell this week." aria-describedby="ai-question-note" />
            <small id="ai-question-note">{question.length.toLocaleString()} / 8,000 characters. Keep passwords, payment details, personal customer information and confidential documents out of the question.</small>
          </label>
          <label className={styles.consentRow}>
            <input type="checkbox" checked={includeSummary} onChange={(event) => setIncludeSummary(event.target.checked)} disabled={sending} />
            <span><strong>Include recent business totals (optional)</strong><small>If enabled in future, LEXA will share aggregate totals from the last 30 days with the selected provider. Leave this off unless figures are needed. Workspace-wide analytics access is required.</small></span>
          </label>
          <div className="header-actions">
            <button type="submit" className="button button-dark" disabled={sending || loadingProviders || !sessionReady || !canAsk}>{sending ? "Preparing guidance…" : "Get guidance"}</button>
            <button type="button" className="button button-soft" disabled={sending || (!question && !result)} onClick={() => { setQuestion(""); setResult(null); setError(""); }}>Clear question</button>
          </div>
        </form>
      </section>

      {result && <section className={`workspace-section ${styles.section}`} aria-labelledby="ai-answer-title">
        <div className="section-head"><div><span className="section-label">RESPONSE TO REVIEW</span><h2 id="ai-answer-title">LEXA's guidance</h2><p>{providers.find((provider) => provider.id === result.provider)?.label || result.provider}{result.used_business_summary ? " · included your optional business summary" : " · no business summary shared"}</p></div></div>
        <div className={styles.answer} role="status" aria-live="polite">{result.answer}</div>
        <p className={styles.answerNote}>Check important details against LEXA's saved records and, where appropriate, your accountant or manager. This guidance does not approve or complete a business action.</p>
      </section>}

      <section className={`workspace-section ${styles.section}`} aria-labelledby="ai-provider-notice">
        <div className="section-head"><div><span className="section-label">PRIVACY & COST</span><h2 id="ai-provider-notice">Before sharing business information</h2><p>Questions sent to an external provider are handled under that provider's data and service terms.</p></div></div>
        <div className={styles.noticeGrid}>
          <article className={styles.noticeCard}><h3>Free and trial quotas</h3><p>Some providers offer limited free usage or trial credits, and limits can change. Review the current quota, data-use policy and retention terms before sharing business information. Some free services may use submitted content to improve their products.</p></article>
          <article className={styles.noticeCard}><h3>Paid services and budgets</h3><p>Some models charge for each request. LEXA will not silently switch to a paid service. Confirm pricing, usage limits and a budget before enabling any paid provider.</p></article>
          <article className={styles.noticeCard}><h3>Access keys stay on the server</h3><p>Provider keys are not shown on this page. When the feature is enabled, the question and any optional summary you choose are sent to the selected provider. Avoid names, account numbers, payment details and confidential documents.</p></article>
        </div>
      </section>
    </main>
  </AppShell>;
}
