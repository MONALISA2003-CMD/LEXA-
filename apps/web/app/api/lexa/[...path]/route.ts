import { NextRequest, NextResponse } from "next/server";

const DEFAULT_API_ORIGIN = "https://lexa-n10e.onrender.com";
const API_ORIGIN = (process.env.LEXA_API_URL || process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_ORIGIN).replace(/\/$/, "");

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
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
  const init: RequestInit = { method: request.method, headers, cache: "no-store" };
  if (!["GET", "HEAD"].includes(request.method)) init.body = await request.text();

  try {
    const response = await fetch(target, init);
    const body = await response.arrayBuffer();
    const out = new NextResponse(body, { status: response.status, statusText: response.statusText });
    const responseType = response.headers.get("content-type");
    if (responseType) out.headers.set("content-type", responseType);
    const responseRequestId = response.headers.get("x-request-id");
    if (responseRequestId) out.headers.set("x-request-id", responseRequestId);
    const responseHeaders = response.headers as Headers & { getSetCookie?: () => string[] };
    const cookies = responseHeaders.getSetCookie ? responseHeaders.getSetCookie() : (response.headers.get("set-cookie") ? [response.headers.get("set-cookie") as string] : []);
    for (const cookie of cookies) out.headers.append("set-cookie", cookie);
    const retryAfter = response.headers.get("retry-after");
    if (retryAfter) out.headers.set("retry-after", retryAfter);
    if (response.status >= 500) {
      const headers = new Headers();
      if (retryAfter) headers.set("Retry-After", retryAfter);
      if (responseRequestId) headers.set("X-Request-ID", responseRequestId);
      return NextResponse.json({ detail: { code: "UPSTREAM_UNAVAILABLE", message: "LEXA is temporarily unavailable. Please try again shortly.", request_id: responseRequestId || null } }, { status: response.status, headers });
    }
    return out;
  } catch {
    return NextResponse.json({ detail: "LEXA is temporarily unavailable. Please try again shortly." }, { status: 502 });
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
