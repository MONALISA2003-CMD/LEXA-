"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  assignMemberBranch, assignMemberRole, createRbacInvitation, unassignMemberBranch,
  getAuthSessions, getMe, getOrganizationBranches, getOrganizationSettings, getRbacMembers, getRbacRoles,
  revokeAuthSession, updateOrganizationSettings, updateRbacMember, restoreSession,
  type AuthMe, type AuthSession, type OrganizationBranch, type Role, type TenantMember, type TenantSettings,
} from "../../lib/api";

const defaultSettings = { timezone:"Africa/Kampala", locale:"en-UG", business_type:"", industry:"", fiscal_year_start_month:1 };

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-GB", { dateStyle:"medium", timeStyle:"short" }).format(new Date(value));
}

export default function AdministrationPage() {
  const router = useRouter();
  const [me, setMe] = useState<AuthMe | null>(null);
  const [settings, setSettings] = useState({ ...defaultSettings });
  const [branches, setBranches] = useState<OrganizationBranch[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [members, setMembers] = useState<TenantMember[]>([]);
  const [sessions, setSessions] = useState<AuthSession[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("");
  const [inviteResult, setInviteResult] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const canManage = useMemo(() => me?.roles.some(r => ["Owner", "Administrator", "Manager"].includes(r.name)), [me]);

  async function load() {
    setBusy(true); setError("");
    try {
      const session = await restoreSession();
      if (!session) { router.replace("/login"); return; }
      const [who, tenantSettings, branchRows, roleRows, memberRows, sessionRows] = await Promise.all([
        getMe(), getOrganizationSettings(), getOrganizationBranches(), getRbacRoles(), getRbacMembers(), getAuthSessions(),
      ]);
      setMe(who);
      setSettings({
        timezone: tenantSettings.timezone,
        locale: tenantSettings.locale,
        business_type: tenantSettings.business_type || "",
        industry: tenantSettings.industry || "",
        fiscal_year_start_month: tenantSettings.fiscal_year_start_month,
      });
      setBranches(branchRows); setRoles(roleRows); setMembers(memberRows); setSessions(sessionRows);
      if (!inviteRole && roleRows[0]) setInviteRole(roleRows.find(r => r.name === "Staff / Operator")?.id || roleRows[0].id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Administration data could not be loaded.");
    } finally { setBusy(false); }
  }

  useEffect(() => { void load(); }, []);

  async function saveSettings(event: FormEvent) {
    event.preventDefault(); setMessage(""); setError(""); setBusy(true);
    try {
      await updateOrganizationSettings(settings);
      setMessage("Workspace settings saved.");
    } catch (e) { setError(e instanceof Error ? e.message : "Settings could not be saved."); }
    finally { setBusy(false); }
  }

  async function changeMemberRole(membershipId:string, roleId:string) {
    setError("");
    try { await assignMemberRole(membershipId, roleId); setMembers(await getRbacMembers()); setMessage("Role updated."); }
    catch (e) { setError(e instanceof Error ? e.message : "Role could not be updated."); }
  }

  async function changeMemberStatus(member:TenantMember) {
    const next = member.status === "ACTIVE" ? "SUSPENDED" : "ACTIVE";
    setError("");
    try { await updateRbacMember(member.membership_id, next); setMembers(await getRbacMembers()); setMessage(`Membership set to ${next.toLowerCase()}.`); }
    catch (e) { setError(e instanceof Error ? e.message : "Membership status could not be changed."); }
  }

  async function setBranch(membershipId:string, branchId:string) {
    if (!branchId) return;
    setError("");
    try { await assignMemberBranch(membershipId, branchId); setMembers(await getRbacMembers()); setMessage("Branch assignment updated."); }
    catch (e) { setError(e instanceof Error ? e.message : "Branch assignment failed."); }
  }

  async function removeBranch(membershipId:string, branchId:string) {
    setError("");
    try {
      await unassignMemberBranch(membershipId, branchId);
      setMembers(await getRbacMembers()); setMessage("Branch assignment removed.");
    } catch (e) { setError(e instanceof Error ? e.message : "Branch assignment could not be removed."); }
  }

  async function invite(event:FormEvent) {
    event.preventDefault(); setError(""); setInviteResult(""); setBusy(true);
    try {
      const result = await createRbacInvitation({ email:inviteEmail.trim(), role_id:inviteRole || undefined });
      const url = `${window.location.origin}/invite?token=${encodeURIComponent(result.invitation_token)}`;
      setInviteResult(`Invite created for ${result.email}. Share this one-time invite link before ${formatDate(result.expires_at)}:\n${url}`);
      setInviteEmail("");
    } catch (e) { setError(e instanceof Error ? e.message : "Invitation could not be created."); }
    finally { setBusy(false); }
  }

  async function revoke(id:string) {
    setError("");
    try { await revokeAuthSession(id); setSessions(await getAuthSessions()); setMessage("Session revoked."); }
    catch (e) { setError(e instanceof Error ? e.message : "Session could not be revoked."); }
  }

  if (!me) return <main className="public-page"><section className="module-page"><span className="section-label">LEXA</span><h2>Loading administration…</h2>{error && <p className="auth-error" role="alert">{error}</p>}</section></main>;

  return <main className="workspace module-page admin-page">
    <div className="workspace-header">
      <div><span className="section-label">Administration</span><h1>{me.tenant?.name || "Workspace"}</h1><p>Identity, tenant controls, roles, branch access and active sessions.</p></div>
      <div className="header-actions"><button className="button button-soft" onClick={() => router.push("/")}>Back to workspace</button></div>
    </div>

    {message && <div className="inline-message" role="status">{message}</div>}
    {error && <div className="inline-message" role="alert">{error}</div>}

    <section className="admin-grid" id="settings">
      <article className="section admin-card">
        <div className="admin-card-head"><div><span className="section-label">Tenant</span><h2>Workspace settings</h2></div><span className="tag">{me.roles.map(r=>r.name).join(" · ") || "Member"}</span></div>
        <form className="command-form" onSubmit={saveSettings}>
          <div className="form-grid">
            <label>Time zone<input value={settings.timezone} onChange={e=>setSettings({...settings,timezone:e.target.value})} placeholder="Africa/Kampala" /></label>
            <label>Locale<input value={settings.locale} onChange={e=>setSettings({...settings,locale:e.target.value})} placeholder="en-UG" /></label>
          </div>
          <div className="form-grid">
            <label>Business type<input value={settings.business_type} onChange={e=>setSettings({...settings,business_type:e.target.value})} placeholder="Retail, services, wholesale…" /></label>
            <label>Industry<input value={settings.industry} onChange={e=>setSettings({...settings,industry:e.target.value})} placeholder="Industry" /></label>
          </div>
          <label>Fiscal year starts in month<input type="number" min="1" max="12" value={settings.fiscal_year_start_month} onChange={e=>setSettings({...settings,fiscal_year_start_month:Number(e.target.value)})} /></label>
          <button className="primary" disabled={busy}>Save workspace settings</button>
        </form>
      </article>

      <article className="section admin-card" id="invite">
        <div className="admin-card-head"><div><span className="section-label">Identity</span><h2>Invite a teammate</h2><p>Role templates are capability-based; permissions are enforced by the API and database policy.</p></div></div>
        <form className="command-form" onSubmit={invite}>
          <label>Email<input type="email" required value={inviteEmail} onChange={e=>setInviteEmail(e.target.value)} placeholder="teammate@example.com" /></label>
          <label>Role<select value={inviteRole} onChange={e=>setInviteRole(e.target.value)} required><option value="">Select role</option>{roles.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
          <button className="primary" disabled={busy}>Create invitation</button>
        </form>
        {inviteResult && <pre className="admin-invite-result">{inviteResult}</pre>}
      </article>
    </section>

    <section className="section admin-card" id="members">
      <div className="admin-card-head"><div><span className="section-label">Memberships</span><h2>People and access</h2></div><span className="tag">{members.length} members</span></div>
      {!members.length ? <div className="empty-inline">No tenant members are available.</div> : (
        <div className="table-wrap"><table><thead><tr><th>Person</th><th>Status</th><th>Role</th><th>Branches</th><th>Actions</th></tr></thead><tbody>
          {members.map(member => {
            const selectedRole = roles.find(role => member.roles.includes(role.name))?.id || "";
            const availableBranches = branches.filter(branch => !member.branch_ids.includes(branch.id));
            return (
              <tr key={member.membership_id}>
                <td><strong>{member.display_name || member.email}</strong><small>{member.email}</small></td>
                <td><span className={`status ${member.status === "ACTIVE" ? "good" : member.status === "SUSPENDED" ? "warn" : "danger"}`}>{member.status}</span></td>
                <td>
                  <select value={selectedRole} onChange={e=>changeMemberRole(member.membership_id,e.target.value)} disabled={!canManage || member.status === "REMOVED"}>
                    <option value="">Select role</option>{roles.map(role=><option key={role.id} value={role.id}>{role.name}</option>)}
                  </select>
                </td>
                <td>
                  <div className="admin-branch-stack">
                    {member.branch_ids.length ? member.branch_ids.map(id => {
                      const branch = branches.find(item => item.id === id);
                      return <span className="tag" key={id}>{branch?.name || id.slice(0,8)} <button type="button" className="admin-chip-remove" onClick={()=>removeBranch(member.membership_id,id)} disabled={!canManage} aria-label={`Remove ${branch?.name || "branch"}`}>×</button></span>;
                    }) : <small>All tenant branches</small>}
                    <select value="" onChange={e=>setBranch(member.membership_id,e.target.value)} disabled={!canManage || member.status !== "ACTIVE"}>
                      <option value="">Assign branch…</option>{availableBranches.map(branch=><option key={branch.id} value={branch.id}>{branch.name}</option>)}
                    </select>
                  </div>
                </td>
                <td><button type="button" className="secondary" onClick={()=>changeMemberStatus(member)} disabled={!canManage || member.status === "REMOVED"}>{member.status === "ACTIVE" ? "Suspend" : "Restore"}</button></td>
              </tr>
            );
          })}
        </tbody></table></div>
      )}
    </section>

    <section className="admin-grid">
      <article className="section admin-card">
        <div className="admin-card-head"><div><span className="section-label">Branches</span><h2>Current branch scope</h2><p>Branch assignments narrow access for a membership. Members without assignments retain tenant-wide branch access.</p></div></div>
        <div className="admin-branch-list">{branches.length ? branches.map(b=><div className="location-card" key={b.id}><span className="tag">{b.code}</span><h3>{b.name}</h3><small>{b.status}</small></div>) : <div className="empty-inline">No branches have been created yet.</div>}</div>
      </article>

      <article className="section admin-card">
        <div className="admin-card-head"><div><span className="section-label">Sessions</span><h2>Your active sessions</h2></div></div>
        <div className="admin-session-list">{sessions.map(s=><div className="workflow-row" key={s.id}><div><strong>{s.current ? "Current session" : (s.device_name || s.platform || "Browser session")}</strong><small>Created {formatDate(s.created_at)} · Expires {formatDate(s.expires_at)}</small></div><span className={`status ${s.revoked_at ? "danger" : "good"}`}>{s.revoked_at ? "REVOKED" : "ACTIVE"}</span>{!s.current && !s.revoked_at && <button className="secondary" onClick={()=>revoke(s.id)}>Revoke</button>}</div>)}{!sessions.length && <div className="empty-inline">No sessions found.</div>}</div>
      </article>
    </section>

    <section className="section admin-card admin-security-note"><span className="section-label">Security boundary</span><h2>Tenant data remains database-authorized</h2><p>LEXA sets the authenticated tenant and user context on each request. Tenant-owned records are protected by forced PostgreSQL row-level security; branch-aware tables additionally evaluate membership assignments.</p></section>
  </main>;
}
