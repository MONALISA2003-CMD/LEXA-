"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../components/app-shell";
import { getSetupProgress, type SetupProgress } from "../../lib/api";

export default function OnboardingPage() {
  const [progress, setProgress] = useState<SetupProgress | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setProgress(await getSetupProgress()); }
    catch (e) { setProgress(null); setError(e instanceof Error ? e.message : "Setup progress could not be verified."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  return <AppShell title="Workspace setup" eyebrow="Resume where you left off">
    <section className="panel" style={{ maxWidth: 850, padding: "1.25rem" }}>
      <div className="panel-head"><div><p className="eyebrow">BUSINESS SETUP</p><h2>{progress?.complete ? "The required setup is complete" : "Set up your workspace"}</h2></div></div>
      <p>LEXA derives progress from your saved business profile, branches, warehouses and stock locations. Refreshing this page will not lose completed steps.</p>
      {loading && <p role="status">Checking saved setup…</p>}
      {error && <div className="notice notice-error" role="alert">{error}<button className="button button-soft" type="button" onClick={() => void load()}>Retry</button></div>}
      {progress && <>
        <p><strong>{progress.completed_required_steps} of {progress.required_steps}</strong> required steps complete</p>
        <div role="progressbar" aria-valuemin={0} aria-valuemax={progress.required_steps} aria-valuenow={progress.completed_required_steps} aria-label="Required workspace setup progress" style={{ height: 8, background: "var(--border, #ddd)", borderRadius: 8, overflow: "hidden" }}><div style={{ height: "100%", width: `${progress.required_steps ? progress.completed_required_steps / progress.required_steps * 100 : 100}%`, background: "var(--accent, #2563eb)" }} /></div>
        <ol style={{ paddingLeft: "1.25rem", marginTop: "1.25rem" }}>
          {progress.steps.map(step => <li key={step.key} style={{ marginBottom: ".9rem" }}>
            <span aria-label={step.complete ? "Complete" : "Incomplete"}>{step.complete ? "✓ " : "○ "}</span><strong>{step.label}</strong> <small>{step.complete ? "Saved" : "Needs attention"}</small>
            {!step.complete && <> · <Link href={step.href} className="text-link">Continue</Link></>}
          </li>)}
        </ol>
        <div className="header-actions"><Link href={progress.resume_path} className="button button-dark">{progress.complete ? "Open workspace" : "Resume setup"}</Link><Link href="/workspace" className="button button-soft">Switch workspace</Link></div>
      </>}
    </section>
  </AppShell>;
}
