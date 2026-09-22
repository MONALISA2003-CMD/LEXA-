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
  const method = (init?.method || "GET").toUpperCase();
  const retryable = (method === "GET" && /^\/(health|ready)$/.test(path)) || (method === "POST" && path === "/api/v1/auth/dev-session");
  let response: Response | null = null;
  let lastNetworkError: unknown = null;
  for (let attempt = 0; attempt < (retryable ? 4 : 1); attempt += 1) {
    try {
      response = await fetch(`/api/lexa${path}`, { cache: "no-store", ...init, headers });
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


export type BusinessCapability = { id:string; tenant_id:string; code:string; name:string; status:string; enabled:boolean; configuration:Record<string,unknown>; version:number };
export type BusinessConfiguration = { id:string; tenant_id:string; config_key:string; value_json:unknown; value_type:string; version:number; updated_by?:string|null };
export type PartyRelationship = { id:string; tenant_id:string; from_party_id:string; to_party_id:string; relationship_type:string; status:string; valid_from?:string|null; valid_to?:string|null; metadata_json:Record<string,unknown>; from_party_name?:string|null; to_party_name?:string|null };
export type TransactionType = { id:string; tenant_id:string; code:string; name:string; category:string; initial_status:string; statuses:string[]; transitions:Record<string,string[]>; active:boolean; configuration:Record<string,unknown> };
export type BusinessTransaction = { id:string; tenant_id:string; transaction_type:string; reference:string; status:string; party_id?:string|null; branch_id?:string|null; source_transaction_id?:string|null; total_amount?:string|null; currency_code?:string|null; occurred_at:string; closed_at?:string|null; metadata_json:Record<string,unknown>; line_count?:number; lines?:TransactionLine[]; history?:TransactionStatusHistory[]; payments?:unknown[] };
export type TransactionLine = { id:string; transaction_id:string; line_no:number; line_type:string; product_variant_id?:string|null; service_id?:string|null; resource_id?:string|null; description?:string|null; quantity:string; unit_price:string; line_total:string; currency_code:string };
export type TransactionStatusHistory = { id:string; transaction_id:string; from_status?:string|null; to_status:string; reason?:string|null; changed_by?:string|null; changed_at:string };
export type WorkflowStep = { id:string; workflow_definition_id:string; step_key:string; name:string; step_type:string; position:number; configuration:Record<string,unknown> };
export type WorkflowDefinition = { id:string; tenant_id:string; code:string; name:string; description?:string|null; status:string; trigger_event?:string|null; version:number; configuration:Record<string,unknown>; steps:WorkflowStep[] };
export type WorkflowInstance = { id:string; tenant_id:string; workflow_definition_id:string; entity_type:string; entity_id:string; current_step_id?:string|null; status:string; context:Record<string,unknown>; started_at:string; completed_at?:string|null; current_step?:WorkflowStep|null; runs?:unknown[] };
export type BusinessContext = { entity_type:string; entity_id:string; primary:Record<string,unknown>; related:Record<string,unknown[]>; evidence:{source:string;id:string;observed_at?:string|null}[] };

export function getBusinessCapabilities(){return getJson<BusinessCapability[]>('/api/v1/business-engine/capabilities');}
export function setBusinessCapability(code:string,body:{enabled:boolean;configuration?:Record<string,unknown>}){return getJson<BusinessCapability>(`/api/v1/business-engine/capabilities/${encodeURIComponent(code)}`,{method:'PUT',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify({configuration:{},...body})});}
export function getBusinessConfiguration(){return getJson<BusinessConfiguration[]>('/api/v1/business-engine/configuration');}
export function putBusinessConfiguration(keyName:string,body:{value:unknown;value_type?:string}){return getJson<BusinessConfiguration>(`/api/v1/business-engine/configuration/${encodeURIComponent(keyName)}`,{method:'PUT',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}
export function getPartyRelationships(partyId?:string){return getJson<PartyRelationship[]>(`/api/v1/business-engine/relationships${partyId?`?party_id=${encodeURIComponent(partyId)}`:''}`);}
export function createPartyRelationship(body:{from_party_id:string;to_party_id:string;relationship_type:string;valid_from?:string;valid_to?:string;metadata?:Record<string,unknown>}){return getJson<PartyRelationship>('/api/v1/business-engine/relationships',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}
export function getTransactionTypes(){return getJson<TransactionType[]>('/api/v1/business-engine/transaction-types');}
export function createTransactionType(body:Partial<TransactionType> & {code:string;name:string}){return getJson<TransactionType>('/api/v1/business-engine/transaction-types',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}
export function getBusinessTransactions(filters?:{status?:string;transaction_type?:string}){const q=new URLSearchParams(); if(filters?.status)q.set('status',filters.status); if(filters?.transaction_type)q.set('transaction_type',filters.transaction_type); return getJson<BusinessTransaction[]>(`/api/v1/business-engine/transactions${q.toString()?`?${q}`:''}`);}
export function getBusinessTransaction(id:string){return getJson<BusinessTransaction & {history:TransactionStatusHistory[]}>(`/api/v1/business-engine/transactions/${id}`);}
export function createBusinessTransaction(body:{transaction_type:string;reference:string;party_id?:string|null;branch_id?:string|null;source_transaction_id?:string|null;currency_code?:string|null;metadata?:Record<string,unknown>;lines?:Partial<TransactionLine>[]}){return getJson<BusinessTransaction>('/api/v1/business-engine/transactions',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}
export function transitionBusinessTransaction(id:string,to_status:string,reason?:string){return getJson<BusinessTransaction>(`/api/v1/business-engine/transactions/${id}/transition`,{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify({to_status,reason})});}
export function getWorkflowDefinitions(){return getJson<WorkflowDefinition[]>('/api/v1/business-engine/workflows/definitions');}
export function createWorkflowDefinition(body:{code:string;name:string;description?:string;trigger_event?:string;configuration?:Record<string,unknown>;steps:WorkflowStep[]}){return getJson<WorkflowDefinition>('/api/v1/business-engine/workflows/definitions',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}
export function getWorkflowInstances(status?:string){return getJson<WorkflowInstance[]>(`/api/v1/business-engine/workflows/instances${status?`?status=${encodeURIComponent(status)}`:''}`);}
export function createWorkflowInstance(body:{workflow_definition_id:string;entity_type:string;entity_id:string;context?:Record<string,unknown>}){return getJson<WorkflowInstance>('/api/v1/business-engine/workflows/instances',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}
export function advanceWorkflow(id:string,output?:Record<string,unknown>){return getJson<WorkflowInstance>(`/api/v1/business-engine/workflows/instances/${id}/advance`,{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(output||{})});}
export function getWorkflowInstance(id:string){return getJson<WorkflowInstance>(`/api/v1/business-engine/workflows/instances/${id}`);}
export function getBusinessContext(entityType:string,id:string){return getJson<BusinessContext>(`/api/v1/business-engine/context/${encodeURIComponent(entityType)}/${id}`);}

// Phase 4A commerce contracts
export type CommerceCustomer = { id:string; party_id:string; display_name:string; party_type:string; email?:string|null; phone?:string|null; credit_limit:string; status:string; notes?:string|null; created_at:string };
export type PaymentChannel = { id:string; tenant_id:string; name:string; channel_type:string; provider?:string|null; currency_code:string; active:boolean; created_at:string; updated_at:string };
export type CommerceProduct = { variant_id:string; sku:string; variant_name:string; product_name:string; track_inventory:boolean; selling_price:string };
export type CommerceSale = { id:string; transaction_id:string; customer_party_id?:string|null; customer_name?:string|null; currency_code:string; status:string; subtotal:string; discount_total:string; tax_total:string; total:string; amount_paid:string; amount_due:string; return_adjustment_amount?:string; created_at:string; completed_at?:string|null };
export type Receivable = { id:string; sale_id:string; customer_party_id:string; customer_name:string; original_amount:string; paid_amount:string; adjustment_amount:string; balance:string; status:string; due_at?:string|null; created_at:string };
export type ReconciliationLine = { line_id:string; payment_channel_id:string; channel_name:string; channel_type:string; expected_amount:string; actual_amount?:string|null; variance?:string|null; line_status:string; line_notes?:string|null; reviewed_by?:string|null };
export type Reconciliation = { id:string; business_date:string; status:string; notes?:string|null; closed_at?:string|null; lines:ReconciliationLine[] };
export type CommerceDashboard = { business_date:string; sales:{sales:string;collected:string;credit:string}; payment_channels:Array<{id:string;name:string;channel_type:string;currency_code:string;active:boolean;expected:string}>; outstanding_receivables:string };
export type CommerceSaleLine = { sale_line_id:string; product_variant_id:string; sku?:string|null; variant_name?:string|null; quantity:string; unit_price:string; discount_amount:string; tax_amount:string; line_total:string };
export type CommerceSaleDetail = CommerceSale & { branch_id?:string|null; location_id?:string|null; notes?:string|null; lines:CommerceSaleLine[] };
export type SaleReturn = { id:string; sale_id:string; status:string; reason:string; total:string; completed_at?:string|null; created_at:string; refunded:string; credit_balance:string };

export function getCommerceDashboard(dateValue=''){return getJson<CommerceDashboard>(`/api/v1/commerce/dashboard${dateValue?`?business_date=${encodeURIComponent(dateValue)}`:''}`);}
export function getCommerceCustomers(search=''){return getJson<CommerceCustomer[]>(`/api/v1/commerce/customers${search?`?search=${encodeURIComponent(search)}`:''}`);}
export function createCommerceCustomer(body:{display_name:string;party_type?:'PERSON'|'ORGANIZATION';legal_name?:string;email?:string;phone?:string;credit_limit?:string;notes?:string}){return getJson<CommerceCustomer>('/api/v1/commerce/customers',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}
export function getPaymentChannels(){return getJson<PaymentChannel[]>('/api/v1/commerce/payment-channels');}
export function createPaymentChannel(body:{name:string;channel_type:string;provider?:string;currency_code:string}){return getJson<PaymentChannel>('/api/v1/commerce/payment-channels',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}
export function getCommerceProducts(){return getJson<CommerceProduct[]>('/api/v1/commerce/products');}
export function getCommerceSales(){return getJson<CommerceSale[]>('/api/v1/commerce/sales?limit=100');}
export function getCommerceSale(id:string){return getJson<CommerceSaleDetail>(`/api/v1/commerce/sales/${id}`);}
export function createCommerceSale(body:{customer_party_id?:string|null;branch_id?:string|null;location_id:string;currency_code:string;business_date:string;lines:Array<{variant_id:string;quantity:string;unit_price:string;discount_amount?:string;tax_rate?:string}>;payments:Array<{payment_channel_id:string;amount:string;reference?:string|null}>;notes?:string|null}){return getJson<CommerceSale>('/api/v1/commerce/sales',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key()},body:JSON.stringify(body)});}
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
