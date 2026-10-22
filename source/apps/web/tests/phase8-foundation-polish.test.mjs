import fs from "node:fs";
import assert from "node:assert/strict";

const root = new URL("../", import.meta.url);
const read = (path) => fs.readFileSync(new URL(path, root), "utf8");
const shell = read("components/app-shell.tsx");
const home = read("app/page.tsx");
const reports = read("app/reports/page.tsx");
const customers = read("app/customers/page.tsx");
const onboarding = read("app/onboarding/page.tsx");
const api = read("lib/api.ts");
const register = read("app/register/page.tsx");
const layout = read("app/layout.tsx");
const logo = read("public/lexa-mark.svg");

assert.match(shell, /app-brand-logo/);
for (const label of ["Home", "Sales", "Stock", "Products", "Customers", "Purchases", "Finance", "Reports"]) assert.ok(shell.includes(`"${label}"`));
assert.doesNotMatch(shell, /\["\/intelligence"/);
assert.match(home, /getSetupProgress\(\)/);
assert.match(home, /Finish setting up your business/);
assert.match(onboarding, /initializeWorkspaceSetup\(\)/);
assert.match(onboarding, /Prepare my business/);
assert.match(reports, /SalesTrendChart/);
assert.match(reports, /ProductPerformanceBars/);
assert.match(customers, /getCommerceSales\(\{ search: activeCustomer\.display_name/);
assert.match(customers, /Sales history/);
assert.match(customers, /amount_due/);
assert.match(api, /export function userFacingError/);
assert.match(api, /WORKSPACE_SETUP_REQUIRED/);
assert.match(register, /Your business, clearly\./);
assert.doesNotMatch(register, /Business business|NEW WORKSPACE|one transaction/);
assert.match(layout, /lexa-mark\.svg/);
assert.match(logo, /#496CFF/);
assert.match(logo, /#14C7B7/);
assert.match(logo, /#FFC857/);

console.log("Phase 8 foundation repair, module navigation, business reports, customer sales history and bright LEXA branding: PASS");

const shellText = fs.readFileSync(new URL("../components/app-shell.tsx", import.meta.url), "utf8");
assert.match(shellText, /getSetupProgress\(\)/);
assert.match(shellText, /Your business needs a few setup details/);
assert.match(shellText, /Add a main branch, stock room and stock location/);
assert.match(shellText, /Finish setup/);
assert.doesNotMatch(shellText, /workspace-wide|RLS|tenant_id|schema migration/);
