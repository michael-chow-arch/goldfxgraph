import type { ForecastDirection } from "@/types/forecast";

export const DIRECTION_LABELS: Record<ForecastDirection, string> = {
  bullish: "看多",
  bearish: "看空",
  neutral: "震荡/中性",
};

export const DIRECTION_STYLES: Record<ForecastDirection, string> = {
  bullish: "border-emerald-500/35 bg-emerald-500/10 text-emerald-300",
  bearish: "border-orange-500/35 bg-orange-500/10 text-orange-300",
  neutral: "border-sky-500/35 bg-sky-500/10 text-sky-300",
};

export const AGENT_LABELS: Record<string, string> = {
  technical: "技术 Agent",
  macro: "宏观 Agent",
  news: "新闻 Agent",
  risk: "风险 Agent",
  planner: "预测规划 Agent",
};

export const SUMMARY_SECTIONS = [
  { key: "technical_summary", title: "技术分析" },
  { key: "macro_summary", title: "宏观分析" },
  { key: "news_summary", title: "新闻分析" },
  { key: "risk_summary", title: "风险分析" },
] as const;

export const EMPTY_FORECAST_MESSAGE = "尚未生成可展示的最新研究结果。";
