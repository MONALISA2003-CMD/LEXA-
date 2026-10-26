import fs from "node:fs";
import assert from "node:assert/strict";

const root = new URL("../", import.meta.url);
const read = (path) => fs.readFileSync(new URL(path, root), "utf8");
const shell = read("components/app-shell.tsx");
const navigation = read("lib/navigation.mjs");
const home = read("app/page.tsx");
const reports = read("app/reports/page.tsx");
const customers = read("app/customers/page.tsx");
const onboarding = read("app/onboarding/page.tsx");
const api = read("lib/api.ts");
const register = read("app/register/page.tsx");
const layout = read("app/layout.tsx");
const logo = read("public/lexa-mark.svg");
const wordmark = read("public/lexa-logo.svg");
const brandStyles = read("app/lexa-brand-authority.css");

assert.match(shell, /app-brand-logo/);
assert.match(shell, /setupProgressChecked/);
assert.match(shell, /NavGlyph name="menu"/);
assert.match(shell, /NavGlyph name="search"/);
assert.match(shell, /setup-welcome-card/);
for (const label of ["Home", "Sales", "Stock", "Products", "Customers", "Purchases", "Money & records", "Reports"]) assert.ok(navigation.includes(`"${label}"`));
assert.doesNotMatch(shell, /\["\/intelligence"/);
assert.match(shell, /getSetupProgress\(\)/);
assert.match(onboarding, /initializeWorkspaceSetup\(\)/);
assert.match(onboarding, /Set up missing details/);
assert.match(reports, /SalesTrendChart/);
assert.match(reports, /ProductPerformanceBars/);
assert.match(customers, /getCommerceSales\(\{ search: activeCustomer\.display_name/);
assert.match(customers, /Sales history/);
assert.match(customers, /amount_due/);
assert.match(api, /export function userFacingError/);
assert.match(api, /WORKSPACE_SETUP_REQUIRED/);
assert.match(register, /Your business, clearly\./);
assert.doesNotMatch(register, /Business business|NEW WORKSPACE|one transaction/);

// Master brand is now the authority. The compact mark derives from the logo artwork;
// the full horizontal wordmark and the shared tokens define the visual system.
assert.match(layout, /lexa-mark\.svg/);
assert.match(logo, /lexa-app-mark\.png/);
assert.match(wordmark, /lexa-wordmark-master\.jpg/);
assert.match(brandStyles, /--lexa-blue:\s*#075FE8/i);
assert.match(brandStyles, /--lexa-cyan:\s*#01B9BB/i);
assert.match(brandStyles, /--lexa-green:\s*#00B77D/i);
assert.match(brandStyles, /--lexa-gold:\s*#E1C140/i);
assert.match(brandStyles, /--lexa-red:\s*#E91D3A/i);

console.log("Phase 8 foundation repair, module navigation, business reports, customer sales history and LEXA master brand authority: PASS");

const shellText = fs.readFileSync(new URL("../components/app-shell.tsx", import.meta.url), "utf8");
assert.match(shellText, /getSetupProgress\(\)/);
assert.match(shellText, /A few business details still need attention/);
assert.match(shellText, /business details that still need attention/);
assert.match(shellText, /Finish setup/);
assert.match(shellText, /get your business ready/i);
assert.doesNotMatch(shellText, /workspace-wide|RLS|schema migration/);
