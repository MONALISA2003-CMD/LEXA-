import { getCachedSession, restoreSession } from "./api";

export type DemandForecastDay = {
  date: string;
  forecast_units: string;
  historical_same_weekday_low: string;
  historical_same_weekday_high: string;
};
export type DemandForecastBacktest = {
  method: string;
  test_days_evaluated: number;
  mae_units: string | null;
  wape_percent: string | null;
  last_week_baseline_wape_percent: string | null;
  comparison_to_baseline: string | null;
  wape_unavailable_when_test_actuals_are_zero: true;
};
export type DemandForecastItem = {
  variant_id: string;
  product_id: string;
  sku: string | null;
  product_name: string;
  variant_name: string;
  status: "available" | "partial";
  reason_code: string | null;
  reason?: string;
  history_days: number;
  active_demand_days: number;
  horizon_days: number;
  forecast_version: string;
  method: string;
  forecast: DemandForecastDay[];
  total_forecast_units: string;
  backtest: DemandForecastBacktest;
};
export type ExcludedForecastItem = {
  product_name: string;
  variant_name: string;
  sku: string | null;
  reason_code: string;
  message: string;
};
export type DemandForecastResponse = {
  schema_version: string;
  forecast_version: string;
  status: "available" | "partial" | "unavailable";
  reason_code: string | null;
  message: string;
  as_of_date: string;
  scope: string;
  history_from_date: string;
  history_to_date: string;
  history_days_required: number;
  horizon_days: number;
  history_coverage_verified: boolean;
  history_refresh_completed_at: string | null;
  source_tables: string[];
  advisory_only: true;
  external_ai_used: false;
  business_writes_performed: false;
  stockout_censoring_corrected: false;
  limitations: string[];
  items: DemandForecastItem[];
  excluded_items: ExcludedForecastItem[];
};

async function authToken() {
  const session = getCachedSession() || await restoreSession();
  if (!session?.access_token) throw new Error("Your sign-in has expired. Sign in again to continue.");
  return session.access_token;
}

export async function getDemandForecast(horizonDays = 14): Promise<DemandForecastResponse> {
  if (!Number.isInteger(horizonDays) || horizonDays < 7 || horizonDays > 28) {
    throw new Error("Choose a forecast window from 7 to 28 days.");
  }
  const token = await authToken();
  const response = await fetch(`/api/lexa/api/v1/intelligence/demand-forecast?horizon_days=${horizonDays}`, {
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
    throw new Error("LEXA could not verify the demand forecast. Check analytics freshness and try again.");
  }
  return payload as DemandForecastResponse;
}
