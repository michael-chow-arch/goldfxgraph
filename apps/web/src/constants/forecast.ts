import type { ForecastDirection } from "@/types/forecast";

export const DIRECTION_LABELS: Record<ForecastDirection, string> = {
  bullish: "看多",
  bearish: "看空",
  neutral: "震荡/中性",
};

export const DIRECTION_STYLES: Record<ForecastDirection, string> = {
  bullish: "status-pill--success",
  bearish: "status-pill--danger",
  neutral: "status-pill--neutral",
};

export const WINDOW_DIRECTION_LABELS: Record<string, string> = {
  "0-3天": "0-3天",
  "3-5天": "3-5天",
  "6-15天": "6-15天",
  "15天后": "15天后",
};

export const AGENT_LABELS: Record<string, string> = {
  technical: "技术分析",
  macro: "宏观分析",
  news: "新闻分析",
  market_sentiment: "市场情绪",
  alt_data: "另类数据",
  risk: "风险分析",
  planner: "预测规划",
  bull_opening_case: "多头开场",
  bear_opening_case: "空头开场",
  bull_rebuttal: "多头反驳",
  bear_rebuttal: "空头反驳",
  bull_final_position: "多头终局",
  bear_final_position: "空头终局",
  chair: "委员会主席",
  repair: "修复委员会",
};

export const COMMITTEE_BIAS_LABELS: Record<string, string> = {
  bullish: "看多",
  bearish: "看空",
  range_bound: "区间震荡",
  cautious: "谨慎观望",
};

export const ACTIONABILITY_LABELS: Record<string, string> = {
  trade_candidate: "可交易候选",
  prepare_only: "仅准备",
  observe_only: "仅观察",
  no_trade: "不交易",
};

export const COMMITTEE_NODE_LABELS: Record<string, string> = {
  router_validate_request: "请求校验",
  tool_load_market_data: "加载市场数据",
  tool_ensure_market_data_freshness: "检查数据鲜度",
  tool_fetch_current_gold_quote: "获取最新行情",
  tool_compute_indicators: "计算技术指标",
  agent_technical_analysis: "技术分析",
  tool_fetch_macro_inputs: "宏观输入",
  agent_macro_analysis: "宏观分析",
  tool_fetch_newsflow_inputs: "新闻输入",
  agent_news_analysis: "新闻分析",
  tool_fetch_pizza_index_inputs: "Pizza 指数",
  tool_load_forecast_feedback_history: "反馈历史",
  tool_fetch_polymarket_inputs: "Polymarket",
  tool_fetch_market_sentiment_inputs: "市场情绪输入",
  tool_fetch_alt_data_inputs: "另类数据输入",
  agent_market_sentiment_analysis: "市场情绪分析",
  agent_alt_data_analysis: "另类数据分析",
  agent_risk_analysis: "风险分析",
  node_build_evidence_package: "构建证据包",
  agent_bull_opening_case: "多头开场",
  agent_bear_opening_case: "空头开场",
  agent_bull_rebuttal: "多头反驳",
  agent_bear_rebuttal: "空头反驳",
  agent_bull_final_position: "多头终局",
  agent_bear_final_position: "空头终局",
  agent_trading_committee_chair: "主席仲裁",
  node_validate_committee_decision: "校验决策",
  agent_repair_committee_decision: "修复决策",
  node_persist_forecast: "持久化 forecast",
  router_finalize_result: "结束",
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

export const SCHEDULER_STATUS_LABELS: Record<string, string> = {
  running: "运行中",
  success: "数据加载完成",
  failed: "已失败",
  skipped: "已跳过",
};

export const SCHEDULER_STAGE_LABELS: Record<string, string> = {
  scheduled: "已排程",
  router_validate_request: "校验请求",
  tool_load_market_data: "加载市场数据",
  tool_ensure_market_data_freshness: "检查市场数据鲜度",
  tool_fetch_current_gold_quote: "获取最新黄金报价",
  tool_compute_indicators: "计算技术指标",
  tool_fetch_macro_inputs: "拉取宏观输入",
  tool_fetch_market_sentiment_inputs: "拉取市场情绪",
  tool_fetch_alt_data_inputs: "拉取另类数据",
  tool_fetch_newsflow_inputs: "拉取新闻流",
  tool_fetch_pizza_index_inputs: "拉取 Pizza 指数",
  tool_fetch_polymarket_inputs: "拉取 Polymarket",
  agent_technical_analysis: "技术分析中",
  agent_macro_analysis: "宏观分析中",
  agent_news_analysis: "新闻分析中",
  agent_risk_analysis: "风险分析中",
  agent_forecast_planning: "规划预测中",
  tool_persist_research_run: "保存研究运行",
  tool_persist_forecast: "保存 forecast",
  router_finalize_result: "分析完成",
  persist_result: "分析完成",
  failed: "执行失败",
  completed: "分析完成",
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
