export type BusinessInsightQuestionFocus = "all" | "sales" | "margin" | "stock" | "balances";
export type BusinessInsightQuestionResult = {
  status: "supported" | "guardrail" | "unsupported";
  focus: BusinessInsightQuestionFocus | null;
  message: string;
};
export function resolveBusinessInsightQuestion(question: string): BusinessInsightQuestionResult;
