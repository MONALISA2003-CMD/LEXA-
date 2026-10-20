import test from "node:test";
import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const bundledRoot = path.resolve(here, "..");
const repoRoot = path.resolve(here, "../../..");
async function exists(file) {
  try { await access(file); return true; } catch { return false; }
}
const isBundle = await exists(path.join(bundledRoot, "overrides/apps/api/app/routes/organization.py"));
const root = isBundle ? bundledRoot : repoRoot;
const pagePath = path.join(root, isBundle ? "overrides/apps/web/app/administration/page.tsx" : "apps/web/app/administration/page.tsx");
const apiPath = path.join(root, isBundle ? "docs/api-helpers-phase3.ts.txt" : "apps/web/lib/api.ts");
const backendPath = path.join(root, isBundle ? "overrides/apps/api/app/routes/organization.py" : "apps/api/app/routes/organization.py");
const page = await readFile(pagePath, "utf8");
const api = await readFile(apiPath, "utf8");
const backend = await readFile(backendPath, "utf8");

test("administration screen uses real profile, branch, warehouse and location contracts", () => {
  for (const helper of [
    "getBusinessProfile", "createBusinessProfile", "updateBusinessProfile", "getBranches", "createBranch",
    "updateBranch", "getWarehouses", "createWarehouse", "getLocations", "createLocation",
  ]) assert.match(page, new RegExp(`\\b${helper}\\b`));
  assert.doesNotMatch(page, /ModuleFoundation/);
  assert.match(page, /Promise\.allSettled/);
});

test("forms have explicit labels, browser validation and accessible status messages", () => {
  for (const label of ["Business profile", "Branches", "Warehouses", "Locations"]) assert.ok(page.includes(label));
  assert.match(page, /aria-live="assertive"/);
  assert.match(page, /aria-live="polite"/);
  assert.match(page, /minLength=\{2\}/);
  assert.match(page, /required/);
  assert.match(page, /loadState !== "ready"/);
});

test("client API exposes idempotency-key helpers for profile and branch mutations", () => {
  for (const helper of ["getBusinessProfile", "createBusinessProfile", "updateBusinessProfile", "createBranch", "updateBranch"]) {
    assert.ok(api.includes(helper), `Missing API helper ${helper}`);
  }
  if (isBundle) assert.match(api, /Idempotency-Key/);
  else {
    assert.match(api, /createBusinessProfile[\s\S]{0,350}Idempotency-Key/);
    assert.match(api, /updateBranch[\s\S]{0,350}Idempotency-Key/);
  }
});

test("backend configuration writes are permissioned, tenant-scoped, idempotent and audited", () => {
  assert.match(backend, /Depends\(require_permission\("organization\.manage"\)\)/);
  for (const op of [
    "organization.profile.create", "organization.profile.update", "organization.branch.create", "organization.branch.update",
    "organization.warehouse.create", "organization.location.create", "organization.pos_terminal.create",
  ]) assert.ok(backend.includes(`operation_type="${op}"`), `Missing idempotency operation ${op}`);
  for (const event of ["BusinessProfileCreated", "BusinessProfileUpdated", "BranchCreated", "BranchUpdated", "WarehouseCreated", "LocationCreated", "PosTerminalCreated"]) {
    assert.ok(backend.includes(`event_type="${event}"`), `Missing outbox event ${event}`);
  }
  assert.match(backend, /select\(Branch\)\.where\(Branch\.id == branch_id, Branch\.tenant_id == tenant_id\)/);
  assert.match(backend, /select\(Warehouse\.id\)\.where\(Warehouse\.id == body\.warehouse_id, Warehouse\.tenant_id == tenant_id\)/);
  assert.match(backend, /CatalogValidation/);
  assert.match(backend, /Header\(\.\.\., alias="Idempotency-Key"/);
});
