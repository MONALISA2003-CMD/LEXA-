/** Local calendar-date defaults for form controls and report-window selection. */
const pad2 = (value) => String(value).padStart(2, "0");

/** @param {Date} [date] @returns {string} */
export function localDateISO(date = new Date()) {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

/** @param {Date} [date] @returns {string} */
export function localMonthStartISO(date = new Date()) {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-01`;
}
