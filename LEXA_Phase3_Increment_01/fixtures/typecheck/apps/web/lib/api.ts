export type BusinessProfile = { id:string; tenant_id:string; legal_name:string; display_name:string; country_code:string; currency_code:string };
export type Branch = { id:string; tenant_id:string; name:string; code:string; status:string };
export type Warehouse = { id:string; tenant_id:string; name:string; code:string; branch_id?:string|null; status:string };
export type Location = { id:string; tenant_id:string; warehouse_id:string; name:string; code:string; status:string };
export function getBusinessProfile(): Promise<BusinessProfile|null> { return Promise.resolve(null); }
export function createBusinessProfile(body: {legal_name:string; display_name:string; country_code:string; currency_code:string}): Promise<BusinessProfile> { return Promise.reject(body); }
export function updateBusinessProfile(body: {legal_name:string; display_name:string; country_code:string; currency_code:string}): Promise<BusinessProfile> { return Promise.reject(body); }
export function getBranches(): Promise<Branch[]> { return Promise.resolve([]); }
export function createBranch(body: {name:string; code:string}): Promise<Branch> { return Promise.reject(body); }
export function updateBranch(id:string, body: {name:string; code:string}): Promise<Branch> { return Promise.reject({id, body}); }
export function getWarehouses(): Promise<Warehouse[]> { return Promise.resolve([]); }
export function createWarehouse(body: {name:string; code:string; branch_id?:string|null}): Promise<Warehouse> { return Promise.reject(body); }
export function getLocations(): Promise<Location[]> { return Promise.resolve([]); }
export function createLocation(body: {name:string; code:string; warehouse_id:string}): Promise<Location> { return Promise.reject(body); }
