export type ForecastDirection = "bullish" | "bearish" | "neutral";
export type SchedulerRunStatusValue = "running" | "success" | "failed" | "skipped";
export type SchedulerAgentStatusValue = "pending" | "running" | "success" | "failed";

export interface ForecastWindowDirection {
  window_label: string;
  direction: ForecastDirection;
  strength: "strong" | "moderate" | "mild";
  confidence: number;
  reason: string;
}

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
  window_directions: ForecastWindowDirection[];
  entry_price?: number | null;
  entry_price_low?: number | null;
  entry_price_high?: number | null;
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

export interface SchedulerAgentStatus {
  agent: string;
  status: SchedulerAgentStatusValue;
  error?: string | null;
}

export interface SchedulerAgentDiagnostic {
  agent: string;
  stage: string;
  status: string;
  message: string;
  detail?: string | null;
}

export interface SchedulerRunStatus {
  id?: number | null;
  status: SchedulerRunStatusValue;
  started_at: string;
  completed_at?: string | null;
  current_stage: string;
  agent_statuses: SchedulerAgentStatus[];
  agent_diagnostics: SchedulerAgentDiagnostic[];
  last_error?: string | null;
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
