import fs from "node:fs";
import assert from "node:assert/strict";

const web = new URL("../", import.meta.url);
const read = (path) => fs.readFileSync(new URL(path, web), "utf8");
const css = read("app/globals.css");
const ui = read("components/ui.tsx");
const shell = read("components/app-shell.tsx");
const login = read("app/login/page.tsx");
const register = read("app/register/page.tsx");
const products = read("app/products/page.tsx");
const inventory = read("app/inventory/page.tsx");
const api = read("lib/api.ts");
const auth = read("../api/app/routes/auth.py");

// Responsive foundation and keyboard-accessible navigation.
for (const token of ["--type-body", "--space-4", "--focus-ring"]) assert.match(css, new RegExp(token));
assert.match(css, /env\(safe-area-inset-bottom\)/);
assert.match(css, /prefers-reduced-motion/);
assert.match(shell, /\["\/sales", "Sales"/);
assert.match(shell, /Business settings/);
assert.match(shell, /aria-label="Quick navigation"/);
assert.match(shell, /getReadiness\(\)/);
assert.match(shell, /Checking connection/);
assert.match(shell, /PageHeader/);

// Shared components and list states are actually consumed by the primary lists.
for (const name of ["DataState", "StatusBanner", "PageHeader", "FormField", "ConfirmDialog", "ResponsiveDataTable", "MobileRecordCard"]) assert.match(ui, new RegExp(`export function ${name}`));
assert.match(products, /<ResponsiveDataTable/);
assert.match(inventory, /<ResponsiveDataTable/);
assert.match(inventory, /metricUnavailable \? "—"/);
assert.match(products, /catalogState/);

// Sign-in: accessible labels, autocomplete, reveal control, and explicit workspace selection.
assert.match(login, /autoComplete="username"/);
assert.match(login, /autoComplete="current-password"/);
assert.match(login, /Show password/);
assert.match(login, /WorkspaceSelectionError/);
assert.doesNotMatch(login, /Forgot password/i);

// Onboarding: resumable safe draft, idempotent retry, and no secrets in session storage.
assert.match(register, /lexa-onboarding-draft-v1/);
assert.match(register, /registrationKey\.current \|\|= crypto\.randomUUID\(\)/);
assert.match(register, /sessionStorage\.setItem\(draftKey, JSON\.stringify\(\{ \.\.\.draft, step \}\)\)/);
assert.doesNotMatch(register, /sessionStorage\.setItem.*(password|confirmPassword)/i);
for (const field of ["country_code", "currency_code", "branch_name", "warehouse_name", "location_name"]) assert.match(register, new RegExp(field));
assert.match(auth, /branch_id/);
assert.match(auth, /warehouse_id/);
assert.match(auth, /location_id/);
assert.match(auth, /body\.branch_name/);
assert.match(auth, /body\.warehouse_name/);
assert.match(auth, /body\.location_name/);

// API errors use explicit customer-facing status mappings, especially 422.
assert.match(api, /function friendlyMessage/);
assert.match(api, /if \(status === 422\) return "Please check the required fields/);
assert.match(api, /status === 503/);
assert.match(api, /Check the record before retrying/);
console.log("phase 1 UX/onboarding contract: PASS");
