export type Product = { id: string; tenant_id: string; category_id: string; brand_id?: string | null; name: string; description?: string | null; product_type: string; status: string; has_variants: boolean; tax_category_id?: string | null; metadata?: Record<string, unknown> };
export type Variant = { id: string; tenant_id: string; product_id: string; name: string; sku: string; base_unit_id: string; track_inventory: boolean; allow_fractional_quantity: boolean; status: string; costing_method?: string | null; metadata?: Record<string, unknown> };
export type Page<T> = { items: T[]; next_cursor?: string | null };
export type Location = { id: string; tenant_id: string; warehouse_id: string; name: string; code: string; status: string };
export type VariantOption = { id: string; sku: string; name: string; product_name: string };
export type InventoryBalance = { id: string; tenant_id: string; location_id: string; variant_id: string; on_hand: string; reserved: string; available: string; inbound: string; average_cost: string; stock_value: string; updated_at: string };
export type InventoryLedger = { id: string; tenant_id: string; location_id: string; variant_id: string; transaction_type: string; quantity_delta: string; unit_cost: string; total_cost: string; balance_after: string; reference_type?: string | null; reference_id?: string | null; source_transaction_id?: string | null; occurred_at: string; metadata: Record<string, unknown> };
export type InventoryAdjustment = { id: string; location_id: string; reason_code: string; notes?: string | null; status: string; created_at: string; lines: { id: string; variant_id: string; quantity_delta: string; unit_cost: string; notes?: string | null }[] };
export type StockCount = { id: string; location_id: string; status: string; scope_description?: string | null; started_at?: string | null; created_at: string; lines: { id: string; variant_id: string; expected_quantity: string; counted_quantity?: string | null; variance_quantity?: string | null; unit_cost: string }[] };
export type Transfer = { id: string; source_location_id: string; destination_location_id: string; status: string; notes?: string | null; created_at: string; lines: { id: string; variant_id: string; requested_quantity: string; dispatched_quantity: string; received_quantity: string; unit_cost: string }[] };

export type ApiHealth = { status: string };
export type ApiReadiness = { status: string; dependencies?: { database?: string } };

export type WorkspaceChoice = { tenant_id: string; tenant_name: string };
export class WorkspaceSelectionError extends Error {
  workspaces: WorkspaceChoice[];
  constructor(workspaces: WorkspaceChoice[]) {
    super("Choose a workspace to continue.");
    this.name = "WorkspaceSelectionError";
    this.workspaces = workspaces;
  }
}

function friendlyMessage(status: number, payload: unknown): string {
  const detail = typeof payload === "object" && payload !== null && "detail" in payload ? (payload as { detail?: unknown }).detail : null;
  const code = typeof detail === "object" && detail !== null && "code" in detail ? String((detail as { code?: unknown }).code) : "";
  const raw = typeof detail === "string" ? detail : "";
  if (code === "WORKSPACE_SELECTION_REQUIRED") return "Choose a workspace to continue.";
  if (status === 401) return "Those sign-in details don't match.";
  if (status === 409 && raw === "User already exists") return "An account with this email already exists. Sign in to continue.";
  if (status === 409 && raw.includes("Business")) return "That business information conflicts with an existing workspace.";
  if (status === 400 && raw === "Business name is required") return "Enter your business name to continue.";
  if (status === 422) return "Please check the information and try again.";
  if (status === 429) return "Too many attempts. Please wait a moment and try again.";
  if (status >= 500) return "We couldn't connect to LEXA right now. Please try again in a moment.";
  if (status >= 400) return "We couldn't complete that action. Please review the information and try again.";
  return "Something went wrong. Please try again.";
}

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const auth = typeof window !== "undefined" ? window.sessionStorage.getItem("lexa_access_token") : null;
  const headers: HeadersInit = { Accept: "application/json", ...(auth ? { Authorization: `Bearer ${auth}` } : {}), ...(init?.headers || {}) };
  let response: Response;
  try {
    response = await fetch(`/api/lexa${path}`, { cache: "no-store", ...init, headers });
  } catch {
    throw new Error("We couldn't connect to LEXA right now. Check your connection and try again.");
  }
  const text = await response.text();
  let payload: unknown = null;
  try { payload = text ? JSON.parse(text) : null; } catch { payload = text; }
  if (!response.ok) {
    const detail = typeof payload === "object" && payload !== null && "detail" in payload ? (payload as { detail?: unknown }).detail : null;
    const code = typeof detail === "object" && detail !== null && "code" in detail ? String((detail as { code?: unknown }).code) : "";
    if (code === "WORKSPACE_SELECTION_REQUIRED" && typeof detail === "object" && detail !== null && "workspaces" in detail) {
      const workspaces = Array.isArray((detail as { workspaces?: unknown }).workspaces) ? (detail as { workspaces: unknown[] }).workspaces.filter((x): x is WorkspaceChoice => Boolean(x && typeof x === "object" && "tenant_id" in x && "tenant_name" in x)) : [];
      throw new WorkspaceSelectionError(workspaces);
    }
    throw new Error(friendlyMessage(response.status, payload));
  }
  return payload as T;
}
function key() { return crypto.randomUUID(); }
export function getHealth(signal?: AbortSignal) { return getJson<ApiHealth>("/health", { signal }); }
export function getReadiness() { return getJson<ApiReadiness>("/ready"); }

export type Category = { id:string; tenant_id:string; parent_id?:string|null; name:string; code:string; description?:string|null; status:string; sort_order:number };
export type Brand = { id:string; tenant_id:string; name:string; code?:string|null; description?:string|null; status:string };
export type Unit = { id:string; tenant_id?:string|null; name:string; code:string; symbol:string; unit_type:string; allows_fraction:boolean; precision_scale:number; is_system:boolean };
export type PriceList = { id:string; tenant_id:string; name:string; currency:string; price_type:string; status:string; effective_from:string; effective_to?:string|null };
export type ProductPrice = { id:string; tenant_id:string; price_list_id:string; variant_id:string; unit_price:string; minimum_quantity:string; effective_from:string; effective_to?:string|null };

export type CatalogWorkspaceItem = Product & { brand_name?: string|null; category_name?: string|null; family_id?: string|null; family_name?: string|null; variant_count:number; variants: Array<{id:string;name:string;sku:string;status:string;unit_code:string;track_inventory:boolean}> };
export type CatalogWorkspace = { items: CatalogWorkspaceItem[]; next_cursor?: string|null; totals: {products:number;brands:number;categories:number;families:number}; references: { categories:Category[]; brands:Brand[]; families:Array<{id:string;name:string;code:string}>; units:Unit[]; price_lists:PriceList[]; price_contexts:Array<{id:string;name:string;code:string;currency:string;sales_channel?:string|null;customer_segment?:string|null;priority:number;status:string}> } };
export function getCatalogWorkspace(params: {q?:string; brand_id?:string; category_id?:string; family_id?:string; status_filter?:string; price_context_id?:string; limit?:number; cursor?:string}={}, signal?:AbortSignal) { const q=new URLSearchParams(); Object.entries(params).forEach(([k,v])=>{ if(v!==undefined && v!=="") q.set(k,String(v)); }); return getJson<CatalogWorkspace>(`/api/v1/catalog/workspace?${q.toString()}`, {signal}); }
export function getCategories() { return getJson<Page<Category>>('/api/v1/catalog/categories?limit=100'); }
export function getBrands() { return getJson<Page<Brand>>('/api/v1/catalog/brands?limit=100'); }
export function getUnits() { return getJson<Page<Unit>>('/api/v1/catalog/units?limit=100'); }
export function createProduct(body: {name:string; category_id:string; brand_id?:string|null; description?:string|null; product_type?:string; has_variants?:boolean}) { return getJson<Product>('/api/v1/catalog/products', { method:'POST', headers:{'Content-Type':'application/json','Idempotency-Key':key()}, body:JSON.stringify(body) }); }
export function createVariant(body: {product_id:string; name:string; sku:string; base_unit_id:string; track_inventory?:boolean; allow_fractional_quantity?:boolean}) { return getJson<Variant>('/api/v1/catalog/variants', { method:'POST', headers:{'Content-Type':'application/json','Idempotency-Key':key()}, body:JSON.stringify(body) }); }
export function getPriceLists() { return getJson<PriceList[]>('/api/v1/catalog/price-lists'); }
export function getPrices(params: {variant_id?:string; price_list_id?:string}={}) { const q=new URLSearchParams(); Object.entries(params).forEach(([k,v])=>v&&q.set(k,v)); return getJson<ProductPrice[]>(`/api/v1/catalog/prices?${q}`); }

export function getProducts(query = "", signal?: AbortSignal) { const params = new URLSearchParams({ limit: "50" }); if (query.trim()) params.set("q", query.trim()); return getJson<Page<Product>>(`/api/v1/catalog/products?${params.toString()}`, { signal }); }
export function getVariants(productId: string) { return getJson<Variant[]>(`/api/v1/catalog/products/${productId}/variants`); }

export function createWarehouse(body: {name:string; code:string; branch_id?:string|null}) { return getJson<{id:string;name:string;code:string}>("/api/v1/organization/warehouses", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body) }); }
export function createLocation(body: {name:string; code:string; warehouse_id:string}) { return getJson<Location>("/api/v1/organization/locations", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body) }); }
export function getLocations() { return getJson<Location[]>("/api/v1/organization/locations"); }
export function getVariantOptions() { return getJson<VariantOption[]>("/api/v1/inventory/variant-options"); }
export function getInventoryBalances(params: { location_id?: string; variant_id?: string; q?: string } = {}) { const q = new URLSearchParams(); q.set("limit", "500"); Object.entries(params).forEach(([k,v]) => v && q.set(k,v)); return getJson<InventoryBalance[]>(`/api/v1/inventory/balances?${q}`); }
export function getInventoryIntegrity() { return getJson<{status:string;checked:number;mismatches:any[]}>("/api/v1/inventory/integrity"); }
export function getInventoryLedger(params: { location_id?: string; variant_id?: string } = {}) { const q = new URLSearchParams(); q.set("limit", "500"); Object.entries(params).forEach(([k,v]) => v && q.set(k,v)); return getJson<InventoryLedger[]>(`/api/v1/inventory/ledger?${q}`); }
export function getAdjustments() { return getJson<InventoryAdjustment[]>("/api/v1/inventory/adjustments?limit=100"); }
export function getStockCounts() { return getJson<StockCount[]>("/api/v1/inventory/stock-counts?limit=100"); }
export function getTransfers() { return getJson<Transfer[]>("/api/v1/inventory/transfers?limit=100"); }
export function createAdjustment(body: unknown) { return getJson<{id:string;status:string}>("/api/v1/inventory/adjustments", { method:"POST", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }
export function approveAdjustment(id:string) { return getJson<{id:string;status:string}>(`/api/v1/inventory/adjustments/${id}/approve`, { method:"POST", headers:{"Idempotency-Key":key()} }); }
export function postAdjustment(id:string) { return getJson<{id:string;status:string}>(`/api/v1/inventory/adjustments/${id}/post`, { method:"POST", headers:{"Idempotency-Key":key()} }); }
export function createStockCount(body: unknown) { return getJson<{id:string;status:string}>("/api/v1/inventory/stock-counts", { method:"POST", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }
export function updateCountLines(id:string, body:unknown) { return getJson<{id:string;status:string}>(`/api/v1/inventory/stock-counts/${id}/lines`, { method:"PATCH", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body) }); }
export function submitStockCount(id:string) { return getJson<{id:string;status:string}>(`/api/v1/inventory/stock-counts/${id}/submit`, { method:"POST", headers:{"Idempotency-Key":key()} }); }
export function approveStockCount(id:string) { return getJson<{id:string;status:string}>(`/api/v1/inventory/stock-counts/${id}/approve`, { method:"POST", headers:{"Idempotency-Key":key()} }); }
export function postStockCount(id:string) { return getJson<{id:string;status:string}>(`/api/v1/inventory/stock-counts/${id}/post`, { method:"POST", headers:{"Idempotency-Key":key()} }); }
export function createTransfer(body: unknown) { return getJson<{id:string;status:string}>("/api/v1/inventory/transfers", { method:"POST", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }
export function approveTransfer(id:string) { return getJson<{id:string;status:string}>(`/api/v1/inventory/transfers/${id}/approve`, { method:"POST", headers:{"Idempotency-Key":key()} }); }
export function dispatchTransfer(id:string) { return getJson<{id:string;status:string}>(`/api/v1/inventory/transfers/${id}/dispatch`, { method:"POST", headers:{"Idempotency-Key":key()} }); }
export function receiveTransfer(id:string, body:unknown) { return getJson<{id:string;status:string}>(`/api/v1/inventory/transfers/${id}/receive`, { method:"POST", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }
export function completeTransfer(id:string) { return getJson<{id:string;status:string}>(`/api/v1/inventory/transfers/${id}/complete`, { method:"POST", headers:{"Idempotency-Key":key()} }); }
export type LoginRequest = { email: string; password: string; tenant_id?: string; };
export type AuthResponse = { access_token: string; refresh_token: string; token_type: string; session_id: string; tenant_id: string; tenant_name: string };
export type RegisterResponse = { user_id: string; tenant_id: string };
export function login(body: LoginRequest) { return getJson<AuthResponse>("/api/v1/auth/login", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body) }); }
export function register(body: { email:string; password:string; tenant_name:string }) { return getJson<RegisterResponse>("/api/v1/auth/register", { method:"POST", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }

export function openDevSession() { return getJson<AuthResponse>("/api/v1/auth/dev-session", { method:"POST" }); }
