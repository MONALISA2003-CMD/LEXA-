function key() { return "test-key"; }
function getJson<T>(path: string, options?: RequestInit): Promise<T> { return Promise.reject({path, options}); }
export type Branch = { id:string; tenant_id:string; name:string; code:string; status:string };
export type Warehouse = { id:string; tenant_id:string; name:string; code:string; branch_id?:string|null; status:string };
export function getBranches() { return getJson<Branch[]>("/api/v1/organization/branches"); }
export function getWarehouses() { return getJson<Warehouse[]>("/api/v1/organization/warehouses"); }
