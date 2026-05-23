import type { ForecastDirection } from "@/types/forecast";

export const DIRECTION_LABELS: Record<ForecastDirection, string> = {
  bullish: "看多",
  bearish: "看空",
  neutral: "震荡/中性",
};

export const DIRECTION_STYLES: Record<ForecastDirection, string> = {
  bullish: "border-emerald-300/35 bg-emerald-500/10 text-emerald-200",
  bearish: "border-rose-400/35 bg-rose-500/10 text-rose-200",
  neutral: "border-amber-300/30 bg-amber-500/10 text-amber-100",
};

export const AGENT_LABELS: Record<string, string> = {
  technical: "技术分析",
  macro: "宏观分析",
  news: "新闻分析",
  risk: "风险分析",
  planner: "预测规划",
};

export const SUMMARY_SECTIONS = [
  { key: "technical_summary", title: "技术分析" },
  { key: "macro_summary", title: "宏观分析" },
  { key: "news_summary", title: "新闻分析" },
  { key: "risk_summary", title: "风险分析" },
] as const;

export const EMPTY_FORECAST_MESSAGE = "当前还没有可展示的最新研究结果，等研究任务完成后这里会自动更新。";
