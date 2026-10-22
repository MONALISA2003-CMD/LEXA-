"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { login, register, setAccessToken, type RegisterRequest } from "../../lib/api";
import { FormField, StatusBanner } from "../../components/ui";

type CountryChoice = { code: string; name: string; currency: string; currencyName: string };
const countries: CountryChoice[] = [
  { code: "UG", name: "Uganda", currency: "UGX", currencyName: "Ugandan shilling" },
  { code: "KE", name: "Kenya", currency: "KES", currencyName: "Kenyan shilling" },
  { code: "TZ", name: "Tanzania", currency: "TZS", currencyName: "Tanzanian shilling" },
  { code: "RW", name: "Rwanda", currency: "RWF", currencyName: "Rwandan franc" },
  { code: "SS", name: "South Sudan", currency: "SSP", currencyName: "South Sudanese pound" },
];
const draftKey = "lexa-onboarding-draft-v1";
type SafeDraft = Pick<RegisterRequest, "email" | "tenant_name" | "country_code" | "currency_code" | "branch_name" | "warehouse_name" | "location_name">;

const initialDraft: SafeDraft = {
  email: "", tenant_name: "", country_code: "UG", currency_code: "UGX",
  branch_name: "Main branch", warehouse_name: "Main warehouse", location_name: "Main location",
};

export default function RegisterPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [draft, setDraft] = useState<SafeDraft>(initialDraft);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [workspaceCreated, setWorkspaceCreated] = useState(false);
  const registrationKey = useRef<string | null>(null);

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(draftKey);
      if (saved) {
        const parsed = JSON.parse(saved) as Partial<SafeDraft> & { step?: number };
        setDraft({ ...initialDraft, ...parsed });
        // Step 3 requires the password, which is intentionally never persisted; resume at the account step instead.
        if (typeof parsed.step === "number" && parsed.step >= 1 && parsed.step <= 3) setStep(Math.min(Math.floor(parsed.step), 2));
      }
    } catch {
      // Browser storage is optional; the form remains usable without it.
    } finally {
      setHydrated(true);
    }
  }, []);

  useEffect(() => {
    if (!hydrated || workspaceCreated) return;
    try {
      // Never persist the password or password confirmation in browser storage.
      sessionStorage.setItem(draftKey, JSON.stringify({ ...draft, step }));
    } catch {
      // Storage can be unavailable in private browsing; keep the in-memory draft.
    }
  }, [draft, step, hydrated, workspaceCreated]);

  function updateDraft<K extends keyof SafeDraft>(key: K, value: SafeDraft[K]) {
    registrationKey.current = null;
    setDraft(current => ({ ...current, [key]: value }));
    setError("");
  }

  function onCountryChange(code: string) {
    const choice = countries.find(item => item.code === code) || countries[0];
    registrationKey.current = null;
    setDraft(current => ({ ...current, country_code: choice.code, currency_code: choice.currency }));
    setError("");
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setError("");
    if (step === 1) { setStep(2); return; }
    if (step === 2) {
      if (password.length < 12) { setError("Use a password with at least 12 characters."); return; }
      if (password !== confirmPassword) { setError("The passwords do not match. Enter them again before continuing."); return; }
      setStep(3);
      return;
    }

    if (password.length < 12) { setStep(2); setError("Use a password with at least 12 characters to finish creating the workspace."); return; }
    if (password !== confirmPassword) { setStep(2); setError("The passwords do not match. Enter them again before continuing."); return; }

    setBusy(true);
    try {
      const request: RegisterRequest = { ...draft, email: draft.email.trim(), password };
      registrationKey.current ||= crypto.randomUUID();
      await register(request, registrationKey.current);
      setWorkspaceCreated(true);
      try { sessionStorage.removeItem(draftKey); } catch { /* optional cleanup */ }
      try {
        const session = await login({ email: request.email, password });
        setAccessToken(session.access_token);
        router.replace("/");
      } catch {
        setError("Your workspace was created, but automatic sign-in did not finish. Sign in with the account you just created; your setup has been saved.");
      }
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "We couldn't create your workspace. Check the details and try again.");
    } finally {
      setBusy(false);
    }
  }

  const country = countries.find(item => item.code === draft.country_code) || countries[0];
  const stepNames = ["Business", "Account", "Review"];

  return (
    <main className="auth-page">
      <section className="auth-story" aria-label="About LEXA">
        <div className="auth-story-brand"><span className="auth-story-brand-mark" aria-hidden="true">L</span><div><strong>LEXA</strong><small>Business workspace</small></div></div>
        <div className="auth-story-copy">
          <span className="auth-story-kicker">A strong start for your business</span>
          <h1>Set up the basics. Keep the rest manageable.</h1>
          <p>Create your business workspace with a starting branch and stock location. You can add teammates, products and other locations after signing in.</p>
          <div className="auth-story-promises"><span>Your first setup is saved together</span><span>Workspace defaults can be edited later</span><span>No business records are invented as sales or stock</span></div>
        </div>
        <div className="auth-story-foot">LEXA · Start with a clear foundation.</div>
      </section>

      <section className="auth-panel">
        <div className="auth-card">
          <header className="auth-card-heading"><span className="section-label">NEW WORKSPACE</span><h2>Create your LEXA workspace</h2><p>Three small steps. Your draft is kept in this browser session; your password is never saved to browser storage.</p></header>
          <div className="auth-stepper" aria-label={`Step ${step} of 3`}>
            {stepNames.map((name, index) => <div className={`auth-step ${step === index + 1 ? "active" : step > index + 1 ? "complete" : ""}`} key={name}><span>{step > index + 1 ? "✓" : index + 1}</span><b>{name}</b></div>)}
          </div>

          <form className="auth-form-v2" onSubmit={submit}>
            {error && <StatusBanner variant={workspaceCreated ? "success" : "error"} title={workspaceCreated ? "Workspace created" : step === 3 ? "Check your setup" : "We couldn't continue"}>{error}</StatusBanner>}

            {step === 1 && <>
              <FormField id="register-business" label="Business name" hint="Use the name your team recognises." required><input id="register-business" name="business" value={draft.tenant_name} onChange={event => updateDraft("tenant_name", event.target.value)} minLength={2} maxLength={200} autoComplete="organization" required /></FormField>
              <FormField id="register-country" label="Country" required><select id="register-country" name="country" value={draft.country_code} onChange={event => onCountryChange(event.target.value)} required>{countries.map(item => <option key={item.code} value={item.code}>{item.name}</option>)}</select></FormField>
              <FormField id="register-currency" label="Business currency" hint="Used for the initial business profile. You can review accounting settings later." required><select id="register-currency" name="currency" value={draft.currency_code} onChange={event => updateDraft("currency_code", event.target.value)} required>{countries.map(item => <option key={item.currency} value={item.currency}>{item.currency} · {item.currencyName}</option>)}</select></FormField>
              <div className="auth-onboarding-summary"><strong>Starting operating location</strong><span>Branch, warehouse and stock location are created together with your workspace.</span></div>
              <FormField id="register-branch" label="First branch" required><input id="register-branch" value={draft.branch_name} onChange={event => updateDraft("branch_name", event.target.value)} minLength={2} maxLength={200} required /></FormField>
              <FormField id="register-warehouse" label="First warehouse" required><input id="register-warehouse" value={draft.warehouse_name} onChange={event => updateDraft("warehouse_name", event.target.value)} minLength={2} maxLength={200} required /></FormField>
              <FormField id="register-location" label="Stock location" hint="For example, Main floor or Store room." required><input id="register-location" value={draft.location_name} onChange={event => updateDraft("location_name", event.target.value)} minLength={2} maxLength={200} required /></FormField>
            </>}

            {step === 2 && <>
              <FormField id="register-email" label="Owner email address" hint="Use an inbox you can access for account support." required><input id="register-email" type="email" value={draft.email} onChange={event => updateDraft("email", event.target.value)} autoComplete="email" inputMode="email" autoCapitalize="none" spellCheck={false} required /></FormField>
              <FormField id="register-password" label="Create password" hint="Use at least 12 characters." required><div className="auth-password-wrap"><input id="register-password" type={showPassword ? "text" : "password"} value={password} onChange={event => { setPassword(event.target.value); registrationKey.current = null; }} autoComplete="new-password" minLength={12} maxLength={256} required /><button type="button" className="auth-password-toggle" onClick={() => setShowPassword(value => !value)} aria-label={showPassword ? "Hide password" : "Show password"} aria-pressed={showPassword}>{showPassword ? "Hide" : "Show"}</button></div></FormField>
              <FormField id="register-confirm-password" label="Confirm password" required><input id="register-confirm-password" type={showPassword ? "text" : "password"} value={confirmPassword} onChange={event => { setConfirmPassword(event.target.value); setError(""); }} autoComplete="new-password" minLength={12} maxLength={256} required /></FormField>
              <div className="auth-onboarding-summary"><strong>Owner access</strong><span>The first account will be assigned the workspace Owner role. Add separate team members after setup.</span></div>
            </>}

            {step === 3 && <>
              <div className="auth-onboarding-summary"><strong>Business workspace</strong><span>{draft.tenant_name || "Business name not set"} · {country.name} · {draft.currency_code}</span></div>
              <div className="auth-onboarding-summary"><strong>Starting operations</strong><span>{draft.branch_name} → {draft.warehouse_name} → {draft.location_name}</span></div>
              <div className="auth-onboarding-summary"><strong>Workspace owner</strong><span>{draft.email || "Email address not set"}</span></div>
              <StatusBanner variant="info" title="Before you create the workspace">We will create the workspace, its Owner membership, business profile and starting stock location in one transaction. No sales or inventory quantities are created.</StatusBanner>
            </>}

            {workspaceCreated ? <Link className="button button-dark auth-submit" href="/login">Go to sign in</Link> : <div className="auth-nav-buttons">
              {step > 1 ? <button type="button" className="button button-soft" onClick={() => { setStep(current => current - 1); setError(""); }} disabled={busy}>Back</button> : <Link className="button button-soft" href="/login">Sign in instead</Link>}
              <button type="submit" className="button button-dark" disabled={busy}>{busy ? "Creating workspace…" : step === 3 ? "Create workspace" : "Continue"}</button>
            </div>}
          </form>
          {!workspaceCreated && <footer className="auth-form-footer">Already have an account? <Link href="/login">Sign in</Link><br /><span>Keep access details private. LEXA staff will never ask for your password.</span></footer>}
        </div>
      </section>
    </main>
  );
}
