"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { acceptInvitation } from "../../lib/api";

export default function InvitePage() {
  const params = useSearchParams();
  const router = useRouter();
  const [token, setToken] = useState(params.get("token") || "");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const canSubmit = useMemo(() => token.trim().length >= 20 && password.length >= 12, [token,password]);

  async function submit(event:FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      await acceptInvitation({ token:token.trim(), password, display_name:displayName.trim() || undefined });
      setMessage("Invitation accepted. Sign in to open the workspace.");
      setTimeout(() => router.replace("/login"), 700);
    } catch (e) { setError(e instanceof Error ? e.message : "Invitation could not be accepted."); }
    finally { setBusy(false); }
  }

  return <main className="public-page"><section className="public-cta" style={{minHeight:"100vh",display:"grid",placeItems:"center"}}><form className="command-form" onSubmit={submit} style={{width:"min(520px,100%)"}}>
    <div><span className="section-label">LEXA</span><h2>Join your workspace</h2><p>Accept your invitation, choose a password, and your membership will be activated in the invited workspace.</p></div>
    <label>Invitation token<input value={token} onChange={e=>setToken(e.target.value)} required autoComplete="off" /></label>
    <label>Display name<input value={displayName} onChange={e=>setDisplayName(e.target.value)} autoComplete="name" placeholder="Your name" /></label>
    <label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required minLength={12} autoComplete="new-password" /><small>Use at least 12 characters. Existing accounts must enter their current password.</small></label>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    <button className="primary" disabled={busy || !canSubmit}>{busy ? "Joining…" : "Accept invitation"}</button>
    <a className="text-link" href="/login">Back to sign in</a>
  </form></section></main>;
}
