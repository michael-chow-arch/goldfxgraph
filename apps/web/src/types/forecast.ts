export type ForecastDirection = "bullish" | "bearish" | "neutral";

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
  data_source: string;
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
  risk_summary: string;
  agent_votes: AgentVote[];
  risk_notes: string[];
  disclaimer: string;
}
