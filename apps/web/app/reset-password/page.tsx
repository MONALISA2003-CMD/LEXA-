"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, completePasswordReset, userFacingError } from "../../lib/api";
import { FormField, StatusBanner } from "../../components/ui";

export default function ResetPasswordPage() {
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [complete, setComplete] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    // Tokens are delivered in the URL fragment, which browsers do not send to
    // the server. Remove it from the address bar as soon as it is read.
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const received = params.get("token") || "";
    setToken(received);
    if (received) window.history.replaceState({}, document.title, window.location.pathname + window.location.search);
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setError("");
    if (!token) { setError("This reset link is missing or has expired. Request a new one."); return; }
    if (password.length < 12) { setError("Use at least 12 characters for your new password."); return; }
    if (password !== confirmPassword) { setError("The passwords do not match."); return; }
    setBusy(true);
    try {
      await completePasswordReset(token, password);
      setComplete(true);
      setPassword("");
      setConfirmPassword("");
      setToken("");
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 400) setError("This reset link is invalid or expired. Request a new one.");
      else setError(userFacingError(reason, "Your password could not be reset. Request a new link and try again."));
    } finally {
      setBusy(false);
    }
  }

  return <main className="auth-page"><meta name="referrer" content="no-referrer" />
    <section className="auth-story" aria-label="About LEXA"><div className="auth-story-brand"><img className="auth-story-logo" src="/lexa-mark.svg" alt=""/><div><strong>LEXA</strong><small>Your business, clearly.</small></div></div><div className="auth-story-copy"><span className="auth-story-kicker">SECURE YOUR ACCOUNT</span><h1>A stronger password. A fresh start.</h1><p>Choose a password only you know. For your protection, LEXA will sign out existing sessions after a successful reset.</p><div className="auth-story-promises"><span>At least 12 characters</span><span>Reset link can be used once</span><span>Existing sessions are revoked</span></div></div><div className="auth-story-foot">LEXA · Your business, more clearly.</div></section>
    <section className="auth-panel"><div className="auth-card"><header className="auth-card-heading"><span className="section-label">NEW PASSWORD</span><h2>{complete ? "Password updated" : "Create a new password"}</h2><p>{complete ? "Your password is changed. Sign in again on your devices." : "Choose a strong password with at least 12 characters."}</p></header>
      {error && <StatusBanner variant="error" title="Could not reset password">{error}</StatusBanner>}
      {complete ? <div className="auth-form-v2"><StatusBanner variant="success" title="You're ready to sign in">For your security, all active sessions for this account have been revoked.</StatusBanner><Link className="button button-dark auth-submit auth-link-button" href="/login">Back to sign in</Link></div> : <form className="auth-form-v2" onSubmit={submit}>
        {!token && <StatusBanner variant="warning" title="Reset link required">Open the most recent reset link from your email, or request a new one below.</StatusBanner>}
        <FormField id="reset-password" label="New password" hint="Use 12–256 characters." required><input id="reset-password" name="new-password" type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="new-password" minLength={12} maxLength={256} required disabled={!token} /></FormField>
        <FormField id="reset-confirm-password" label="Confirm new password" required><input id="reset-confirm-password" name="confirm-password" type="password" value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} autoComplete="new-password" minLength={12} maxLength={256} required disabled={!token} /></FormField>
        <button className="button button-dark auth-submit" type="submit" disabled={busy || !token}>{busy ? "Updating password…" : "Update password"}</button>
      </form>}
      <footer className="auth-form-footer"><Link href="/forgot-password">Request a new reset link</Link> · <Link href="/login">Sign in</Link></footer>
    </div></section>
  </main>;
}
