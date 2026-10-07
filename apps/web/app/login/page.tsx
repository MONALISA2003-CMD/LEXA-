"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { login, setAccessToken, WorkspaceSelectionError, type WorkspaceChoice } from "../../lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [choices, setChoices] = useState<WorkspaceChoice[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      const session = await login({ email, password, tenant_id: workspace || undefined });
      setAccessToken(session.access_token);
      router.replace("/");
    } catch (e) {
      if (e instanceof WorkspaceSelectionError) { setChoices(e.workspaces); setError("Select the workspace you want to open."); }
      else setError(e instanceof Error ? e.message : "We could not sign you in.");
    } finally { setBusy(false); }
  }

  return <main className="public-page"><section className="public-cta" style={{minHeight:"100vh",display:"grid",placeItems:"center"}}><form className="command-form" onSubmit={submit} style={{width:"min(460px,100%)"}}><div><span className="section-label">LEXA</span><h2>Sign in to your workspace</h2><p>Use the email and password for your LEXA account.</p></div><label>Email<input type="email" value={email} onChange={e=>setEmail(e.target.value)} autoComplete="email" required /></label><label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password" required /></label>{choices.length>0&&<label>Workspace<select value={workspace} onChange={e=>setWorkspace(e.target.value)} required><option value="">Select workspace</option>{choices.map(c=><option key={c.tenant_id} value={c.tenant_id}>{c.tenant_name}</option>)}</select></label>}{error&&<p role="alert">{error}</p>}<button className="primary" disabled={busy}>{busy?"Signing in…":"Sign in"}</button><a className="text-link" href="/register">Create a workspace</a></form></section></main>;
}
