import { getBusinessProfile, getCachedSession, restoreSession } from "./api";

export type BriefEvidence = {
  label: string;
  href: string;
  source_tables: string[];
  record_count: number;
  as_of_date: string | null;
  refreshed_at: string | null;
};
export type BriefItem = {
  rule_id: string;
  source_insight_id: string;
  category: string;
  title: string;
  summary: string;
  status: string;
  severity: string;
  action_label: string;
  action_href: string;
  evidence: BriefEvidence;
  metric: { label: string; value: string | number; unit: string; currency_code?: string } | null;
  comparison: Record<string, unknown> | null;
  details: Record<string, unknown> | null;
  examples: Record<string, unknown>[];
  limitations: string[];
};
export type DailyBrief = {
  schema_version: string;
  rule_version: string;
  generated_at: string;
  as_of_date: string;
  currency_code: string;
  period: { from_date: string; to_date: string; comparison_period: Record<string, unknown> };
  scope: string;
  headline: string;
  status: "available" | "attention" | "partial" | "unavailable" | string;
  counts: { insights_considered: number; action_items: number; information_items: number; data_quality_items: number };
  action_items: BriefItem[];
  information_items: BriefItem[];
  data_quality: BriefItem[];
  last_successful_refresh_at: string | null;
  advisory_only: true;
  external_ai_used: false;
  business_writes_performed: false;
  limitations: string[];
};

async function authToken() {
  const session = getCachedSession() || await restoreSession();
  if (!session?.access_token) throw new Error("Your sign-in has expired. Sign in again to continue.");
  return session.access_token;
}

export async function getDailyBrief(currencyCode?: string): Promise<DailyBrief> {
  let currency = currencyCode;
  if (!currency) {
    const profile = await getBusinessProfile();
    currency = profile?.currency_code;
  }
  if (!currency || !/^[A-Z]{3}$/i.test(currency)) {
    throw new Error("Set up your business profile and currency before opening the daily brief.");
  }
  const token = await authToken();
  const response = await fetch(`/api/lexa/api/v1/intelligence/daily-brief?currency_code=${encodeURIComponent(currency.toUpperCase())}`, {
    headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
    credentials: "include",
    cache: "no-store",
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload && typeof payload === "object" && "detail" in payload ? (payload as { detail?: unknown }).detail : null;
    if (detail && typeof detail === "object" && "message" in detail && typeof (detail as { message?: unknown }).message === "string") {
      throw new Error((detail as { message: string }).message);
    }
    if (typeof detail === "string" && detail.trim()) throw new Error(detail);
    throw new Error("LEXA could not verify the daily brief. Refresh the saved reports and try again.");
  }
  return payload as DailyBrief;
}
