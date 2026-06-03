export type ForecastDirection = "bullish" | "bearish" | "neutral";
export type SchedulerRunStatusValue = "running" | "success" | "failed" | "skipped";
export type SchedulerAgentStatusValue = "pending" | "running" | "success" | "failed";
export type FinalBias = "bullish" | "bearish" | "range_bound" | "cautious";
export type Actionability = "trade_candidate" | "prepare_only" | "observe_only" | "no_trade";
export type DebateSide = "bull" | "bear";
export type EvidenceToolStatus = "ok" | "degraded" | "unavailable";
export type DebateStance = "maintain" | "soften" | "abandon";

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

export interface EvidencePackageItem {
  item_id: string;
  specialist_name: string;
  category: string;
  signal: string;
  confidence: number;
  key_evidence: string[];
  risk_factors: string[];
  invalidation_conditions: string[];
  important_levels: string[];
  data_freshness?: string | null;
  tool_status: EvidenceToolStatus;
  degraded_reason?: string | null;
  evidence_refs: string[];
}

export interface EvidencePackage {
  symbol: string;
  reference_time: string;
  data_timestamp: string;
  data_source?: string | null;
  summary?: string | null;
  items: EvidencePackageItem[];
  notes: string[];
}

export interface DebateCase {
  side: DebateSide;
  thesis: string;
  evidence_item_refs: string[];
  entry_zone: string;
  stop_loss_or_invalidation: string;
  target_zone: string;
  risk_reward?: number | null;
  weakness_acknowledged: string[];
  supporting_arguments: string[];
  confidence?: number | null;
  notes: string[];
}

export interface DebateRebuttal {
  side: DebateSide;
  responds_to_side: DebateSide;
  rebutted_points: string[];
  accepted_points: string[];
  plan_adjustments: string[];
  confidence_trend: "up" | "down" | "flat";
  confidence_change?: number | null;
  evidence_item_refs: string[];
  notes: string[];
}

export interface FinalDebatePosition {
  side: DebateSide;
  stance: DebateStance;
  confidence: number;
  confidence_change?: number | null;
  adopted_arguments: string[];
  rejected_arguments: string[];
  plan_adjustments: string[];
  abandon_conditions: string[];
  evidence_item_refs: string[];
  notes: string[];
}

export interface LongPlan {
  entry_zone: string;
  stop_loss?: string | null;
  invalidation_level?: string | null;
  target_zone: string;
  risk_reward?: number | null;
  conditions_to_enter: string[];
  conditions_to_abort: string[];
  evidence_item_refs: string[];
}

export interface ShortPlan {
  entry_zone: string;
  stop_loss?: string | null;
  invalidation_level?: string | null;
  target_zone: string;
  risk_reward?: number | null;
  conditions_to_enter: string[];
  conditions_to_abort: string[];
  evidence_item_refs: string[];
}

export interface RangePlan {
  upper_sell_zone: string;
  lower_buy_zone: string;
  upper_stop: string;
  lower_stop: string;
  midline_target: string;
  breakout_confirmation_level: string;
  breakdown_confirmation_level: string;
  range_invalidated_if: string;
  risk_reward?: number | null;
  conditions_to_enter: string[];
  conditions_to_abort: string[];
  evidence_item_refs: string[];
}

export interface CommitteeDecision {
  evidence_package: EvidencePackage;
  bull_opening_case: DebateCase;
  bear_opening_case: DebateCase;
  bull_rebuttal: DebateRebuttal;
  bear_rebuttal: DebateRebuttal;
  bull_final_position: FinalDebatePosition;
  bear_final_position: FinalDebatePosition;
  final_bias: FinalBias;
  actionability: Actionability;
  winning_side?: DebateSide | "none" | null;
  adopted_arguments: string[];
  rejected_arguments: string[];
  long_plan?: LongPlan | null;
  short_plan?: ShortPlan | null;
  range_plan?: RangePlan | null;
  wait_conditions: string[];
  confidence_score: number;
  decision_summary: string;
  risk_notes: string[];
  evidence_item_refs: string[];
}

export interface ValidationResult {
  is_valid: boolean;
  checked_at: string;
  summary?: string | null;
  errors: string[];
  warnings: string[];
  validation_rules: string[];
}

export interface PromptVersionMetadata {
  prompt_key: string;
  version: string;
  prompt_type: string;
  agent_name?: string | null;
  node_name?: string | null;
  model_family?: string | null;
  is_active?: boolean | null;
  rendered_variable_names: string[];
  output_schema_ref?: string | null;
}

export interface FinalForecast extends ForecastResult {
  bull_opening_case?: DebateCase | null;
  bear_opening_case?: DebateCase | null;
  bull_rebuttal?: DebateRebuttal | null;
  bear_rebuttal?: DebateRebuttal | null;
  bull_final_position?: FinalDebatePosition | null;
  bear_final_position?: FinalDebatePosition | null;
  final_bias?: FinalBias | null;
  actionability?: Actionability | null;
  evidence_package?: EvidencePackage | null;
  committee_decision?: CommitteeDecision | null;
  validation_status?: ValidationResult | null;
  prompt_versions?: PromptVersionMetadata[];
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
  forecast: FinalForecast;
  evaluation?: ForecastEvaluationResult | null;
  trading_day?: string | null;
}
