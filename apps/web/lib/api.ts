export type ApiHealth = {
  status: string;
  service?: string;
  environment?: string;
};

const rawApiUrl = process.env.NEXT_PUBLIC_API_URL;

export const API_URL = rawApiUrl?.replace(/\/$/, "") ?? "";

export class ApiConfigurationError extends Error {
  constructor() {
    super("NEXT_PUBLIC_API_URL is not configured.");
    this.name = "ApiConfigurationError";
  }
}

export async function getHealth(signal?: AbortSignal): Promise<ApiHealth> {
  if (!API_URL) {
    throw new ApiConfigurationError();
  }

  const response = await fetch(`${API_URL}/health`, {
    cache: "no-store",
    signal,
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`LEXA API returned HTTP ${response.status}.`);
  }

  return (await response.json()) as ApiHealth;
}
