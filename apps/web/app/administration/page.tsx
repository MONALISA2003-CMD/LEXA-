"use client";

import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { AppShell } from "../../components/app-shell";
import {
  createBranch,
  createBusinessProfile,
  createLocation,
  createWarehouse,
  getBranches,
  getBusinessProfile,
  getLocations,
  getWarehouses,
  updateBranch,
  updateBusinessProfile,
  type Branch,
  type BusinessProfile,
  type Location,
  type Warehouse,
} from "../../lib/api";

type LoadState = "loading" | "ready" | "partial";
type ProfileForm = { legal_name: string; display_name: string; country_code: string; currency_code: string };
const emptyProfile: ProfileForm = { legal_name: "", display_name: "", country_code: "UG", currency_code: "UGX" };

function describeError(value: unknown): string {
  return value instanceof Error ? value.message : "LEXA could not complete this request. Please try again.";
}

function Field({ id, label, children, hint }: { id: string; label: string; children: ReactNode; hint?: string }) {
  return <label htmlFor={id}>
    <span>{label}</span>
    {children}
    {hint && <small className="workflow-color">{hint}</small>}
  </label>;
}

function EmptyState({ children }: { children: ReactNode }) {
  return <div className="empty-state compact"><span>{children}</span></div>;
}

export default function AdministrationPage() {
  const [profile, setProfile] = useState<BusinessProfile | null>(null);
  const [profileForm, setProfileForm] = useState<ProfileForm>(emptyProfile);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [loadError, setLoadError] = useState("");
  const [mutationError, setMutationError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [branchForm, setBranchForm] = useState({ name: "", code: "" });
  const [warehouseForm, setWarehouseForm] = useState({ name: "", code: "", branch_id: "" });
  const [locationForm, setLocationForm] = useState({ name: "", code: "", warehouse_id: "" });
  const [editBranchId, setEditBranchId] = useState<string | null>(null);
  const [editBranchForm, setEditBranchForm] = useState({ name: "", code: "" });

  const reload = useCallback(async () => {
    setLoadState("loading");
    setLoadError("");
    const [profileResult, branchResult, warehouseResult, locationResult] = await Promise.allSettled([
      getBusinessProfile(), getBranches(), getWarehouses(), getLocations(),
    ]);
    let partial = false;
    if (profileResult.status === "fulfilled") {
      setProfile(profileResult.value);
      if (profileResult.value) {
        setProfileForm({
          legal_name: profileResult.value.legal_name,
          display_name: profileResult.value.display_name,
          country_code: profileResult.value.country_code,
          currency_code: profileResult.value.currency_code,
        });
      }
    } else partial = true;
    if (branchResult.status === "fulfilled") setBranches(branchResult.value); else partial = true;
    if (warehouseResult.status === "fulfilled") setWarehouses(warehouseResult.value); else partial = true;
    if (locationResult.status === "fulfilled") setLocations(locationResult.value); else partial = true;
    setLoadState(partial ? "partial" : "ready");
    if (partial) setLoadError("Some workspace settings could not be loaded. Check access or service readiness, then retry.");
  }, []);

  useEffect(() => { void reload(); }, [reload]);

  async function mutate(key: string, action: () => Promise<unknown>, successMessage: string) {
    if (busy) return;
    setBusy(key);
    setMutationError("");
    setNotice("");
    try {
      await action();
      setNotice(successMessage);
      await reload();
    } catch (error) {
      setMutationError(describeError(error));
    } finally {
      setBusy(null);
    }
  }

  function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = {
      legal_name: profileForm.legal_name.trim(),
      display_name: profileForm.display_name.trim(),
      country_code: profileForm.country_code.trim().toUpperCase(),
      currency_code: profileForm.currency_code.trim().toUpperCase(),
    };
    void mutate("profile", () => profile ? updateBusinessProfile(body) : createBusinessProfile(body), profile ? "Business profile updated." : "Business profile created.");
  }

  function saveBranch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = { name: branchForm.name.trim(), code: branchForm.code.trim().toUpperCase() };
    void mutate("branch", async () => {
      const result = await createBranch(body);
      setBranchForm({ name: "", code: "" });
      return result;
    }, "Branch created.");
  }

  function beginEditBranch(branch: Branch) {
    setEditBranchId(branch.id);
    setEditBranchForm({ name: branch.name, code: branch.code });
    setMutationError("");
    setNotice("");
  }

  function saveBranchChanges(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editBranchId) return;
    const id = editBranchId;
    const body = { name: editBranchForm.name.trim(), code: editBranchForm.code.trim().toUpperCase() };
    void mutate("branch-edit", async () => {
      const result = await updateBranch(id, body);
      setEditBranchId(null);
      return result;
    }, "Branch updated.");
  }

  function saveWarehouse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = { name: warehouseForm.name.trim(), code: warehouseForm.code.trim().toUpperCase(), branch_id: warehouseForm.branch_id || null };
    void mutate("warehouse", async () => {
      const result = await createWarehouse(body);
      setWarehouseForm({ name: "", code: "", branch_id: "" });
      return result;
    }, "Warehouse created.");
  }

  function saveLocation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = { name: locationForm.name.trim(), code: locationForm.code.trim().toUpperCase(), warehouse_id: locationForm.warehouse_id };
    void mutate("location", async () => {
      const result = await createLocation(body);
      setLocationForm({ name: "", code: "", warehouse_id: "" });
      return result;
    }, "Stock location created.");
  }

  return <AppShell title="Administration" eyebrow="Workspace Control">
    <div className="command-toolbar">
      <div>
        <strong>Business setup and workspace administration</strong>
        <span>Configure the business profile, branches, warehouses and stock locations for the selected workspace.</span>
      </div>
      <div className="toolbar-actions">
        <span className={`status ${loadState === "ready" ? "good" : "warn"}`} role="status">{loadState === "loading" ? "Loading settings" : loadState === "partial" ? "Some settings unavailable" : "Workspace settings loaded"}</span>
        <button className="button button-soft" type="button" disabled={loadState === "loading" || Boolean(busy)} onClick={() => void reload()}>Refresh</button>
      </div>
    </div>

    {loadError && <div className="inline-message" role="alert">{loadError}</div>}
    {mutationError && <div className="notice notice-error" role="alert" aria-live="assertive">{mutationError}</div>}
    {notice && <div className="inline-message" role="status" aria-live="polite">{notice}</div>}
    {!loadError && loadState === "ready" && !profile && <div className="inline-message">Start by saving the legal and display name for this workspace. Profile changes are tenant-scoped and audited.</div>}

    <section className="workspace-section" aria-labelledby="business-profile-heading">
      <div className="section-head"><div><p className="eyebrow">BUSINESS IDENTITY</p><h2 id="business-profile-heading">Business profile</h2></div><span className={`status ${profile ? "good" : "neutral"}`}>{profile ? "Configured" : "Setup required"}</span></div>
      <form className="command-form" onSubmit={saveProfile}>
        <div className="form-grid">
          <Field id="profile-legal-name" label="Legal business name">
            <input id="profile-legal-name" name="legal_name" autoComplete="organization" value={profileForm.legal_name} onChange={event => setProfileForm(previous => ({ ...previous, legal_name: event.target.value }))} minLength={2} maxLength={250} required />
          </Field>
          <Field id="profile-display-name" label="Trading / display name">
            <input id="profile-display-name" name="display_name" value={profileForm.display_name} onChange={event => setProfileForm(previous => ({ ...previous, display_name: event.target.value }))} minLength={2} maxLength={250} required />
          </Field>
          <Field id="profile-country-code" label="Country code" hint="Two-letter ISO code, for example UG.">
            <input id="profile-country-code" name="country_code" value={profileForm.country_code} onChange={event => setProfileForm(previous => ({ ...previous, country_code: event.target.value.toUpperCase() }))} pattern="[A-Z]{2}" minLength={2} maxLength={2} required />
          </Field>
          <Field id="profile-currency-code" label="Currency code" hint="Three-letter currency code, for example UGX.">
            <input id="profile-currency-code" name="currency_code" value={profileForm.currency_code} onChange={event => setProfileForm(previous => ({ ...previous, currency_code: event.target.value.toUpperCase() }))} pattern="[A-Z]{3}" minLength={3} maxLength={3} required />
          </Field>
        </div>
        <div className="top-actions"><button className="primary" type="submit" disabled={Boolean(busy) || loadState !== "ready"}>{busy === "profile" ? "Saving…" : profile ? "Save profile changes" : "Create business profile"}</button></div>
      </form>
    </section>

    <div className="split-panel">
      <section className="workspace-section" aria-labelledby="branches-heading">
        <div className="section-head"><div><p className="eyebrow">OPERATING STRUCTURE</p><h2 id="branches-heading">Branches</h2></div><span className="status neutral">{branches.length} total</span></div>
        <form className="command-form compact" onSubmit={saveBranch}>
          <div className="form-grid">
            <Field id="branch-name" label="Branch name"><input id="branch-name" value={branchForm.name} onChange={event => setBranchForm(previous => ({ ...previous, name: event.target.value }))} minLength={2} maxLength={200} required /></Field>
            <Field id="branch-code" label="Branch code"><input id="branch-code" value={branchForm.code} onChange={event => setBranchForm(previous => ({ ...previous, code: event.target.value.toUpperCase() }))} minLength={2} maxLength={50} required /></Field>
          </div>
          <button className="primary" type="submit" disabled={Boolean(busy) || loadState !== "ready"}>{busy === "branch" ? "Creating…" : "Add branch"}</button>
        </form>
        <div className="workflow-list" aria-label="Configured branches">
          {branches.length === 0 ? <EmptyState>No branches were returned for this workspace.</EmptyState> : branches.map(branch => <div className="foundation-row" key={branch.id}>
            <div><strong>{branch.name}</strong><small className="workflow-color">{branch.code}</small></div>
            <div className="row-actions"><span className={`status ${branch.status === "ACTIVE" ? "good" : "neutral"}`}>{branch.status}</span><button type="button" onClick={() => beginEditBranch(branch)} disabled={Boolean(busy) || loadState !== "ready"} aria-label={`Edit ${branch.name}`}>Edit</button></div>
          </div>)}
        </div>
        {editBranchId && <form className="command-form compact" onSubmit={saveBranchChanges} aria-label="Edit branch">
          <div className="panel-head"><h3>Edit branch</h3><button className="secondary" type="button" onClick={() => setEditBranchId(null)}>Cancel</button></div>
          <div className="form-grid">
            <Field id="branch-edit-name" label="Branch name"><input id="branch-edit-name" value={editBranchForm.name} onChange={event => setEditBranchForm(previous => ({ ...previous, name: event.target.value }))} minLength={2} maxLength={200} required /></Field>
            <Field id="branch-edit-code" label="Branch code"><input id="branch-edit-code" value={editBranchForm.code} onChange={event => setEditBranchForm(previous => ({ ...previous, code: event.target.value.toUpperCase() }))} minLength={2} maxLength={50} required /></Field>
          </div>
          <button className="primary" type="submit" disabled={Boolean(busy) || loadState !== "ready"}>{busy === "branch-edit" ? "Saving…" : "Save branch"}</button>
        </form>}
      </section>

      <section className="workspace-section" aria-labelledby="warehouses-heading">
        <div className="section-head"><div><p className="eyebrow">STOCK STORAGE</p><h2 id="warehouses-heading">Warehouses</h2></div><span className="status neutral">{warehouses.length} total</span></div>
        <form className="command-form compact" onSubmit={saveWarehouse}>
          <div className="form-grid">
            <Field id="warehouse-name" label="Warehouse name"><input id="warehouse-name" value={warehouseForm.name} onChange={event => setWarehouseForm(previous => ({ ...previous, name: event.target.value }))} minLength={2} maxLength={200} required /></Field>
            <Field id="warehouse-code" label="Warehouse code"><input id="warehouse-code" value={warehouseForm.code} onChange={event => setWarehouseForm(previous => ({ ...previous, code: event.target.value.toUpperCase() }))} minLength={2} maxLength={50} required /></Field>
          </div>
          <Field id="warehouse-branch" label="Branch (optional)">
            <select id="warehouse-branch" value={warehouseForm.branch_id} onChange={event => setWarehouseForm(previous => ({ ...previous, branch_id: event.target.value }))}>
              <option value="">Not assigned to a branch</option>{branches.map(branch => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
            </select>
          </Field>
          <button className="primary" type="submit" disabled={Boolean(busy) || loadState !== "ready"}>{busy === "warehouse" ? "Creating…" : "Add warehouse"}</button>
        </form>
        <div className="workflow-list" aria-label="Configured warehouses">
          {warehouses.length === 0 ? <EmptyState>No warehouses were returned for this workspace.</EmptyState> : warehouses.map(warehouse => <div className="foundation-row" key={warehouse.id}>
            <div><strong>{warehouse.name}</strong><small className="workflow-color">{warehouse.code}{warehouse.branch_id ? ` · ${branches.find(branch => branch.id === warehouse.branch_id)?.name ?? "Assigned branch"}` : " · No branch assignment"}</small></div>
            <span className={`status ${warehouse.status === "ACTIVE" ? "good" : "neutral"}`}>{warehouse.status}</span>
          </div>)}
        </div>
      </section>
    </div>

    <section className="workspace-section" aria-labelledby="locations-heading">
      <div className="section-head"><div><p className="eyebrow">STOCK LOCATIONS</p><h2 id="locations-heading">Locations</h2></div><span className="status neutral">{locations.length} total</span></div>
      <div className="split-panel">
        <form className="command-form compact" onSubmit={saveLocation}>
          <Field id="location-name" label="Location name"><input id="location-name" value={locationForm.name} onChange={event => setLocationForm(previous => ({ ...previous, name: event.target.value }))} minLength={2} maxLength={200} required /></Field>
          <Field id="location-code" label="Location code"><input id="location-code" value={locationForm.code} onChange={event => setLocationForm(previous => ({ ...previous, code: event.target.value.toUpperCase() }))} minLength={2} maxLength={50} required /></Field>
          <Field id="location-warehouse" label="Warehouse">
            <select id="location-warehouse" value={locationForm.warehouse_id} onChange={event => setLocationForm(previous => ({ ...previous, warehouse_id: event.target.value }))} required disabled={warehouses.length === 0}>
              <option value="">Select a warehouse</option>{warehouses.map(warehouse => <option key={warehouse.id} value={warehouse.id}>{warehouse.name} ({warehouse.code})</option>)}
            </select>
          </Field>
          {warehouses.length === 0 && <small className="workflow-color">Create or load a warehouse before adding a stock location.</small>}
          <button className="primary" type="submit" disabled={Boolean(busy) || loadState !== "ready" || warehouses.length === 0}>{busy === "location" ? "Creating…" : "Add stock location"}</button>
        </form>
        <div className="workflow-list" aria-label="Configured stock locations">
          {locations.length === 0 ? <EmptyState>No stock locations were returned for this workspace.</EmptyState> : locations.map(location => {
            const warehouse = warehouses.find(item => item.id === location.warehouse_id);
            return <article className="location-card" key={location.id}>
              <div className="panel-head"><h3>{location.name}</h3><span className={`status ${location.status === "ACTIVE" ? "good" : "neutral"}`}>{location.status}</span></div>
              <p>{location.code}</p><small>{warehouse ? `${warehouse.name} · ${warehouse.code}` : "Warehouse details unavailable"}</small>
            </article>;
          })}
        </div>
      </div>
    </section>
  </AppShell>;
}
