export type ApiHealth = { status: string; service?: string; environment?: string };
export type ApiReadiness = { status: string; service?: string; environment?: string; dependencies?: { database?: string } };

const rawApiUrl = process.env.NEXT_PUBLIC_API_URL;
export const API_URL = rawApiUrl?.replace(/\/$/, "") ?? "";

export class ApiConfigurationError extends Error {
  constructor() { super("NEXT_PUBLIC_API_URL is not configured in this Vercel build."); this.name = "ApiConfigurationError"; }
}

async function getJson<T>(path: string): Promise<T> {
  if (!API_URL) throw new ApiConfigurationError();
  let response: Response;
  try { response = await fetch(`${API_URL}${path}`, { cache: "no-store", headers: { Accept: "application/json" } }); }
  catch { throw new Error(`Failed to fetch LEXA API at ${API_URL}${path}. Check the deployed Vercel API URL and Render CORS origin.`); }
  if (!response.ok) throw new Error(`LEXA API returned HTTP ${response.status} for ${path}.`);
  return (await response.json()) as T;
}

export function getHealth(signal?: AbortSignal): Promise<ApiHealth> {
  if (!API_URL) return Promise.reject(new ApiConfigurationError());
  return fetch(`${API_URL}/health`, { cache: "no-store", signal, headers: { Accept: "application/json" } }).then(async response => {
    if (!response.ok) throw new Error(`LEXA API returned HTTP ${response.status} for /health.`);
    return (await response.json()) as ApiHealth;
  }).catch(error => {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    if (error instanceof Error && error.message.startsWith("LEXA API")) throw error;
    throw new Error(`Failed to fetch LEXA API at ${API_URL}/health. Check the deployed Vercel API URL and Render CORS origin.`);
  });
}

export function getReadiness(): Promise<ApiReadiness> { return getJson<ApiReadiness>("/ready"); }
