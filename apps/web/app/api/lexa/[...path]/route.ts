import { NextRequest, NextResponse } from "next/server";

const configuredApiOrigin = process.env.LEXA_API_URL || "";
// Never silently direct an unconfigured preview/production deployment at live data.
// Local development alone may fall back to the documented local API endpoint.
const API_ORIGIN = (configuredApiOrigin || (process.env.NODE_ENV !== "production" ? "http://127.0.0.1:8000" : "")).replace(/\/$/, "");

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (!API_ORIGIN) {
    return NextResponse.json(
      { detail: { code: "API_ORIGIN_NOT_CONFIGURED", message: "LEXA's API connection is not configured for this deployment." } },
      { status: 503, headers: { "Cache-Control": "no-store, max-age=0", "Pragma": "no-cache", "X-Content-Type-Options": "nosniff" } },
    );
  }
  const target = `${API_ORIGIN}/${path.join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  const authorization = request.headers.get("authorization");
  if (authorization) headers.set("authorization", authorization);
  headers.set("accept", request.headers.get("accept") || "application/json");
  for (const key of ["content-type", "idempotency-key", "x-request-id"]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  const cookie = request.headers.get("cookie");
  if (cookie) headers.set("cookie", cookie);
  // Vercel overwrites x-real-ip at its edge. Only forward this platform-derived
  // address with a server-only shared secret; FastAPI rejects unverified claims.
  const proxySecret = process.env.LEXA_PROXY_SHARED_SECRET || "";
  const clientIp = request.headers.get("x-real-ip") || "";
  if (proxySecret.length >= 32 && clientIp) {
    headers.set("x-lexa-client-ip", clientIp);
    headers.set("x-lexa-proxy-secret", proxySecret);
  }
  const init: RequestInit = { method: request.method, headers, cache: "no-store" };
  if (!["GET", "HEAD"].includes(request.method)) init.body = await request.text();

  try {
    const response = await fetch(target, init);
    const body = await response.arrayBuffer();
    const out = new NextResponse(body, { status: response.status, statusText: response.statusText });
    const responseType = response.headers.get("content-type");
    if (responseType) out.headers.set("content-type", responseType);
    out.headers.set("cache-control", "no-store, max-age=0");
    out.headers.set("pragma", "no-cache");
    out.headers.set("x-content-type-options", "nosniff");
    const responseRequestId = response.headers.get("x-request-id");
    if (responseRequestId) out.headers.set("x-request-id", responseRequestId);
    // Preserve the API's timing signal so browser diagnostics can separate API
    // handling time from the overall browser-to-Vercel request time.
    const serverTiming = response.headers.get("server-timing");
    if (serverTiming) out.headers.set("server-timing", serverTiming);
    const responseHeaders = response.headers as Headers & { getSetCookie?: () => string[] };
    const cookies = responseHeaders.getSetCookie ? responseHeaders.getSetCookie() : (response.headers.get("set-cookie") ? [response.headers.get("set-cookie") as string] : []);
    for (const cookie of cookies) out.headers.append("set-cookie", cookie);
    const retryAfter = response.headers.get("retry-after");
    if (retryAfter) out.headers.set("retry-after", retryAfter);
    if (response.status >= 500) {
      const headers = new Headers();
      if (retryAfter) headers.set("Retry-After", retryAfter);
      if (responseRequestId) headers.set("X-Request-ID", responseRequestId);
      const errorServerTiming = response.headers.get("server-timing");
      if (errorServerTiming) headers.set("Server-Timing", errorServerTiming);
      headers.set("Cache-Control", "no-store, max-age=0");
      headers.set("Pragma", "no-cache");
      headers.set("X-Content-Type-Options", "nosniff");
      return NextResponse.json({ detail: { code: "UPSTREAM_UNAVAILABLE", message: "LEXA is temporarily unavailable. Please try again shortly.", request_id: responseRequestId || null } }, { status: response.status, headers });
    }
    return out;
  } catch {
    return NextResponse.json(
      { detail: "LEXA is temporarily unavailable. Please try again shortly." },
      { status: 502, headers: { "Cache-Control": "no-store, max-age=0", "Pragma": "no-cache", "X-Content-Type-Options": "nosniff" } },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
