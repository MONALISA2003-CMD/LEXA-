"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../../components/app-shell";
import {
  createWorkspaceInvitation, createWorkspaceRole, getBranches, getWorkspaceInvitations, getWorkspaceMembers,
  getWorkspaceRolePermissionCatalog, getWorkspaceRoles, replaceWorkspaceMemberBranches, replaceWorkspaceMemberRoles,
  replaceWorkspaceRolePermissions, resendWorkspaceInvitation,
  revokeWorkspaceInvitation, updateWorkspaceMemberStatus,
  type Branch, type WorkspaceInvitation, type WorkspaceMember, type WorkspacePermission, type WorkspaceRole,
} from "../../../lib/api";

export default function MembersAdminPage() {
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [invitations, setInvitations] = useState<WorkspaceInvitation[]>([]);
  const [roles, setRoles] = useState<WorkspaceRole[]>([]);
  const [permissions, setPermissions] = useState<WorkspacePermission[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [email, setEmail] = useState("");
  const [roleId, setRoleId] = useState("");
  const [inviteBranchIds, setInviteBranchIds] = useState<string[]>([]);
  const [days, setDays] = useState("7");
  const [memberBranchDrafts, setMemberBranchDrafts] = useState<Record<string, string[]>>({});
  const [memberRoleDrafts, setMemberRoleDrafts] = useState<Record<string, string[]>>({});
  const [rolePermissionDrafts, setRolePermissionDrafts] = useState<Record<string, string[]>>({});
  const [newRoleName, setNewRoleName] = useState("");
  const [newRoleDescription, setNewRoleDescription] = useState("");
  const [lastInviteUrl, setLastInviteUrl] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [memberResult, inviteResult, roleResult, branchResult, rolePermissionCatalog] = await Promise.all([
        getWorkspaceMembers(), getWorkspaceInvitations(), getWorkspaceRoles(), getBranches(), getWorkspaceRolePermissionCatalog(),
      ]);
      setMembers(memberResult.items); setInvitations(inviteResult.items); setRoles(roleResult); setBranches(branchResult);
      setPermissions(rolePermissionCatalog.permissions);
      setRolePermissionDrafts(Object.fromEntries(rolePermissionCatalog.roles.map(role => [role.id, role.permission_ids])));
      setMemberBranchDrafts(Object.fromEntries(memberResult.items.map(member => [member.id, member.branch_ids])));
      setMemberRoleDrafts(Object.fromEntries(memberResult.items.map(member => [member.id, member.roles.map(role => role.id)])));
      setRoleId(current => current && roleResult.some(role => role.id === current) ? current : roleResult.find(role => role.name.toLowerCase() !== "owner")?.id || roleResult[0]?.id || "");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Team access could not be loaded. No changes are available until it can be verified.");
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  function toggleBranch(value: string, values: string[], setValues: (next: string[]) => void) {
    setValues(values.includes(value) ? values.filter(item => item !== value) : [...values, value]);
  }

  async function invite(event: FormEvent) {
    event.preventDefault(); if (busy || !roleId) return;
    setBusy(true); setError(""); setMessage(""); setLastInviteUrl("");
    try {
      const result = await createWorkspaceInvitation({ email: email.trim(), role_id: roleId, branch_ids: inviteBranchIds, expires_in_days: Number(days) });
      setMessage(result.message || (result.replayed ? "The previous invitation was already created." : "Invitation created. Share the one-time link privately; it is not retained by LEXA."));
      if (result.invite_url) setLastInviteUrl(`${window.location.origin}${result.invite_url}`);
      setEmail(""); setInviteBranchIds([]);
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Invitation could not be created."); }
    finally { setBusy(false); }
  }

  async function saveBranches(member: WorkspaceMember) {
    setBusy(true); setError(""); setMessage("");
    try { await replaceWorkspaceMemberBranches(member.id, memberBranchDrafts[member.id] || []); setMessage(`Branch assignments saved for ${member.email}.`); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Branch assignments could not be saved."); }
    finally { setBusy(false); }
  }

  async function createRole(event: FormEvent) {
    event.preventDefault(); if (busy || !newRoleName.trim()) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const role = await createWorkspaceRole({ name: newRoleName.trim(), description: newRoleDescription.trim() || undefined });
      setNewRoleName(""); setNewRoleDescription(""); setMessage(`Role “${role.name}” created. Assign only the permissions this role needs.`); await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Role could not be created."); }
    finally { setBusy(false); }
  }

  async function saveRolePermissions(role: WorkspaceRole) {
    if (role.name.trim().toLowerCase() === "owner") return;
    setBusy(true); setError(""); setMessage("");
    try {
      await replaceWorkspaceRolePermissions(role.id, rolePermissionDrafts[role.id] || []);
      setMessage(`Permissions saved for role ${role.name}.`); await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Role permissions could not be saved."); }
    finally { setBusy(false); }
  }

  async function saveRoles(member: WorkspaceMember) {
    const selected = memberRoleDrafts[member.id] || [];
    if (selected.length === 0) { setError("Assign at least one role or deactivate the membership."); return; }
    setBusy(true); setError(""); setMessage("");
    try {
      await replaceWorkspaceMemberRoles(member.id, selected);
      setMessage(`Roles saved for ${member.email}.`);
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Role assignments could not be saved."); }
    finally { setBusy(false); }
  }

  async function changeStatus(member: WorkspaceMember, status: "ACTIVE" | "INACTIVE") {
    setBusy(true); setError(""); setMessage("");
    try { await updateWorkspaceMemberStatus(member.id, status); setMessage(`Membership for ${member.email} is now ${status.toLowerCase()}.`); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Membership status could not be changed."); }
    finally { setBusy(false); }
  }

  async function resend(invitation: WorkspaceInvitation) {
    setBusy(true); setError(""); setMessage(""); setLastInviteUrl("");
    try { const result = await resendWorkspaceInvitation(invitation.id); setMessage(result.message || "A fresh invite link was issued. The previous token has been invalidated."); if (result.invite_url) setLastInviteUrl(`${window.location.origin}${result.invite_url}`); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Invitation could not be resent."); }
    finally { setBusy(false); }
  }

  async function revoke(invitation: WorkspaceInvitation) {
    setBusy(true); setError(""); setMessage("");
    try { await revokeWorkspaceInvitation(invitation.id); setMessage(`Invitation for ${invitation.email} revoked.`); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Invitation could not be revoked."); }
    finally { setBusy(false); }
  }

  return <AppShell title="Team and access" eyebrow="Administration">
    <div className="command-toolbar"><div><strong>Manage workspace members and their assigned branches.</strong><span>Invitations are single-use, expire, and bind the invited email, role and selected branches.</span></div><div className="toolbar-actions"><Link href="/administration" className="button button-soft">Business setup</Link><button type="button" className="button button-soft" onClick={() => void load()} disabled={loading || busy}>Refresh</button></div></div>
    <p className="notice" role="note">Branch assignments are enforced on the core inventory, sales, returns and branch-aware analytics paths. Workspace-wide finance/reporting operations require assignment to every active branch; additional authenticated end-to-end tests and a route-by-route query audit remain before this access model is accepted for release.</p>
    {error && <div className="notice notice-error" role="alert">{error}</div>}
    {message && <div className="notice" role="status">{message}</div>}
    {lastInviteUrl && <section className="panel" style={{ padding: "1rem", marginBottom: "1rem" }}><strong>New one-time invitation link</strong><p>The raw token is only shown in this response. Copy it now and share it privately; a resend invalidates this link.</p><code style={{ overflowWrap: "anywhere" }}>{lastInviteUrl}</code><div className="header-actions"><button className="button button-dark" type="button" onClick={() => void navigator.clipboard.writeText(lastInviteUrl).then(() => setMessage("Invitation link copied."), () => setError("Clipboard access was blocked. Select and copy the link manually."))}>Copy invitation link</button></div></section>}

    <section className="panel" style={{ padding: "1.25rem", marginBottom: "1.25rem" }}>
      <div className="panel-head"><div><p className="eyebrow">INVITE A TEAM MEMBER</p><h2>Create invitation</h2></div></div>
      <form onSubmit={invite} style={{ display: "grid", gap: "1rem", maxWidth: 760 }}>
        <label>Email address<input type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} required /></label>
        <label>Workspace role<select value={roleId} onChange={event => setRoleId(event.target.value)} required disabled={!roles.length}><option value="">Select a role</option>{roles.map(role => <option key={role.id} value={role.id}>{role.name}</option>)}</select></label>
        <label>Invitation expires<select value={days} onChange={event => setDays(event.target.value)}><option value="1">In 1 day</option><option value="7">In 7 days</option><option value="14">In 14 days</option><option value="30">In 30 days</option></select></label>
        <fieldset><legend>Branches this member may be assigned to</legend><p><small>Leave unchecked if the role does not need branch-specific access. Assignments are checked against this workspace.</small></p>{branches.filter(branch => branch.status === "ACTIVE").map(branch => <label key={branch.id} style={{ display: "flex", gap: ".5rem", alignItems: "center", marginBottom: ".5rem" }}><input type="checkbox" checked={inviteBranchIds.includes(branch.id)} onChange={() => toggleBranch(branch.id, inviteBranchIds, setInviteBranchIds)} />{branch.name} ({branch.code})</label>)}</fieldset>
        <button className="button button-dark" type="submit" disabled={busy || loading || !roleId}>{busy ? "Saving…" : "Create one-time invitation"}</button>
      </form>
    </section>

    <section className="panel" style={{ padding: "1.25rem", marginBottom: "1.25rem" }}>
      <div className="panel-head"><div><p className="eyebrow">CURRENT MEMBERS</p><h2>People and branch scope</h2></div></div>
      {loading ? <p role="status">Loading team access…</p> : members.length === 0 ? <p>No workspace memberships were returned.</p> : <div style={{ display: "grid", gap: "1rem" }}>
        {members.map(member => <article key={member.id} style={{ borderBottom: "1px solid var(--border, #ddd)", paddingBottom: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}><div><strong>{member.email}</strong><div><small>{member.roles.map(role => role.name).join(", ") || "No role assigned"} · {member.status}</small></div></div><button type="button" className="button button-soft" disabled={busy || (member.status === "ACTIVE" && member.roles.some(role => role.name.toLowerCase() === "owner") && members.filter(x => x.status === "ACTIVE" && x.roles.some(r => r.name.toLowerCase() === "owner")).length <= 1)} onClick={() => void changeStatus(member, member.status === "ACTIVE" ? "INACTIVE" : "ACTIVE")}>{member.status === "ACTIVE" ? "Deactivate" : "Reactivate"}</button></div>
          <fieldset style={{ marginTop: ".75rem" }}><legend>Assigned roles</legend><p><small>At least one role is required for an active member. Only an existing workspace owner can grant the Owner role; the server protects the last active owner.</small></p>{roles.map(role => { const draft = memberRoleDrafts[member.id] || []; return <label key={role.id} style={{ display: "inline-flex", gap: ".4rem", alignItems: "center", margin: "0 .9rem .5rem 0" }}><input type="checkbox" checked={draft.includes(role.id)} disabled={member.status !== "ACTIVE" || busy} onChange={() => setMemberRoleDrafts(old => ({ ...old, [member.id]: draft.includes(role.id) ? draft.filter(id => id !== role.id) : [...draft, role.id] }))} />{role.name}</label>; })}</fieldset>
          <button type="button" className="button button-soft" disabled={busy || member.status !== "ACTIVE" || !(memberRoleDrafts[member.id] || []).length} onClick={() => void saveRoles(member)}>Save role assignments</button>
          <fieldset style={{ marginTop: ".75rem" }}><legend>Assigned branches</legend>{branches.filter(branch => branch.status === "ACTIVE").map(branch => { const draft = memberBranchDrafts[member.id] || []; return <label key={branch.id} style={{ display: "inline-flex", gap: ".4rem", alignItems: "center", margin: "0 .9rem .5rem 0" }}><input type="checkbox" checked={draft.includes(branch.id)} disabled={member.status !== "ACTIVE" || busy} onChange={() => setMemberBranchDrafts(old => ({ ...old, [member.id]: draft.includes(branch.id) ? draft.filter(id => id !== branch.id) : [...draft, branch.id] }))} />{branch.name}</label>; })}</fieldset>
          <button type="button" className="button button-soft" disabled={busy || member.status !== "ACTIVE"} onClick={() => void saveBranches(member)}>Save branch assignments</button>
        </article>)}
      </div>}
    </section>

    <section className="panel" style={{ padding: "1.25rem", marginBottom: "1.25rem" }}>
      <div className="panel-head"><div><p className="eyebrow">ROLE CONFIGURATION</p><h2>Roles and permissions</h2></div></div>
      <p><small>Workspace owners can create roles and replace their permission sets. The built-in Owner role is protected. Permission changes affect every active member assigned to that role.</small></p>
      <form onSubmit={createRole} style={{ display: "grid", gap: ".75rem", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", marginBottom: "1.25rem" }}>
        <label>New role name<input value={newRoleName} onChange={event => setNewRoleName(event.target.value)} minLength={2} maxLength={100} required /></label>
        <label>Description (optional)<input value={newRoleDescription} onChange={event => setNewRoleDescription(event.target.value)} maxLength={1000} /></label>
        <div style={{ display: "flex", alignItems: "end" }}><button type="submit" className="button button-dark" disabled={busy || !newRoleName.trim()}>Create role</button></div>
      </form>
      {roles.map(role => { const selected = rolePermissionDrafts[role.id] || []; const ownerRole = role.name.trim().toLowerCase() === "owner"; return <details key={role.id} style={{ borderTop: "1px solid var(--border, #ddd)", padding: ".8rem 0" }}>
        <summary style={{ cursor: "pointer", fontWeight: 600 }}>{role.name} · {selected.length} permissions{ownerRole ? " · protected" : ""}</summary>
        {role.description && <p><small>{role.description}</small></p>}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: ".35rem", margin: ".75rem 0", maxHeight: 360, overflowY: "auto" }}>
          {permissions.map(permission => <label key={permission.id} style={{ display: "flex", gap: ".45rem", alignItems: "start", padding: ".2rem" }}><input type="checkbox" checked={selected.includes(permission.id)} disabled={busy || ownerRole} onChange={() => setRolePermissionDrafts(old => ({ ...old, [role.id]: selected.includes(permission.id) ? selected.filter(id => id !== permission.id) : [...selected, permission.id] }))} /><span><span>{permission.code}</span>{permission.description && <small style={{ display: "block", opacity: .75 }}>{permission.description}</small>}</span></label>)}
        </div>
        {!ownerRole && <button type="button" className="button button-soft" disabled={busy} onClick={() => void saveRolePermissions(role)}>Save role permissions</button>}
      </details>; })}
    </section>

    <section className="panel" style={{ padding: "1.25rem" }}>
      <div className="panel-head"><div><p className="eyebrow">INVITATION LIFECYCLE</p><h2>Invitations</h2></div></div>
      {loading ? <p>Loading invitations…</p> : invitations.length === 0 ? <p>No invitation records.</p> : <div style={{ display: "grid", gap: ".8rem" }}>{invitations.map(invitation => <article key={invitation.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap", borderBottom: "1px solid var(--border, #ddd)", paddingBottom: ".75rem" }}><div><strong>{invitation.email}</strong><div><small>{invitation.status} · Expires {new Date(invitation.expires_at).toLocaleString()}</small></div></div>{["PENDING", "EXPIRED"].includes(invitation.status) && <div className="toolbar-actions"><button type="button" className="button button-soft" disabled={busy} onClick={() => void resend(invitation)}>Resend</button><button type="button" className="button button-soft" disabled={busy} onClick={() => void revoke(invitation)}>Revoke</button></div>}</article>)}</div>}
    </section>
  </AppShell>;
}
