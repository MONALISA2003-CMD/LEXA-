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
export type ApiReadiness = { status: string; dependencies?: { database?: string; cache?: string; [key: string]: string | undefined } };

export type WorkspaceChoice = { tenant_id: string; tenant_name: string };
export class WorkspaceSelectionError extends Error {
  workspaces: WorkspaceChoice[];
  constructor(workspaces: WorkspaceChoice[]) {
    super("Choose a workspace to continue.");
    this.name = "WorkspaceSelectionError";
    this.workspaces = workspaces;
  }
}
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function friendlyMessage(status: number, payload: unknown, path = ""): string {
  const detail = typeof payload === "object" && payload !== null && "detail" in payload ? (payload as { detail?: unknown }).detail : null;
  const code = typeof detail === "object" && detail !== null && "code" in detail ? String((detail as { code?: unknown }).code) : "";
  const raw = typeof detail === "string" ? detail : "";
  if (code === "WORKSPACE_SELECTION_REQUIRED") return "Choose a workspace to continue.";
  if (code === "NO_ACTIVE_WORKSPACE") return "Your sign-in worked, but this account has no active workspace yet. Ask your workspace administrator for access.";
  if (status === 401 && path === "/api/v1/auth/login") return "We couldn't sign you in. Check your email and password, then try again.";
  if (status === 401 && path === "/api/v1/auth/register") return "We could not verify that registration. Check the details and try again.";
  if (status === 401) return "Your session may have expired. Sign in again to continue.";
  if (status === 403) return "You don't have permission to do this. Ask your workspace administrator to review your access.";
  if (status === 404) return "We couldn't find that record. It may have been removed or you may not have access.";
  if (status === 409 && raw === "User already exists") return "An account with this email already exists. Sign in to continue.";
  if (status === 409 && raw.toLowerCase().includes("business")) return "That business information conflicts with an existing workspace.";
  if (status === 409 && code !== "WORKSPACE_SELECTION_REQUIRED") return "This change conflicts with the latest record. Refresh the page and review it before trying again.";
  if (status === 400 && raw === "Business name is required") return "Enter your business name to continue.";
  if (status === 422) return "Please check the required fields and correct any invalid information.";
  if (status === 429) return "Too many attempts. Please wait a moment before trying again.";
  if (status === 408 || status === 502 || status === 503 || status === 504 || status >= 500) return "LEXA couldn't complete the request right now. Your change may not have been saved. Check the record before retrying.";
  if (status >= 400) return "We couldn't complete that action. Review the information and try again.";
  return "Something went wrong. Please try again.";
}

let accessToken: string | null = null;
let refreshInFlight: Promise<AuthResponse> | null = null;
export function setAccessToken(token: string | null) { accessToken = token; }

function requiresSession(path: string): boolean {
  if (/^\/(health|ready)$/.test(path)) return false;
  if (/^\/api\/v1\/auth\/(login|register|refresh|logout)$/.test(path)) return false;
  // Invitation preview/accept are token-authorized public routes; they must not trigger cookie refresh.
  if (/^\/api\/v1\/invitations\/(preview|accept)(\?|$)/.test(path)) return false;
  return true;
}

async function getJson<T>(path: string, init?: RequestInit, retried = false): Promise<T> {
  // Protected pages often mount several data loaders at once. Restore the
  // cookie-backed session before sending those requests so they do not all
  // race into 401 -> refresh, and so failed auth never looks like empty data.
  if (!accessToken && requiresSession(path)) {
    await refreshSession();
  }
  const auth = accessToken;
  const headers: HeadersInit = { Accept: "application/json", ...(auth ? { Authorization: `Bearer ${auth}` } : {}), ...(init?.headers || {}) };
  const method = (init?.method || "GET").toUpperCase();
  const retryable = method === "GET" && /^\/(health|ready)$/.test(path);
  let response: Response | null = null;
  let lastNetworkError: unknown = null;
  for (let attempt = 0; attempt < (retryable ? 4 : 1); attempt += 1) {
    try {
      response = await fetch(`/api/lexa${path}`, { credentials: "include", cache: "no-store", ...init, headers });
      if (!retryable || ![502, 503, 504].includes(response.status) || attempt === 3) break;
      const retryAfter = Number(response.headers.get("retry-after") || "0");
      const delay = Number.isFinite(retryAfter) && retryAfter > 0 ? Math.min(retryAfter * 1000, 4000) : 500 * (attempt + 1);
      await new Promise(resolve => setTimeout(resolve, delay));
    } catch (error) {
      lastNetworkError = error;
      if (!retryable || attempt === 3) {
        throw new Error("We couldn't connect to LEXA right now. Check your connection and try again.");
      }
      await new Promise(resolve => setTimeout(resolve, 500 * (attempt + 1)));
    }
  }
  if (!response) {
    if (lastNetworkError) throw new Error("We couldn't connect to LEXA right now. Check your connection and try again.");
    throw new Error("We couldn't connect to LEXA right now. Check your connection and try again.");
  }
  const text = await response.text();
  let payload: unknown = null;
  try { payload = text ? JSON.parse(text) : null; } catch { payload = text; }
  if (!response.ok) {
    if (response.status === 401 && !retried && path !== "/api/v1/auth/login" && path !== "/api/v1/auth/refresh" && path !== "/api/v1/auth/logout" && path !== "/api/v1/auth/register") {
      try {
        await refreshSession();
        return getJson<T>(path, init, true);
      } catch {
        accessToken = null;
      }
    }
    const detail = typeof payload === "object" && payload !== null && "detail" in payload ? (payload as { detail?: unknown }).detail : null;
    const code = typeof detail === "object" && detail !== null && "code" in detail ? String((detail as { code?: unknown }).code) : "";
    if (code === "WORKSPACE_SELECTION_REQUIRED" && typeof detail === "object" && detail !== null && "workspaces" in detail) {
      const workspaces = Array.isArray((detail as { workspaces?: unknown }).workspaces) ? (detail as { workspaces: unknown[] }).workspaces.filter((x): x is WorkspaceChoice => Boolean(x && typeof x === "object" && "tenant_id" in x && "tenant_name" in x)) : [];
      throw new WorkspaceSelectionError(workspaces);
    }
    throw new ApiError(response.status, friendlyMessage(response.status, payload, path));
  }
  return payload as T;
}
function key() { return crypto.randomUUID(); }
export function getHealth(signal?: AbortSignal) { return getJson<ApiHealth>("/health", { signal }); }
export function getReadiness(signal?: AbortSignal) { return getJson<ApiReadiness>("/ready", signal ? { signal } : undefined); }

export type Category = { id:string; tenant_id:string; parent_id?:string|null; name:string; code:string; description?:string|null; status:string; sort_order:number };
export type Brand = { id:string; tenant_id:string; name:string; code?:string|null; description?:string|null; status:string };
export type Unit = { id:string; tenant_id?:string|null; name:string; code:string; symbol:string; unit_type:string; allows_fraction:boolean; precision_scale:number; is_system:boolean };
export type PriceList = { id:string; tenant_id:string; name:string; currency:string; price_type:string; status:string; effective_from:string; effective_to?:string|null };
export type ProductPrice = { id:string; tenant_id:string; price_list_id:string; variant_id:string; unit_price:string; minimum_quantity:string; effective_from:string; effective_to?:string|null };
export type Barcode = { id:string; tenant_id:string; variant_id:string; barcode:string; barcode_type:string; is_primary:boolean; status:string };
export function getCategories() { return getJson<Page<Category>>('/api/v1/catalog/categories?limit=100'); }
export function getBrands() { return getJson<Page<Brand>>('/api/v1/catalog/brands?limit=100'); }
export function getUnits() { return getJson<Page<Unit>>('/api/v1/catalog/units?limit=100'); }
export function createProduct(body: {name:string; category_id:string; brand_id?:string|null; description?:string|null; product_type?:string; has_variants?:boolean}) { return getJson<Product>('/api/v1/catalog/products', { method:'POST', headers:{'Content-Type':'application/json','Idempotency-Key':key()}, body:JSON.stringify(body) }); }
export function createVariant(body: {product_id:string; name:string; sku:string; base_unit_id:string; track_inventory?:boolean; allow_fractional_quantity?:boolean; costing_method?:string|null}) { return getJson<Variant>('/api/v1/catalog/variants', { method:'POST', headers:{'Content-Type':'application/json','Idempotency-Key':key()}, body:JSON.stringify(body) }); }
export function updateVariant(id:string, body:{name?:string;base_unit_id?:string;track_inventory?:boolean;allow_fractional_quantity?:boolean;status?:string;costing_method?:string|null}) { return getJson<Variant>(`/api/v1/catalog/variants/${id}`, { method:'PATCH', headers:{'Content-Type':'application/json','Idempotency-Key':key()}, body:JSON.stringify(body) }); }
export function getBarcodes(variantId?:string) { return getJson<Barcode[]>(variantId ? `/api/v1/catalog/barcodes?variant_id=${encodeURIComponent(variantId)}` : '/api/v1/catalog/barcodes'); }
export function createBarcode(body:{variant_id:string;barcode:string;barcode_type?:string;is_primary?:boolean}) { return getJson<Barcode>('/api/v1/catalog/barcodes',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)}); }
export function getPriceLists() { return getJson<PriceList[]>('/api/v1/catalog/price-lists'); }
export function createPriceList(body:{name:string;currency?:string;price_type?:string;effective_from:string;effective_to?:string|null}) { return getJson<PriceList>('/api/v1/catalog/price-lists',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)}); }
export function getPrices(params: {variant_id?:string; price_list_id?:string}={}) { const q=new URLSearchParams(); Object.entries(params).forEach(([k,v])=>v&&q.set(k,v)); return getJson<ProductPrice[]>(`/api/v1/catalog/prices?${q}`); }
export function createPrice(body:{price_list_id:string;variant_id:string;unit_price:string;minimum_quantity?:string;effective_from:string;effective_to?:string|null}) { return getJson<ProductPrice>('/api/v1/catalog/prices',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)}); }

export type CatalogLookupResult = { variant_id: string; product_id: string; product_name: string; variant_name: string; sku: string };
export function getProducts(query = "", signal?: AbortSignal) { const params = new URLSearchParams({ limit: "50" }); if (query.trim()) params.set("q", query.trim()); return getJson<Page<Product>>(`/api/v1/catalog/products?${params.toString()}`, { signal }); }
export function getProduct(productId: string, signal?: AbortSignal) { return getJson<Product>(`/api/v1/catalog/products/${encodeURIComponent(productId)}`, signal ? { signal } : undefined); }
export function getCatalogLookup(query: string, signal?: AbortSignal) { const params = new URLSearchParams({ q: query.trim(), limit: "10" }); return getJson<CatalogLookupResult[]>(`/api/v1/catalog/lookup?${params.toString()}`, signal ? { signal } : undefined); }
export function getVariants(productId: string) { return getJson<Variant[]>(`/api/v1/catalog/products/${productId}/variants`); }

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
export function createWarehouse(body: {name:string; code:string; branch_id?:string|null}) { return getJson<Warehouse>("/api/v1/organization/warehouses", { method:"POST", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }
export function createLocation(body: {name:string; code:string; warehouse_id:string}) { return getJson<Location>("/api/v1/organization/locations", { method:"POST", headers:{"Content-Type":"application/json","Idempotency-Key":key()}, body:JSON.stringify(body) }); }
export function getLocations() { return getJson<Location[]>("/api/v1/organization/locations"); }
export function getVariantOptions() { return getJson<VariantOption[]>("/api/v1/inventory/variant-options"); }
export function getInventoryBalances(params: { location_id?: string; variant_id?: string; q?: string } = {}, signal?: AbortSignal) { const q = new URLSearchParams(); q.set("limit", "500"); Object.entries(params).forEach(([k,v]) => v && q.set(k,v)); return getJson<InventoryBalance[]>(`/api/v1/inventory/balances?${q}`, signal ? { signal } : undefined); }
export type InventorySummaryAttention = { variant_id: string; location_id: string; on_hand: string; reserved: string; available: string; product_name: string; sku: string | null; location_name: string };
export type InventorySummary = { stock_value: string; balance_rows: number; out_of_stock_rows: number; low_stock_rows: number; attention: InventorySummaryAttention[] };
export function getInventorySummary(signal?: AbortSignal) { return getJson<InventorySummary>("/api/v1/inventory/summary", signal ? { signal } : undefined); }
export function getInventoryIntegrity() { return getJson<{status:string;checked:number;mismatches:any[]}>("/api/v1/inventory/integrity"); }
export type InventoryMovementHealth = { location_id:string; location_name:string; variant_id:string; product_name:string; variant_name:string; sku:string|null; on_hand:string; reserved:string; available:string; inbound:string; stock_value:string; last_sale_at:string|null; days_since_last_sale:number|null; units_sold_30d:string; units_returned_30d:string; net_units_sold_30d:string; units_sold_90d:string; units_returned_90d:string; net_units_sold_90d:string; minimum_available:string|null; health_status:string; currency_note:string };
export function getInventoryMovementHealth(locationId?:string) { const q = new URLSearchParams({limit:"500"}); if(locationId) q.set("location_id",locationId); return getJson<{source:string;counts_as_completed_sale_only:boolean;count:number;items:InventoryMovementHealth[]}>(`/api/v1/inventory/movement-health?${q}`); }
export type InventoryAgeing = { location_id:string; location_name:string; variant_id:string; sku:string|null; product_name:string; variant_name:string; on_hand:string; reserved:string; available:string; stock_value:string; average_cost:string; aged_over_30:string; aged_over_60:string; aged_over_90:string; traceable_remaining:string; unknown_age_quantity:string; oldest_remaining_age_days:number|null; last_movement_at:string|null; reconciliation_gap:boolean; age_status:string; currency_note:string };
export function getInventoryAgeing(locationId?:string) { const q = new URLSearchParams({limit:"500"}); if(locationId) q.set("location_id",locationId); return getJson<{source:string;age_method:string;count:number;items:InventoryAgeing[]}>(`/api/v1/inventory/ageing?${q}`); }
export type ReplenishmentPolicy = { id:string; location_id:string; variant_id:string; location_name:string; product_name:string; variant_name:string; sku:string|null; lead_time_days:number; review_period_days:number; lookback_days:number; minimum_available:string; safety_stock:string; enabled:boolean; created_at:string; updated_at:string };
export type ReplenishmentRecommendation = { policy_id:string; location_id:string; variant_id:string; location_name:string; product_name:string; variant_name:string; sku:string|null; on_hand:string; reserved:string; available:string; inbound:string; units_sold:string; units_returned:string; net_units_demand:string; lookback_days:number; average_daily_demand:string; days_cover:string|null; target_stock:string; reorder_quantity:string; recommended_action:string; reason_code:string; average_cost:string; estimated_reorder_value:string; currency_note:string; methodology:string };
export function getInventoryReplenishmentPolicies(locationId?:string) { const q = new URLSearchParams(); q.set("limit","500"); if(locationId) q.set("location_id",locationId); return getJson<ReplenishmentPolicy[]>(`/api/v1/inventory/replenishment/policies?${q}`); }
export function getInventoryReplenishmentRecommendations(locationId?:string) { const q = new URLSearchParams(); q.set("limit","500"); q.set("include_covered","true"); if(locationId) q.set("location_id",locationId); return getJson<{source:string;advisory_only:boolean;count:number;items:ReplenishmentRecommendation[]}>(`/api/v1/inventory/replenishment/recommendations?${q}`); }
export function upsertInventoryReplenishmentPolicy(body:{location_id:string;variant_id:string;lead_time_days:number;review_period_days:number;lookback_days:number;minimum_available:string;safety_stock:string;enabled:boolean}) { return getJson<Partial<ReplenishmentPolicy>>("/api/v1/inventory/replenishment/policies",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}); }
export function getInventoryLedger(params: { location_id?: string; variant_id?: string; transaction_type?: string } = {}, signal?: AbortSignal) { const q = new URLSearchParams(); q.set("limit", "500"); Object.entries(params).forEach(([k,v]) => v && q.set(k,v)); return getJson<InventoryLedger[]>(`/api/v1/inventory/ledger?${q}`, signal ? { signal } : undefined); }
export function getProductInventory(variantId:string) { return getJson<{balances:InventoryBalance[];ledger:InventoryLedger[]}>(`/api/v1/inventory/products/${variantId}`); }
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
export type AuthResponse = { access_token: string; token_type: string; session_id: string; tenant_id: string; tenant_name: string };
export type RegisterResponse = { user_id: string; tenant_id: string; branch_id?: string; warehouse_id?: string; location_id?: string };

/**
 * Refresh via the HttpOnly cookie. Share the promise across simultaneous page
 * loaders so refresh-token rotation only happens once at a time.
 */
function refreshSession(): Promise<AuthResponse> {
  if (!refreshInFlight) {
    refreshInFlight = getJson<AuthResponse>("/api/v1/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }, true)
      .then((response) => {
        setAccessToken(response.access_token);
        return response;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

export async function login(body: LoginRequest) { const response = await getJson<AuthResponse>("/api/v1/auth/login", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body) }); setAccessToken(response.access_token); return response; }
export type RegisterRequest = { email: string; password: string; tenant_name: string; country_code: string; currency_code: string; branch_name: string; warehouse_name: string; location_name: string };
export function register(body: RegisterRequest, idempotencyKey = key()) { return getJson<RegisterResponse>("/api/v1/auth/register", { method:"POST", headers:{"Content-Type":"application/json","Idempotency-Key":idempotencyKey}, body:JSON.stringify(body) }); }

export type CurrentIdentity = {
  user: { id: string; email: string; is_active: boolean };
  workspace: { id: string; name: string; status: string };
  membership: { id: string; status: string };
  roles: string[];
  permissions: string[];
};
export function getCurrentIdentity() { return getJson<CurrentIdentity>("/api/v1/auth/me"); }

export async function restoreSession() {
  try {
    const session = await refreshSession();
    // Do not unlock the workspace until the API confirms user + tenant membership.
    await getCurrentIdentity();
    return session;
  } catch (error) {
    setAccessToken(null);
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}
export async function logout() {
  try { await getJson<{status:string}>("/api/v1/auth/logout", { method:"POST", headers:{"Content-Type":"application/json"}, body:"{}" }, true); } finally { setAccessToken(null); }
}


export type KernelSummary = { tenant_id:string; counts:Record<string,number> };
export type KernelParty = { id:string; tenant_id:string; party_type:string; display_name:string; legal_name?:string|null; email?:string|null; phone?:string|null; status:string; metadata:Record<string,unknown> };
export type KernelService = { id:string; tenant_id:string; name:string; code:string; description?:string|null; service_type?:string|null; status:string; metadata:Record<string,unknown> };
export type KernelResource = { id:string; tenant_id:string; resource_type:string; name:string; code:string; capacity?:string|null; status:string; metadata:Record<string,unknown> };
export type KernelTask = { id:string; tenant_id:string; title:string; description?:string|null; status:string; priority:string; assigned_to_user_id?:string|null; entity_type?:string|null; entity_id?:string|null; due_at?:string|null; metadata:Record<string,unknown> };
export function getKernelSummary() { return getJson<KernelSummary>('/api/v1/kernel/summary'); }
export function getKernelParties() { return getJson<KernelParty[]>('/api/v1/kernel/parties'); }
export function createKernelParty(body:{party_type:'PERSON'|'ORGANIZATION';display_name:string;legal_name?:string;email?:string;phone?:string}) { return getJson<KernelParty>('/api/v1/kernel/parties',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)}); }
export function getKernelServices() { return getJson<KernelService[]>('/api/v1/kernel/services'); }
export function createKernelService(body:{name:string;code:string;description?:string;service_type?:string}) { return getJson<KernelService>('/api/v1/kernel/services',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)}); }
export function getKernelResources() { return getJson<KernelResource[]>('/api/v1/kernel/resources'); }
export function createKernelResource(body:{resource_type:string;name:string;code:string;capacity?:string}) { return getJson<KernelResource>('/api/v1/kernel/resources',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)}); }
export function getKernelTasks() { return getJson<KernelTask[]>('/api/v1/kernel/tasks'); }
export function createKernelTask(body:{title:string;description?:string;priority?:'LOW'|'NORMAL'|'HIGH'|'URGENT'}) { return getJson<KernelTask>('/api/v1/kernel/tasks',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)}); }



// Phase 5 analytics / BI contracts
export type AnalyticsDailyMetric = { business_date:string; currency_code:string; sales_total:string; returns_total:string; net_sales:string; payments_collected:string; refunds_total:string; credit_created:string; expenses_total:string; net_cash_movement:string; sale_count:number; return_count:number; payment_count:number; expense_count:number };
export type AnalyticsProductMetric = { business_date:string; variant_id:string; product_id:string; sku?:string|null; product_name?:string|null; variant_name?:string|null; units_sold:string; sales_amount:string; discount_amount:string; tax_amount:string; returns_units:string; returns_amount:string; net_sales:string; cogs:string; gross_margin:string; currency_code:string };
export type AnalyticsCustomerMetric = { customer_party_id:string; customer_name?:string|null; first_sale_date?:string|null; last_sale_date?:string|null; sale_count:number; total_sales:string; total_returns:string; net_sales:string; total_paid:string; outstanding_balance:string; average_sale_value:string };
export type AnalyticsInventoryHealth = { snapshot_date:string; location_id:string; location_name?:string|null; variant_id:string; sku?:string|null; product_name?:string|null; variant_name?:string|null; on_hand:string; reserved:string; available:string; stock_value:string; units_sold_30d:string; daily_velocity:string; days_cover?:string|null };
export type AnalyticsBranchMetric = { branch_id:string; branch_name?:string|null; business_date:string; currency_code:string; sales_total:string; returns_total:string; net_sales:string; payments_collected:string; credit_created:string; sale_count:number };
export type AnalyticsOverview = { from_date:string; to_date:string; currency_code:string; totals:{sales_total:string;returns_total:string;net_sales:string;payments_collected:string;refunds_total:string;credit_created:string;expenses_total:string;net_cash_movement:string;sale_count:number}; daily:AnalyticsDailyMetric[] };
export function getAnalyticsOverview(fromDate:string,toDate:string,currency:string){return getJson<AnalyticsOverview>(`/api/v1/analytics/overview?start_date=${encodeURIComponent(fromDate)}&end_date=${encodeURIComponent(toDate)}&currency_code=${encodeURIComponent(currency)}`);}
export function getAnalyticsDaily(fromDate:string,toDate:string,currency:string){return getJson<AnalyticsDailyMetric[]>(`/api/v1/analytics/daily?start_date=${encodeURIComponent(fromDate)}&end_date=${encodeURIComponent(toDate)}&currency_code=${encodeURIComponent(currency)}`);}
export function getAnalyticsProducts(fromDate:string,toDate:string,currency:string){return getJson<AnalyticsProductMetric[]>(`/api/v1/analytics/products?start_date=${encodeURIComponent(fromDate)}&end_date=${encodeURIComponent(toDate)}&currency_code=${encodeURIComponent(currency)}&limit=100`);}
export type AnalyticsProductSummary = { variant_id:string; product_id:string; sku?:string|null; product_name?:string|null; variant_name?:string|null; units_sold:string; sales_amount:string; discount_amount:string; tax_amount:string; returns_units:string; returns_amount:string; net_sales:string; cogs:string; gross_margin:string; currency_code:string };
export function getAnalyticsProductSummary(fromDate:string,toDate:string,currency:string,limit=5){return getJson<AnalyticsProductSummary[]>(`/api/v1/analytics/products/summary?start_date=${encodeURIComponent(fromDate)}&end_date=${encodeURIComponent(toDate)}&currency_code=${encodeURIComponent(currency)}&limit=${encodeURIComponent(String(limit))}`);}
export function getAnalyticsCustomers(){return getJson<AnalyticsCustomerMetric[]>('/api/v1/analytics/customers?limit=100');}
export function getAnalyticsInventoryHealth(){return getJson<AnalyticsInventoryHealth[]>('/api/v1/analytics/inventory-health?limit=100');}
export function getAnalyticsBranches(fromDate:string,toDate:string,currency:string){return getJson<AnalyticsBranchMetric[]>(`/api/v1/analytics/branches?start_date=${encodeURIComponent(fromDate)}&end_date=${encodeURIComponent(toDate)}&currency_code=${encodeURIComponent(currency)}`);}
export function refreshAnalytics(fromDate:string,toDate:string){return getJson<{run_id:string;status:string}>(`/api/v1/analytics/refresh?start_date=${encodeURIComponent(fromDate)}&end_date=${encodeURIComponent(toDate)}`,{method:'POST',headers:{'Idempotency-Key':key()}});}

// Phase 4A commerce contracts
export type CommerceCustomer = { id:string; party_id:string; display_name:string; party_type:string; email?:string|null; phone?:string|null; credit_limit:string; status:string; notes?:string|null; created_at:string };
export type PaymentChannel = { id:string; tenant_id:string; name:string; channel_type:string; provider?:string|null; currency_code:string; active:boolean; created_at:string; updated_at:string };
export type CommerceProduct = { variant_id:string; sku:string; variant_name:string; product_name:string; track_inventory:boolean; selling_price:string };
export type CommerceSale = { id:string; transaction_id:string; customer_party_id?:string|null; customer_name?:string|null; currency_code:string; status:string; subtotal:string; discount_total:string; tax_total:string; total:string; amount_paid:string; amount_due:string; return_adjustment_amount?:string; created_at:string; completed_at?:string|null };
export type Receivable = { id:string; sale_id:string; customer_party_id:string; customer_name:string; original_amount:string; paid_amount:string; adjustment_amount:string; balance:string; status:string; due_at?:string|null; created_at:string };
export type ReconciliationLine = { line_id:string; payment_channel_id:string; channel_name:string; channel_type:string; expected_amount:string; actual_amount?:string|null; variance?:string|null; line_status:string; line_notes?:string|null; reviewed_by?:string|null };
export type Reconciliation = { id:string; business_date:string; status:string; notes?:string|null; closed_at?:string|null; lines:ReconciliationLine[] };
export type CommerceDashboard = { business_date:string; currency_code:string; sales:{sales:string;collected:string;credit:string}; payment_channels:Array<{id:string;name:string;channel_type:string;currency_code:string;active:boolean;expected:string}>; outstanding_receivables:string };
export type CommerceSaleLine = { sale_line_id:string; product_variant_id:string; sku?:string|null; variant_name?:string|null; quantity:string; unit_price:string; discount_amount:string; tax_amount:string; line_total:string };
export type CommerceSalePayment = { id:string; payment_channel_id:string; channel_name?:string|null; payment_amount:string; allocated_amount:string; currency_code:string; method:string; reference?:string|null; business_date:string; paid_at:string; status:string; allocation_type:'SALE'|'RECEIVABLE' };
export type SaleReturn = { id:string; sale_id:string; status:string; reason:string; total:string; completed_at?:string|null; created_at:string; refunded:string; credit_balance:string; journal_entry_id?:string|null; fiscal_document_id?:string|null; fiscal_document_status?:string|null; cogs_journal_entry_id?:string|null };
export type CommerceAccountingEntry = { id:string; source_type:string; source_id?:string|null; entry_role:string; entry_date:string; reference?:string|null; description:string; currency_code:string; status:string; posted_at?:string|null };
export type CommerceSaleRefund = { id:string; return_id:string; payment_channel_id:string; channel_name?:string|null; amount:string; currency_code:string; reference?:string|null; business_date:string; status:string; reason:string };
export type CommerceSaleDetail = CommerceSale & { branch_id?:string|null; location_id?:string|null; notes?:string|null; lines:CommerceSaleLine[]; payments?:CommerceSalePayment[]; returns?:SaleReturn[]; refunds?:CommerceSaleRefund[]; accounting_entries?:CommerceAccountingEntry[] };

export function getCommerceDashboard(dateValue=''){return getJson<CommerceDashboard>(`/api/v1/commerce/dashboard${dateValue?`?business_date=${encodeURIComponent(dateValue)}`:''}`);}
export function getCommerceCustomers(search=''){return getJson<CommerceCustomer[]>(`/api/v1/commerce/customers${search?`?search=${encodeURIComponent(search)}`:''}`);}
export function createCommerceCustomer(body:{display_name:string;party_type?:'PERSON'|'ORGANIZATION';legal_name?:string;email?:string;phone?:string;credit_limit?:string;notes?:string}){return getJson<CommerceCustomer>('/api/v1/commerce/customers',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}
export function getPaymentChannels(){return getJson<PaymentChannel[]>('/api/v1/commerce/payment-channels');}
export function createPaymentChannel(body:{name:string;channel_type:string;provider?:string;currency_code:string}){return getJson<PaymentChannel>('/api/v1/commerce/payment-channels',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}
export function getCommerceProducts(){return getJson<CommerceProduct[]>('/api/v1/commerce/products');}
export type CommerceSalesQuery = { limit?:number; offset?:number; search?:string; status?:string; start_date?:string; end_date?:string; branch_id?:string };
export function getCommerceSales(query:CommerceSalesQuery={}){
  const params = new URLSearchParams({limit:String(query.limit ?? 100),offset:String(query.offset ?? 0)});
  for (const field of ["search","status","start_date","end_date","branch_id"] as const) {
    const value = query[field];
    if (value && value.trim()) params.set(field,value.trim());
  }
  return getJson<CommerceSale[]>(`/api/v1/commerce/sales?${params.toString()}`);
}
export function getCommerceSale(id:string){return getJson<CommerceSaleDetail>(`/api/v1/commerce/sales/${id}`);}
export function createCommerceSale(body:{customer_party_id?:string|null;branch_id?:string|null;location_id:string;currency_code:string;business_date:string;lines:Array<{variant_id:string;quantity:string;unit_price:string;discount_amount?:string;tax_rate?:string}>;payments:Array<{payment_channel_id:string;amount:string;reference?:string|null}>;notes?:string|null}, idempotencyKey?:string){return getJson<CommerceSale>('/api/v1/commerce/sales',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':idempotencyKey || key()},body:JSON.stringify(body)});}
export function getReceivables(){return getJson<Receivable[]>('/api/v1/commerce/receivables');}
export function payReceivable(id:string,body:{payment_channel_id:string;amount:string;business_date:string;reference?:string|null}){return getJson<Receivable>(`/api/v1/commerce/receivables/${id}/payments`,{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}
export function getReconciliations(dateValue=''){return getJson<Reconciliation[]>(`/api/v1/commerce/reconciliations${dateValue?`?business_date=${encodeURIComponent(dateValue)}`:''}`);}
export function createReconciliation(body:{business_date:string;notes?:string}){return getJson<Reconciliation>('/api/v1/commerce/reconciliations',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}
export function setReconciliationActual(id:string,body:{actual_amount:string;notes?:string}){return getJson<ReconciliationLine>(`/api/v1/commerce/reconciliation-lines/${id}/actual`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});}
export function resolveReconciliationLine(id:string,body:{status:'RESOLVED'|'ACKNOWLEDGED';notes?:string}){return getJson<ReconciliationLine>(`/api/v1/commerce/reconciliation-lines/${id}/resolve`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});}
export function closeReconciliation(id:string){return getJson<{id:string;business_date:string;status:string;closed_at:string}>(`/api/v1/commerce/reconciliations/${id}/close`,{method:'POST',headers:{'Idempotency-Key':key()}});}
export function getSaleReturns(){return getJson<SaleReturn[]>('/api/v1/commerce/returns');}
export function createSaleReturn(saleId:string,body:{reason:string;inventory_location_id?:string|null;business_date:string;settlement_type:'NONE'|'REFUND'|'CUSTOMER_CREDIT';refund_channel_id?:string|null;lines:Array<{sale_line_id:string;quantity:string}>}){return getJson<SaleReturn>(`/api/v1/commerce/sales/${saleId}/returns`,{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}

// Phase 4B accounting + compliance
export type AccountingAccount = { id:string; code:string; name:string; account_type:string; normal_balance:string; system_key?:string|null; currency_code?:string|null; allow_posting:boolean; status:string; created_at:string; updated_at:string };
export type AccountingPeriod = { id:string; period_name:string; start_date:string; end_date:string; status:string; closed_at?:string|null; closed_by?:string|null; created_at:string; updated_at:string };
export type JournalEntry = { id:string; entry_date:string; source_type:string; source_id?:string|null; entry_role:string; reference?:string|null; description:string; currency_code:string; status:string; posted_at?:string|null; posted_by?:string|null; created_at:string };
export type JournalLine = { id:string; line_no:number; account_id:string; account_code:string; account_name:string; description?:string|null; debit:string; credit:string; currency_code:string; party_id?:string|null };
export type JournalEntryDetail = { entry:JournalEntry; lines:JournalLine[] };
export type ExpenseRecord = { id:string; expense_date:string; reference:string; description:string; expense_account_id:string; expense_account_code:string; expense_account_name:string; payment_channel_id?:string|null; payment_channel_name?:string|null; currency_code:string; subtotal:string; tax_amount:string; total:string; status:string; journal_entry_id?:string|null; created_at:string; updated_at:string };
export type FiscalDocument = { id:string; source_type:string; source_id:string; document_type:string; currency_code:string; issue_date:string; status:string; document_number?:string|null; fdn?:string|null; verification_code?:string|null; qr_code?:string|null; efris_reference?:string|null; response_code?:string|null; response_message?:string|null; submitted_at?:string|null; accepted_at?:string|null; voided_at?:string|null; last_error?:string|null; created_at:string; updated_at:string };
export type EfrisConfig = { id:string; enabled:boolean; integration_mode:string; registration_status:string; tin?:string|null; legal_name?:string|null; effective_date?:string|null; created_at:string; updated_at:string };
export function getAccountingAccounts(){return getJson<AccountingAccount[]>('/api/v1/accounting/accounts');}
export function createAccountingAccount(body:{code:string;name:string;account_type:string;normal_balance:string;system_key?:string|null;currency_code?:string|null;allow_posting?:boolean}){return getJson<AccountingAccount>('/api/v1/accounting/accounts',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}
export function getAccountingPeriods(){return getJson<AccountingPeriod[]>('/api/v1/accounting/periods');}
export function closeAccountingPeriod(id:string){return getJson<{id:string;status:string}>(`/api/v1/accounting/periods/${id}/close`,{method:'POST',headers:{'Idempotency-Key':key()}});}
export function getTrialBalance(startDate:string,endDate:string){return getJson<AccountingAccount[]>(`/api/v1/accounting/trial-balance?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`);}
export function getIncomeStatement(startDate:string,endDate:string){return getJson<Array<{account_id:string;code:string;name:string;account_type:string;amount:string}>>(`/api/v1/accounting/income-statement?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`);}
export function getBalanceSheet(asOf:string){return getJson<Array<{account_id:string;code:string;name:string;account_type:string;amount:string}>>(`/api/v1/accounting/balance-sheet?as_of=${encodeURIComponent(asOf)}`);}
export function getJournalEntries(status?:string){return getJson<JournalEntry[]>(`/api/v1/accounting/journal-entries${status?`?status=${encodeURIComponent(status)}`:''}`);}
export function getJournalEntry(id:string){return getJson<JournalEntryDetail>(`/api/v1/accounting/journal-entries/${id}`);}
export function postJournalEntry(id:string){return getJson<{id:string;status:string}>(`/api/v1/accounting/journal-entries/${id}/post`,{method:'POST',headers:{'Idempotency-Key':key()}});}
export function reverseJournalEntry(id:string){return getJson<{id:string;status:string;reversal_of:string}>(`/api/v1/accounting/journal-entries/${id}/reverse`,{method:'POST',headers:{'Idempotency-Key':key()}});}
export function postSaleAccounting(id:string){return getJson<{sale_id:string;sale_journal_id:string;cogs_journal_id?:string|null}>(`/api/v1/accounting/sales/${id}/post`,{method:'POST',headers:{'Idempotency-Key':key()}});}
export function postPaymentAccounting(id:string){return getJson<{payment_id:string;journal_entry_id:string}>(`/api/v1/accounting/payments/${id}/post`,{method:'POST',headers:{'Idempotency-Key':key()}});}
export function getExpenses(){return getJson<ExpenseRecord[]>('/api/v1/accounting/expenses');}
export function createExpense(body:{expense_date:string;reference:string;description:string;expense_account_id:string;payment_channel_id?:string|null;currency_code:string;subtotal:string;tax_amount?:string;supplier_party_id?:string|null}){return getJson<{id:string;status:string;total:string}>('/api/v1/accounting/expenses',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}
export function postExpense(id:string){return getJson<{expense_id:string;journal_entry_id:string;status:string}>(`/api/v1/accounting/expenses/${id}/post`,{method:'POST',headers:{'Idempotency-Key':key()}});}
export function getEfrisConfig(){return getJson<EfrisConfig>('/api/v1/compliance/efris/config');}
export function updateEfrisConfig(body:{enabled:boolean;integration_mode:string;registration_status:string;tin?:string|null;legal_name?:string|null;effective_date?:string|null}){return getJson<EfrisConfig>('/api/v1/compliance/efris/config',{method:'PUT',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}
export function getFiscalDocuments(status?:string){return getJson<FiscalDocument[]>(`/api/v1/compliance/fiscal-documents${status?`?status=${encodeURIComponent(status)}`:''}`);}
export function fiscalizeSale(saleId:string,documentType:'INVOICE'|'RECEIPT'='INVOICE'){return getJson<{fiscal_document_id:string;status:string}>(`/api/v1/compliance/sales/${saleId}/fiscalize?document_type=${documentType}`,{method:'POST',headers:{'Idempotency-Key':key()}});}
export type TaxRate = { id:string; code:string; name:string; rate_percent:string; inclusive:boolean; effective_from:string; effective_to?:string|null; status:string; created_at:string; updated_at:string };
export type TaxConfiguration = { id:string; name:string; tax_rate_id:string; tax_code:string; rate_percent:string; inclusive:boolean; scope_type:string; scope_id?:string|null; effective_from:string; effective_to?:string|null; status:string };
export function getTaxRates(){return getJson<TaxRate[]>('/api/v1/accounting/tax-rates');}
export function getTaxConfigurations(){return getJson<TaxConfiguration[]>('/api/v1/accounting/tax-configurations');}
export function createTaxRate(body:{code:string;name:string;rate_percent:string;inclusive?:boolean;effective_from:string;effective_to?:string|null}){return getJson<TaxRate>('/api/v1/accounting/tax-rates',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}
export function createTaxConfiguration(body:{name:string;tax_rate_id:string;scope_type:'DEFAULT'|'PRODUCT'|'CATEGORY';scope_id?:string|null;effective_from:string;effective_to?:string|null}){return getJson<TaxConfiguration>('/api/v1/accounting/tax-configurations',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}
// Phase 3 Increment 02: authoritative workspace context and resumable setup.
export type WorkspaceOption = { tenant_id: string; tenant_name: string; membership_id: string; current: boolean };
export type WorkspaceContext = {
  workspace: { id: string; name: string; status: string };
  membership: { id: string; status: string };
  branches: { id: string; name: string; code: string; assigned: boolean }[];
  session_id: string;
};
export type SetupProgress = {
  status: "COMPLETE" | "IN_PROGRESS";
  complete: boolean;
  completed_required_steps: number;
  required_steps: number;
  resume_path: string;
  steps: { key: string; label: string; href: string; required: boolean; complete: boolean }[];
};
export function getWorkspaceOptions() { return getJson<{ items: WorkspaceOption[] }>("/api/v1/workspace/options"); }
export async function selectWorkspace(tenantId: string) {
  const session = await getJson<AuthResponse>("/api/v1/workspace/select", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tenant_id: tenantId }),
  });
  setAccessToken(session.access_token);
  return session;
}
export function getWorkspaceContext() { return getJson<WorkspaceContext>("/api/v1/workspace/context"); }
export function getSetupProgress() { return getJson<SetupProgress>("/api/v1/workspace/setup/progress"); }

// Phase 3 Increment 03: member lifecycle, invitation lifecycle and branch scope.
export type WorkspaceRole = { id: string; tenant_id: string; name: string; description?: string | null };
export type WorkspaceMember = {
  id: string; user_id: string; email: string; status: "ACTIVE" | "INACTIVE";
  roles: { id: string; name: string }[]; branch_ids: string[];
};
export type WorkspaceInvitation = {
  id: string; email: string; status: "PENDING" | "ACCEPTED" | "REVOKED" | "EXPIRED";
  role_id: string | null; branch_ids: string[]; expires_at: string; created_at?: string | null;
};
export function getWorkspaceRoles() { return getJson<WorkspaceRole[]>("/api/v1/rbac/roles"); }
export function getWorkspaceMembers() { return getJson<{ items: WorkspaceMember[] }>("/api/v1/members"); }
export function updateWorkspaceMemberStatus(id: string, status: "ACTIVE" | "INACTIVE") {
  return getJson<{ id: string; status: string; changed: boolean }>(`/api/v1/members/${encodeURIComponent(id)}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }),
  });
}
export function replaceWorkspaceMemberBranches(id: string, branchIds: string[]) {
  return getJson<{ membership_id: string; branch_ids: string[]; status: string }>(`/api/v1/members/${encodeURIComponent(id)}/branches`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ branch_ids: branchIds }),
  });
}
export function getWorkspaceInvitations() { return getJson<{ items: WorkspaceInvitation[] }>("/api/v1/invitations"); }
export function createWorkspaceInvitation(body: { email: string; role_id: string; branch_ids: string[]; expires_in_days: number }) {
  return getJson<{ id: string; status: string; email: string; expires_at: string; invite_url: string | null; replayed: boolean; message?: string }>(
    "/api/v1/invitations", { method: "POST", headers: { "Content-Type": "application/json", "Idempotency-Key": key() }, body: JSON.stringify(body) },
  );
}
export function resendWorkspaceInvitation(id: string) {
  return getJson<{ id: string; email?: string; status: string; invite_url: string | null; replayed: boolean; message?: string }>(
    `/api/v1/invitations/${encodeURIComponent(id)}/resend`, { method: "POST", headers: { "Idempotency-Key": key() } },
  );
}
export function revokeWorkspaceInvitation(id: string) {
  return getJson<{ id: string; status: string; changed: boolean }>(`/api/v1/invitations/${encodeURIComponent(id)}/revoke`, { method: "POST" });
}
export function previewWorkspaceInvitation(token: string) {
  return getJson<{ email: string; workspace_name: string; expires_at: string }>("/api/v1/invitations/preview", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token }),
  });
}
export async function acceptWorkspaceInvitation(token: string, password: string) {
  const session = await getJson<AuthResponse & { user_id: string }>("/api/v1/invitations/accept", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, password }),
  });
  setAccessToken(session.access_token);
  return session;
}

// Phase 3 Increment 04: replace role assignments through tenant-scoped, audited API.
export function replaceWorkspaceMemberRoles(id: string, roleIds: string[]) {
  return getJson<{ membership_id: string; roles: { id: string; name: string }[]; changed: boolean }>(`/api/v1/members/${encodeURIComponent(id)}/roles`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ role_ids: roleIds }),
  });
}

// Phase 3 Increment 06: owner-managed role and permission catalog.
export type WorkspacePermission = { id: string; code: string; description?: string | null };
export type WorkspaceRolePermissionEntry = WorkspaceRole & { permission_ids: string[] };
export function getWorkspaceRolePermissionCatalog() {
  return getJson<{ roles: WorkspaceRolePermissionEntry[]; permissions: WorkspacePermission[] }>("/api/v1/members/role-permissions");
}
export function createWorkspaceRole(body: { name: string; description?: string }) {
  return getJson<WorkspaceRole>("/api/v1/members/roles", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}
export function replaceWorkspaceRolePermissions(roleId: string, permissionIds: string[]) {
  return getJson<{ role_id: string; permission_ids: string[]; changed: boolean }>(`/api/v1/members/roles/${encodeURIComponent(roleId)}/permissions`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ permission_ids: permissionIds }),
  });
}

// Phase 7 — supplier, purchasing, receiving, returns and payables.
export type PurchasingSupplier = {
  supplier_party_id: string; supplier_id?: string | null; name: string; legal_name?: string | null;
  email?: string | null; phone?: string | null; currency_code: string; payment_terms_days: number;
  default_receiving_location_id?: string | null; tax_number?: string | null; notes?: string | null;
  party_status?: string; profile_status?: string; status?: string; code?: string | null;
  net_balance?: string | number; created_at?: string; updated_at?: string;
};
export type PurchasingSupplierCost = {
  id: string; supplier_party_id: string; variant_id: string; currency_code: string; unit_cost: string;
  minimum_quantity: string; effective_from: string; effective_to?: string | null; lead_time_days?: number | null;
  sku?: string; variant_name?: string; product_name?: string;
};
export type PurchaseOrderLine = {
  id: string; purchase_order_id: string; line_number: number; variant_id: string; ordered_quantity: string;
  received_quantity: string; unit_cost: string; tax_rate: string; tax_amount: string; line_subtotal: string;
  line_total: string; sku?: string; variant_name?: string; product_name?: string; description?: string | null;
};
export type PurchaseOrder = {
  id: string; po_number: string; supplier_party_id: string; supplier_name?: string; branch_id: string;
  branch_name?: string; receiving_location_id: string; receiving_location_name?: string; status: string;
  order_date: string; expected_date?: string | null; currency_code: string; notes?: string | null;
  subtotal: string; tax_amount: string; total: string; line_count?: number; received_units?: string;
  lines?: PurchaseOrderLine[]; status_history?: Array<Record<string, unknown>>;
};
export type PurchaseReceiptLine = {
  id: string; receipt_id: string; purchase_order_line_id: string; variant_id: string; received_quantity: string;
  unit_cost: string; base_unit_cost: string; landed_cost_amount: string; variance_reason?: string | null;
  sku?: string; variant_name?: string; product_name?: string; ordered_quantity?: string; already_received?: string;
};
export type PurchaseReceipt = {
  id: string; receipt_number: string; purchase_order_id: string; po_number?: string; supplier_name?: string;
  supplier_party_id?: string; receiving_location_id: string; location_name?: string; status: string; currency_code?: string;
  received_at: string; posted_at?: string | null; landed_cost_total: string; line_count?: number;
  lines?: PurchaseReceiptLine[]; landed_costs?: Array<Record<string, unknown>>; allocations?: Array<Record<string, unknown>>;
};
export type PurchaseReturn = {
  id: string; return_number: string; purchase_receipt_id: string; receipt_number?: string; po_number?: string;
  supplier_name?: string; supplier_party_id?: string; status: string; reason: string; currency_code?: string;
  return_value?: string; value?: string; lines?: Array<{id:string; purchase_receipt_line_id:string; variant_id:string; quantity:string; unit_cost:string; supplier_credit_unit_cost?:string; sku?:string; product_name?:string; variant_name?:string; reason?:string|null}>;
};
export type SupplierBill = {
  id: string; supplier_party_id: string; supplier_name?: string; bill_number: string; bill_date: string; due_date: string;
  currency_code: string; subtotal: string; tax_amount: string; other_charges: string; total: string; status: string;
  purchase_order_id?: string | null; purchase_receipt_id?: string | null; paid_amount?: string; allocated_outstanding?: string;
  match_status?: 'NOT_LINKED'|'WAITING_RECEIPT'|'MATCHED'|'VARIANCE'|'OVERRIDDEN'; match_variance?: string; match_reason?: string | null; match_checked_at?: string | null;
};
export type SupplierPayment = {
  id: string; supplier_party_id: string; supplier_name?: string; payment_number: string; payment_date: string;
  currency_code: string; amount: string; payment_method: string; reference?: string | null; status: string;
  allocated_amount?: string; unallocated_amount?: string;
};
export type SupplierBalance = {
  supplier_party_id: string; supplier_name: string; payment_terms_days: number; currency_code: string;
  debits: string; credits: string; net_balance: string; payable: string; supplier_credit: string;
  last_activity?: string; entry_count: number; overdue_bills: number;
};
export type SupplierLedgerEntry = {
  id: string; supplier_party_id: string; currency_code: string; entry_type: string; source_type: string;
  source_id: string; reference?: string | null; debit_amount: string; credit_amount: string;
  occurred_at: string; running_balance?: string; metadata?: Record<string, unknown>;
};
function purchasingPost<T>(path: string, body?: unknown) {
  return getJson<T>(path, { method: "POST", headers: { ...(body === undefined ? {} : { "Content-Type": "application/json" }), "Idempotency-Key": key() }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
}
export function getPurchasingSummary() { return getJson<Record<string, string | number>>('/api/v1/purchasing/summary'); }
export function getPurchasingSuppliers(params: { q?: string; status?: string } = {}) { const p=new URLSearchParams(); Object.entries(params).forEach(([k,v])=>v&&p.set(k,v)); return getJson<PurchasingSupplier[]>(`/api/v1/purchasing/suppliers${p.size?`?${p}`:''}`); }
export function createPurchasingSupplier(body: {name:string;code?:string;legal_name?:string|null;email?:string|null;phone?:string|null;currency_code:string;payment_terms_days:number;default_receiving_location_id?:string|null;tax_number?:string|null;notes?:string|null}) { return purchasingPost<PurchasingSupplier>('/api/v1/purchasing/suppliers', body); }
export function updatePurchasingSupplier(id:string, body:Partial<{name:string;legal_name:string|null;email:string|null;phone:string|null;currency_code:string;payment_terms_days:number;default_receiving_location_id:string|null;tax_number:string|null;notes:string|null;status:'ACTIVE'|'INACTIVE'|'ARCHIVED'}>) { return getJson<PurchasingSupplier>(`/api/v1/purchasing/suppliers/${encodeURIComponent(id)}`, { method:'PATCH', headers:{'Content-Type':'application/json','Idempotency-Key':key()}, body:JSON.stringify(body) }); }
export function getSupplierCosts(id:string) { return getJson<PurchasingSupplierCost[]>(`/api/v1/purchasing/suppliers/${encodeURIComponent(id)}/costs`); }
export function setSupplierCost(id:string, body:{variant_id:string;unit_cost:string;minimum_quantity:string;currency_code:string;lead_time_days?:number|null}) { return purchasingPost<PurchasingSupplierCost>(`/api/v1/purchasing/suppliers/${encodeURIComponent(id)}/costs`, body); }
export function getPurchaseOrders(params:{status?:string;supplier_party_id?:string}={}) { const p=new URLSearchParams(); Object.entries(params).forEach(([k,v])=>v&&p.set(k,v)); return getJson<PurchaseOrder[]>(`/api/v1/purchasing/purchase-orders${p.size?`?${p}`:''}`); }
export function getPurchaseOrder(id:string) { return getJson<PurchaseOrder>(`/api/v1/purchasing/purchase-orders/${encodeURIComponent(id)}`); }
export function createPurchaseOrder(body:{supplier_party_id:string;branch_id:string;receiving_location_id:string;order_date:string;expected_date?:string|null;currency_code:string;notes?:string|null;lines:Array<{variant_id:string;ordered_quantity:string;unit_cost:string;tax_rate:string;description?:string|null}>}) { return purchasingPost<{id:string;po_number:string;status:string;currency_code:string;subtotal:string;tax_amount:string;total:string}>('/api/v1/purchasing/purchase-orders', body); }
export function submitPurchaseOrder(id:string, reason?:string) { return purchasingPost<{id:string;status:string}>(`/api/v1/purchasing/purchase-orders/${encodeURIComponent(id)}/submit`, {reason}); }
export function approvePurchaseOrder(id:string, reason?:string) { return purchasingPost<{id:string;status:string}>(`/api/v1/purchasing/purchase-orders/${encodeURIComponent(id)}/approve`, {reason}); }
export function cancelPurchaseOrder(id:string, reason?:string) { return purchasingPost<{id:string;status:string}>(`/api/v1/purchasing/purchase-orders/${encodeURIComponent(id)}/cancel`, {reason}); }
export function closePurchaseOrder(id:string, reason?:string) { return purchasingPost<{id:string;status:string}>(`/api/v1/purchasing/purchase-orders/${encodeURIComponent(id)}/close`, {reason}); }
export function getPurchaseReceipts(status?:string) { return getJson<PurchaseReceipt[]>(`/api/v1/purchasing/receipts${status?`?status=${encodeURIComponent(status)}`:''}`); }
export function getPurchaseReceipt(id:string) { return getJson<PurchaseReceipt>(`/api/v1/purchasing/receipts/${encodeURIComponent(id)}`); }
export function createPurchaseReceipt(id:string, body:{received_at?:string;notes?:string|null;lines:Array<{purchase_order_line_id:string;received_quantity:string;unit_cost?:string|null;variance_reason?:string|null;notes?:string|null}>;landed_costs:Array<{cost_code:string;description:string;amount:string;currency_code:string;allocation_method:'BY_VALUE'|'BY_QUANTITY'|'EQUALLY';reference?:string|null}>}) { return purchasingPost<{id:string;receipt_number:string;status:string;purchase_order_id:string;line_count:number;landed_cost_total:string}>(`/api/v1/purchasing/purchase-orders/${encodeURIComponent(id)}/receipts`, body); }
export function postPurchaseReceipt(id:string) { return purchasingPost<Record<string,string|number>>(`/api/v1/purchasing/receipts/${encodeURIComponent(id)}/post`); }
export function cancelPurchaseReceipt(id:string,reason?:string) { return purchasingPost<{id:string;status:string}>(`/api/v1/purchasing/receipts/${encodeURIComponent(id)}/cancel`,{reason}); }
export function getPurchaseReturns(status?:string) { return getJson<PurchaseReturn[]>(`/api/v1/purchasing/returns${status?`?status=${encodeURIComponent(status)}`:''}`); }
export function getPurchaseReturn(id:string) { return getJson<PurchaseReturn>(`/api/v1/purchasing/returns/${encodeURIComponent(id)}`); }
export function createPurchaseReturn(body:{purchase_receipt_id:string;reason:string;notes?:string|null;lines:Array<{purchase_receipt_line_id:string;quantity:string;reason?:string|null}>}) { return purchasingPost<PurchaseReturn>('/api/v1/purchasing/returns',body); }
export function approvePurchaseReturn(id:string) { return purchasingPost<{id:string;status:string}>(`/api/v1/purchasing/returns/${encodeURIComponent(id)}/approve`); }
export function cancelPurchaseReturn(id:string,reason?:string) { return purchasingPost<{id:string;status:string}>(`/api/v1/purchasing/returns/${encodeURIComponent(id)}/cancel`,{reason}); }
export function postPurchaseReturn(id:string) { return purchasingPost<{id:string;status:string;supplier_credit:string;currency_code:string}>(`/api/v1/purchasing/returns/${encodeURIComponent(id)}/post`); }
export function getSupplierBills(params:{status?:string;supplier_party_id?:string;due_before?:string}={}) { const p=new URLSearchParams(); Object.entries(params).forEach(([k,v])=>v&&p.set(k,v)); return getJson<SupplierBill[]>(`/api/v1/purchasing/supplier-bills${p.size?`?${p}`:''}`); }
export function createSupplierBill(body:{supplier_party_id:string;bill_number:string;bill_date:string;due_date?:string|null;currency_code:string;subtotal:string;tax_amount:string;other_charges:string;purchase_order_id?:string|null;purchase_receipt_id?:string|null;supplier_reference?:string|null;notes?:string|null}) { return purchasingPost<{id:string;bill_number:string;status:string;total:string;currency_code:string;due_date:string}>('/api/v1/purchasing/supplier-bills',body); }
export function postSupplierBill(id:string) { return purchasingPost<{id:string;status:string;payable_added:string;currency_code:string}>(`/api/v1/purchasing/supplier-bills/${encodeURIComponent(id)}/post`); }
export function acceptSupplierBillVariance(id:string,reason:string) { return purchasingPost<{id:string;match_status:string;match_variance:string;reason:string}>(`/api/v1/purchasing/supplier-bills/${encodeURIComponent(id)}/accept-variance`,{reason}); }
export function voidSupplierBill(id:string,reason?:string) { return purchasingPost<{id:string;status:string}>(`/api/v1/purchasing/supplier-bills/${encodeURIComponent(id)}/void`,{reason}); }
export function getSupplierPayments(params:{status?:string;supplier_party_id?:string}={}) { const p=new URLSearchParams(); Object.entries(params).forEach(([k,v])=>v&&p.set(k,v)); return getJson<SupplierPayment[]>(`/api/v1/purchasing/supplier-payments${p.size?`?${p}`:''}`); }
export function createSupplierPayment(body:{supplier_party_id:string;payment_number:string;payment_date:string;currency_code:string;amount:string;payment_method:string;reference?:string|null;notes?:string|null;allocations:Array<{bill_id:string;amount:string}>}) { return purchasingPost<{id:string;payment_number:string;status:string;amount:string;allocated_amount:string;unallocated_amount:string;currency_code:string}>('/api/v1/purchasing/supplier-payments',body); }
export function postSupplierPayment(id:string) { return purchasingPost<{id:string;status:string;supplier_balance_credit:string;allocated_amount:string;advance_amount:string;currency_code:string}>(`/api/v1/purchasing/supplier-payments/${encodeURIComponent(id)}/post`); }
export function voidSupplierPayment(id:string,reason?:string) { return purchasingPost<{id:string;status:string}>(`/api/v1/purchasing/supplier-payments/${encodeURIComponent(id)}/void`,{reason}); }
export function getSupplierBalances(params:{supplier_party_id?:string;currency_code?:string;include_zero?:boolean}={}) { const p=new URLSearchParams(); Object.entries(params).forEach(([k,v])=>v!==undefined&&v!==null&&v!==''&&p.set(k,String(v))); return getJson<SupplierBalance[]>(`/api/v1/purchasing/supplier-balances${p.size?`?${p}`:''}`); }
export function getSupplierLedger(id:string,currencyCode?:string) { return getJson<SupplierLedgerEntry[]>(`/api/v1/purchasing/supplier-ledger/${encodeURIComponent(id)}${currencyCode?`?currency_code=${encodeURIComponent(currencyCode)}`:''}`); }
