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
  market_sentiment: "市场情绪",
  alt_data: "另类数据",
  risk: "风险分析",
  planner: "预测规划",
};

export const SUMMARY_SECTIONS = [
  { key: "technical_summary", title: "技术分析" },
  { key: "macro_summary", title: "宏观分析" },
  { key: "news_summary", title: "新闻分析" },
  { key: "market_sentiment_summary", title: "市场情绪" },
  { key: "alt_data_summary", title: "另类数据" },
  { key: "risk_summary", title: "风险分析" },
] as const;

export const HISTORY_RESULT_LABELS: Record<string, string> = {
  win: "命中止盈",
  loss: "触发止损",
  flat: "持平/区间",
};

export const TRADINGVIEW_SOURCE_LABEL = "TradingView 实时行情";
export const TRADINGVIEW_SOURCE_UNAVAILABLE_LABEL = "TradingView 实时行情不可用";
export const TRADINGVIEW_SOURCE_ERROR_LABEL = "TradingView 实时行情错误";

const LEGACY_RUNTIME_SOURCE_PATTERNS = [/api\.gold-api\.com/i, /gold api/i, /gold-api/i];

export const LOADING_FORECAST_MESSAGE = "正在请求 TradingView 实时行情与最新研究结果。";
export const EMPTY_FORECAST_MESSAGE = "当前还没有可展示的 TradingView 研究快照，等最新结果生成后这里会自动更新。";
export const ERROR_FORECAST_MESSAGE = "TradingView 实时行情暂不可用，无法加载最新研究结果。";

export const LOADING_MARKET_BARS_MESSAGE = "正在加载 TradingView 实时行情日线。";
export const EMPTY_MARKET_BARS_MESSAGE = "暂无可展示的 TradingView 日线数据。";
export const ERROR_MARKET_BARS_MESSAGE = "TradingView 实时行情暂不可用，无法加载 TradingView 日线。";

export function formatRuntimeSourceLabel(value?: string | null): string {
  const normalized = value?.trim();

  if (!normalized || normalized === "—") {
    return TRADINGVIEW_SOURCE_UNAVAILABLE_LABEL;
  }

  const lowerCased = normalized.toLowerCase();
  if (lowerCased.includes("unavailable")) {
    return TRADINGVIEW_SOURCE_UNAVAILABLE_LABEL;
  }
  if (lowerCased.includes("error")) {
    return TRADINGVIEW_SOURCE_ERROR_LABEL;
  }
  if (lowerCased.includes("tradingview")) {
    return TRADINGVIEW_SOURCE_LABEL;
  }
  if (LEGACY_RUNTIME_SOURCE_PATTERNS.some((pattern) => pattern.test(normalized))) {
    return TRADINGVIEW_SOURCE_LABEL;
  }

  return TRADINGVIEW_SOURCE_LABEL;
}
