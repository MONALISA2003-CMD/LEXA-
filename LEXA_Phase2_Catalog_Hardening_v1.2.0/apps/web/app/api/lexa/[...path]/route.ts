import { NextRequest, NextResponse } from "next/server";

const API_ORIGIN = (process.env.LEXA_API_URL || process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  if (!API_ORIGIN) {
    return NextResponse.json({ detail: "LEXA_API_URL is not configured on the web server." }, { status: 500 });
  }

  const { path } = await context.params;
  const target = `${API_ORIGIN}/${path.join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  const authorization = request.headers.get("authorization");
  if (authorization) headers.set("authorization", authorization);
  headers.set("accept", request.headers.get("accept") || "application/json");
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const idempotency = request.headers.get("idempotency-key");
  if (idempotency) headers.set("idempotency-key", idempotency);
  const requestId = request.headers.get("x-request-id");
  if (requestId) headers.set("x-request-id", requestId);

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
    return out;
  } catch (error) {
    return NextResponse.json(
      { detail: "LEXA API proxy could not reach the backend.", error: error instanceof Error ? error.message : "upstream_fetch_failed" },
      { status: 502 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
