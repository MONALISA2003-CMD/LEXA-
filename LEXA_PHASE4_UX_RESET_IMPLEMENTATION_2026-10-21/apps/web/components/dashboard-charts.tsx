"use client";

import { useId } from "react";
import type { AnalyticsDailyMetric } from "../lib/api";

const money = (value: string | number) => new Intl.NumberFormat("en-UG", {
  style: "currency",
  currency: "UGX",
  maximumFractionDigits: 0,
}).format(Number(value));

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
export function SalesTrendChart({ daily, startDate, endDate }: {
  daily: AnalyticsDailyMetric[];
  startDate: string;
  endDate: string;
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
      <span>There are no daily analytics records between {dateLabel(startDate, "long")} and {dateLabel(endDate, "long")}. LEXA has not replaced missing data with zeroes.</span>
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
      <desc id={descriptionId}>Two series are drawn from LEXA's daily analytics records. Gaps in returned dates are left as gaps; they are not interpreted as zero activity.</desc>
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
        {segment.map(point => <circle key={`${point.date}-net`} cx={point.x} cy={point.y} r="3.5" className="chart-series-dot chart-series-sales-dot"><title>{`${dateLabel(point.date, "long")} — Net sales: ${money(point.value)}`}</title></circle>)}
      </g>)}
      {contiguousSegments(collectedPoints).map((segment, index) => <g key={`collected-${index}`}>
        {segment.length > 1 && <polyline points={segment.map(point => `${point.x},${point.y}`).join(" ")} className="chart-series-line chart-series-collected" />}
        {segment.map(point => <circle key={`${point.date}-collected`} cx={point.x} cy={point.y} r="3.5" className="chart-series-dot chart-series-collected-dot"><title>{`${dateLabel(point.date, "long")} — Payments collected: ${money(point.value)}`}</title></circle>)}
      </g>)}
    </svg>
    <details className="chart-data-details">
      <summary>View the underlying daily data</summary>
      <div className="chart-data-table-wrap">
        <table className="data-table chart-data-table">
          <thead><tr><th scope="col">Business date</th><th scope="col">Net sales</th><th scope="col">Collected</th><th scope="col">Returns</th><th scope="col">Expenses</th></tr></thead>
          <tbody>{sorted.map(row => <tr key={row.business_date}>
            <td>{dateLabel(row.business_date, "long")}</td>
            <td>{money(row.net_sales)}</td>
            <td>{money(row.payments_collected)}</td>
            <td>{money(row.returns_total)}</td>
            <td>{money(row.expenses_total)}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </details>
  </div>;
}
