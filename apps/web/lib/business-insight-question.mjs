/**
 * Small, deterministic question router for the Phase 9 insight view.
 * It classifies only the user's question and returns a fixed, allowlisted focus.
 * It never sends the question or business data to an external provider.
 */
export function resolveBusinessInsightQuestion(question) {
  const normalized = String(question ?? "").trim().toLowerCase().replace(/\s+/g, " ");
  if (!normalized) {
    return {
      status: "unsupported",
      focus: null,
      message: "Type a question about sales movement, gross margin, stock risk or current balances.",
    };
  }

  if (/\b(net profit|profit after expenses|bottom line)\b/.test(normalized)) {
    return {
      status: "guardrail",
      focus: null,
      message: "Gross margin is not net profit. This insight view does not calculate net profit; use the Finance reports to review the available sales, cost and expense figures separately.",
    };
  }

  if (/\b(stock|stocks|inventory|stockout|stockout risk|out of stock|slow moving|slow-moving|days of cover|replenish|replenishment)\b/.test(normalized)) {
    return {
      status: "supported",
      focus: "stock",
      message: "Showing the stock-risk insight from the latest saved inventory-health snapshot. A stale or missing snapshot is reported as unavailable, not zero.",
    };
  }

  if (/\b(receivables?|customers? owe|customer balances?|outstanding customer|payables?|supplier payables?|suppliers? owe|owe suppliers?|supplier balances?|working capital|open balances?)\b/.test(normalized)) {
    return {
      status: "supported",
      focus: "balances",
      message: "Showing current receivables and supplier-ledger balances in the selected currency. This is a balance snapshot, not a movement for the selected date range.",
    };
  }

  if (/\b(gross margin|margin|cogs|cost of goods sold|discount|discounts)\b/.test(normalized)) {
    return {
      status: "supported",
      focus: "margin",
      message: "Showing gross-margin movement from saved product metrics. The result is product-cost margin, not net profit.",
    };
  }

  if (/\b(sales|sale|revenue|turnover)\b/.test(normalized)) {
    return {
      status: "supported",
      focus: "sales",
      message: "Showing sales movement from saved daily metrics compared with the preceding equal-length period.",
    };
  }

  if (/^(overview|business health|all insights|show all insights|everything)$/.test(normalized)) {
    return {
      status: "supported",
      focus: "all",
      message: "Showing all source-linked insights currently supported by the rule layer.",
    };
  }

  return {
    status: "unsupported",
    focus: null,
    message: "I can answer questions about sales movement, gross margin, stock risk and current receivables/supplier balances. Other questions are not guessed; open the relevant Finance, Purchasing, Inventory or Reports screen.",
  };
}
