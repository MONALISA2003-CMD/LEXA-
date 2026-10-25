/** Deterministic reporting-period ranges anchored to a supplied reporting date. */
const DAY_MS = 86400000;
const MAX_REPORTING_DAYS = 366;
function validDate(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00.000Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}
function shiftDate(value, days) {
  const date = new Date(`${value}T00:00:00.000Z`);
  date.setTime(date.getTime() + days * DAY_MS);
  return date.toISOString().slice(0, 10);
}
function result(fromDate, toDate, label) {
  if (!validDate(fromDate) || !validDate(toDate)) return { fromDate, toDate, label, days: 0, valid: false, error: "Choose valid start and end dates." };
  if (fromDate > toDate) return { fromDate, toDate, label, days: 0, valid: false, error: "The start date must be on or before the end date." };
  const days = Math.round((Date.parse(`${toDate}T00:00:00.000Z`) - Date.parse(`${fromDate}T00:00:00.000Z`)) / DAY_MS) + 1;
  if (days > MAX_REPORTING_DAYS) return { fromDate, toDate, label, days, valid: false, error: `Choose a reporting period of ${MAX_REPORTING_DAYS} days or less.` };
  return { fromDate, toDate, label, days, valid: true, error: "" };
}
/** Period keys: today, yesterday, this-week, last-7-days, last-30-days, month-to-date, previous-month, year-to-date, custom. Week starts Monday. */
export function getIntelligencePeriodRange(key, todayISO, customFrom = "", customTo = "") {
  if (!validDate(todayISO)) return { fromDate: "", toDate: "", label: "Reporting period", days: 0, valid: false, error: "The reporting date is unavailable." };
  const date = new Date(`${todayISO}T00:00:00.000Z`);
  const year = date.getUTCFullYear(); const month = date.getUTCMonth(); const weekday = date.getUTCDay();
  if (key === "custom") return result(customFrom, customTo, "Custom range");
  if (key === "today") return result(todayISO, todayISO, "Today");
  if (key === "yesterday") { const d = shiftDate(todayISO, -1); return result(d, d, "Yesterday"); }
  if (key === "this-week") return result(shiftDate(todayISO, -(weekday === 0 ? 6 : weekday - 1)), todayISO, "This week");
  if (key === "last-7-days") return result(shiftDate(todayISO, -6), todayISO, "Last 7 days");
  if (key === "last-30-days") return result(shiftDate(todayISO, -29), todayISO, "Last 30 days");
  if (key === "month-to-date") return result(`${year}-${String(month + 1).padStart(2, "0")}-01`, todayISO, "This month");
  if (key === "previous-month") return result(new Date(Date.UTC(year, month - 1, 1)).toISOString().slice(0, 10), new Date(Date.UTC(year, month, 0)).toISOString().slice(0, 10), "Last month");
  if (key === "year-to-date") return result(`${year}-01-01`, todayISO, "Year to date");
  return { fromDate: "", toDate: "", label: "Reporting period", days: 0, valid: false, error: "Choose a supported reporting period." };
}
