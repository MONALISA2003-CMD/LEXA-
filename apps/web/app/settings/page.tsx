"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../components/app-shell";
import { BUSINESS_COUNTRIES as countries, BUSINESS_CURRENCIES as currencies } from "../../lib/business-options";
import {
  createBusinessProfile,
  getBusinessProfile,
  updateBusinessProfile,
  type BusinessProfile,
  userFacingError,
} from "../../lib/api";

type ProfileDraft = {
  legal_name: string;
  display_name: string;
  country_code: string;
  currency_code: string;
};

const emptyDraft: ProfileDraft = {
  legal_name: "",
  display_name: "",
  country_code: "UG",
  currency_code: "UGX",
};

export default function SettingsPage() {
  const [profile, setProfile] = useState<BusinessProfile | null>(null);
  const [draft, setDraft] = useState<ProfileDraft>(emptyDraft);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const saved = await getBusinessProfile();
      setProfile(saved);
      setDraft(saved ? {
        legal_name: saved.legal_name,
        display_name: saved.display_name,
        country_code: saved.country_code,
        currency_code: saved.currency_code,
      } : emptyDraft);
    } catch (reason) {
      setError(userFacingError(reason, "Your business details could not be loaded. Try again."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    const body: ProfileDraft = {
      legal_name: draft.legal_name.trim(),
      display_name: draft.display_name.trim(),
      country_code: draft.country_code.trim().toUpperCase(),
      currency_code: draft.currency_code.trim().toUpperCase(),
    };
    if (body.legal_name.length < 2 || body.display_name.length < 2) {
      setError("Enter both your registered business name and the name your customers know.");
      return;
    }
    if (!/^[A-Z]{2}$/.test(body.country_code) || !/^[A-Z]{3}$/.test(body.currency_code)) {
      setError("Check the country and currency codes before saving.");
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const saved = profile ? await updateBusinessProfile(body) : await createBusinessProfile(body);
      setProfile(saved);
      setDraft({ legal_name: saved.legal_name, display_name: saved.display_name, country_code: saved.country_code, currency_code: saved.currency_code });
      setSuccess("Your business details have been saved.");
    } catch (reason) {
      setError(userFacingError(reason, "Your details were not saved. Please try again."));
    } finally {
      setSaving(false);
    }
  }

  return <AppShell title="Settings" eyebrow="Your business">
    <main className="workspace" style={{ maxWidth: 1160 }}>
      <div className="workspace-header">
        <div>
          <span className="workspace-breadcrumb">LEXA · BUSINESS DETAILS</span>
          <h1>Settings</h1>
          <p>Keep your business name, country and currency correct for everyday work and reports.</p>
        </div>
        <div className="header-actions">
          <Link href="/onboarding" className="button button-soft">Business setup</Link>
          <button type="button" className="button button-soft" onClick={() => void load()} disabled={loading || saving}>Refresh</button>
        </div>
      </div>

      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {success && <div className="notice" role="status">{success}</div>}

      <section className="workspace-section">
        <div className="section-head">
          <div>
            <span className="section-label">BUSINESS PROFILE</span>
            <h2>{profile ? "Business details" : "Set up your business details"}</h2>
            <p>These details help LEXA present your business consistently across sales, stock and reports.</p>
          </div>
          {profile && <span className="status status-good" aria-label="Details saved">✓ Saved</span>}
        </div>
        {loading ? <p role="status">Loading your business details…</p> : <form onSubmit={save}>
          <div className="form-grid">
            <label htmlFor="settings-legal-name">Registered business name
              <input id="settings-legal-name" name="legal_name" autoComplete="organization" value={draft.legal_name} onChange={event => setDraft(current => ({ ...current, legal_name: event.target.value }))} maxLength={250} minLength={2} required />
            </label>
            <label htmlFor="settings-display-name">Display name
              <input id="settings-display-name" name="display_name" value={draft.display_name} onChange={event => setDraft(current => ({ ...current, display_name: event.target.value }))} maxLength={250} minLength={2} required />
            </label>
            <label htmlFor="settings-country">Country
              <select id="settings-country" name="country_code" autoComplete="country" value={draft.country_code} onChange={event => setDraft(current => ({ ...current, country_code: event.target.value }))} required>
                {!countries.some(country => country.code === draft.country_code) && draft.country_code && <option value={draft.country_code}>{draft.country_code} · saved country</option>}
                {countries.map(country => <option key={country.code} value={country.code}>{country.name}</option>)}
              </select>
            </label>
            <label htmlFor="settings-currency">Business currency
              <select id="settings-currency" name="currency_code" value={draft.currency_code} onChange={event => setDraft(current => ({ ...current, currency_code: event.target.value }))} required>
                {!currencies.some(currency => currency.code === draft.currency_code) && draft.currency_code && <option value={draft.currency_code}>{draft.currency_code} · saved currency</option>}
                {currencies.map(currency => <option key={currency.code} value={currency.code}>{currency.name} ({currency.code})</option>)}
              </select>
            </label>
          </div>
          <p className="muted">Currency is used when showing money in reports. Confirm it carefully before recording financial activity.</p>
          <div className="header-actions" style={{ justifyContent: "flex-end", marginTop: 20 }}>
            <button type="submit" className="button button-dark" disabled={saving || loading}>{saving ? "Saving…" : profile ? "Save changes" : "Save business details"}</button>
          </div>
        </form>}
      </section>

      <section className="workspace-section">
        <div className="section-head"><div><span className="section-label">KEEP THINGS IN ORDER</span><h2>Manage business settings</h2><p>Continue with the areas your team uses every day.</p></div></div>
        <div className="foundation-grid">
          <Link className="panel foundation-panel" href="/onboarding"><div className="panel-head"><div><h2>Business setup</h2><p>Review your branches, stock locations and required setup.</p></div><span aria-hidden="true">→</span></div></Link>
          <Link className="panel foundation-panel" href="/administration/members"><div className="panel-head"><div><h2>Team and access</h2><p>Manage team members and who can access the business.</p></div><span aria-hidden="true">→</span></div></Link>
          <Link className="panel foundation-panel" href="/settings/security"><div className="panel-head"><div><h2>Sign-in and security</h2><p>Review active sessions, sign out devices and recover your account.</p></div><span aria-hidden="true">→</span></div></Link>
          <Link className="panel foundation-panel" href="/reports"><div className="panel-head"><div><h2>Business reports</h2><p>Review performance using your saved business details.</p></div><span aria-hidden="true">→</span></div></Link>
        </div>
      </section>
    </main>
  </AppShell>;
}
