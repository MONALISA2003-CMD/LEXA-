import { getCachedSession, restoreSession } from "./api";

export type AssistantProvider = {
  id: string;
  label: string;
  tier: string;
  model: string;
  configured: boolean;
  allowed: boolean;
  selectable: boolean;
};

export type AssistantProvidersResponse = {
  enabled: boolean;
  providers: AssistantProvider[];
  maximum_prompt_characters: number;
  business_data_sharing: false;
  conversation_history_saved: false;
  policy_version: string;
  message: string;
};

export type AssistantReply = {
  provider: string;
  model: string;
  answer: string;
  used_business_summary: false;
  advisory_only: true;
};

async function authToken(): Promise<string> {
  const session = getCachedSession() || await restoreSession();
  if (!session?.access_token) throw new Error("Your sign-in has expired. Please sign in again to continue.");
  return session.access_token;
}

async function readError(response: Response): Promise<string> {
  const payload: unknown = await response.json().catch(() => null);
  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "object" && detail !== null && "message" in detail) {
      const message = (detail as { message?: unknown }).message;
      if (typeof message === "string" && message.trim()) return message;
    }
    if (typeof detail === "string" && detail.trim()) return detail;
  }
  if (response.status === 401) return "Your sign-in has expired. Please sign in again.";
  if (response.status === 429) return "You've reached the assistant request limit. Please wait a moment and try again.";
  if (response.status >= 500) return "LEXA couldn't complete the request just now. Please try again shortly.";
  return "Please check your question and try again.";
}

export async function getAssistantProviders(): Promise<AssistantProvidersResponse> {
  const token = await authToken();
  const response = await fetch("/api/lexa/api/v1/ai/providers", {
    method: "GET",
    credentials: "include",
    cache: "no-store",
    headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(await readError(response));
  return await response.json() as AssistantProvidersResponse;
}

export async function askLexaAssistant(input: {
  prompt: string;
  area: "general" | "sales" | "stock" | "purchasing" | "finance" | "customers";
  provider?: string;
}): Promise<AssistantReply> {
  const token = await authToken();
  const response = await fetch("/api/lexa/api/v1/ai/assistant", {
    method: "POST",
    credentials: "include",
    cache: "no-store",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ prompt: input.prompt, area: input.area, provider: input.provider || null, include_business_summary: false }),
  });
  if (!response.ok) throw new Error(await readError(response));
  return await response.json() as AssistantReply;
}
