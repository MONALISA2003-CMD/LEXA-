"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { ApiError, requestPasswordReset, userFacingError } from "../../lib/api";
import { FormField, StatusBanner } from "../../components/ui";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await requestPasswordReset(email.trim());
      setSubmitted(true);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 503) {
        setError("Password reset email is temporarily unavailable. Please contact LEXA support or your business administrator.");
      } else {
        setError(userFacingError(reason, "We couldn't submit the request. Please try again."));
      }
    } finally {
      setBusy(false);
    }
  }

  return <main className="auth-page">
    <section className="auth-story" aria-label="About LEXA">
      <div className="auth-story-brand"><img className="auth-story-logo" src="/lexa-mark.svg" alt=""/><div><strong>LEXA</strong><small>Your business, clearly.</small></div></div>
      <div className="auth-story-copy"><span className="auth-story-kicker">ACCOUNT RECOVERY</span><h1>Get back to business.</h1><p>We’ll help you recover access safely. Reset links expire and can only be used once.</p><div className="auth-story-promises"><span>Your password stays private</span><span>Reset links expire quickly</span><span>Other sessions are signed out after a reset</span></div></div>
      <div className="auth-story-foot">LEXA · Your business, more clearly.</div>
    </section>
    <section className="auth-panel"><div className="auth-card">
      <header className="auth-card-heading"><span className="section-label">PASSWORD RECOVERY</span><h2>Forgot your password?</h2><p>Enter the email associated with your LEXA account.</p></header>
      {error && <StatusBanner variant="error" title="Request not submitted">{error}</StatusBanner>}
      {submitted ? <div className="auth-form-v2"><StatusBanner variant="success" title="Check your email">If an active account matches that address, password reset instructions will be sent. Check your spam folder too.</StatusBanner><Link className="button button-dark auth-submit auth-link-button" href="/login">Back to sign in</Link></div> : <form className="auth-form-v2" onSubmit={submit}>
        <FormField id="forgot-email" label="Email address" required><input id="forgot-email" name="email" type="email" value={email} onChange={event => setEmail(event.target.value)} autoComplete="email" autoCapitalize="none" spellCheck={false} inputMode="email" maxLength={320} required /></FormField>
        <button className="button button-dark auth-submit" type="submit" disabled={busy}>{busy ? "Submitting…" : "Send reset instructions"}</button>
      </form>}
      <footer className="auth-form-footer"><Link href="/login">Return to sign in</Link></footer>
    </div></section>
  </main>;
}
