export type ForecastDirection = "bullish" | "bearish" | "neutral";

export interface DailyBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number | null;
  source?: string | null;
  symbol?: string;
}

export interface AgentVote {
  agent: string;
  direction: ForecastDirection;
  confidence: number;
  rationale: string;
}

export interface ForecastResult {
  id?: number | null;
  run_id?: number | null;
  symbol: string;
  reference_time: string;
  data_timestamp: string;
  data_source: string | null;
  current_price: number;
  daily_open: number;
  daily_high: number;
  daily_low: number;
  daily_close: number;
  direction: ForecastDirection;
  entry_price?: number | null;
  take_profit_price?: number | null;
  stop_loss_price?: number | null;
  holding_period: string;
  intraday_action: string;
  long_term_action: string;
  confidence_score: number;
  technical_summary: string;
  macro_summary?: string | null;
  news_summary?: string | null;
  market_sentiment_summary?: string | null;
  alt_data_summary?: string | null;
  risk_summary: string;
  agent_votes: AgentVote[];
  risk_notes: string[];
  disclaimer: string;
}

export interface ForecastEvaluationResult {
  id?: number | null;
  forecast_id: number;
  run_id: number;
  evaluated_at: string;
  evaluation_window_end: string;
  result: string;
  direction_hit: boolean;
  pnl_points: number;
  settlement_price: number;
  summary: string;
  feedback_notes: string[];
  signal_coverage: Record<string, unknown>;
}

export interface ForecastHistoryItem {
  forecast: ForecastResult;
  evaluation?: ForecastEvaluationResult | null;
  trading_day?: string | null;
}
