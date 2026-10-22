"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../components/app-shell";
import { getSetupProgress, initializeWorkspaceSetup, type SetupProgress } from "../../lib/api";

export default function OnboardingPage() {
  const [progress, setProgress] = useState<SetupProgress | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [preparing, setPreparing] = useState(false);
  const [message, setMessage] = useState("");
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setProgress(await getSetupProgress()); }
    catch (e) { setProgress(null); setError(e instanceof Error ? e.message : "Setup progress could not be verified."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  async function prepareBusiness() {
    if (preparing) return;
    setPreparing(true); setError(""); setMessage("");
    try { const result = await initializeWorkspaceSetup(); setMessage(result.message); setProgress(result.progress); }
    catch (e) { setError(e instanceof Error ? e.message : "We couldn't finish setting up your business. Please try again."); }
    finally { setPreparing(false); }
  }
  return <AppShell title="Business setup" eyebrow="Let’s get your business ready">
    <section className="panel" style={{ maxWidth: 850, padding: "1.25rem" }}>
      <div className="panel-head"><div><p className="eyebrow">BUSINESS SETUP</p><h2>{progress?.complete ? "The required setup is complete" : "Set up your business"}</h2></div></div>
      <p>We’ll check your business details, stock location, payment method and basic money records so sales, stock and reports work together.</p>
      {loading && <p role="status">Checking your business setup…</p>}
      {message && <div className="notice notice-success" role="status">{message}</div>}
      {error && <div className="notice notice-error" role="alert">{error}<button className="button button-soft" type="button" onClick={() => void load()}>Retry</button></div>}
      {progress && <>
        <p><strong>{progress.completed_required_steps} of {progress.required_steps}</strong> setup steps complete</p>
        <div role="progressbar" aria-valuemin={0} aria-valuemax={progress.required_steps} aria-valuenow={progress.completed_required_steps} aria-label="Business setup progress" style={{ height: 8, background: "var(--border, #ddd)", borderRadius: 8, overflow: "hidden" }}><div style={{ height: "100%", width: `${progress.required_steps ? progress.completed_required_steps / progress.required_steps * 100 : 100}%`, background: "var(--accent, #2563eb)" }} /></div>
        <ol style={{ paddingLeft: "1.25rem", marginTop: "1.25rem" }}>
          {progress.steps.map(step => <li key={step.key} style={{ marginBottom: ".9rem" }}>
            <span aria-label={step.complete ? "Complete" : "Incomplete"}>{step.complete ? "✓ " : "○ "}</span><strong>{step.label}</strong> <small>{step.complete ? "Saved" : "To do"}</small>
            {!step.complete && <> · <Link href={step.href} className="text-link">Continue</Link></>}
          </li>)}
        </ol>
        <div className="header-actions">{!progress.complete && <button className="button button-dark" type="button" onClick={() => void prepareBusiness()} disabled={preparing}>{preparing ? "Setting up your business…" : "Set up missing details"}</button>}<Link href={progress.resume_path} className="button button-dark">{progress.complete ? "Open my business" : "Continue setup"}</Link><Link href="/workspace" className="button button-soft">Switch business</Link></div>
      </>}
    </section>
  </AppShell>;
}
