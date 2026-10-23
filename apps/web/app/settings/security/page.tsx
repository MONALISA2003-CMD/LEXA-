"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../../components/app-shell";
import { getMyAuthSessions, revokeMyAuthSession, userFacingError, type ActiveAuthSession } from "../../../lib/api";

function formatDate(value?: string | null) {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not available" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export default function SecuritySessionsPage() {
  const [sessions, setSessions] = useState<ActiveAuthSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [revoking, setRevoking] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try { const result = await getMyAuthSessions(); setSessions(result.items); }
    catch (reason) { setError(userFacingError(reason, "Your active sessions could not be loaded.")); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function revoke(session: ActiveAuthSession) {
    if (session.is_current || revoking) return;
    if (!window.confirm(`Sign out ${session.device_name} from this workspace?`)) return;
    setRevoking(session.id); setError(""); setSuccess("");
    try {
      await revokeMyAuthSession(session.id);
      setSessions(current => current.filter(item => item.id !== session.id));
      setSuccess("That session has been signed out.");
    } catch (reason) { setError(userFacingError(reason, "That session could not be revoked. Refresh and try again.")); }
    finally { setRevoking(null); }
  }

  return <AppShell title="Sign-in and security" eyebrow="Account security"><main className="workspace" style={{ maxWidth: 1160 }}>
    <div className="workspace-header"><div><span className="workspace-breadcrumb">LEXA · ACCOUNT SECURITY</span><h1>Sign-in and security</h1><p>Review the active sessions connected to your current business workspace.</p></div><div className="header-actions"><Link className="button button-soft" href="/settings">Back to settings</Link><button type="button" className="button button-soft" onClick={() => void load()} disabled={loading || Boolean(revoking)}>Refresh sessions</button></div></div>
    {error && <div className="notice notice-error" role="alert">{error}</div>}
    {success && <div className="notice" role="status">{success}</div>}
    <section className="workspace-section"><div className="section-head"><div><span className="section-label">ACTIVE SESSIONS</span><h2>{sessions.length} active {sessions.length === 1 ? "session" : "sessions"}</h2><p>Signing out a session revokes it immediately. Your current session is protected from accidental revocation here.</p></div></div>
      {loading ? <p role="status">Loading active sessions…</p> : sessions.length === 0 ? <div className="empty-state"><h3>No active sessions found</h3><p>Refresh this page or sign in again if the list looks wrong.</p></div> : <div className="security-session-list">{sessions.map(session => <article className="panel security-session" key={session.id}><div className="security-session-main"><div className="security-session-icon" aria-hidden="true">{session.is_current ? "✓" : "↗"}</div><div><h3>{session.device_name}{session.is_current && <span className="status status-good security-current-pill">This device</span>}</h3><p>{session.platform || "Platform not reported"}</p><dl><div><dt>Last activity</dt><dd>{formatDate(session.last_used_at || session.created_at)}</dd></div><div><dt>Created</dt><dd>{formatDate(session.created_at)}</dd></div><div><dt>Expires</dt><dd>{formatDate(session.expires_at)}</dd></div></dl></div></div>{!session.is_current && <button type="button" className="button button-soft button-danger-soft" onClick={() => void revoke(session)} disabled={Boolean(revoking)}>{revoking === session.id ? "Signing out…" : "Sign out this session"}</button>}</article>)}</div>}
    </section>
    <section className="workspace-section"><div className="section-head"><div><span className="section-label">PASSWORD</span><h2>Need a new password?</h2><p>Use a one-time reset link. Changing your password signs active sessions out across your account.</p></div><Link className="button button-soft" href="/forgot-password">Reset password</Link></div></section>
  </main></AppShell>;
}
