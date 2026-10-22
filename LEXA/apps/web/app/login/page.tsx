"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { login, setAccessToken, WorkspaceSelectionError, type WorkspaceChoice } from "../../lib/api";
import { FormField, StatusBanner } from "../../components/ui";
import { safeReturnPath as resolveSafeReturnPath } from "../../lib/navigation.mjs";

function safeReturnPath() {
  const next = new URLSearchParams(window.location.search).get("next");
  return resolveSafeReturnPath(next, window.location.origin);
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [choices, setChoices] = useState<WorkspaceChoice[]>([]);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const session = await login({ email: email.trim(), password, tenant_id: workspace || undefined });
      setAccessToken(session.access_token);
      router.replace(safeReturnPath());
    } catch (e) {
      if (e instanceof WorkspaceSelectionError) {
        setChoices(e.workspaces);
        setError(e.workspaces.length ? "Choose which business to open." : "This account is not linked to an active business. Ask the business owner for help.");
      } else {
        setError(e instanceof Error ? e.message : "We could not sign you in. Check your details and try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-story" aria-label="About LEXA">
        <div className="auth-story-brand"><img className="auth-story-logo" src="/lexa-mark.svg" alt=""/><div><strong>LEXA</strong><small>Your business, clearly.</small></div></div>
        <div className="auth-story-copy">
          <span className="auth-story-kicker">One clear view of your business</span>
          <h1>Spend less time finding the answer.</h1>
          <p>Sales, stock, customers and money records stay together in one place. Sign in to continue.</p>
          <div className="auth-story-promises"><span>Your records stay together</span><span>Only the right people can open them</span><span>Clear messages when something needs attention</span></div>
        </div>
        <div className="auth-story-foot">LEXA · Your business, more clearly.</div>
      </section>

      <section className="auth-panel">
        <div className="auth-card">
          <header className="auth-card-heading"><span className="section-label">WELCOME BACK</span><h2>Sign in to LEXA</h2><p>Use the email and password you chose when you created your account.</p></header>
          <form className="auth-form-v2" onSubmit={submit}>
            {error && <StatusBanner variant="error" title={choices.length ? "Choose a business" : "We couldn't sign you in"}>{error}</StatusBanner>}
            <FormField id="login-email" label="Email address" required>
              <input id="login-email" name="email" type="email" value={email} onChange={event => setEmail(event.target.value)} autoComplete="username" inputMode="email" autoCapitalize="none" spellCheck={false} required aria-invalid={Boolean(error && !choices.length)} />
            </FormField>
            <FormField id="login-password" label="Password" required>
              <div className="auth-password-wrap"><input id="login-password" name="password" type={showPassword ? "text" : "password"} value={password} onChange={event => setPassword(event.target.value)} autoComplete="current-password" required aria-invalid={Boolean(error && !choices.length)} /><button type="button" className="auth-password-toggle" onClick={() => setShowPassword(value => !value)} aria-label={showPassword ? "Hide password" : "Show password"} aria-pressed={showPassword}>{showPassword ? "Hide" : "Show"}</button></div>
            </FormField>
            {choices.length > 0 && <div className="auth-workspace-select"><label htmlFor="login-workspace">Business</label><select id="login-workspace" value={workspace} onChange={event => setWorkspace(event.target.value)} required><option value="">Select a business</option>{choices.map(choice => <option key={choice.tenant_id} value={choice.tenant_id}>{choice.tenant_name}</option>)}</select></div>}
            <button className="button button-dark auth-submit" type="submit" disabled={busy}>{busy ? "Checking your details…" : choices.length ? "Continue to business" : "Sign in"}</button>
          </form>
          <footer className="auth-form-footer">New to LEXA? <Link href="/register">Create a business account</Link><br /><span>For account access help, contact the business owner.</span></footer>
        </div>
      </section>
    </main>
  );
}
