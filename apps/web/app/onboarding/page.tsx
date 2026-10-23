"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../components/app-shell";
import { getSetupProgress, initializeWorkspaceSetup, type SetupProgress,
  userFacingError,
} from "../../lib/api";

export default function OnboardingPage() {
  const [progress, setProgress] = useState<SetupProgress | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [preparing, setPreparing] = useState(false);
  const [message, setMessage] = useState("");
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setProgress(await getSetupProgress()); }
    catch (e) { setProgress(null); setError(userFacingError(e, "Setup progress could not be verified.")); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  async function prepareBusiness() {
    if (preparing) return;
    setPreparing(true); setError(""); setMessage("");
    try { const result = await initializeWorkspaceSetup(); setMessage(result.message); setProgress(result.progress); }
    catch (e) { setError(userFacingError(e, "We couldn't finish setting up your business. Please try again.")); }
    finally { setPreparing(false); }
  }
  return <AppShell title="Business setup" eyebrow="Let’s get your business ready">
    <section className="panel" style={{ maxWidth: 850, padding: "1.25rem" }}>
      <div className="panel-head"><div><p className="eyebrow">BUSINESS SETUP</p><h2>{progress?.complete ? "Your business is ready for day-to-day work" : "Set up your business"}</h2><p className="muted">We verify the saved settings used by checkout, inventory and finance. A step is only complete when the matching configuration is present.</p></div></div>
      <p>We’ll check your business details, stock location, payment method and basic money records so sales, stock and reports work together.</p>
      {loading && <p role="status">Checking your business setup…</p>}
      {message && <div className="notice notice-success" role="status">{message}</div>}
      {error && <div className="notice notice-error" role="alert">{error}<button className="button button-soft" type="button" onClick={() => void load()}>Retry</button></div>}
      {progress && <>
        <p><strong>{progress.completed_required_steps} of {progress.required_steps}</strong> required steps complete</p>
        <div role="progressbar" aria-valuemin={0} aria-valuemax={progress.required_steps} aria-valuenow={progress.completed_required_steps} aria-label="Required business setup progress" style={{ height: 8, background: "var(--border, #ddd)", borderRadius: 8, overflow: "hidden" }}><div style={{ height: "100%", width: `${progress.required_steps ? progress.completed_required_steps / progress.required_steps * 100 : 100}%`, background: "var(--accent, #2563eb)" }} /></div>
        <ol className="setup-checklist" style={{ paddingLeft: "1.25rem", marginTop: "1.25rem" }}>
          {progress.steps.filter(step => step.required).map(step => <li key={step.key} className={step.complete ? "setup-checklist-complete" : "setup-checklist-incomplete"} style={{ marginBottom: ".9rem" }}>
            <span aria-label={step.complete ? "Complete" : "Incomplete"}>{step.complete ? "✓ " : "○ "}</span><strong>{step.label}</strong> <small>{step.complete ? "Verified" : "Needs attention"}</small>
            {!step.complete && <> · <Link href={step.href} className="text-link">Continue</Link></>}
          </li>)}
        </ol>
        <section className="workspace-section" aria-labelledby="setup-recommended-heading" style={{ marginTop: "1.25rem" }}>
          <div className="section-head"><div><span className="section-label">RECOMMENDED CHECKS</span><h2 id="setup-recommended-heading">Review before you grow</h2><p>These checks do not block basic work, but they help keep tax and team settings clear.</p></div></div>
          <div className="foundation-grid">
            {progress.steps.filter(step => !step.required).map(step => <Link key={step.key} className="panel foundation-panel" href={step.href}>
              <div className="panel-head"><div><h2>{step.label}</h2><p>{step.key === "tax_configuration" ? "Confirm that the right current default tax rule is configured for your business, or review what applies to you." : "Check active team members, roles and access to business records."}</p><small className={step.complete ? "status status-good" : "status status-warn"}>{step.complete ? "Configured" : "Review recommended"}</small></div><span aria-hidden="true">→</span></div>
            </Link>)}
          </div>
        </section>
        <div className="header-actions">{!progress.complete && <button className="button button-dark" type="button" onClick={() => void prepareBusiness()} disabled={preparing}>{preparing ? "Setting up your business…" : "Set up missing details"}</button>}<Link href={progress.resume_path} className="button button-dark">{progress.complete ? "Open my business" : "Continue setup"}</Link><Link href="/workspace" className="button button-soft">Switch business</Link></div>
      </>}
    </section>
  </AppShell>;
}
