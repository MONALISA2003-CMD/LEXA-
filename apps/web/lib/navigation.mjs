/**
 * Canonical workspace navigation contract.
 * Keep hrefs in one place so desktop navigation, mobile quick links, search,
 * and static link tests all use the same set of real application routes.
 */
export const primaryNavigation = [
  ["/", "Home", "home"],
  ["/sales", "Sales", "cart"],
  ["/inventory", "Stock", "boxes"],
  ["/products", "Products", "package"],
  ["/commerce", "Commerce", "commerce"],
  ["/customers", "Customers", "users"],
  ["/purchasing", "Purchases", "truck"],
  ["/accounting", "Finance", "wallet"],
  ["/reports", "Reports", "chart"],
  ["/team-chat", "Team chat", "chat"],
  ["/ai-assistant", "AI assistant", "brain"],
];

// The mobile dock intentionally keeps the four most frequently used routes.
export const quickNavigation = primaryNavigation.slice(0, 4);

export const secondaryNavigation = [
  ["/compliance", "Tax and official receipts", "receipt"],
  ["/administration", "Business settings", "building"],
  ["/administration/members", "Team and access", "users"],
  ["/workspace", "Switch business", "switch"],
  ["/onboarding", "Business setup", "check"],
  ["/settings", "Settings", "settings"],
  ["/settings/security", "Sign-in and security", "shield"],
];

export const workspaceSearchSuggestions = [
  ["Today’s sales", "/sales"],
  ["Inventory and low stock", "/inventory"],
  ["Products, codes and barcodes", "/products"],
  ["Checkout and daily closing", "/commerce"],
  ["Customers and balances", "/customers"],
  ["Purchase orders and suppliers", "/purchasing"],
  ["Money, expenses and accounting", "/accounting"],
  ["Business reports and graphs", "/reports"],
  ["Business intelligence", "/intelligence"],
  ["AI business assistant", "/ai-assistant"],
  ["Tax and official receipts", "/compliance"],
  ["Team messages", "/team-chat"],
  ["Team roles and access", "/administration/members"],
  ["Business details", "/administration"],
  ["Business setup", "/onboarding"],
  ["Settings", "/settings"],
  ["Sign-in and active sessions", "/settings/security"],
  ["Forgot password and session security", "/settings/security"],
  ["Switch business", "/workspace"],
];

/** Segment-safe route activity; /sales does not activate /sales-history. */
export function isRouteActive(pathname, href) {
  if (typeof pathname !== "string" || typeof href !== "string") return false;
  if (href === "/settings" && pathname.startsWith("/settings/")) return false;
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

/** Route a plain-language search to a real LEXA module while keeping its query. */
export function resolveBusinessSearchDestination(query) {
  const q = String(query ?? "").trim();
  if (!q) return "/";
  const lower = q.toLowerCase();
  const encoded = encodeURIComponent(q);
  if (/\b(ai assistant|ask lexa|artificial intelligence|ai help)\b/.test(lower)) return `/ai-assistant?q=${encoded}`;
  if (/\b(ura|efris|tax|fiscal|compliance|tax receipt|official receipt)\b/.test(lower)) return `/compliance?q=${encoded}`;
  if (/\b(intelligence|forecast|forecasting|trend|anomaly|insight|insights|business health)\b/.test(lower)) return `/intelligence?q=${encoded}`;
  if (/\b(team|member|members|permission|role|invite|access control)\b/.test(lower)) return `/administration/members?q=${encoded}`;
  if (/\b(setup|onboarding|setup progress)\b/.test(lower)) return "/onboarding";
  if (/\b(switch business|workspace|businesses)\b/.test(lower)) return "/workspace";
  if (/\b(password|forgot password|reset password|active session|sessions|sign-in security|account security)\b/.test(lower)) return `/settings/security?q=${encoded}`;
  if (/\b(setting|settings|business profile|currency|branch)\b/.test(lower)) return `/administration?q=${encoded}`;
  if (/\b(customer|client|debtor|receivable|credit balance)\b/.test(lower)) return `/customers?q=${encoded}`;
  if (/\b(inventory|stock|warehouse|transfer|count|adjustment|low stock)\b/.test(lower)) return `/inventory?q=${encoded}`;
  if (/\b(product|sku|barcode|catalog|category|variant)\b/.test(lower)) return `/products?q=${encoded}`;
  if (/\b(checkout|point of sale|\bpos\b|daily closing|reconciliation|till)\b/.test(lower)) return `/commerce?q=${encoded}`;
  if (/\b(sale|sales|payment|invoice|receipt|refund|return)\b/.test(lower)) return `/sales?q=${encoded}`;
  if (/\b(purchase|supplier|receiving|purchase order|payable)\b/.test(lower)) return `/purchasing?q=${encoded}`;
  if (/\b(finance|journal|expense|accounting|cash flow|money owed|ledger)\b/.test(lower)) return `/accounting?q=${encoded}`;
  if (/\b(chat|message|handover|discussion)\b/.test(lower)) return "/team-chat";
  return `/reports?q=${encoded}`;
}

/** Real page routes used by the internal-link integrity tests. */
export const applicationRoutes = [
  "/", "/accounting", "/administration", "/administration/members", "/commerce",
  "/compliance", "/customers", "/intelligence", "/inventory", "/invite", "/login",
  "/onboarding", "/products", "/purchasing", "/register", "/reports", "/sales",
  "/settings", "/settings/security", "/forgot-password", "/reset-password", "/team-chat", "/workspace", "/ai-assistant",
];

/**
 * Resolve a post-auth destination without allowing protocol-relative or
 * backslash-normalized external origins to escape the current application.
 */
export function safeReturnPath(next, currentOrigin) {
  if (typeof next !== "string" || !next.startsWith("/") || next.startsWith("//")) return "/";
  try {
    const origin = new URL(currentOrigin).origin;
    const destination = new URL(next, origin);
    if (destination.origin !== origin) return "/";
    return `${destination.pathname}${destination.search}${destination.hash}`;
  } catch {
    return "/";
  }
}
