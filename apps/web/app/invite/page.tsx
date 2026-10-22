"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { acceptWorkspaceInvitation, previewWorkspaceInvitation,
  userFacingError,
} from "../../lib/api";

type Preview = { email: string; workspace_name: string; expires_at: string };
export default function InvitePage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    // The bearer token is accepted only in the URL fragment; fragments are not sent to the web server.
    // Remove it from the visible URL/history before making any network request.
    const fragment = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : "";
    const value = new URLSearchParams(fragment).get("token") || "";
    setToken(value);
    if (window.location.hash) window.history.replaceState(null, "", window.location.pathname);
    if (!value) { setError("This invitation link is missing its token. Ask the workspace owner to issue a new link."); setLoading(false); return () => { active = false; }; }
    void previewWorkspaceInvitation(value).then(result => { if (active) setPreview(result); })
      .catch(e => { if (active) setError(userFacingError(e, "This invitation is invalid or expired.")); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault(); if (busy || !token) return;
    setBusy(true); setError("");
    try { await acceptWorkspaceInvitation(token, password); router.replace("/"); router.refresh(); }
    catch (e) { setError(userFacingError(e, "The invitation could not be accepted.")); }
    finally { setBusy(false); }
  }
  return <main className="public-page"><section className="public-cta" style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: "1rem" }}><div className="command-form" style={{ width: "min(520px, 100%)" }}>
    <span className="section-label">LEXA · WORKSPACE INVITATION</span><h1>Join a workspace</h1>
    {loading ? <p role="status">Checking your invitation…</p> : preview ? <><p>You have been invited to <strong>{preview.workspace_name}</strong> as <strong>{preview.email}</strong>.</p><p><small>This link expires {new Date(preview.expires_at).toLocaleString()}. It can be accepted once and is bound to the invited email.</small></p><form onSubmit={submit} style={{ display: "grid", gap: "1rem" }}><label htmlFor="invite-password">Password <small>(use your current LEXA password if you already have an account)</small></label><input id="invite-password" type="password" autoComplete="current-password" minLength={12} maxLength={256} required value={password} onChange={event => setPassword(event.target.value)} /><button type="submit" className="primary" disabled={busy}>{busy ? "Accepting invitation…" : "Accept invitation"}</button></form></> : <p>This invitation cannot be used. Ask the workspace owner to resend it.</p>}
    {error && <p role="alert" className="notice notice-error">{error}</p>}<p style={{ marginTop: "1rem" }}><Link href="/login">Back to sign in</Link></p>
  </div></section></main>;
}
