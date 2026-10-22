"use client";

import { useId } from "react";
import type { AnalyticsDailyMetric } from "../lib/api";

const money = (value: string | number, currencyCode?: string | null) => {
  if (!currencyCode || !/^[A-Z]{3}$/.test(currencyCode)) return "Business currency not set";
  try { return new Intl.NumberFormat("en-UG", { style: "currency", currency: currencyCode, maximumFractionDigits: 0 }).format(Number(value)); }
  catch { return `${currencyCode} ${Number(value).toLocaleString("en-UG", { maximumFractionDigits: 0 })}`; }
};

const compactMoney = (value: number) => new Intl.NumberFormat("en-UG", {
  notation: "compact",
  maximumFractionDigits: 1,
}).format(value);

function dateLabel(value: string, style: "short" | "long" = "short") {
  const date = new Date(`${value}T12:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-UG", style === "long"
    ? { day: "numeric", month: "short", year: "numeric" }
    : { day: "numeric", month: "short" },
  ).format(date);
}

function daysBetween(a: string, b: string) {
  const first = new Date(`${a}T12:00:00`).getTime();
  const second = new Date(`${b}T12:00:00`).getTime();
  return Math.round((second - first) / 86_400_000);
}

type Point = { date: string; value: number; x: number; y: number };

function contiguousSegments(points: Point[]) {
  const segments: Point[][] = [];
  let current: Point[] = [];
  for (const point of points) {
    const previous = current[current.length - 1];
    if (previous && daysBetween(previous.date, point.date) > 1) {
      if (current.length) segments.push(current);
      current = [];
    }
    current.push(point);
  }
  if (current.length) segments.push(current);
  return segments;
}

/** An accessible, dependency-free time-series chart sourced only from API records. */
export function SalesTrendChart({ daily, startDate, endDate, currencyCode }: {
  daily: AnalyticsDailyMetric[];
  startDate: string;
  endDate: string;
  currencyCode?: string | null;
}) {
  const titleId = useId();
  const descriptionId = useId();
  const sorted = [...daily].sort((a, b) => a.business_date.localeCompare(b.business_date));
  const width = 720;
  const height = 264;
  const margin = { top: 20, right: 22, bottom: 42, left: 76 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const startMs = new Date(`${startDate}T12:00:00`).getTime();
  const endMs = new Date(`${endDate}T12:00:00`).getTime();
  const spanMs = Math.max(86_400_000, endMs - startMs);
  const values = sorted.flatMap(row => [Number(row.net_sales), Number(row.payments_collected)])
    .filter(Number.isFinite);
  const minValue = Math.min(0, ...values);
  const rawMax = Math.max(0, ...values);
  const maxValue = rawMax === minValue ? minValue + 1 : rawMax;
  const valueSpan = maxValue - minValue;
  const xFor = (date: string) => margin.left + ((new Date(`${date}T12:00:00`).getTime() - startMs) / spanMs) * plotWidth;
  const yFor = (value: number) => margin.top + ((maxValue - value) / valueSpan) * plotHeight;
  const netPoints: Point[] = sorted.map(row => ({ date: row.business_date, value: Number(row.net_sales), x: xFor(row.business_date), y: yFor(Number(row.net_sales)) }));
  const collectedPoints: Point[] = sorted.map(row => ({ date: row.business_date, value: Number(row.payments_collected), x: xFor(row.business_date), y: yFor(Number(row.payments_collected)) }));
  const yTicks = Array.from({ length: 5 }, (_, index) => minValue + (valueSpan * index) / 4).reverse();
  const xTicks = Array.from({ length: 5 }, (_, index) => {
    const timestamp = startMs + (spanMs * index) / 4;
    const date = new Date(timestamp);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  });

  if (!sorted.length) {
    return <div className="chart-empty-state">
      <span className="chart-empty-mark" aria-hidden="true">⌁</span>
      <strong>No sales metrics in this period</strong>
      <span>No daily figures were recorded between {dateLabel(startDate, "long")} and {dateLabel(endDate, "long")}. Missing dates are left blank rather than shown as zero.</span>
    </div>;
  }

  return <div className="trend-chart-wrap">
    <div className="chart-summary-row" aria-label="Chart summary">
      <span><i className="chart-legend-dot legend-sales" aria-hidden="true"/> Net sales</span>
      <span><i className="chart-legend-dot legend-collected" aria-hidden="true"/> Payments collected</span>
      <small>{dateLabel(startDate, "long")} – {dateLabel(endDate, "long")}</small>
    </div>
    <svg className="sales-trend-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby={`${titleId} ${descriptionId}`}>
      <title id={titleId}>Net sales and payments collected over time</title>
      <desc id={descriptionId}>The lines use saved daily sales and payment figures. Missing dates are left blank rather than counted as zero activity.</desc>
      {yTicks.map((value, index) => {
        const y = yFor(value);
        return <g key={`y-${index}`}>
          <line x1={margin.left} x2={width - margin.right} y1={y} y2={y} className="chart-grid-line" />
          <text x={margin.left - 12} y={y + 4} textAnchor="end" className="chart-axis-label">{compactMoney(value)}</text>
        </g>;
      })}
      {xTicks.map((date, index) => {
        const x = margin.left + (plotWidth * index) / 4;
        return <g key={`x-${date}-${index}`}>
          <line x1={x} x2={x} y1={margin.top} y2={height - margin.bottom} className="chart-grid-line chart-grid-vertical" />
          <text x={x} y={height - 15} textAnchor={index === 0 ? "start" : index === 4 ? "end" : "middle"} className="chart-axis-label">{dateLabel(date)}</text>
        </g>;
      })}
      {contiguousSegments(netPoints).map((segment, index) => <g key={`net-${index}`}>
        {segment.length > 1 && <polyline points={segment.map(point => `${point.x},${point.y}`).join(" ")} className="chart-series-line chart-series-sales" />}
        {segment.map(point => <circle key={`${point.date}-net`} cx={point.x} cy={point.y} r="3.5" className="chart-series-dot chart-series-sales-dot"><title>{`${dateLabel(point.date, "long")} — Net sales: ${money(point.value, currencyCode)}`}</title></circle>)}
      </g>)}
      {contiguousSegments(collectedPoints).map((segment, index) => <g key={`collected-${index}`}>
        {segment.length > 1 && <polyline points={segment.map(point => `${point.x},${point.y}`).join(" ")} className="chart-series-line chart-series-collected" />}
        {segment.map(point => <circle key={`${point.date}-collected`} cx={point.x} cy={point.y} r="3.5" className="chart-series-dot chart-series-collected-dot"><title>{`${dateLabel(point.date, "long")} — Payments collected: ${money(point.value, currencyCode)}`}</title></circle>)}
      </g>)}
    </svg>
    <details className="chart-data-details">
      <summary>View daily figures</summary>
      <div className="chart-data-table-wrap">
        <table className="data-table chart-data-table">
          <thead><tr><th scope="col">Business date</th><th scope="col">Net sales</th><th scope="col">Collected</th><th scope="col">Returns</th><th scope="col">Expenses</th></tr></thead>
          <tbody>{sorted.map(row => <tr key={row.business_date}>
            <td>{dateLabel(row.business_date, "long")}</td>
            <td>{money(row.net_sales, currencyCode)}</td>
            <td>{money(row.payments_collected, currencyCode)}</td>
            <td>{money(row.returns_total, currencyCode)}</td>
            <td>{money(row.expenses_total, currencyCode)}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </details>
  </div>;
}


/** Product comparison chart built only from saved report rows. */
export function ProductPerformanceBars({ rows, currencyCode }: {
  rows: Array<{ label: string; value: number; detail?: string; href?: string }>;
  currencyCode?: string | null;
}) {
  const safeRows = rows.filter(row => Number.isFinite(row.value)).slice(0, 8);
  const maxValue = Math.max(1, ...safeRows.map(row => Math.max(0, row.value)));
  if (!safeRows.length) return <div className="chart-empty-state"><strong>No product sales in this period</strong><span>Product comparisons will appear after sales are recorded.</span></div>;
  return <div className="product-comparison-bars" role="list" aria-label="Product sales comparison">
    {safeRows.map((row, index) => <div className="product-comparison-row" role="listitem" key={`${row.label}-${index}`}>
      <div className="product-comparison-label">{row.href ? <a className="report-record-link" href={row.href}>{row.label}</a> : <strong>{row.label}</strong>}<small>{row.detail || ""}</small></div>
      <div className="product-comparison-track" aria-hidden="true"><span style={{ width: `${Math.max(0, Math.min(100, row.value / maxValue * 100))}%` }} /></div>
      <b className="product-comparison-value">{money(row.value, currencyCode)}</b>
    </div>)}
  </div>;
}


/** Clear expense-category comparison built from posted expense records only. */
export function ExpenseCategoryBars({ rows, currencyCode }: {
  rows: Array<{ label: string; value: number; detail?: string; href?: string }>;
  currencyCode?: string | null;
}) {
  const safeRows = rows.filter(row => Number.isFinite(row.value) && row.value >= 0).sort((a, b) => b.value - a.value).slice(0, 8);
  const maxValue = Math.max(1, ...safeRows.map(row => row.value));
  if (!safeRows.length) return <div className="chart-empty-state"><strong>No recorded expenses in this period</strong><span>Expense categories will appear here after an expense is recorded.</span></div>;
  return <div className="product-comparison-bars" role="list" aria-label="Expenses by category">
    {safeRows.map((row, index) => <div className="product-comparison-row" role="listitem" key={`${row.label}-${index}`}>
      <div className="product-comparison-label">{row.href ? <a className="report-record-link" href={row.href}>{row.label}</a> : <strong>{row.label}</strong>}<small>{row.detail || "Recorded expenses"}</small></div>
      <div className="product-comparison-track expense-comparison-track" aria-hidden="true"><span style={{ width: `${Math.max(0, Math.min(100, row.value / maxValue * 100))}%` }} /></div>
      <b className="product-comparison-value">{money(row.value, currencyCode)}</b>
    </div>)}
  </div>;
}


/** Recorded customer receipts by the payment-method names configured by the owner. */
export function PaymentMethodBars({ rows, currencyCode }: {
  rows: Array<{ label: string; value: number; detail?: string; href?: string }>;
  currencyCode?: string | null;
}) {
  const safeRows = rows.filter(row => Number.isFinite(row.value) && row.value >= 0).sort((a, b) => b.value - a.value).slice(0, 8);
  const maxValue = Math.max(1, ...safeRows.map(row => row.value));
  if (!safeRows.length) return <div className="chart-empty-state"><strong>No recorded payments in this period</strong><span>Payment methods will appear here after customer payments are recorded.</span></div>;
  return <div className="product-comparison-bars" role="list" aria-label="Money recorded by payment method">
    {safeRows.map((row, index) => <div className="product-comparison-row" role="listitem" key={`${row.label}-${index}`}>
      <div className="product-comparison-label">{row.href ? <a className="report-record-link" href={row.href}>{row.label}</a> : <strong>{row.label}</strong>}<small>{row.detail || "Recorded customer payments"}</small></div>
      <div className="product-comparison-track payment-method-track" aria-hidden="true"><span style={{ width: `${Math.max(0, Math.min(100, row.value / maxValue * 100))}%` }} /></div>
      <b className="product-comparison-value">{money(row.value, currencyCode)}</b>
    </div>)}
  </div>;
}


/** Location comparison built from current stock snapshots. */
export function StockValueByLocationBars({ rows, currencyCode }: {
  rows: Array<{ label: string; value: number; detail?: string; href?: string }>;
  currencyCode?: string | null;
}) {
  const safeRows = rows.filter(row => Number.isFinite(row.value) && row.value >= 0).sort((a, b) => b.value - a.value).slice(0, 8);
  const maxValue = Math.max(1, ...safeRows.map(row => row.value));
  if (!safeRows.length) return <div className="chart-empty-state"><strong>No current stock value to compare</strong><span>Location values will appear after stock has been recorded and cost information is available.</span></div>;
  return <div className="product-comparison-bars" role="list" aria-label="Stock value by location">
    {safeRows.map((row, index) => <div className="product-comparison-row" role="listitem" key={`${row.label}-${index}`}>
      <div className="product-comparison-label">{row.href ? <a className="report-record-link" href={row.href}>{row.label}</a> : <strong>{row.label}</strong>}<small>{row.detail || "Current stock snapshot"}</small></div>
      <div className="product-comparison-track stock-value-track" aria-hidden="true"><span style={{ width: `${Math.max(0, Math.min(100, row.value / maxValue * 100))}%` }} /></div>
      <b className="product-comparison-value">{money(row.value, currencyCode)}</b>
    </div>)}
  </div>;
}

/** Current customer balances ranked by the amount still owed. */
export function CustomerBalanceBars({ rows, currencyCode }: {
  rows: Array<{ label: string; value: number; detail?: string; href?: string }>;
  currencyCode?: string | null;
}) {
  const safeRows = rows.filter(row => Number.isFinite(row.value) && row.value > 0).sort((a, b) => b.value - a.value).slice(0, 8);
  const maxValue = Math.max(1, ...safeRows.map(row => row.value));
  if (!safeRows.length) return <div className="chart-empty-state"><strong>No outstanding customer balances</strong><span>Balances will appear here when customers have an amount remaining to pay.</span></div>;
  return <div className="product-comparison-bars" role="list" aria-label="Outstanding customer balances">
    {safeRows.map((row, index) => <div className="product-comparison-row" role="listitem" key={`${row.label}-${index}`}>
      <div className="product-comparison-label">{row.href ? <a className="report-record-link" href={row.href}>{row.label}</a> : <strong>{row.label}</strong>}<small>{row.detail || "Amount remaining"}</small></div>
      <div className="product-comparison-track customer-balance-track" aria-hidden="true"><span style={{ width: `${Math.max(0, Math.min(100, row.value / maxValue * 100))}%` }} /></div>
      <b className="product-comparison-value">{money(row.value, currencyCode)}</b>
    </div>)}
  </div>;
}

/** Net sales by location over the selected reporting period. */
export function BranchPerformanceBars({ rows, currencyCode }: {
  rows: Array<{ label: string; value: number; detail?: string; href?: string }>;
  currencyCode?: string | null;
}) {
  const safeRows = rows.filter(row => Number.isFinite(row.value)).sort((a, b) => b.value - a.value).slice(0, 8);
  const maxValue = Math.max(1, ...safeRows.map(row => Math.max(0, row.value)));
  if (!safeRows.length) return <div className="chart-empty-state"><strong>No location sales in this period</strong><span>Location comparisons will appear when completed sales are recorded for accessible locations.</span></div>;
  return <div className="product-comparison-bars" role="list" aria-label="Sales by business location">
    {safeRows.map((row, index) => <div className="product-comparison-row" role="listitem" key={`${row.label}-${index}`}>
      <div className="product-comparison-label">{row.href ? <a className="report-record-link" href={row.href}>{row.label}</a> : <strong>{row.label}</strong>}<small>{row.detail || "Sales after returns"}</small></div>
      <div className="product-comparison-track branch-performance-track" aria-hidden="true"><span style={{ width: `${Math.max(0, Math.min(100, Math.max(0, row.value) / maxValue * 100))}%` }} /></div>
      <b className="product-comparison-value">{money(row.value, currencyCode)}</b>
    </div>)}
  </div>;
}
