"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AppShell } from "../../components/app-shell";
import { getWorkspaceOptions, selectWorkspace, type WorkspaceOption,
  userFacingError,
} from "../../lib/api";

export default function WorkspacePage() {
  const router = useRouter();
  const [items, setItems] = useState<WorkspaceOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void getWorkspaceOptions().then(result => { if (active) setItems(result.items); })
      .catch(e => { if (active) setError(userFacingError(e, "Could not load your workspaces.")); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  async function choose(item: WorkspaceOption) {
    if (item.current || busyId) return;
    setBusyId(item.tenant_id); setError("");
    try {
      await selectWorkspace(item.tenant_id);
      router.replace("/");
      router.refresh();
    } catch (e) {
      setError(userFacingError(e, "LEXA could not switch workspaces."));
    } finally { setBusyId(""); }
  }

  return <AppShell title="Switch business" eyebrow="Your businesses">
    <section className="panel" style={{ padding: "1.25rem", maxWidth: 860 }}>
      <div className="panel-head"><div><p className="eyebrow">YOUR BUSINESSES</p><h2>Choose where to work</h2></div></div>
      <p>Only businesses you have access to appear here.</p>
      {error && <div className="notice notice-error" role="alert">{error}</div>}
      {loading ? <p role="status">Loading your businesses…</p> : items.length === 0 ? <div className="empty-state"><strong>No business is available yet</strong><span>Ask the business owner to invite you.</span><Link href="/login" className="button button-soft">Return to sign in</Link></div> : <div className="workspace-choice-list">
        {items.map(item => <article key={item.tenant_id} className="workspace-choice" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", padding: "1rem 0", borderBottom: "1px solid var(--border, #ddd)" }}>
          <div><strong>{item.tenant_name}</strong><div><small>{item.current ? "Current business" : "Available to you"}</small></div></div>
          <button className="button button-dark" type="button" disabled={item.current || Boolean(busyId)} onClick={() => void choose(item)}>{busyId === item.tenant_id ? "Switching…" : item.current ? "Current" : "Open business"}</button>
        </article>)}
      </div>}
      <p style={{ marginTop: "1rem" }}><Link href="/onboarding" className="text-link">Finish business setup →</Link></p>
    </section>
  </AppShell>;
}
