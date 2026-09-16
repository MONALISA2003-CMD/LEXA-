export type ApiHealth = { status: string; service?: string; environment?: string };
export type ApiReadiness = { status: string; service?: string; environment?: string; dependencies?: { database?: string } };
export type Product = {
  id: string;
  tenant_id: string;
  category_id: string;
  brand_id?: string | null;
  name: string;
  description?: string | null;
  product_type: string;
  status: string;
  has_variants: boolean;
  tax_category_id?: string | null;
  metadata?: Record<string, unknown>;
};
export type Variant = {
  id: string;
  tenant_id: string;
  product_id: string;
  name: string;
  sku: string;
  base_unit_id: string;
  track_inventory: boolean;
  allow_fractional_quantity: boolean;
  status: string;
  costing_method?: string | null;
  metadata?: Record<string, unknown>;
};
export type Page<T> = { items: T[]; next_cursor?: string | null };

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const auth = typeof window !== "undefined" ? window.sessionStorage.getItem("lexa_access_token") : null;
  const response = await fetch(`/api/lexa${path}`, { cache: "no-store", ...init, headers: { Accept: "application/json", ...(auth ? { Authorization: `Bearer ${auth}` } : {}), ...(init?.headers || {}) } });
  const text = await response.text();
  let payload: unknown = null;
  try { payload = text ? JSON.parse(text) : null; } catch { payload = text; }
  if (!response.ok) {
    const detail = typeof payload === "object" && payload && "detail" in payload ? String((payload as { detail: unknown }).detail) : `HTTP ${response.status}`;
    throw new Error(`LEXA API ${response.status}: ${detail}`);
  }
  return payload as T;
}

export function getHealth(signal?: AbortSignal) { return getJson<ApiHealth>("/health", { signal }); }
export function getReadiness() { return getJson<ApiReadiness>("/ready"); }
export function getProducts(query = "", signal?: AbortSignal) {
  const params = new URLSearchParams({ limit: "50" });
  if (query.trim()) params.set("q", query.trim());
  return getJson<Page<Product>>(`/api/v1/catalog/products?${params.toString()}`, { signal });
}
export function getVariants(productId: string) { return getJson<Variant[]>(`/api/v1/catalog/products/${productId}/variants`); }

export type LoginRequest = { email: string; password: string; tenant_id: string };
export type AuthResponse = { access_token: string; refresh_token: string; token_type: string; session_id: string };
export type RegisterResponse = { user_id: string; tenant_id: string };

export function login(body: LoginRequest) {
  return getJson<AuthResponse>("/api/v1/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}
export function register(body: { email: string; password: string; tenant_name: string }) {
  return getJson<RegisterResponse>("/api/v1/auth/register", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}
