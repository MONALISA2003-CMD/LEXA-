/** Build an Excel-friendly CSV while protecting cells from formula injection. */
export function csvCell(value) {
  if (value === null || value === undefined) return '""';
  let text = String(value);
  // Spreadsheet applications may execute user-entered text beginning with formula markers.
  // Numeric values remain numeric-looking (including legitimate negatives).
  if (typeof value === "string" && (/^[\s\u0000-\u001f]*[=+@]/.test(text) || /^[\s\u0000-\u001f]*-/.test(text))) {
    text = `'${text}`;
  }
  return `"${text.replaceAll('"', '""')}"`;
}

export function toCsv(headers, rows) {
  const safeRows = [headers, ...rows].map((row) => row.map(csvCell).join(','));
  // BOM helps Excel recognize UTF-8 names and references.
  return `\uFEFF${safeRows.join('\r\n')}\r\n`;
}
