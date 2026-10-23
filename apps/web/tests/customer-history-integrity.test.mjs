import fs from "node:fs";
import assert from "node:assert/strict";

const root = new URL("../", import.meta.url);
const page = fs.readFileSync(new URL("app/customers/page.tsx", root), "utf8");
const api = fs.readFileSync(new URL("lib/api.ts", root), "utf8");
assert.match(api, /getCustomerSalesHistory\(partyId:string, limit=200, offset=0\)/);
assert.match(api, /customers\/\$\{encodeURIComponent\(partyId\)\}\/history/);
assert.match(page, /getCustomerSalesHistory\(activeCustomer\.party_id, 100, 0\)/);
assert.match(page, /Original sale amounts, returned value, cash refunds and customer credit are shown separately/);
assert.match(page, /Load older sales/);
assert.match(page, /historyRequestRef/);
assert.doesNotMatch(page, /getCommerceSales\(\{ search: activeCustomer\.display_name/);
assert.match(api, /a required service or database update is still missing/);
console.log("Customer-ID history with separate return/refund/customer-credit evidence: PASS");
