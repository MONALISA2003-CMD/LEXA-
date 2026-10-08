"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { login, register, setAccessToken } from "../../lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [business, setBusiness] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await register({ email, password, tenant_name: business });
      const session = await login({ email, password });
      setAccessToken(session.access_token);
      router.replace("/");
    } catch (e) { setError(e instanceof Error ? e.message : "We could not create your workspace."); }
    finally { setBusy(false); }
  }

  return <main className="public-page"><section className="public-cta" style={{minHeight:"100vh",display:"grid",placeItems:"center"}}><form className="command-form" onSubmit={submit} style={{width:"min(460px,100%)"}}><div><span className="section-label">LEXA</span><h2>Create your workspace</h2><p>Start with the core business identity. You can configure the rest inside LEXA.</p></div><label>Business name<input value={business} onChange={e=>setBusiness(e.target.value)} required minLength={2} maxLength={200} /></label><label>Email<input type="email" value={email} onChange={e=>setEmail(e.target.value)} autoComplete="email" required /></label><label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="new-password" minLength={12} required /><small>Use at least 12 characters.</small></label>{error&&<p role="alert">{error}</p>}<button className="primary" disabled={busy}>{busy?"Creating…":"Create workspace"}</button><a className="text-link" href="/login">Already have a workspace?</a></form></section></main>;
}
