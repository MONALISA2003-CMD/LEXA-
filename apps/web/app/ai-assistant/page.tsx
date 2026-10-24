"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import Link from "next/link";
import { AppShell } from "../../components/app-shell";
import { askLexaAssistant, getAssistantProviders, type AssistantProvidersResponse } from "../../lib/ai-assistant-api";
import styles from "./page.module.css";

type ChatMessage = { id: string; role: "user" | "assistant"; text: string; meta?: string; evidenceHref?: string; evidenceLabel?: string };
type Area = "general" | "sales" | "stock" | "purchasing" | "finance" | "customers";

function inlineMarkdown(text: string): ReactNode[] {
  const result: ReactNode[] = [];
  const pattern = /\*\*(.+?)\*\*|\*(.+?)\*/g;
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) result.push(text.slice(last, match.index));
    if (match[1]) result.push(<strong key={`b-${match.index}`}>{match[1]}</strong>);
    else if (match[2]) result.push(<em key={`i-${match.index}`}>{match[2]}</em>);
    last = pattern.lastIndex;
  }
  if (last < text.length) result.push(text.slice(last));
  return result;
}

/** Safe, intentionally small Markdown renderer: no raw HTML or external links. */
function MarkdownAnswer({ text }: { text: string }) {
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let index = 0;
  let key = 0;
  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) { index += 1; continue; }
    if (/^#{1,3}\s/.test(line)) {
      const heading = line.replace(/^#{1,3}\s+/, "");
      blocks.push(<h4 key={key++}>{inlineMarkdown(heading)}</h4>);
      index += 1;
      continue;
    }
    if (/^(?:[-*])\s+/.test(line)) {
      const items: ReactNode[] = [];
      while (index < lines.length && /^(?:\s*[-*])\s+/.test(lines[index])) {
        items.push(<li key={key++}>{inlineMarkdown(lines[index].replace(/^\s*[-*]\s+/, ""))}</li>);
        index += 1;
      }
      blocks.push(<ul key={key++}>{items}</ul>);
      continue;
    }
    if (/^\d+[.)]\s+/.test(line)) {
      const items: ReactNode[] = [];
      while (index < lines.length && /^\s*\d+[.)]\s+/.test(lines[index])) {
        items.push(<li key={key++}>{inlineMarkdown(lines[index].replace(/^\s*\d+[.)]\s+/, ""))}</li>);
        index += 1;
      }
      blocks.push(<ol key={key++}>{items}</ol>);
      continue;
    }
    const paragraph: string[] = [line];
    index += 1;
    while (index < lines.length && lines[index].trim() && !/^\s*(?:#{1,3}\s|[-*]\s+|\d+[.)]\s+)/.test(lines[index])) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push(<p key={key++}>{inlineMarkdown(paragraph.join(" "))}</p>);
  }
  return <div className={styles.markdown}>{blocks}</div>;
}

function makeId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function AiAssistantPage() {
  const [providers, setProviders] = useState<AssistantProvidersResponse | null>(null);
  const [area, setArea] = useState<Area>("general");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [providerError, setProviderError] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);
  const availableProviders = useMemo(() => (providers?.providers ?? []).filter(item => item.selectable), [providers]);

  const loadProviders = useCallback(async () => {
    setLoadingProviders(true);
    setProviderError("");
    try {
      const result = await getAssistantProviders();
      setProviders(result);
    } catch (cause) {
      setProviderError(cause instanceof Error ? cause.message : "Assistant settings could not be checked.");
    } finally {
      setLoadingProviders(false);
    }
  }, []);

  useEffect(() => { void loadProviders(); }, [loadProviders]);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const activeWorkspace = () => {
      try { return window.sessionStorage.getItem("lexa_workspace_id") ?? ""; }
      catch { return ""; }
    };
    let workspaceSnapshot = activeWorkspace();
    const resetForWorkspaceChange = () => {
      const currentWorkspace = activeWorkspace();
      if (currentWorkspace === workspaceSnapshot) return;
      workspaceSnapshot = currentWorkspace;
      setMessages([]);
      setQuestion("");
      setError("");
      setProviderError("");
      void loadProviders();
    };
    window.addEventListener("storage", resetForWorkspaceChange);
    window.addEventListener("focus", resetForWorkspaceChange);
    window.addEventListener("pageshow", resetForWorkspaceChange);
    window.addEventListener("lexa:workspace-changed", resetForWorkspaceChange);
    return () => {
      window.removeEventListener("storage", resetForWorkspaceChange);
      window.removeEventListener("focus", resetForWorkspaceChange);
      window.removeEventListener("pageshow", resetForWorkspaceChange);
      window.removeEventListener("lexa:workspace-changed", resetForWorkspaceChange);
    };
  }, [loadProviders]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages, sending]);

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const prompt = question.trim();
    if (!prompt || sending) return;
    setError("");
    setQuestion("");
    setSending(true);
    const userMessage: ChatMessage = { id: makeId(), role: "user", text: prompt };
    setMessages(previous => [...previous, userMessage]);
    const requestStartedAt = performance.now();
    try {
      const reply = await askLexaAssistant({ prompt, area });
      const sourceLabel = reply.source_mode === "local_business_data"
        ? reply.evidence?.status === "available" ? "Based on saved LEXA business records" : "Saved figures could not be verified"
        : reply.source_mode === "external_question_only"
          ? "General guidance · screened question only"
          : "LEXA guidance";
      const elapsedLabel = ` · ${(Math.max(0, performance.now() - requestStartedAt) / 1000).toFixed(1)}s`;
      setMessages(previous => [...previous, {
        id: makeId(), role: "assistant", text: reply.answer,
        meta: `${sourceLabel}${elapsedLabel}`,
        evidenceHref: reply.evidence?.href,
        evidenceLabel: reply.evidence?.status === "available" ? "View source" : "Open related page",
      }]);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "LEXA couldn't respond just now. Please try again.";
      setError(message);
      setMessages(previous => [...previous, {
        id: makeId(), role: "assistant",
        text: `**I couldn't complete that request.** ${message}\n\nPlease try again shortly or use Business Insights, Reports or Daily Brief to review your saved figures.`,
      }]);
    } finally {
      setSending(false);
    }
  }

  function clearConversation() {
    setMessages([]);
    setQuestion("");
    setError("");
  }

  return <AppShell title="Business assistant" eyebrow="LEXA BUSINESS SUPPORT">
    <main className={`workspace ${styles.page}`} style={{ maxWidth: 1120 }}>
      <div className="workspace-header">
        <div>
          <span className="workspace-breadcrumb">LEXA · BUSINESS SUPPORT</span>
          <h1>Your LEXA business assistant</h1>
          <p>Ask for practical guidance on using LEXA and managing the business workflows it supports.</p>
        </div>
        <div className="header-actions">
          <Link href="/intelligence" className="button button-soft">Business insights</Link>
          {messages.length > 0 && <button type="button" className="button button-soft" onClick={clearConversation}>Clear chat</button>}
        </div>
      </div>

      <section className={styles.privacyBar} aria-label="Assistant privacy details">
        <span className={styles.privacyIcon} aria-hidden="true">✦</span>
        <div>
          <strong>Private to your signed-in workspace</strong>
          <p>When you ask for figures, LEXA checks permission-approved saved business summaries inside your workspace and shows when the data was refreshed. Those records are not shared with external services. For general guidance, LEXA may share the question you type with an approved service. This chat is not saved as conversation history.</p>
        </div>
      </section>

      {(providerError || error) && <div className="notice notice-error" role="alert">{providerError || error}</div>}

      <section className={styles.chatShell} aria-label="LEXA assistant conversation">
        <div className={styles.chatHeader}>
          <div>
            <span className="section-label">BUSINESS GUIDANCE</span>
            <h2>How can I help with LEXA?</h2>
          </div>
          <span className={styles.statusDot}>{loadingProviders ? "Checking…" : availableProviders.length ? "Ready when you are" : "Private guidance available"}</span>
        </div>

        {messages.length === 0 ? <div className={styles.welcome}>
          <div className={styles.welcomeMark} aria-hidden="true">✦</div>
          <h3>Let's work through your next business step.</h3>
          <p>Get clear recommendations on sales processes, stock control, purchasing, finance workflows, customer follow-up and the reports available in LEXA.</p>
          <div className={styles.suggestionGrid}>
            {["How can I reduce stockouts in LEXA?", "How should I review this month's sales?", "What should I check before receiving a supplier order?", "How can I follow up on customer balances responsibly?"].map(item => <button key={item} type="button" className={styles.suggestion} onClick={() => setQuestion(item)}>{item}<span aria-hidden="true">↗</span></button>)}
          </div>
        </div> : <div className={styles.messages} role="log" aria-live="polite" aria-relevant="additions text">
          {messages.map(message => <article key={message.id} className={`${styles.message} ${message.role === "user" ? styles.userMessage : styles.assistantMessage}`}>
            <div className={styles.messageLabel}>{message.role === "user" ? "YOU" : "LEXA"}</div>
            {message.role === "assistant" ? <>
              <MarkdownAnswer text={message.text} />
              {message.meta && <div className={styles.responseMeta}>
                <span>{message.meta}</span>
                {message.evidenceHref && <Link href={message.evidenceHref}>{message.evidenceLabel || "View source"}</Link>}
              </div>}
            </> : <p className={styles.userText}>{message.text}</p>}
          </article>)}
          {sending && <article className={`${styles.message} ${styles.assistantMessage}`} role="status"><div className={styles.messageLabel}>LEXA</div><div className={styles.thinking}><span></span><span></span><span></span><span className={styles.thinkingText}>Preparing guidance…</span></div></article>}
          <div ref={endRef} />
        </div>}

        <form className={styles.composer} onSubmit={submitQuestion}>
          <label htmlFor="assistant-question">Your business question</label>
          <textarea id="assistant-question" value={question} onChange={event => setQuestion(event.target.value)} maxLength={2400} rows={3} placeholder="Ask about a LEXA workflow or a business task…" disabled={sending} required />
          <div className={styles.composerFooter}>
            <div className={styles.controls}>
              <label className={styles.controlLabel} htmlFor="assistant-area">Business area</label>
              <select id="assistant-area" value={area} onChange={event => setArea(event.target.value as Area)} disabled={sending}>
                <option value="general">General LEXA help</option><option value="sales">Sales</option><option value="stock">Stock & inventory</option><option value="purchasing">Purchasing</option><option value="finance">Finance</option><option value="customers">Customers</option>
              </select>
            </div>
            <button type="submit" className="button button-dark" disabled={sending || loadingProviders || !question.trim()}>{sending ? "Thinking…" : "Ask LEXA"}<span aria-hidden="true"> →</span></button>
          </div>
          {!loadingProviders && !providers?.enabled && <p className={styles.disabledNote}>Private LEXA guidance remains available, but external business advice is disabled by the current safety settings. Business Insights, Daily Brief and Reports remain available for your saved records.</p>}
          <p className={styles.disclaimer}>LEXA only answers questions in its business-support scope. Do not enter names, phone numbers, private customer details, payment credentials or account identifiers. For supported figures, LEXA checks saved metrics locally and clearly says when the data is missing or out of date.</p>
        </form>
      </section>
      <div className={styles.quickLinks}><Link href="/daily-brief">Daily Brief</Link><Link href="/demand-forecast">Demand Forecast</Link><Link href="/documents">Business documents</Link><Link href="/reports">Reports</Link></div>
    </main>
  </AppShell>;
}
