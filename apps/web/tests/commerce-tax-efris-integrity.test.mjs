import fs from "node:fs";
import assert from "node:assert/strict";

const root = new URL("../", import.meta.url);
const commerce = fs.readFileSync(new URL("app/commerce/page.tsx", root), "utf8");
const api = fs.readFileSync(new URL("lib/api.ts", root), "utf8");
const complianceUi = fs.readFileSync(new URL("app/compliance/page.tsx", root), "utf8");
const apiCommerce = fs.readFileSync(new URL("../../../apps/api/app/routes/commerce.py", import.meta.url), "utf8");
const apiFinance = fs.readFileSync(new URL("../../../apps/api/app/routes/finance.py", import.meta.url), "utf8");

assert.match(apiCommerce, /public\.resolve_tax_rate\(:tenant_id,:product_id,:category_id,:business_date\)/);
assert.match(apiCommerce, /effective_tax_rate/);
assert.match(apiCommerce, /tax_inclusive/);
assert.match(api, /getCommerceProducts\(businessDate=''/);
assert.match(commerce, /lineTotal = product\?\.tax_inclusive \? discountedGross : discountedGross \* \(1 \+ rate \/ 100\)/);
assert.match(commerce, /changeSaleDate/);
assert.match(commerce, /Discounts and tax are recalculated by LEXA on the server/);
assert.match(complianceUi, /readOnly aria-readonly="true"/);
assert.match(complianceUi, /real URA-approved connector/);
assert.doesNotMatch(complianceUi, /value="ACTIVE"/);
assert.doesNotMatch(apiFinance.split("class EfrisConfigPatch")[1].split("\n\n")[0], /registration_status:/);
assert.match(apiFinance, /registration_status=CASE WHEN EXCLUDED\.integration_mode='MANUAL' THEN 'NOT_REGISTERED' ELSE 'PENDING' END/);

console.log("Commerce effective-dated tax preview and EFRIS verified-state contracts: PASS");
