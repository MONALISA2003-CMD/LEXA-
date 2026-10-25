export type IntelligencePeriodKey =
  | "today"
  | "yesterday"
  | "this-week"
  | "last-7-days"
  | "last-30-days"
  | "month-to-date"
  | "previous-month"
  | "year-to-date"
  | "custom";

export interface IntelligencePeriodRange {
  fromDate: string;
  toDate: string;
  label: string;
  days: number;
  valid: boolean;
  error: string;
}

export function getIntelligencePeriodRange(
  key: IntelligencePeriodKey,
  todayISO: string,
  customFrom?: string,
  customTo?: string,
): IntelligencePeriodRange;
