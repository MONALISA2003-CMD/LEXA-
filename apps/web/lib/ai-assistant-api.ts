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


function friendlyNetworkError(cause: unknown, purpose: "status" | "answer"): Error {
  if (cause instanceof DOMException && (cause.name === "AbortError" || cause.name === "TimeoutError")) {
    return new Error(purpose === "answer"
      ? "LEXA is taking longer than expected. Please try again."
      : "LEXA could not check availability just now. You can still try your business question.");
  }
  if (cause instanceof TypeError) {
    return new Error("LEXA could not be reached. Check your connection and try again.");
  }
  return cause instanceof Error ? cause : new Error("LEXA could not complete the request. Please try again.");
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
  let response: Response;
  try {
    response = await fetch("/api/lexa/api/v1/ai/providers", {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(7_000),
    });
  } catch (cause) {
    throw friendlyNetworkError(cause, "status");
  }
  if (!response.ok) throw new Error(await readError(response));
  return await response.json() as AssistantProvidersResponse;
}

export async function askLexaAssistant(input: {
  prompt: string;
  area: "general" | "sales" | "stock" | "purchasing" | "finance" | "customers";
}): Promise<AssistantReply> {
  const token = await authToken();
  let response: Response;
  try {
    response = await fetch("/api/lexa/api/v1/ai/assistant", {
      method: "POST",
      credentials: "include",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ prompt: input.prompt, area: input.area, include_business_summary: false }),
      signal: AbortSignal.timeout(14_500),
    });
  } catch (cause) {
    throw friendlyNetworkError(cause, "answer");
  }
  if (!response.ok) throw new Error(await readError(response));
  return await response.json() as AssistantReply;
}
