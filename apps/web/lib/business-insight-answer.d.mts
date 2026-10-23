import type { BusinessInsight, BusinessInsightFocus } from "./api";

export type BusinessInsightAnswer = {
  state: "overview" | BusinessInsight["status"];
  title: string;
  summary: string;
  insight: BusinessInsight | null;
  totalCount: number;
  reviewableCount: number;
};

export function buildBusinessInsightAnswer(
  focus: BusinessInsightFocus,
  insights: BusinessInsight[],
): BusinessInsightAnswer | null;
