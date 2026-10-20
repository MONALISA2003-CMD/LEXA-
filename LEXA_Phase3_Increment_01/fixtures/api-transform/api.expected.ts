function key() { return "test-key"; }
function getJson<T>(path: string, options?: RequestInit): Promise<T> { return Promise.reject({path, options}); }
export type BusinessProfile = { id:string; tenant_id:string; legal_name:string; display_name:string; country_code:string; currency_code:string };
export type Branch = { id:string; tenant_id:string; name:string; code:string; status:string };
export type Warehouse = { id:string; tenant_id:string; name:string; code:string; branch_id?:string|null; status:string };
export function getBusinessProfile() { return getJson<BusinessProfile | null>("/api/v1/organization/profile"); }
export function createBusinessProfile(body: {legal_name:string; display_name:string; country_code:string; currency_code:string}) { return getJson<BusinessProfile>("/api/v1/organization/profile", { method:"POST", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }
export function updateBusinessProfile(body: {legal_name:string; display_name:string; country_code:string; currency_code:string}) { return getJson<BusinessProfile>("/api/v1/organization/profile", { method:"PATCH", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }
export function getBranches() { return getJson<Branch[]>("/api/v1/organization/branches"); }
export function createBranch(body: {name:string; code:string}) { return getJson<Branch>("/api/v1/organization/branches", { method:"POST", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }
export function updateBranch(id:string, body: {name:string; code:string}) { return getJson<Branch>(`/api/v1/organization/branches/${encodeURIComponent(id)}`, { method:"PATCH", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }
export function getWarehouses() { return getJson<Warehouse[]>("/api/v1/organization/warehouses"); }
