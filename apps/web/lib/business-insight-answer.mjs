/**
 * Maps the local question router's approved focus to a saved Phase 9 insight.
 * This deliberately formats no invented business facts: the summary, metrics,
 * period and provenance are taken directly from the authorized API response.
 */
const INSIGHT_ID_BY_FOCUS = {
  sales: "sales-movement",
  margin: "gross-margin-movement",
  stock: "stock-risk",
  balances: "working-capital-balances",
};

const UNVERIFIED_STATUSES = new Set(["unavailable", "stale"]);

export function buildBusinessInsightAnswer(focus, insights) {
  const rows = Array.isArray(insights) ? insights : [];

  if (focus === "all") {
    const reviewableCount = rows.filter((item) => !UNVERIFIED_STATUSES.has(item?.status)).length;
    return {
      state: "overview",
      title: "Business overview",
      summary: rows.length
        ? `LEXA returned ${rows.length} insight${rows.length === 1 ? "" : "s"}; ${reviewableCount} currently have a reviewable result. Check each insight's freshness, source and limitations before acting.`
        : "No saved insights were returned. LEXA has not assumed that missing data means zero.",
      insight: null,
      totalCount: rows.length,
      reviewableCount,
    };
  }

  const expectedId = INSIGHT_ID_BY_FOCUS[focus];
  if (!expectedId) return null;

  const insight = rows.find((item) => item?.id === expectedId);
  if (!insight) {
    return {
      state: "unavailable",
      title: "No verified answer yet",
      summary: "LEXA did not receive the matching saved insight. No business value has been inferred or substituted as zero.",
      insight: null,
      totalCount: rows.length,
      reviewableCount: 0,
    };
  }

  return {
    state: insight.status,
    title: insight.title,
    summary: insight.summary,
    insight,
    totalCount: rows.length,
    reviewableCount: UNVERIFIED_STATUSES.has(insight.status) ? 0 : 1,
  };
}
