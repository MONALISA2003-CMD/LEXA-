"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "../../components/app-shell";
import styles from "./page.module.css";
import { getCachedSession, restoreSession, type AuthResponse } from "../../lib/api";

type Provider = { id: string; label: string; tier: string; model: string; configured: boolean };
type ProviderList = { enabled: boolean; providers: Provider[]; maximum_prompt_characters: number };
type AssistResult = { provider: string; model: string; answer: string; used_business_summary: boolean; advisory_only: true };
type Area = "general" | "sales" | "stock" | "purchasing" | "finance" | "customers";

const areas: { value: Area; label: string }[] = [
  { value: "general", label: "General business" },
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
      if (!response.ok) throw new Error(readApiMessage(payload, "Could not load the available AI providers."));
      const data = payload as ProviderList;
      const rows = Array.isArray(data.providers) ? data.providers : [];
      setProviders(rows);
      setSelectedProvider((current) => current && rows.some((row) => row.id === current && row.configured) ? current : (rows.find((row) => row.configured)?.id || ""));
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load the available AI providers.");
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
          setError("Your session could not be restored. Please sign in again.");
          setLoadingProviders(false);
          return;
        }
        setSession(auth);
        setSessionReady(true);
        await loadProviders(auth);
      } catch (cause) {
        if (active) {
          setError(cause instanceof Error ? cause.message : "Please sign in again to use the AI assistant.");
          setLoadingProviders(false);
        }
      }
    };
    void boot();
    return () => { active = false; };
  }, [loadProviders]);

  const configuredProviders = useMemo(() => providers.filter((provider) => provider.configured), [providers]);
  const currentProvider = providers.find((provider) => provider.id === selectedProvider);

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) { setError("Please sign in again to use the AI assistant."); return; }
    if (!selectedProvider) { setError("No AI provider is configured on the LEXA API server yet."); return; }
    const prompt = question.trim();
    if (!prompt) { setError("Enter a question for the assistant."); return; }
    setSending(true); setError(""); setResult(null);
    try {
      const response = await fetch("/api/lexa/api/v1/ai/assist", {
        method: "POST", cache: "no-store", credentials: "include",
        headers: { Authorization: `Bearer ${session.access_token}`, "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ provider: selectedProvider, area, prompt, include_business_summary: includeSummary }),
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(readApiMessage(payload, "LEXA couldn't complete the AI request."));
      setResult(payload as AssistResult);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "LEXA couldn't complete the AI request.");
    } finally { setSending(false); }
  }

  return <AppShell title="AI business assistant" eyebrow="LEXA intelligence">
    <main className={`workspace ${styles.page}`} style={{ maxWidth: 1160 }}>
      <div className="workspace-header">
        <div>
          <span className="workspace-breadcrumb">LEXA · AI ASSISTANT</span>
          <h1>Make the next decision clearer.</h1>
          <p>Ask for explanations, options, and checklists. LEXA keeps the assistant advisory-only; it cannot post transactions or change saved business records.</p>
        </div>
      </div>

      <section className={`workspace-section ${styles.section}`} aria-labelledby="assistant-form-title">
        <div className="section-head"><div><span className="section-label">CHOOSE YOUR MODEL</span><h2 id="assistant-form-title">Ask LEXA</h2><p>Select a server-configured provider. There is no automatic switch to a paid provider.</p></div></div>
        {error && <div className="notice notice-error" role="alert">{error}</div>}
        {!loadingProviders && providers.length > 0 && configuredProviders.length === 0 && <div className="notice" role="status"><strong>AI is not configured yet.</strong><p>Add a provider API key to the backend environment. Do not add keys to the browser or any <code>NEXT_PUBLIC_</code> variable.</p></div>}

        <form onSubmit={ask} className={styles.form}>
          <div className={styles.formGrid}>
            <label className={styles.field}><span>AI provider</span>
              <select value={selectedProvider} onChange={(event) => setSelectedProvider(event.target.value)} disabled={loadingProviders || sending || configuredProviders.length === 0} required>
                <option value="">{loadingProviders ? "Checking providers…" : "Choose a configured provider"}</option>
                {providers.filter((provider) => provider.configured).map((provider) => <option key={provider.id} value={provider.id}>{provider.label} · {provider.model}</option>)}
              </select>
              {currentProvider && <small>{currentProvider.tier}</small>}
            </label>
            <label className={styles.field}><span>Business area</span>
              <select value={area} onChange={(event) => setArea(event.target.value as Area)} disabled={sending}>
                {areas.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
          </div>
          <label className={styles.field}><span>Your question</span>
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={5} maxLength={8000} disabled={sending} required placeholder="Example: Give me a checklist to investigate why stock value and sales margin changed this week." aria-describedby="ai-question-note" />
            <small id="ai-question-note">{question.length.toLocaleString()} / 8,000 characters. Avoid entering personal customer data, passwords, payment details, or confidential secrets.</small>
          </label>
          <label className={styles.consentRow}>
            <input type="checkbox" checked={includeSummary} onChange={(event) => setIncludeSummary(event.target.checked)} disabled={sending} />
            <span><strong>Include a summary of my saved business figures (optional)</strong><small>Shares aggregate totals for the last 30 days with the selected provider. Off by default; requires workspace-wide analytics access.</small></span>
          </label>
          <div className="header-actions">
            <button type="submit" className="button button-dark" disabled={sending || loadingProviders || !sessionReady || configuredProviders.length === 0}>{sending ? "Thinking…" : "Ask assistant"}</button>
            <button type="button" className="button button-soft" disabled={sending || (!question && !result)} onClick={() => { setQuestion(""); setResult(null); setError(""); }}>Clear</button>
          </div>
        </form>
      </section>

      {result && <section className={`workspace-section ${styles.section}`} aria-labelledby="ai-answer-title">
        <div className="section-head"><div><span className="section-label">ADVISORY RESPONSE</span><h2 id="ai-answer-title">Assistant response</h2><p>{providers.find((provider) => provider.id === result.provider)?.label || result.provider} · {result.model}{result.used_business_summary ? " · used your optional business summary" : " · no business summary shared"}</p></div></div>
        <div className={styles.answer} role="status" aria-live="polite">{result.answer}</div>
        <p className="muted">Check important claims against LEXA’s saved records and your accountant or manager. The assistant cannot perform actions for you.</p>
      </section>}

      <section className={`workspace-section ${styles.section}`} aria-labelledby="ai-provider-notice">
        <div className="section-head"><div><span className="section-label">PRIVACY AND COST</span><h2 id="ai-provider-notice">Know where your question goes</h2></div></div>
        <div className={styles.noticeGrid}>
          <article className={styles.noticeCard}><h3>Free provider quotas</h3><p>Gemini, Groq, and free OpenRouter routes can offer no-cost usage within changing quotas. Some other providers offer trial credits rather than a permanent free tier. Google may use data sent through its free Gemini API tier to improve products; paid-tier data is treated differently. Confirm each provider’s current quota, billing settings, and data terms before sending business information.</p></article>
          <article className={styles.noticeCard}><h3>OpenAI API is paid</h3><p>OpenAI is available only when its server key is configured and selected. LEXA does not silently fall back to OpenAI. Set a low output-token cap and a budget in the provider account.</p></article>
          <article className={styles.noticeCard}><h3>Keys stay server-side</h3><p>Provider keys are read only by the API server and are never returned to this page. Requests leave LEXA and are subject to the selected provider’s terms, logging, retention, and training policies.</p></article>
        </div>
      </section>
    </main>
  </AppShell>;
}
