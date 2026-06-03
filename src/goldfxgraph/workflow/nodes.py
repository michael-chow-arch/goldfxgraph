from __future__ import annotations

import asyncio
import json
import logging
import operator
import re
from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal, Protocol, TypedDict, TypeVar

import httpx
from pydantic import BaseModel, Field

from goldfxgraph.indicators.technical import compute_technical_indicators
from goldfxgraph.llm.openai_client import OpenAIAgentClient, OpenAIClientError
from goldfxgraph.market_data.current_quote import CurrentQuoteProvider, QuoteProviderError
from goldfxgraph.market_data.external_signals import (
    ExternalSignalError,
    fetch_cftc_gold_commitments,
    fetch_dollar_index,
    fetch_real_rates,
)
from goldfxgraph.market_data.newsflow import (
    NewsflowError,
    fetch_newsflow,
    translate_headline_to_chinese,
    translate_source_name_to_chinese,
)
from goldfxgraph.market_data.pizza_index import PizzaIndexError, fetch_pizza_index
from goldfxgraph.market_data.polymarket import PolymarketError, fetch_polymarket_inputs
from goldfxgraph.market_data.tradingview_quote import DEFAULT_TRADINGVIEW_SOURCE
from goldfxgraph.packages.common.settings import GoldFXGraphSettings, get_settings
from goldfxgraph.persistence.prompt_registry import PromptTemplateService, RenderedPrompt
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import (
    Actionability,
    AgentVote,
    CommitteeDecision,
    CurrentQuote,
    DailyBar,
    DebateCase,
    DebateRebuttal,
    DebateSide,
    DebateStance,
    DecisionValidationResult,
    EvidencePackage,
    EvidencePackageItem,
    EvidenceToolStatus,
    FinalBias,
    FinalDebatePosition,
    FinalForecast,
    ForecastDirection,
    ForecastEvaluationResult,
    ForecastResult,
    ForecastWindowDirection,
    LongPlan,
    MarketDataSet,
    PromptVersionMetadata,
    RangePlan,
    ShortPlan,
    TechnicalIndicators,
)

logger = logging.getLogger(__name__)

run_eod_backfill = None
TCommitteeModel = TypeVar("TCommitteeModel", bound=BaseModel)


class QuoteProvider(Protocol):
    def fetch(self) -> CurrentQuote: ...


class MarketDataFreshnessError(ValueError):
    """市场数据强校验失败的受控异常。"""


class WorkflowState(TypedDict, total=False):
    settings: GoldFXGraphSettings
    quote_provider: QuoteProvider
    agent_http_transport: httpx.BaseTransport
    signal_http_transport: httpx.BaseTransport
    repository: ForecastRepository
    scheduler_run_id: int
    market_data: MarketDataSet
    bars: list[DailyBar]
    latest_bar: DailyBar
    quote: CurrentQuote
    indicators: TechnicalIndicators
    technical_summary: str
    macro_inputs: dict[str, object]
    macro_summary: str
    news_summary: str
    market_sentiment_summary: str
    alt_data_summary: str
    newsflow_inputs: dict[str, object]
    pizza_index_inputs: dict[str, object]
    polymarket_inputs: dict[str, object]
    risk_summary: str
    agent_votes: list[AgentVote]
    risk_notes: list[str]
    agent_diagnostics: list[dict[str, Any]]
    forecast_feedback_history: list[str]
    market_sentiment_inputs: dict[str, object]
    alt_data_inputs: dict[str, object]
    market_sentiment_votes: list[AgentVote]
    alt_data_votes: list[AgentVote]
    unavailable_signals: list[str]
    forecast_evaluation: ForecastEvaluationResult
    evidence_package: EvidencePackage
    bull_opening_case: DebateCase
    bear_opening_case: DebateCase
    bull_rebuttal: DebateRebuttal
    bear_rebuttal: DebateRebuttal
    bull_final_position: FinalDebatePosition
    bear_final_position: FinalDebatePosition
    committee_decision: CommitteeDecision
    validation_status: DecisionValidationResult
    validation_errors: list[str]
    validation_warnings: list[str]
    committee_validation_attempts: int
    committee_repair_attempts: int
    final_forecast: FinalForecast
    prompt_versions: Annotated[list[PromptVersionMetadata], operator.add]
    forecast: ForecastResult
    run_id: int
    persistence_status: str
    errors: list[str]
    result: ForecastResult


RESEARCH_DISCLAIMER = "本结果仅用于研究和决策支持，不构成金融建议、投资建议或交易指令。"
SCHEDULER_AGENT_NAMES = (
    "technical",
    "macro",
    "news",
    "market_sentiment",
    "alt_data",
    "risk",
    "forecast",
)


class AgentApiResponse(BaseModel):
    summary: str
    direction: ForecastDirection
    confidence: float = Field(ge=0, le=1)
    risk_notes: list[str] = Field(default_factory=list)


def _schedule_scheduler_status_update(
    state: WorkflowState,
    *,
    current_stage: str,
    active_agent: str | None = None,
    status: str = "running",
    last_error: str | None = None,
) -> None:
    repository = state.get("repository")
    scheduler_run_id = state.get("scheduler_run_id")
    if repository is None or scheduler_run_id is None:
        return

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return

    agent_statuses = []
    for agent_name in SCHEDULER_AGENT_NAMES:
        if active_agent is not None and agent_name == active_agent:
            agent_statuses.append({"agent": agent_name, "status": status})
        else:
            agent_statuses.append({"agent": agent_name, "status": "pending"})

    asyncio.create_task(
        repository.update_scheduler_run_stage(
            scheduler_run_id,
            current_stage=current_stage,
            agent_statuses=agent_statuses,
            agent_diagnostics=list(state.get("agent_diagnostics") or []),
            status="running",
            last_error=last_error,
        )
    )


def evaluate_forecast_performance(
    forecast: ForecastResult,
    settlement_bar: DailyBar,
    *,
    evaluated_at: datetime | None = None,
) -> ForecastEvaluationResult:
    if forecast.id is None or forecast.run_id is None:
        raise ValueError("forecast id and run_id are required for evaluation")
    if forecast.entry_price is None:
        raise ValueError("forecast entry_price is required for evaluation")

    evaluated_at = evaluated_at or datetime.now(UTC)
    settlement_price = settlement_bar.close
    direction_hit = False
    result = "flat"
    pnl_points = 0.0
    feedback_notes = [
        f"使用 {settlement_bar.date.isoformat()} 的日线收盘 bar 进行复盘。",
    ]

    if forecast.direction == ForecastDirection.bullish:
        pnl_points, settlement_price, result, direction_hit = _evaluate_bullish_forecast(forecast, settlement_bar)
    elif forecast.direction == ForecastDirection.bearish:
        pnl_points, settlement_price, result, direction_hit = _evaluate_bearish_forecast(forecast, settlement_bar)
    else:
        entry = forecast.entry_price or forecast.current_price
        pnl_points = round(settlement_bar.close - entry, 2)
        settlement_price = settlement_bar.close
        result = "flat"
        direction_hit = False
        feedback_notes.append("中性预测按研究持有基准计算结算差值，用于观察市场实际波动。")

    feedback_notes.append(
        f"结算结果：{_evaluation_result_label(result)}，收益点数 {pnl_points:+.2f}，结算价 {settlement_price:.2f}。"
    )

    return ForecastEvaluationResult(
        forecast_id=forecast.id,
        run_id=forecast.run_id,
        evaluated_at=evaluated_at,
        evaluation_window_end=datetime(
            settlement_bar.date.year,
            settlement_bar.date.month,
            settlement_bar.date.day,
            23,
            59,
            59,
            tzinfo=UTC,
        ),
        result=result,
        direction_hit=direction_hit,
        pnl_points=pnl_points,
        settlement_price=settlement_price,
        summary="；".join(feedback_notes),
        feedback_notes=feedback_notes,
        signal_coverage={
            "settlement_date": settlement_bar.date.isoformat(),
            "settlement_source": settlement_bar.source or forecast.data_source,
            "bar_high": settlement_bar.high,
            "bar_low": settlement_bar.low,
        },
    )


async def tool_load_forecast_feedback_history(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="tool_load_forecast_feedback_history")
    repository = state.get("repository")
    if repository is None:
        return {"forecast_feedback_history": []}

    limit = int(state.get("feedback_history_limit") or 5)
    history = await repository.get_latest_evaluation_summary(limit=limit)
    return {"forecast_feedback_history": history}


def tool_fetch_market_sentiment_inputs(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="tool_fetch_market_sentiment_inputs")
    latest_bar = _required(state, "latest_bar")
    quote = _required(state, "quote")
    indicators = _required(state, "indicators")
    feedback_history = state.get("forecast_feedback_history", [])
    signal_transport = state.get("signal_http_transport")

    trend_bias = _direction_from_inputs(quote.current_price, latest_bar, indicators)
    cftc_commitments, _ = _fetch_cftc_commitments(signal_transport)
    newsflow_inputs = state.get("newsflow_inputs") or {}
    polymarket_inputs = state.get("polymarket_inputs") or {}
    unavailable_signals = list(state.get("unavailable_signals") or [])
    if newsflow_inputs.get("status") != "available":
        unavailable_signals.append("newsflow")
    if cftc_commitments.get("status") != "available":
        unavailable_signals.extend(["positioning", "cftc_commitments"])
    if polymarket_inputs.get("status") != "available":
        unavailable_signals.append("polymarket")
    unavailable_signals = _unique_strings([str(item) for item in unavailable_signals])
    available_signals = [
        "price_action",
        "technical_indicators",
        "recent_evaluation_feedback",
    ]
    if cftc_commitments.get("status") == "available":
        available_signals.extend(["cftc_commitments", "positioning"])
    if newsflow_inputs.get("status") == "available":
        available_signals.append("newsflow")
    if polymarket_inputs.get("status") == "available":
        available_signals.append("polymarket")
    inputs = {
        "trend_bias": trend_bias.value,
        "current_price": round(quote.current_price, 4),
        "latest_close": latest_bar.close,
        "rsi_14": indicators.rsi_14,
        "feedback_history": list(feedback_history[:5]),
        "feedback_signal_count": len(feedback_history),
        "cftc_commitments": cftc_commitments,
        "positioning_bias": cftc_commitments.get("positioning_bias"),
        "newsflow_headline_count": int(newsflow_inputs.get("headline_count") or 0),
        "newsflow_sentiment": newsflow_inputs.get("sentiment"),
        "newsflow_topics": list(newsflow_inputs.get("topics") or []),
        "polymarket_market_count": int(polymarket_inputs.get("market_count") or 0),
        "polymarket_gold_related_market_count": int(polymarket_inputs.get("gold_related_market_count") or 0),
        "polymarket_bullish_count": int(polymarket_inputs.get("bullish_count") or 0),
        "polymarket_bearish_count": int(polymarket_inputs.get("bearish_count") or 0),
        "polymarket_neutral_count": int(polymarket_inputs.get("neutral_count") or 0),
        "polymarket_markets": list(polymarket_inputs.get("markets") or []),
        "polymarket_summary": polymarket_inputs.get("summary"),
        "available_signals": available_signals,
        "unavailable_signals": unavailable_signals,
    }
    return {
        **state,
        "market_sentiment_inputs": inputs,
        "unavailable_signals": unavailable_signals,
    }


def tool_fetch_alt_data_inputs(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="tool_fetch_alt_data_inputs")
    latest_bar = _required(state, "latest_bar")
    quote = _required(state, "quote")
    signal_transport = state.get("signal_http_transport")
    pizza_index = state.get("pizza_index_inputs") or {}
    dollar_index, _ = _fetch_dollar_index(signal_transport)
    real_rates, _ = _fetch_real_rates(signal_transport)
    unavailable_signals = list(state.get("unavailable_signals") or [])
    if pizza_index.get("status") != "available":
        unavailable_signals.append("pizza_index")
    if dollar_index.get("status") != "available":
        unavailable_signals.append("dollar_index")
    if real_rates.get("status") != "available":
        unavailable_signals.append("real_rates")
    unavailable_signals = _unique_strings([str(item) for item in unavailable_signals])
    inputs = {
        "source_status": _external_source_status([pizza_index, dollar_index, real_rates]),
        "pizza_index": pizza_index
        if pizza_index
        else {
            "status": "unavailable",
            "source": "pizzint.watch",
            "summary": "五角大楼披萨指数暂无已接入的可靠实时源，本轮仅保留可审计的 unavailable 标记。",
        },
        "dollar_index": dollar_index,
        "real_rates": real_rates,
        "price_context": {
            "current_price": quote.current_price,
            "latest_close": latest_bar.close,
            "daily_range": latest_bar.high - latest_bar.low,
        },
        "available_signals": [
            signal_name
            for signal_name, signal in (
                ("pizza_index", pizza_index),
                ("dollar_index", dollar_index),
                ("real_rates", real_rates),
            )
            if signal.get("status") == "available"
        ],
        "unavailable_signals": unavailable_signals,
    }
    return {
        **state,
        "alt_data_inputs": inputs,
        "unavailable_signals": unavailable_signals,
    }


def tool_fetch_newsflow_inputs(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="tool_fetch_newsflow_inputs")
    signal_transport = state.get("signal_http_transport")
    try:
        newsflow_inputs = fetch_newsflow(signal_transport)
    except (NewsflowError, httpx.HTTPError, ValueError, TypeError) as exc:
        newsflow_inputs = {
            "status": "unavailable",
            "source": "mainstream-rss",
            "headline_count": 0,
            "source_count": 0,
            "headlines": [],
            "top_headlines": [],
            "sentiment": "neutral",
            "sentiment_score": 0,
            "summary": "新闻流暂不可用，当前没有抓取到可验证的主流媒体标题。",
            "feed_statuses": [],
            "error": str(exc),
        }

    unavailable_signals = list(state.get("unavailable_signals") or [])
    if newsflow_inputs.get("status") != "available":
        unavailable_signals.append("newsflow")
    unavailable_signals = _unique_strings([str(item) for item in unavailable_signals])
    return {
        "newsflow_inputs": newsflow_inputs,
        "unavailable_signals": unavailable_signals,
    }


def tool_fetch_pizza_index_inputs(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="tool_fetch_pizza_index_inputs")
    signal_transport = state.get("signal_http_transport")
    try:
        pizza_index_inputs = fetch_pizza_index(signal_transport)
    except (PizzaIndexError, httpx.HTTPError, ValueError, TypeError) as exc:
        pizza_index_inputs = {
            "status": "unavailable",
            "source": "pizzint.watch",
            "url": "https://www.pizzint.watch/",
            "doughcon_level": None,
            "doughcon_label": None,
            "doughcon_description": None,
            "source_count": 0,
            "average_spike_pct": None,
            "max_spike_pct": None,
            "pizza_index_score": None,
            "activity_bias": "neutral",
            "top_locations": [],
            "summary": "Pentagon Pizza Index 暂不可用，当前没有抓取到可验证的公开活跃度数据。",
            "error": str(exc),
        }

    unavailable_signals = list(state.get("unavailable_signals") or [])
    if pizza_index_inputs.get("status") == "unavailable":
        unavailable_signals.append("pizza_index")
    unavailable_signals = _unique_strings([str(item) for item in unavailable_signals])
    return {
        "pizza_index_inputs": pizza_index_inputs,
        "unavailable_signals": unavailable_signals,
    }


def tool_fetch_polymarket_inputs(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="tool_fetch_polymarket_inputs")
    signal_transport = state.get("signal_http_transport")
    try:
        polymarket_inputs = fetch_polymarket_inputs(signal_transport)
    except (PolymarketError, httpx.HTTPError, ValueError, TypeError) as exc:
        polymarket_inputs = {
            "status": "unavailable",
            "source": "polymarket.com",
            "url": "https://polymarket.com/zh",
            "market_count": 0,
            "gold_related_market_count": 0,
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
            "markets": [],
            "summary": "Polymarket 公开页暂不可用，当前没有抓取到可验证的黄金相关市场。",
            "error": str(exc),
        }

    unavailable_signals = list(state.get("unavailable_signals") or [])
    if polymarket_inputs.get("status") != "available":
        unavailable_signals.append("polymarket")
    unavailable_signals = _unique_strings([str(item) for item in unavailable_signals])
    return {
        "polymarket_inputs": polymarket_inputs,
        "unavailable_signals": unavailable_signals,
    }


def agent_market_sentiment_analysis(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(
        state,
        current_stage="agent_market_sentiment_analysis",
        active_agent="market_sentiment",
    )
    inputs = state.get("market_sentiment_inputs", {})
    remote, _diagnostic, diagnostic_record = _remote_agent_response(
        state,
        "market_sentiment",
        "agent_market_sentiment_analysis",
    )
    diagnostics = _append_agent_diagnostic(state, diagnostic_record)
    polymarket_summary = str(inputs.get("polymarket_summary") or "").strip()
    if remote is None:
        summary = _failure_summary("market_sentiment", diagnostic_record.get("message") if diagnostic_record else None)
        direction = ForecastDirection.neutral
        confidence = 0.0
    else:
        summary = remote.summary
        if "Polymarket" not in summary and polymarket_summary:
            summary = _append_summary_section(summary, "重点·Polymarket", polymarket_summary)
        direction = remote.direction
        confidence = remote.confidence
    vote = AgentVote(
        agent="market_sentiment",
        direction=direction,
        confidence=confidence,
        rationale=summary,
    )
    return {
        "agent_diagnostics": diagnostics,
        "market_sentiment_summary": summary,
        "market_sentiment_votes": [vote],
        "agent_votes": [*_existing_votes_without(state, "market_sentiment"), vote],
    }


def agent_alt_data_analysis(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(
        state,
        current_stage="agent_alt_data_analysis",
        active_agent="alt_data",
    )
    remote, _diagnostic, diagnostic_record = _remote_agent_response(state, "alt_data", "agent_alt_data_analysis")
    diagnostics = _append_agent_diagnostic(state, diagnostic_record)
    if remote is None:
        summary = _failure_summary("alt_data", diagnostic_record.get("message") if diagnostic_record else None)
        direction = ForecastDirection.neutral
        confidence = 0.0
    else:
        summary = remote.summary
        direction = remote.direction
        confidence = remote.confidence
    vote = AgentVote(
        agent="alt_data",
        direction=direction,
        confidence=confidence,
        rationale=summary,
    )
    return {
        "agent_diagnostics": diagnostics,
        "alt_data_summary": summary,
        "alt_data_votes": [vote],
        "agent_votes": [*_existing_votes_without(state, "alt_data"), vote],
    }


def _evaluate_bullish_forecast(forecast: ForecastResult, settlement_bar: DailyBar) -> tuple[float, float, str, bool]:
    entry = forecast.entry_price or forecast.current_price
    take_profit = forecast.take_profit_price or entry
    stop_loss = forecast.stop_loss_price or entry

    tp_hit = settlement_bar.high >= take_profit
    sl_hit = settlement_bar.low <= stop_loss

    if tp_hit and sl_hit:
        return round(stop_loss - entry, 2), stop_loss, "loss", False
    if tp_hit:
        return round(take_profit - entry, 2), take_profit, "win", True
    if sl_hit:
        return round(stop_loss - entry, 2), stop_loss, "loss", False

    pnl_points = round(settlement_bar.close - entry, 2)
    direction_hit = settlement_bar.close >= entry
    return pnl_points, settlement_bar.close, "flat", direction_hit


def _evaluate_bearish_forecast(forecast: ForecastResult, settlement_bar: DailyBar) -> tuple[float, float, str, bool]:
    entry = forecast.entry_price or forecast.current_price
    take_profit = forecast.take_profit_price or entry
    stop_loss = forecast.stop_loss_price or entry

    tp_hit = settlement_bar.low <= take_profit
    sl_hit = settlement_bar.high >= stop_loss

    if tp_hit and sl_hit:
        return round(entry - stop_loss, 2), stop_loss, "loss", False
    if tp_hit:
        return round(entry - take_profit, 2), take_profit, "win", True
    if sl_hit:
        return round(entry - stop_loss, 2), stop_loss, "loss", False

    pnl_points = round(entry - settlement_bar.close, 2)
    direction_hit = settlement_bar.close <= entry
    return pnl_points, settlement_bar.close, "flat", direction_hit


def _evaluation_result_label(result: str) -> str:
    labels = {
        "win": "命中止盈",
        "loss": "触发止损",
        "flat": "持平/区间",
    }
    return labels.get(result, result)


def create_research_forecast_from_inputs(
    latest_bar: DailyBar,
    quote: CurrentQuote,
    indicators: TechnicalIndicators,
) -> ForecastResult:
    price = quote.current_price
    atr = _usable_atr(indicators, latest_bar, price)
    direction = _direction_from_inputs(price, latest_bar, indicators)
    entry_price, take_profit_price, stop_loss_price = _research_levels(price, atr, direction)
    entry_price_low = None
    entry_price_high = None
    if direction == ForecastDirection.neutral:
        entry_price_low, entry_price_high = _neutral_entry_range(price, atr, latest_bar)
        entry_price = round((entry_price_low + entry_price_high) / 2, 2)
    technical_summary = _technical_summary(price, latest_bar, indicators, direction, atr)
    technical_summary = _append_summary_section(
        technical_summary,
        "技术分析·聪明钱",
        _smart_money_summary(price, latest_bar, indicators, direction, atr),
    )
    macro_summary = _macro_summary(
        {
            "current_price": round(price, 4),
            "latest_close": latest_bar.close,
            "sma_20": indicators.sma_20,
            "ema_12": indicators.ema_12,
            "dollar_index": {"status": "unavailable"},
            "real_rates": {"status": "unavailable"},
            "available_signals": ["price_action", "technical_indicators"],
            "unavailable_signals": ["dollar_index", "real_rates"],
        }
    )
    news_summary = "新闻信息未接入外部实时数据源，本轮不使用未经验证的新闻假设影响方向判断。"
    market_sentiment_summary = "市场情绪暂未接入外部实时源，当前按价格结构、RSI 和历史反馈回放推导为中性偏谨慎。"
    alt_data_summary = (
        "另类数据维度以保守处理为主。\n"
        "- 五角大楼披萨指数暂无可靠实时源，本轮标记为 unavailable。\n"
        "- 美元指数和实际利率若不可用，将在后续研究中单独提示。\n"
        "- 本轮仅用于风险提示，不作为方向依据。"
    )
    risk_notes = _risk_notes(latest_bar, indicators, atr)
    risk_summary = "风险评估基于 ATR、最新日线振幅、RSI 和关键价格边界生成，最新K线只用于判断波动边界，不作为复盘结论。"
    agent_votes = [
        AgentVote(
            agent="technical",
            direction=direction,
            confidence=_technical_confidence(indicators, direction),
            rationale=technical_summary,
        ),
        AgentVote(
            agent="macro",
            direction=ForecastDirection.neutral,
            confidence=0.35,
            rationale=macro_summary,
        ),
        AgentVote(
            agent="news",
            direction=ForecastDirection.neutral,
            confidence=0.35,
            rationale=news_summary,
        ),
        AgentVote(
            agent="market_sentiment",
            direction=ForecastDirection.neutral,
            confidence=0.4,
            rationale=market_sentiment_summary,
        ),
        AgentVote(
            agent="alt_data",
            direction=ForecastDirection.neutral,
            confidence=0.3,
            rationale=alt_data_summary,
        ),
        AgentVote(
            agent="risk",
            direction=_risk_vote_direction(direction, atr, price),
            confidence=0.55,
            rationale=risk_summary,
        ),
    ]

    return ForecastResult(
        symbol=quote.symbol or latest_bar.symbol,
        reference_time=datetime.now(UTC),
        data_timestamp=quote.data_timestamp,
        data_source=quote.data_source,
        current_price=round(price, 6),
        daily_open=latest_bar.open,
        daily_high=latest_bar.high,
        daily_low=latest_bar.low,
        daily_close=latest_bar.close,
        direction=direction,
        window_directions=_forecast_window_directions(direction, _combined_confidence(agent_votes, indicators)),
        entry_price=entry_price,
        entry_price_low=entry_price_low,
        entry_price_high=entry_price_high,
        take_profit_price=take_profit_price,
        stop_loss_price=stop_loss_price,
        holding_period=_holding_period(direction, atr, price),
        intraday_action=_intraday_action(
            direction,
            entry_price,
            take_profit_price,
            stop_loss_price,
            entry_price_low,
            entry_price_high,
        ),
        long_term_action=_long_term_action(direction),
        confidence_score=_combined_confidence(agent_votes, indicators),
        technical_summary=technical_summary,
        macro_summary=macro_summary,
        news_summary=news_summary,
        market_sentiment_summary=market_sentiment_summary,
        alt_data_summary=alt_data_summary,
        risk_summary=risk_summary,
        agent_votes=agent_votes,
        risk_notes=risk_notes,
        disclaimer=RESEARCH_DISCLAIMER,
    )


def _forecast_window_directions(
    direction: ForecastDirection,
    confidence_score: float,
) -> list[ForecastWindowDirection]:
    middle_direction = direction if direction != ForecastDirection.neutral else ForecastDirection.neutral
    future_direction = ForecastDirection.neutral if direction == ForecastDirection.neutral else direction
    return [
        ForecastWindowDirection(
            window_label="0-3天",
            direction=direction,
            strength="strong" if confidence_score >= 0.7 else "moderate",
            confidence=round(min(confidence_score + 0.04, 0.99), 2),
            reason="短期仍以当前价格结构与动量节奏为主。",
        ),
        ForecastWindowDirection(
            window_label="3-5天",
            direction=middle_direction,
            strength="moderate" if confidence_score >= 0.55 else "mild",
            confidence=round(max(min(confidence_score - 0.02, 0.95), 0.35), 2),
            reason="中短期继续观察回踩/反弹后的延续性。",
        ),
        ForecastWindowDirection(
            window_label="6-15天",
            direction=middle_direction,
            strength="mild",
            confidence=round(max(min(confidence_score - 0.08, 0.9), 0.3), 2),
            reason="中期方向可能延续，但波动和事件风险会抬升。",
        ),
        ForecastWindowDirection(
            window_label="15天后",
            direction=future_direction,
            strength="mild",
            confidence=round(max(min(confidence_score - 0.12, 0.85), 0.25), 2),
            reason="更远期更容易进入震荡或重新定价阶段。",
        ),
    ]


def router_validate_request(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="router_validate_request")
    if "errors" in state and state["errors"]:
        raise ValueError("; ".join(state["errors"]))
    return {}


async def tool_load_market_data(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="tool_load_market_data")
    if "market_data" in state and "latest_bar" in state and "bars" in state:
        return {}

    repository = state.get("repository")
    if repository is None:
        raise ValueError("workflow state missing repository for market data loading")

    symbol = "XAUUSD"
    latest_bar = await repository.get_latest_market_bar(symbol)
    if latest_bar is None:
        raise ValueError("market data repository does not contain any persisted daily bars")

    bars = await repository.get_market_bars_between(symbol, date(1970, 1, 1), latest_bar.date)
    market_data = MarketDataSet(symbol=latest_bar.symbol, bars=bars, latest_bar=latest_bar)
    return {
        "market_data": market_data,
        "bars": bars,
        "latest_bar": latest_bar,
    }


async def tool_ensure_market_data_freshness(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="tool_ensure_market_data_freshness")
    repository = state.get("repository")
    if repository is None:
        raise ValueError("workflow state missing repository for market data freshness preflight")

    settings = state.get("settings") or get_settings()
    backfill_runner = run_eod_backfill
    if backfill_runner is None:
        from goldfxgraph.backfill.eod_backfill import run_eod_backfill as backfill_runner  # type: ignore[no-redef]

    result = await backfill_runner(
        settings=settings,
        repository=repository,
        now=datetime.now(UTC),
    )
    if result.status == "failed":
        raise MarketDataFreshnessError(
            f"market data freshness check failed: {result.failure_reason or 'unknown failure'}"
        )
    return {}


def tool_fetch_current_gold_quote(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="tool_fetch_current_gold_quote")
    if "quote" in state:
        return {}

    provider = state.get("quote_provider")
    if provider is None:
        settings = state.get("settings") or get_settings()
        provider = CurrentQuoteProvider(
            url=settings.current_quote_url,
        )

    quote = provider.fetch()
    quote = _require_tradingview_quote(quote)
    return {"quote": quote}


def _require_tradingview_quote(quote: CurrentQuote) -> CurrentQuote:
    if quote.data_source.strip().lower() != DEFAULT_TRADINGVIEW_SOURCE.lower():
        raise QuoteProviderError("TradingView quote provider returned a non-TradingView data source")
    if quote.data_source != DEFAULT_TRADINGVIEW_SOURCE:
        quote = quote.model_copy(update={"data_source": DEFAULT_TRADINGVIEW_SOURCE})
    return quote


def tool_compute_indicators(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="tool_compute_indicators")
    if "indicators" in state:
        return {}

    bars = state.get("bars")
    if bars is None:
        market_data = state.get("market_data")
        bars = market_data.bars if market_data else None
    if not bars:
        raise ValueError("workflow state missing daily bars for technical indicator calculation")

    return {"indicators": compute_technical_indicators(bars)}


def tool_fetch_macro_inputs(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="tool_fetch_macro_inputs")
    latest_bar = _required(state, "latest_bar")
    quote = _required(state, "quote")
    indicators = _required(state, "indicators")
    signal_transport = state.get("signal_http_transport")
    dollar_index, _ = _fetch_dollar_index(signal_transport)
    real_rates, _ = _fetch_real_rates(signal_transport)
    unavailable_signals = list(state.get("unavailable_signals") or [])
    if dollar_index.get("status") != "available":
        unavailable_signals.append("dollar_index")
    if real_rates.get("status") != "available":
        unavailable_signals.append("real_rates")
    unavailable_signals = _unique_strings([str(item) for item in unavailable_signals])
    available_signals = ["price_action", "technical_indicators"]
    if dollar_index.get("status") == "available":
        available_signals.append("dollar_index")
    if real_rates.get("status") == "available":
        available_signals.append("real_rates")
    inputs = {
        "current_price": round(quote.current_price, 4),
        "latest_close": latest_bar.close,
        "sma_20": indicators.sma_20,
        "ema_12": indicators.ema_12,
        "dollar_index": dollar_index,
        "real_rates": real_rates,
        "available_signals": available_signals,
        "unavailable_signals": unavailable_signals,
    }
    return {
        "macro_inputs": inputs,
        "unavailable_signals": unavailable_signals,
    }


def agent_technical_analysis(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(
        state,
        current_stage="agent_technical_analysis",
        active_agent="technical",
    )
    latest_bar = _required(state, "latest_bar")
    quote = _required(state, "quote")
    indicators = _required(state, "indicators")
    remote, _diagnostic, diagnostic_record = _remote_agent_response(
        state,
        "technical",
        "agent_technical_analysis",
    )
    diagnostics = _append_agent_diagnostic(state, diagnostic_record)
    atr = _usable_atr(indicators, latest_bar, quote.current_price)
    if remote is None:
        summary = _failure_summary("technical", diagnostic_record.get("message") if diagnostic_record else None)
        direction = ForecastDirection.neutral
        confidence = 0.0
    else:
        direction = remote.direction
        summary = remote.summary
        summary = _append_summary_section(
            summary,
            "技术分析·聪明钱",
            _smart_money_summary(quote.current_price, latest_bar, indicators, direction, atr),
        )
        confidence = remote.confidence
    vote = AgentVote(
        agent="technical",
        direction=direction,
        confidence=confidence,
        rationale=summary,
    )
    return {
        "agent_diagnostics": diagnostics,
        "technical_summary": summary,
        "agent_votes": [*_existing_votes_without(state, "technical"), vote],
    }


def agent_macro_analysis(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(
        state,
        current_stage="agent_macro_analysis",
        active_agent="macro",
    )
    remote, _diagnostic, diagnostic_record = _remote_agent_response(state, "macro", "agent_macro_analysis")
    diagnostics = _append_agent_diagnostic(state, diagnostic_record)
    if remote is None:
        summary = _failure_summary("macro", diagnostic_record.get("message") if diagnostic_record else None)
        direction = ForecastDirection.neutral
        confidence = 0.0
    else:
        summary = remote.summary
        direction = remote.direction
        confidence = remote.confidence
    vote = AgentVote(
        agent="macro",
        direction=direction,
        confidence=confidence,
        rationale=summary,
    )
    return {
        "agent_diagnostics": diagnostics,
        "macro_summary": summary,
        "agent_votes": [*_existing_votes_without(state, "macro"), vote],
    }


def agent_news_analysis(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(
        state,
        current_stage="agent_news_analysis",
        active_agent="news",
    )
    remote, _diagnostic, diagnostic_record = _remote_agent_response(state, "news", "agent_news_analysis")
    diagnostics = _append_agent_diagnostic(state, diagnostic_record)
    inputs = state.get("newsflow_inputs", {})
    reference_summary = _news_summary(inputs)
    if remote is None:
        summary = _failure_summary("news", diagnostic_record.get("message") if diagnostic_record else None)
        direction = ForecastDirection.neutral
        confidence = 0.0
    else:
        summary = remote.summary
        summary = _normalize_news_summary_representative_titles(summary, reference_summary)
        if "代表性标题" not in summary and reference_summary:
            summary = _append_summary_section(summary, "重点·参考新闻", reference_summary)
        direction = remote.direction
        confidence = remote.confidence
    vote = AgentVote(
        agent="news",
        direction=direction,
        confidence=confidence,
        rationale=summary,
    )
    return {
        "agent_diagnostics": diagnostics,
        "news_summary": summary,
        "agent_votes": [*_existing_votes_without(state, "news"), vote],
    }


def agent_risk_analysis(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(
        state,
        current_stage="agent_risk_analysis",
        active_agent="risk",
    )
    latest_bar = _required(state, "latest_bar")
    quote = _required(state, "quote")
    indicators = _required(state, "indicators")
    atr = _usable_atr(indicators, latest_bar, quote.current_price)
    remote, _diagnostic, diagnostic_record = _remote_agent_response(state, "risk", "agent_risk_analysis")
    diagnostics = _append_agent_diagnostic(state, diagnostic_record)
    notes = _merge_notes(
        state.get("risk_notes"),
        remote.risk_notes if remote and remote.risk_notes else _risk_notes(latest_bar, indicators, atr),
    )
    if remote is None:
        summary = _failure_summary("risk", diagnostic_record.get("message") if diagnostic_record else None)
        direction = ForecastDirection.neutral
        confidence = 0.0
    else:
        summary = remote.summary
        direction = remote.direction
        confidence = remote.confidence
    vote = AgentVote(
        agent="risk",
        direction=direction,
        confidence=confidence,
        rationale=summary,
    )
    return {
        "agent_diagnostics": diagnostics,
        "risk_summary": summary,
        "risk_notes": notes,
        "agent_votes": [*_existing_votes_without(state, "risk"), vote],
    }


def _committee_vote(state: WorkflowState, agent_name: str) -> AgentVote | None:
    for vote in reversed(state.get("agent_votes") or []):
        if vote.agent == agent_name:
            return vote
    return None


def _committee_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        for key in ("summary", "note", "sentiment", "label", "value"):
            raw_value = value.get(key)
            if raw_value not in (None, ""):
                return str(raw_value)
    return str(value)


def _committee_source_status(source_block: object) -> EvidenceToolStatus:
    if not isinstance(source_block, dict):
        return EvidenceToolStatus.unavailable
    status = str(source_block.get("status") or "").strip().lower()
    if not status:
        available_signals = source_block.get("available_signals")
        if isinstance(available_signals, list) and available_signals:
            return EvidenceToolStatus.ok
        return EvidenceToolStatus.unavailable
    if status == "available":
        unavailable_signals = source_block.get("unavailable_signals")
        if isinstance(unavailable_signals, list) and unavailable_signals:
            return EvidenceToolStatus.degraded
        return EvidenceToolStatus.ok
    if status == "degraded":
        return EvidenceToolStatus.degraded
    return EvidenceToolStatus.unavailable


def _committee_source_degraded_reason(source_block: object, source_label: str) -> str | None:
    if not isinstance(source_block, dict):
        return f"{source_label} 输入缺失。"

    reasons: list[str] = []
    status = str(source_block.get("status") or "").strip().lower()
    if status and status != "available":
        reasons.append(f"{source_label} status={status}")
    unavailable_signals = source_block.get("unavailable_signals")
    if isinstance(unavailable_signals, list) and unavailable_signals:
        reasons.append(f"{source_label} unavailable={', '.join(str(item) for item in unavailable_signals)}")
    if not reasons:
        return None
    return "；".join(reasons)


def _committee_data_freshness_label(latest_bar: DailyBar, quote: CurrentQuote) -> str:
    return f"quote={quote.data_timestamp.isoformat()}; bar_date={latest_bar.date.isoformat()}"


def _committee_indicators_degraded_reason(indicators: TechnicalIndicators) -> str | None:
    if not indicators.unavailable:
        return None
    unavailable = ", ".join(sorted(indicators.unavailable))
    return f"技术指标缺失：{unavailable}"


def _committee_evidence_package_summary(state: WorkflowState) -> str:
    latest_bar = _required(state, "latest_bar")
    quote = _required(state, "quote")
    return (
        f"围绕 XAUUSD 的两轮对抗式交易委员会证据包。最新报价 {quote.current_price:.2f}，"
        f"最新完成日线 {latest_bar.date.isoformat()}，仅汇总 specialist analyses 的结构化证据。"
    )


def _risk_note_snippets(notes: list[str] | None, *, limit: int = 3) -> list[str]:
    snippets: list[str] = []
    for note in notes or []:
        cleaned = str(note).strip()
        if cleaned and cleaned not in snippets:
            snippets.append(cleaned)
        if len(snippets) >= limit:
            break
    return snippets


def _macro_evidence_snippets(macro_inputs: object) -> list[str]:
    if not isinstance(macro_inputs, dict):
        return []
    snippets: list[str] = []
    dollar_index = macro_inputs.get("dollar_index")
    real_rates = macro_inputs.get("real_rates")
    if isinstance(dollar_index, dict):
        text = _committee_text(dollar_index)
        if text:
            snippets.append(f"美元指数：{text}")
    if isinstance(real_rates, dict):
        text = _committee_text(real_rates)
        if text:
            snippets.append(f"实际利率：{text}")
    return snippets


def _macro_important_levels(macro_inputs: object) -> list[str]:
    if not isinstance(macro_inputs, dict):
        return []
    levels: list[str] = []
    dollar_index = macro_inputs.get("dollar_index")
    real_rates = macro_inputs.get("real_rates")
    if isinstance(dollar_index, dict):
        text = _committee_text(dollar_index.get("value"))
        if text:
            levels.append(f"美元指数 {text}")
    if isinstance(real_rates, dict):
        text = _committee_text(real_rates.get("value"))
        if text:
            levels.append(f"实际利率 {text}")
    return levels


def _news_evidence_snippets(newsflow_inputs: object) -> list[str]:
    if not isinstance(newsflow_inputs, dict):
        return []
    snippets: list[str] = []
    summary = _committee_text(newsflow_inputs.get("summary"))
    if summary:
        snippets.append(summary)
    top_headlines = newsflow_inputs.get("top_headlines")
    if isinstance(top_headlines, list):
        for item in top_headlines[:3]:
            if not isinstance(item, dict):
                continue
            title = _committee_text(item.get("title_cn") or item.get("title"))
            source = _committee_text(item.get("source_cn") or item.get("source"))
            if title and source:
                snippets.append(f"{source}：{title}")
            elif title:
                snippets.append(title)
    return snippets


def _news_important_levels(newsflow_inputs: object) -> list[str]:
    if not isinstance(newsflow_inputs, dict):
        return []
    levels: list[str] = []
    sentiment = _committee_text(newsflow_inputs.get("sentiment"))
    if sentiment:
        levels.append(f"newsflow sentiment={sentiment}")
    headline_count = newsflow_inputs.get("headline_count")
    if headline_count is not None:
        levels.append(f"headline_count={headline_count}")
    return levels


def _market_sentiment_evidence_snippets(market_sentiment_inputs: object) -> list[str]:
    if not isinstance(market_sentiment_inputs, dict):
        return []
    snippets: list[str] = []
    feedback_history = market_sentiment_inputs.get("feedback_history")
    if isinstance(feedback_history, list):
        for item in feedback_history[:3]:
            text = _committee_text(item)
            if text:
                snippets.append(f"反馈历史：{text}")
    cftc_commitments = market_sentiment_inputs.get("cftc_commitments")
    if isinstance(cftc_commitments, dict):
        text = _committee_text(cftc_commitments)
        if text:
            snippets.append(f"CFTC：{text}")
    polymarket_summary = _committee_text(market_sentiment_inputs.get("polymarket_summary"))
    if polymarket_summary:
        snippets.append(f"Polymarket：{polymarket_summary}")
    return snippets


def _market_sentiment_important_levels(market_sentiment_inputs: object) -> list[str]:
    if not isinstance(market_sentiment_inputs, dict):
        return []
    levels: list[str] = []
    count = market_sentiment_inputs.get("feedback_signal_count")
    if count is not None:
        levels.append(f"feedback_signal_count={count}")
    bullish_count = market_sentiment_inputs.get("polymarket_bullish_count")
    bearish_count = market_sentiment_inputs.get("polymarket_bearish_count")
    if bullish_count is not None or bearish_count is not None:
        levels.append(
            f"Polymarket bullish={bullish_count or 0}, bearish={bearish_count or 0}"
        )
    return levels


def _alt_data_evidence_snippets(alt_data_inputs: object) -> list[str]:
    if not isinstance(alt_data_inputs, dict):
        return []
    snippets: list[str] = []
    pizza_index = alt_data_inputs.get("pizza_index")
    dollar_index = alt_data_inputs.get("dollar_index")
    real_rates = alt_data_inputs.get("real_rates")
    if isinstance(pizza_index, dict):
        text = _committee_text(pizza_index)
        if text:
            snippets.append(f"Pizza Index：{text}")
    if isinstance(dollar_index, dict):
        text = _committee_text(dollar_index)
        if text:
            snippets.append(f"美元指数：{text}")
    if isinstance(real_rates, dict):
        text = _committee_text(real_rates)
        if text:
            snippets.append(f"实际利率：{text}")
    return snippets


def _alt_data_important_levels(alt_data_inputs: object) -> list[str]:
    if not isinstance(alt_data_inputs, dict):
        return []
    levels: list[str] = []
    price_context = alt_data_inputs.get("price_context")
    if isinstance(price_context, dict):
        current_price = _committee_text(price_context.get("current_price"))
        latest_close = _committee_text(price_context.get("latest_close"))
        if current_price:
            levels.append(f"current_price={current_price}")
        if latest_close:
            levels.append(f"latest_close={latest_close}")
    return levels


def _committee_source_risk_factors(source_block: object, source_label: str) -> list[str]:
    if not isinstance(source_block, dict):
        return [f"{source_label} 输入缺失。"]

    factors: list[str] = []
    unavailable_signals = source_block.get("unavailable_signals")
    if isinstance(unavailable_signals, list):
        for signal in unavailable_signals:
            text = _committee_text(signal)
            if text:
                factors.append(f"{source_label} unavailable={text}")

    status = str(source_block.get("status") or "").strip().lower()
    if status and status != "available":
        factors.append(f"{source_label} status={status}")
    return factors


def _committee_tool_status(source_block: object, source_label: str) -> EvidenceToolStatus:
    status = _committee_source_status(source_block)
    if status != EvidenceToolStatus.ok:
        return status
    if _committee_source_degraded_reason(source_block, source_label):
        return EvidenceToolStatus.degraded
    return EvidenceToolStatus.ok


def _build_committee_evidence_item(
    *,
    item_id: str,
    specialist_name: str,
    category: str,
    vote: AgentVote | None,
    default_confidence: float,
    key_evidence: list[str],
    risk_factors: list[str],
    invalidation_conditions: list[str],
    important_levels: list[str],
    data_freshness: str,
    tool_status: EvidenceToolStatus,
    degraded_reason: str | None,
    evidence_refs: list[str],
) -> EvidencePackageItem:
    signal = vote.direction.value if vote is not None else ForecastDirection.neutral.value
    confidence = vote.confidence if vote is not None else default_confidence
    return EvidencePackageItem(
        item_id=item_id,
        specialist_name=specialist_name,
        category=category,
        signal=signal,
        confidence=round(confidence, 2),
        key_evidence=[snippet for snippet in key_evidence if snippet],
        risk_factors=[snippet for snippet in risk_factors if snippet],
        invalidation_conditions=[snippet for snippet in invalidation_conditions if snippet],
        important_levels=[snippet for snippet in important_levels if snippet],
        data_freshness=data_freshness,
        tool_status=tool_status,
        degraded_reason=degraded_reason,
        evidence_refs=[snippet for snippet in evidence_refs if snippet],
    )


def node_build_evidence_package(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="node_build_evidence_package")
    latest_bar = _required(state, "latest_bar")
    quote = _required(state, "quote")
    indicators = _required(state, "indicators")
    technical_summary = _required(state, "technical_summary")
    macro_summary = _required(state, "macro_summary")
    news_summary = _required(state, "news_summary")
    market_sentiment_summary = _required(state, "market_sentiment_summary")
    alt_data_summary = _required(state, "alt_data_summary")
    risk_summary = _required(state, "risk_summary")

    data_freshness = _committee_data_freshness_label(latest_bar, quote)
    risk_notes = _risk_note_snippets(state.get("risk_notes"))
    evidence_package = EvidencePackage(
        symbol=quote.symbol or latest_bar.symbol,
        reference_time=datetime.now(UTC),
        data_timestamp=quote.data_timestamp,
        data_source=quote.data_source,
        summary=_committee_evidence_package_summary(state),
        items=[
            _build_committee_evidence_item(
                item_id="technical",
                specialist_name="technical",
                category="price_action",
                vote=_committee_vote(state, "technical"),
                default_confidence=_technical_confidence(
                    indicators,
                    _direction_from_inputs(quote.current_price, latest_bar, indicators),
                ),
                key_evidence=[
                    technical_summary,
                    f"当前报价 {quote.current_price:.2f}",
                    f"最新完成日线收盘 {latest_bar.close:.2f}",
                ],
                risk_factors=risk_notes,
                invalidation_conditions=[
                    f"收盘有效跌破 {latest_bar.low:.2f}",
                    "技术均线结构重新转弱",
                ],
                important_levels=[
                    f"日内高点 {latest_bar.high:.2f}",
                    f"日内低点 {latest_bar.low:.2f}",
                    f"报价 {quote.current_price:.2f}",
                ],
                data_freshness=data_freshness,
                tool_status=EvidenceToolStatus.degraded if indicators.unavailable else EvidenceToolStatus.ok,
                degraded_reason=_committee_indicators_degraded_reason(indicators),
                evidence_refs=[
                    "technical_summary",
                    "quote.current_price",
                    "latest_bar.close",
                    "indicators.sma_20",
                    "indicators.ema_12",
                    "indicators.rsi_14",
                    "indicators.atr_14",
                ],
            ),
            _build_committee_evidence_item(
                item_id="macro",
                specialist_name="macro",
                category="macro_regime",
                vote=_committee_vote(state, "macro"),
                default_confidence=0.35,
                key_evidence=[macro_summary, *_macro_evidence_snippets(state.get("macro_inputs"))],
                risk_factors=_committee_source_risk_factors(state.get("macro_inputs"), "macro"),
                invalidation_conditions=[
                    "美元指数与实际利率方向未能继续支持该宏观情景",
                    "宏观输入恢复后与当前摘要结论相反",
                ],
                important_levels=_macro_important_levels(state.get("macro_inputs")),
                data_freshness=data_freshness,
                tool_status=_committee_tool_status(state.get("macro_inputs"), "macro"),
                degraded_reason=_committee_source_degraded_reason(state.get("macro_inputs"), "macro"),
                evidence_refs=[
                    "macro_summary",
                    "macro_inputs.dollar_index",
                    "macro_inputs.real_rates",
                ],
            ),
            _build_committee_evidence_item(
                item_id="news",
                specialist_name="news",
                category="event_flow",
                vote=_committee_vote(state, "news"),
                default_confidence=0.35,
                key_evidence=[news_summary, *_news_evidence_snippets(state.get("newsflow_inputs"))],
                risk_factors=_committee_source_risk_factors(state.get("newsflow_inputs"), "newsflow"),
                invalidation_conditions=[
                    "可验证新闻流出现明确反向冲击",
                    "后续新闻流与当前摘要结论出现持续背离",
                ],
                important_levels=_news_important_levels(state.get("newsflow_inputs")),
                data_freshness=data_freshness,
                tool_status=_committee_tool_status(state.get("newsflow_inputs"), "newsflow"),
                degraded_reason=_committee_source_degraded_reason(state.get("newsflow_inputs"), "newsflow"),
                evidence_refs=[
                    "news_summary",
                    "newsflow_inputs.top_headlines",
                    "newsflow_inputs.sentiment",
                ],
            ),
            _build_committee_evidence_item(
                item_id="market_sentiment",
                specialist_name="market_sentiment",
                category="positioning_sentiment",
                vote=_committee_vote(state, "market_sentiment"),
                default_confidence=0.4,
                key_evidence=[
                    market_sentiment_summary,
                    *_market_sentiment_evidence_snippets(state.get("market_sentiment_inputs")),
                ],
                risk_factors=_committee_source_risk_factors(
                    state.get("market_sentiment_inputs"),
                    "market_sentiment",
                ),
                invalidation_conditions=[
                    "反馈历史与持仓/预测数据持续反向",
                    "情绪数据恢复后明显推翻当前判断",
                ],
                important_levels=_market_sentiment_important_levels(state.get("market_sentiment_inputs")),
                data_freshness=data_freshness,
                tool_status=_committee_tool_status(
                    state.get("market_sentiment_inputs"),
                    "market_sentiment",
                ),
                degraded_reason=_committee_source_degraded_reason(
                    state.get("market_sentiment_inputs"),
                    "market_sentiment",
                ),
                evidence_refs=[
                    "market_sentiment_summary",
                    "forecast_feedback_history",
                    "market_sentiment_inputs.cftc_commitments",
                    "market_sentiment_inputs.polymarket_summary",
                ],
            ),
            _build_committee_evidence_item(
                item_id="alt_data",
                specialist_name="alt_data",
                category="alternative_data",
                vote=_committee_vote(state, "alt_data"),
                default_confidence=0.3,
                key_evidence=[alt_data_summary, *_alt_data_evidence_snippets(state.get("alt_data_inputs"))],
                risk_factors=_committee_source_risk_factors(state.get("alt_data_inputs"), "alt_data"),
                invalidation_conditions=[
                    "另类数据恢复后明显与当前摘要结论相反",
                    "核心另类数据源全部恢复且指向反向",
                ],
                important_levels=_alt_data_important_levels(state.get("alt_data_inputs")),
                data_freshness=data_freshness,
                tool_status=_committee_tool_status(state.get("alt_data_inputs"), "alt_data"),
                degraded_reason=_committee_source_degraded_reason(state.get("alt_data_inputs"), "alt_data"),
                evidence_refs=[
                    "alt_data_summary",
                    "alt_data_inputs.pizza_index",
                    "alt_data_inputs.dollar_index",
                    "alt_data_inputs.real_rates",
                ],
            ),
            _build_committee_evidence_item(
                item_id="risk",
                specialist_name="risk",
                category="risk_control",
                vote=_committee_vote(state, "risk"),
                default_confidence=0.55,
                key_evidence=[risk_summary, *_risk_note_snippets(state.get("risk_notes"))],
                risk_factors=_risk_note_snippets(state.get("risk_notes")),
                invalidation_conditions=[
                    "波动放大到超出当前风险假设",
                    "风险提示显示仓位/波动结构已失效",
                ],
                important_levels=[
                    f"ATR 参考 {(_usable_atr(indicators, latest_bar, quote.current_price)):.2f}",
                    f"日线波幅 {latest_bar.high - latest_bar.low:.2f}",
                ],
                data_freshness=data_freshness,
                tool_status=EvidenceToolStatus.degraded if indicators.unavailable else EvidenceToolStatus.ok,
                degraded_reason=_committee_indicators_degraded_reason(indicators),
                evidence_refs=[
                    "risk_summary",
                    "risk_notes",
                    "indicators.atr_14",
                ],
            ),
        ],
        notes=[
            "证据包只汇总 specialist analysis 和工具输入，不包含 bull/bear/chair 观点。",
            "后续委员会节点只能基于 evidence package 中可引用的事实发言。",
            "若某项输入不可用，对应 item 会标记为 degraded 或 unavailable。",
        ],
    )

    return {"evidence_package": evidence_package}


COMMITTEE_PROMPT_KEYS: dict[str, tuple[str, str]] = {
    "bull_opening_case": (
        "trading_committee.bull_opening_case.system",
        "trading_committee.bull_opening_case.user",
    ),
    "bear_opening_case": (
        "trading_committee.bear_opening_case.system",
        "trading_committee.bear_opening_case.user",
    ),
    "bull_rebuttal": (
        "trading_committee.bull_rebuttal.system",
        "trading_committee.bull_rebuttal.user",
    ),
    "bear_rebuttal": (
        "trading_committee.bear_rebuttal.system",
        "trading_committee.bear_rebuttal.user",
    ),
    "bull_final_position": (
        "trading_committee.bull_final_position.system",
        "trading_committee.bull_final_position.user",
    ),
    "bear_final_position": (
        "trading_committee.bear_final_position.system",
        "trading_committee.bear_final_position.user",
    ),
    "chair": (
        "trading_committee.chair.system",
        "trading_committee.chair.user",
    ),
    "repair": (
        "trading_committee.repair.system",
        "trading_committee.repair.user",
    ),
}


def _json_block(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str)


def _append_committee_prompt_versions(
    state: WorkflowState,
    rendered_prompts: list[RenderedPrompt],
) -> list[PromptVersionMetadata]:
    prompt_versions = list(state.get("prompt_versions") or [])
    for rendered_prompt in rendered_prompts:
        prompt_versions.append(
            PromptVersionMetadata(
                prompt_key=rendered_prompt.prompt_key,
                version=rendered_prompt.version,
                prompt_type=rendered_prompt.prompt_type,
                agent_name=rendered_prompt.agent_name,
                node_name=rendered_prompt.node_name,
                model_family=rendered_prompt.model_family,
                is_active=rendered_prompt.is_active,
                rendered_variable_names=list(rendered_prompt.rendered_variable_names),
                output_schema_ref=rendered_prompt.output_schema_ref,
            )
        )
    return prompt_versions


def _committee_prompt_variables(state: WorkflowState, role: str) -> dict[str, str]:
    evidence_package = _required(state, "evidence_package")
    if role in {"bull_opening_case", "bear_opening_case"}:
        return {"evidence_package": _json_block(evidence_package)}
    if role in {"bull_rebuttal", "bear_rebuttal"}:
        opening_cases = {
            "bull_opening_case": state.get("bull_opening_case"),
            "bear_opening_case": state.get("bear_opening_case"),
        }
        return {
            "opening_cases": _json_block(opening_cases),
            "evidence_package": _json_block(evidence_package),
        }
    if role in {"bull_final_position", "bear_final_position"}:
        opening_case_key = "bull_opening_case" if role.startswith("bull") else "bear_opening_case"
        rebuttal_key = "bull_rebuttal" if role.startswith("bull") else "bear_rebuttal"
        return {
            "opening_case": _json_block(state.get(opening_case_key)),
            "rebuttal": _json_block(state.get(rebuttal_key)),
            "evidence_package": _json_block(evidence_package),
        }
    if role == "chair":
        return {
            "evidence_package": _json_block(evidence_package),
            "opening_cases": _json_block(
                {
                    "bull_opening_case": state.get("bull_opening_case"),
                    "bear_opening_case": state.get("bear_opening_case"),
                }
            ),
            "rebuttals": _json_block(
                {
                    "bull_rebuttal": state.get("bull_rebuttal"),
                    "bear_rebuttal": state.get("bear_rebuttal"),
                }
            ),
            "final_positions": _json_block(
                {
                    "bull_final_position": state.get("bull_final_position"),
                    "bear_final_position": state.get("bear_final_position"),
                }
            ),
        }
    if role == "repair":
        return {
            "validation_errors": _json_block(state.get("validation_errors") or []),
            "committee_decision": _json_block(state.get("committee_decision")),
            "evidence_package": _json_block(evidence_package),
        }
    raise ValueError(f"unsupported committee role: {role}")


async def _record_committee_prompt_versions(
    state: WorkflowState,
    role: str,
) -> list[PromptVersionMetadata]:
    repository = state.get("repository")
    if repository is None:
        return list(state.get("prompt_versions") or [])
    system_key, user_key = COMMITTEE_PROMPT_KEYS[role]
    service = PromptTemplateService(repository._session_factory)  # type: ignore[attr-defined]
    variables = _committee_prompt_variables(state, role)
    rendered_system = await service.render_prompt(system_key, variables)
    rendered_user = await service.render_prompt(user_key, variables)
    return _append_committee_prompt_versions(state, [rendered_system, rendered_user])


def _committee_supporting_items(evidence_package: EvidencePackage, side: DebateSide) -> list[EvidencePackageItem]:
    supported_signals = {"bullish", "neutral"} if side == DebateSide.bull else {"bearish", "neutral"}
    return [item for item in evidence_package.items if item.signal in supported_signals]


def _committee_opposing_items(evidence_package: EvidencePackage, side: DebateSide) -> list[EvidencePackageItem]:
    opposing_signal = "bearish" if side == DebateSide.bull else "bullish"
    return [item for item in evidence_package.items if item.signal == opposing_signal]


def _committee_item_snippets(items: list[EvidencePackageItem], *, limit: int = 3) -> list[str]:
    snippets: list[str] = []
    for item in items:
        for source in [item.key_evidence, item.risk_factors, item.important_levels]:
            for text in source:
                cleaned = str(text).strip()
                if cleaned and cleaned not in snippets:
                    snippets.append(cleaned)
                if len(snippets) >= limit:
                    return snippets
    return snippets


def _committee_average_confidence(items: list[EvidencePackageItem], *, default: float) -> float:
    if not items:
        return default
    average = sum(item.confidence for item in items) / len(items)
    return round(min(max(average, 0.0), 1.0), 2)


def _committee_price_context(state: WorkflowState) -> tuple[DailyBar, CurrentQuote, TechnicalIndicators, float]:
    latest_bar = _required(state, "latest_bar")
    quote = _required(state, "quote")
    indicators = _required(state, "indicators")
    atr = _usable_atr(indicators, latest_bar, quote.current_price)
    return latest_bar, quote, indicators, atr


def _build_opening_case(state: WorkflowState, side: DebateSide) -> DebateCase:
    evidence_package = _required(state, "evidence_package")
    latest_bar, quote, indicators, atr = _committee_price_context(state)
    supporting_items = _committee_supporting_items(evidence_package, side)
    opposing_items = _committee_opposing_items(evidence_package, side)
    side_label = "看多" if side == DebateSide.bull else "看空"
    thesis = (
        f"{side_label}开场：根据证据包中最相关的结构化信号，"
        f"当前更适合以{side_label}视角解读 XAUUSD。"
    )
    if supporting_items:
        thesis = f"{side_label}开场：{_committee_item_snippets(supporting_items, limit=1)[0]}。"
    if side == DebateSide.bull:
        entry_zone = (
            f"{max(quote.current_price - atr * 0.25, latest_bar.low):.2f}-"
            f"{quote.current_price + atr * 0.25:.2f}"
        )
        stop_loss_or_invalidation = f"跌破 {max(latest_bar.low, quote.current_price - atr):.2f}"
        target_zone = (
            f"{quote.current_price + atr * 1.5:.2f}-{quote.current_price + atr * 2.0:.2f}"
        )
    else:
        entry_zone = (
            f"{quote.current_price - atr * 0.25:.2f}-"
            f"{min(quote.current_price + atr * 0.25, latest_bar.high):.2f}"
        )
        stop_loss_or_invalidation = f"上破 {min(latest_bar.high, quote.current_price + atr):.2f}"
        target_zone = (
            f"{quote.current_price - atr * 2.0:.2f}-{quote.current_price - atr * 1.5:.2f}"
        )
    risk_reward = round(2.0, 2)
    confidence = _committee_average_confidence(supporting_items, default=0.45)
    if side == DebateSide.bull and quote.current_price >= latest_bar.close:
        confidence = min(confidence + 0.05, 0.82)
    if side == DebateSide.bear and quote.current_price <= latest_bar.close:
        confidence = min(confidence + 0.05, 0.82)
    weakness_acknowledged = _committee_item_snippets(opposing_items, limit=2) or [
        "仍需承认反方证据包中的风险提示。",
    ]
    supporting_arguments = _committee_item_snippets(supporting_items, limit=3)
    if not supporting_arguments:
        supporting_arguments = [evidence_package.summary or "证据包没有提供额外文字摘要。"]
    return DebateCase(
        side=side,
        thesis=thesis,
        evidence_item_refs=[
            item.item_id for item in supporting_items
        ]
        or [item.item_id for item in evidence_package.items[:2]],
        entry_zone=entry_zone,
        stop_loss_or_invalidation=stop_loss_or_invalidation,
        target_zone=target_zone,
        risk_reward=risk_reward,
        weakness_acknowledged=weakness_acknowledged,
        supporting_arguments=supporting_arguments,
        confidence=confidence,
        notes=[
            "只允许引用 evidence package 中的事实。",
            f"当前 ATR 参考值约 {atr:.2f}。",
        ],
    )


async def agent_bull_opening_case(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="agent_bull_opening_case")
    prompt_versions = await _record_committee_prompt_versions(state, "bull_opening_case")
    return {
        "prompt_versions": prompt_versions,
        "bull_opening_case": _build_opening_case(state, DebateSide.bull),
    }


async def agent_bear_opening_case(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="agent_bear_opening_case")
    prompt_versions = await _record_committee_prompt_versions(state, "bear_opening_case")
    return {
        "prompt_versions": prompt_versions,
        "bear_opening_case": _build_opening_case(state, DebateSide.bear),
    }


def _build_rebuttal(state: WorkflowState, side: DebateSide) -> DebateRebuttal:
    own_case = _required(state, "bull_opening_case" if side == DebateSide.bull else "bear_opening_case")
    opposing_case = _required(state, "bear_opening_case" if side == DebateSide.bull else "bull_opening_case")
    opposing_side = DebateSide.bear if side == DebateSide.bull else DebateSide.bull
    own_confidence = own_case.confidence or 0.45
    opposing_confidence = opposing_case.confidence or 0.45
    confidence_delta = round(max(min(own_confidence - opposing_confidence, 0.1), -0.12), 2)
    confidence_trend = "up" if confidence_delta > 0.03 else "down" if confidence_delta < -0.03 else "flat"
    rebutted_points = list(opposing_case.supporting_arguments[:2])
    if opposing_case.weakness_acknowledged:
        rebutted_points.extend(opposing_case.weakness_acknowledged[:1])
    if not rebutted_points:
        rebutted_points = [f"对方 {opposing_side.value} 论点与证据包并未形成足够一致的结构。"]
    accepted_points = list(opposing_case.weakness_acknowledged[:2])
    if not accepted_points:
        accepted_points = ["承认对方存在需要确认的风险边界。"]
    plan_adjustments = list(own_case.supporting_arguments[:2])
    if own_case.entry_zone not in plan_adjustments:
        plan_adjustments.append(f"将入场聚焦于 {own_case.entry_zone} 附近的确认信号。")
    return DebateRebuttal(
        side=side,
        responds_to_side=opposing_side,
        rebutted_points=rebutted_points,
        accepted_points=accepted_points,
        plan_adjustments=plan_adjustments,
        confidence_trend=confidence_trend,
        confidence_change=confidence_delta,
        evidence_item_refs=list(dict.fromkeys([*own_case.evidence_item_refs, *opposing_case.evidence_item_refs])),
        notes=[
            "必须逐点回应对方 opening case。",
            "不得新增 evidence package 之外的市场事实。",
        ],
    )


async def agent_bull_rebuttal(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="agent_bull_rebuttal")
    prompt_versions = await _record_committee_prompt_versions(state, "bull_rebuttal")
    return {
        "prompt_versions": prompt_versions,
        "bull_rebuttal": _build_rebuttal(state, DebateSide.bull),
    }


async def agent_bear_rebuttal(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="agent_bear_rebuttal")
    prompt_versions = await _record_committee_prompt_versions(state, "bear_rebuttal")
    return {
        "prompt_versions": prompt_versions,
        "bear_rebuttal": _build_rebuttal(state, DebateSide.bear),
    }


def _build_final_position(state: WorkflowState, side: DebateSide) -> FinalDebatePosition:
    opening_case = _required(state, "bull_opening_case" if side == DebateSide.bull else "bear_opening_case")
    rebuttal = _required(state, "bull_rebuttal" if side == DebateSide.bull else "bear_rebuttal")
    opposing_case = _required(state, "bear_opening_case" if side == DebateSide.bull else "bull_opening_case")
    base_confidence = opening_case.confidence or 0.45
    if rebuttal.confidence_change is not None:
        base_confidence = min(max(base_confidence + (rebuttal.confidence_change / 2), 0.0), 1.0)
    if len(opening_case.supporting_arguments) >= len(opposing_case.supporting_arguments):
        base_confidence = min(base_confidence + 0.03, 1.0)
    if len(rebuttal.accepted_points) > len(rebuttal.rebutted_points):
        base_confidence = max(base_confidence - 0.06, 0.0)

    if base_confidence >= 0.62:
        stance = DebateStance.maintain
    elif base_confidence >= 0.48:
        stance = DebateStance.soften
    else:
        stance = DebateStance.abandon

    adopted_arguments = list(opening_case.supporting_arguments[:2])
    adopted_arguments.extend(rebuttal.accepted_points[:1])
    rejected_arguments = list(rebuttal.rebutted_points[:2])
    if not rejected_arguments:
        rejected_arguments = [f"对方 {('bear' if side == DebateSide.bull else 'bull')} 论点尚未形成足够说服力。"]
    plan_adjustments = list(dict.fromkeys([*opening_case.notes, *rebuttal.plan_adjustments][:3]))
    abandon_conditions = list(dict.fromkeys([*opening_case.weakness_acknowledged, *rebuttal.rebutted_points][:3]))
    if not abandon_conditions:
        abandon_conditions = ["若证据包中的关键信号失效，则放弃该观点。"]
    return FinalDebatePosition(
        side=side,
        stance=stance,
        confidence=round(min(max(base_confidence, 0.0), 1.0), 2),
        confidence_change=round((base_confidence - (opening_case.confidence or 0.45)), 2),
        adopted_arguments=adopted_arguments,
        rejected_arguments=rejected_arguments,
        plan_adjustments=plan_adjustments,
        abandon_conditions=abandon_conditions,
        evidence_item_refs=list(dict.fromkeys([*opening_case.evidence_item_refs, *rebuttal.evidence_item_refs])),
        notes=[
            "最终立场必须说明是否仍坚持原方向。",
            "可从 trade_candidate 降级为 prepare_only / observe_only / no_trade。",
        ],
    )


async def agent_bull_final_position(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="agent_bull_final_position")
    prompt_versions = await _record_committee_prompt_versions(state, "bull_final_position")
    return {
        "prompt_versions": prompt_versions,
        "bull_final_position": _build_final_position(state, DebateSide.bull),
    }


async def agent_bear_final_position(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="agent_bear_final_position")
    prompt_versions = await _record_committee_prompt_versions(state, "bear_final_position")
    return {
        "prompt_versions": prompt_versions,
        "bear_final_position": _build_final_position(state, DebateSide.bear),
    }


def _build_long_plan(state: WorkflowState, side: DebateSide) -> LongPlan:
    opening_case = _required(state, "bull_opening_case" if side == DebateSide.bull else "bear_opening_case")
    latest_bar, quote, indicators, atr = _committee_price_context(state)
    if side == DebateSide.bull:
        entry_zone = opening_case.entry_zone
        stop_loss = opening_case.stop_loss_or_invalidation.replace("跌破 ", "")
        invalidation_level = f"{max(latest_bar.low, quote.current_price - atr):.2f}"
        target_zone = opening_case.target_zone
    else:
        entry_zone = opening_case.entry_zone
        stop_loss = opening_case.stop_loss_or_invalidation.replace("上破 ", "")
        invalidation_level = f"{min(latest_bar.high, quote.current_price + atr):.2f}"
        target_zone = opening_case.target_zone
    risk_reward = round(opening_case.risk_reward or 1.8, 2)
    if indicators.unavailable:
        risk_reward = round(max(risk_reward - 0.2, 1.0), 2)
    return LongPlan(
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        invalidation_level=invalidation_level,
        target_zone=target_zone,
        risk_reward=risk_reward,
        conditions_to_enter=[f"价格重新确认 {entry_zone} 区域。"],
        conditions_to_abort=[opening_case.stop_loss_or_invalidation],
        evidence_item_refs=list(opening_case.evidence_item_refs),
    )


def _build_short_plan(state: WorkflowState, side: DebateSide) -> ShortPlan:
    opening_case = _required(state, "bear_opening_case" if side == DebateSide.bear else "bull_opening_case")
    latest_bar, quote, indicators, atr = _committee_price_context(state)
    if side == DebateSide.bear:
        entry_zone = opening_case.entry_zone
        stop_loss = opening_case.stop_loss_or_invalidation.replace("上破 ", "")
        invalidation_level = f"{min(latest_bar.high, quote.current_price + atr):.2f}"
        target_zone = opening_case.target_zone
    else:
        entry_zone = opening_case.entry_zone
        stop_loss = opening_case.stop_loss_or_invalidation.replace("跌破 ", "")
        invalidation_level = f"{max(latest_bar.low, quote.current_price - atr):.2f}"
        target_zone = opening_case.target_zone
    risk_reward = round(opening_case.risk_reward or 1.8, 2)
    if indicators.unavailable:
        risk_reward = round(max(risk_reward - 0.2, 1.0), 2)
    return ShortPlan(
        entry_zone=entry_zone,
        stop_loss=stop_loss,
        invalidation_level=invalidation_level,
        target_zone=target_zone,
        risk_reward=risk_reward,
        conditions_to_enter=[f"价格重新确认 {entry_zone} 区域。"],
        conditions_to_abort=[opening_case.stop_loss_or_invalidation],
        evidence_item_refs=list(opening_case.evidence_item_refs),
    )


def _build_range_plan(state: WorkflowState) -> RangePlan:
    latest_bar, quote, indicators, atr = _committee_price_context(state)
    midpoint = (latest_bar.high + latest_bar.low) / 2
    upper_sell = f"{max(latest_bar.high - atr * 0.15, quote.current_price + atr * 0.25):.2f}-{latest_bar.high:.2f}"
    lower_buy = f"{latest_bar.low:.2f}-{min(latest_bar.low + atr * 0.15, quote.current_price - atr * 0.25):.2f}"
    risk_reward = round(1.3 if not indicators.unavailable else 1.1, 2)
    return RangePlan(
        upper_sell_zone=upper_sell,
        lower_buy_zone=lower_buy,
        upper_stop=f"{latest_bar.high + atr * 0.3:.2f}",
        lower_stop=f"{max(latest_bar.low - atr * 0.3, quote.current_price - atr * 1.5):.2f}",
        midline_target=f"{midpoint:.2f}",
        breakout_confirmation_level=f"{latest_bar.high + atr * 0.2:.2f}",
        breakdown_confirmation_level=f"{latest_bar.low - atr * 0.2:.2f}",
        range_invalidated_if=f"日线有效突破 {latest_bar.high + atr * 0.2:.2f} 或跌破 {latest_bar.low - atr * 0.2:.2f}",
        risk_reward=risk_reward,
        conditions_to_enter=["价格仍在明确区间内运行。"],
        conditions_to_abort=["区间突破或失效。"],
        evidence_item_refs=["technical", "risk"],
    )


def _build_committee_decision(state: WorkflowState) -> CommitteeDecision:
    evidence_package = _required(state, "evidence_package")
    bull_final = _required(state, "bull_final_position")
    bear_final = _required(state, "bear_final_position")
    bull_opening = _required(state, "bull_opening_case")
    bear_opening = _required(state, "bear_opening_case")
    latest_bar, quote, indicators, atr = _committee_price_context(state)

    bull_score = bull_final.confidence
    bear_score = bear_final.confidence
    score_gap = abs(bull_score - bear_score)
    many_degraded_items = sum(
        1 for item in evidence_package.items if item.tool_status != EvidenceToolStatus.ok
    )
    mixed_structure = score_gap < 0.06 or many_degraded_items >= 2

    if bull_score >= 0.62 and bull_score > bear_score + 0.06:
        final_bias = FinalBias.bullish
        winning_side: DebateSide | Literal["none"] | None = DebateSide.bull
        actionability = (
            Actionability.trade_candidate
            if bull_score >= 0.68 and not indicators.unavailable
            else Actionability.prepare_only
        )
        long_plan = _build_long_plan(state, DebateSide.bull)
        short_plan = None
        range_plan = None
        wait_conditions = []
        adopted_arguments = list(bull_final.adopted_arguments[:2])
        rejected_arguments = list(bear_final.rejected_arguments[:2]) or list(bear_final.abandon_conditions[:2])
    elif bear_score >= 0.62 and bear_score > bull_score + 0.06:
        final_bias = FinalBias.bearish
        winning_side = DebateSide.bear
        actionability = (
            Actionability.trade_candidate
            if bear_score >= 0.68 and not indicators.unavailable
            else Actionability.prepare_only
        )
        long_plan = None
        short_plan = _build_short_plan(state, DebateSide.bear)
        range_plan = None
        wait_conditions = []
        adopted_arguments = list(bear_final.adopted_arguments[:2])
        rejected_arguments = list(bull_final.rejected_arguments[:2]) or list(bull_final.abandon_conditions[:2])
    elif mixed_structure and bull_score >= 0.5 and bear_score >= 0.5:
        final_bias = FinalBias.range_bound
        winning_side = None
        actionability = Actionability.observe_only
        long_plan = None
        short_plan = None
        range_plan = _build_range_plan(state)
        wait_conditions = [
            "等待价格确认区间上沿或下沿。",
            "在突破/跌破确认前不追价。",
        ]
        adopted_arguments = list(dict.fromkeys([*bull_final.adopted_arguments[:1], *bear_final.adopted_arguments[:1]]))
        rejected_arguments = list(
            dict.fromkeys([*bull_final.rejected_arguments[:1], *bear_final.rejected_arguments[:1]])
        )
    else:
        final_bias = FinalBias.cautious
        winning_side = "none"
        actionability = Actionability.no_trade
        long_plan = None
        short_plan = None
        range_plan = None
        wait_conditions = [
            "等待更多高质量证据确认方向。",
            f"当前 ATR 约 {atr:.2f}，波动与信号仍需进一步确认。",
        ]
        adopted_arguments = []
        rejected_arguments = list(
            dict.fromkeys([*bull_final.rejected_arguments[:1], *bear_final.rejected_arguments[:1]])
        )

    confidence_score = round(
        min(
            max(
                (bull_score + bear_score) / 2
                + (0.04 if final_bias in {FinalBias.bullish, FinalBias.bearish} else 0.0),
                0.0,
            ),
            1.0,
        ),
        2,
    )
    decision_summary = (
        f"主席裁定为 {final_bias.value}，"
        f"更强的一方是 {'bull' if bull_score >= bear_score else 'bear'}，"
        f"当前 actionability={actionability.value}。"
    )
    risk_notes = list(dict.fromkeys([
        *evidence_package.notes[:2],
        *bull_final.notes[:1],
        *bear_final.notes[:1],
    ]))
    if indicators.unavailable:
        risk_notes.append("技术指标存在缺失，委员会对 confidence 采取保守折扣。")

    return CommitteeDecision(
        evidence_package=evidence_package,
        bull_opening_case=bull_opening,
        bear_opening_case=bear_opening,
        bull_rebuttal=_required(state, "bull_rebuttal"),
        bear_rebuttal=_required(state, "bear_rebuttal"),
        bull_final_position=bull_final,
        bear_final_position=bear_final,
        final_bias=final_bias,
        actionability=actionability,
        winning_side=winning_side,
        adopted_arguments=adopted_arguments,
        rejected_arguments=rejected_arguments,
        long_plan=long_plan,
        short_plan=short_plan,
        range_plan=range_plan,
        wait_conditions=wait_conditions,
        confidence_score=confidence_score,
        decision_summary=decision_summary,
        risk_notes=risk_notes,
        evidence_item_refs=[item.item_id for item in evidence_package.items],
    )


async def agent_trading_committee_chair(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="agent_trading_committee_chair")
    prompt_versions = await _record_committee_prompt_versions(state, "chair")
    return {
        "prompt_versions": prompt_versions,
        "committee_decision": _build_committee_decision(state),
    }


def _extract_first_float(text: str | None) -> float | None:
    if text is None:
        return None
    match = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if match is None:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _validate_plan_price_logic(committee_decision: CommitteeDecision) -> list[str]:
    errors: list[str] = []
    if committee_decision.final_bias == FinalBias.bullish and committee_decision.long_plan is not None:
        entry = _extract_first_float(committee_decision.long_plan.entry_zone)
        target = _extract_first_float(committee_decision.long_plan.target_zone)
        stop = _extract_first_float(
            committee_decision.long_plan.stop_loss or committee_decision.long_plan.invalidation_level
        )
        if entry is not None and target is not None and target <= entry:
            errors.append("bullish long_plan target_zone must be above entry_zone")
        if entry is not None and stop is not None and stop >= entry:
            errors.append("bullish long_plan stop_loss must be below entry_zone")
    if committee_decision.final_bias == FinalBias.bearish and committee_decision.short_plan is not None:
        entry = _extract_first_float(committee_decision.short_plan.entry_zone)
        target = _extract_first_float(committee_decision.short_plan.target_zone)
        stop = _extract_first_float(
            committee_decision.short_plan.stop_loss or committee_decision.short_plan.invalidation_level
        )
        if entry is not None and target is not None and target >= entry:
            errors.append("bearish short_plan target_zone must be below entry_zone")
        if entry is not None and stop is not None and stop <= entry:
            errors.append("bearish short_plan stop_loss must be above entry_zone")
    if committee_decision.final_bias == FinalBias.range_bound and committee_decision.range_plan is not None:
        upper_sell = _extract_first_float(committee_decision.range_plan.upper_sell_zone)
        lower_buy = _extract_first_float(committee_decision.range_plan.lower_buy_zone)
        if upper_sell is not None and lower_buy is not None and upper_sell <= lower_buy:
            errors.append("range_plan upper_sell_zone must be above lower_buy_zone")
    return errors


def _build_committee_validation_result(state: WorkflowState) -> DecisionValidationResult:
    committee_decision = _required(state, "committee_decision")
    evidence_package = _required(state, "evidence_package")
    validation_rules = [
        "final_bias_present",
        "actionability_present",
        "confidence_in_range",
        "bias_specific_plan_present",
        "trade_candidate_confidence_threshold",
        "degraded_source_confidence_guard",
        "plan_price_logic",
        "risk_reward_guard",
    ]
    errors: list[str] = []
    warnings: list[str] = []

    if not 0.0 <= committee_decision.confidence_score <= 1.0:
        errors.append("confidence must be between 0 and 1")
    if committee_decision.final_bias == FinalBias.bullish and committee_decision.long_plan is None:
        errors.append("bullish decisions require long_plan")
    if committee_decision.final_bias == FinalBias.bearish and committee_decision.short_plan is None:
        errors.append("bearish decisions require short_plan")
    if committee_decision.final_bias == FinalBias.range_bound and committee_decision.range_plan is None:
        errors.append("range_bound decisions require range_plan")
    if committee_decision.final_bias == FinalBias.cautious and not committee_decision.wait_conditions:
        errors.append("cautious decisions require wait_conditions")
    if committee_decision.actionability == Actionability.trade_candidate and committee_decision.confidence_score < 0.55:
        errors.append("trade_candidate confidence should be at least 0.55")

    degraded_items = [item for item in evidence_package.items if item.tool_status != EvidenceToolStatus.ok]
    if degraded_items and committee_decision.confidence_score > 0.8:
        errors.append("evidence package contains degraded sources, confidence should stay conservative")

    errors.extend(_validate_plan_price_logic(committee_decision))

    if committee_decision.actionability == Actionability.trade_candidate:
        plans = [
            plan
            for plan in [committee_decision.long_plan, committee_decision.short_plan, committee_decision.range_plan]
            if plan is not None
        ]
        risk_rewards = [plan.risk_reward for plan in plans if plan.risk_reward is not None]
        if risk_rewards and min(risk_rewards) < 1.5:
            errors.append("risk_reward too low for trade_candidate actionability")

    is_valid = not errors
    return DecisionValidationResult(
        is_valid=is_valid,
        checked_at=datetime.now(UTC),
        summary="；".join(errors) if errors else "委员会输出通过规则校验。",
        errors=errors,
        warnings=warnings,
        validation_rules=validation_rules,
    )


def node_validate_committee_decision(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="node_validate_committee_decision")
    validation_attempts = int(state.get("committee_validation_attempts") or 0) + 1
    validation_status = _build_committee_validation_result(
        {**state, "committee_validation_attempts": validation_attempts}
    )
    return {
        "committee_validation_attempts": validation_attempts,
        "validation_status": validation_status,
        "validation_errors": list(validation_status.errors),
        "validation_warnings": list(validation_status.warnings),
        "errors": list(validation_status.errors),
    }


def _build_repair_decision(state: WorkflowState) -> CommitteeDecision:
    committee_decision = _required(state, "committee_decision")
    validation_errors = list(state.get("validation_errors") or [])
    if not validation_errors:
        return committee_decision

    updated_actionability = committee_decision.actionability
    if committee_decision.final_bias == FinalBias.cautious:
        updated_actionability = Actionability.no_trade
    elif committee_decision.actionability == Actionability.trade_candidate:
        updated_actionability = Actionability.prepare_only

    updated_confidence = round(max(committee_decision.confidence_score - 0.06, 0.0), 2)
    updated_risk_notes = list(dict.fromkeys([*committee_decision.risk_notes, *validation_errors]))
    return committee_decision.model_copy(
        update={
            "actionability": updated_actionability,
            "confidence_score": updated_confidence,
            "risk_notes": updated_risk_notes,
            "decision_summary": f"{committee_decision.decision_summary} 已根据验证错误进行保守修复。",
            "wait_conditions": committee_decision.wait_conditions
            or ["修复后仍需重新确认最终决策是否满足规则。"],
        }
    )


async def agent_repair_committee_decision(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="agent_repair_committee_decision")
    prompt_versions = await _record_committee_prompt_versions(state, "repair")
    repair_attempts = int(state.get("committee_repair_attempts") or 0) + 1
    return {
        "prompt_versions": prompt_versions,
        "committee_repair_attempts": repair_attempts,
        "committee_decision": _build_repair_decision(state),
    }


def _build_final_forecast_from_committee_decision(state: WorkflowState) -> FinalForecast:
    committee_decision = _required(state, "committee_decision")
    latest_bar = _required(state, "latest_bar")
    quote = _required(state, "quote")
    indicators = _required(state, "indicators")
    base_forecast = create_research_forecast_from_inputs(
        latest_bar=latest_bar,
        quote=quote,
        indicators=indicators,
    )

    if committee_decision.final_bias == FinalBias.bullish:
        direction = ForecastDirection.bullish
    elif committee_decision.final_bias == FinalBias.bearish:
        direction = ForecastDirection.bearish
    else:
        direction = ForecastDirection.neutral

    if direction != base_forecast.direction:
        atr = _usable_atr(indicators, latest_bar, quote.current_price)
        entry_price, take_profit_price, stop_loss_price = _research_levels(quote.current_price, atr, direction)
        entry_price_low = None
        entry_price_high = None
        if direction == ForecastDirection.neutral:
            entry_price_low, entry_price_high = _neutral_entry_range(quote.current_price, atr, latest_bar)
            entry_price = round((entry_price_low + entry_price_high) / 2, 2)
        base_forecast.direction = direction
        base_forecast.entry_price = entry_price
        base_forecast.entry_price_low = entry_price_low
        base_forecast.entry_price_high = entry_price_high
        base_forecast.take_profit_price = take_profit_price
        base_forecast.stop_loss_price = stop_loss_price
        base_forecast.holding_period = _holding_period(direction, atr, quote.current_price)
        base_forecast.intraday_action = _intraday_action(
            direction,
            entry_price,
            take_profit_price,
            stop_loss_price,
            entry_price_low,
            entry_price_high,
        )
        base_forecast.long_term_action = _long_term_action(direction)

    return FinalForecast(
        **base_forecast.model_dump(),
        final_bias=committee_decision.final_bias,
        actionability=committee_decision.actionability,
        evidence_package=committee_decision.evidence_package,
        committee_decision=committee_decision,
        validation_status=state.get("validation_status"),
        prompt_versions=list(state.get("prompt_versions") or []),
    )


async def node_persist_forecast(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="node_persist_forecast")
    repository = state.get("repository")
    if repository is None:
        return {"persistence_status": "skipped: repository not provided"}

    validation_status = state.get("validation_status")
    validation_attempts = int(state.get("committee_validation_attempts") or 0)
    if validation_status is not None and not validation_status.is_valid and validation_attempts >= 3:
        run_id = state.get("run_id")
        if run_id is None:
            run = await repository.create_research_run(_input_summary(state))
            run_id = run.id
        if run_id is None:
            raise ValueError("workflow state missing research run id for failed persistence")
        await repository.mark_run_failed(
            run_id,
            validation_status.summary or "committee decision failed validation",
        )
        return {
            "run_id": run_id,
            "persistence_status": "forecast_failed_validation",
        }

    forecast = state.get("final_forecast") or state.get("forecast")
    if forecast is None:
        if state.get("committee_decision") is not None:
            forecast = _build_final_forecast_from_committee_decision(state)
        else:
            latest_bar = _required(state, "latest_bar")
            quote = _required(state, "quote")
            indicators = _required(state, "indicators")
            forecast = create_research_forecast_from_inputs(
                latest_bar=latest_bar,
                quote=quote,
                indicators=indicators,
            )

    run_id = state.get("run_id")
    if run_id is None:
        run = await repository.create_research_run(_input_summary(state))
        run_id = run.id
    if run_id is None:
        raise ValueError("workflow state missing research run id for forecast persistence")

    saved_forecast = await repository.save_forecast(run_id, forecast)
    await repository.mark_run_success(run_id)
    final_forecast = forecast if isinstance(forecast, FinalForecast) else state.get("final_forecast")
    return {
        "run_id": run_id,
        "forecast": saved_forecast,
        "final_forecast": final_forecast,
        "persistence_status": "forecast_saved",
    }


def agent_forecast_planning(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(
        state,
        current_stage="agent_forecast_planning",
        active_agent="forecast",
    )
    latest_bar = _required(state, "latest_bar")
    quote = _required(state, "quote")
    indicators = _required(state, "indicators")
    forecast = create_research_forecast_from_inputs(
        latest_bar=latest_bar,
        quote=quote,
        indicators=indicators,
    )

    agent_votes = state.get("agent_votes")
    if agent_votes:
        direction, confidence_score = _aggregate_agent_votes(agent_votes)
        atr = _usable_atr(indicators, latest_bar, quote.current_price)
        entry_price, take_profit_price, stop_loss_price = _research_levels(quote.current_price, atr, direction)
        entry_price_low = None
        entry_price_high = None
        if direction == ForecastDirection.neutral:
            entry_price_low, entry_price_high = _neutral_entry_range(quote.current_price, atr, latest_bar)
            entry_price = round((entry_price_low + entry_price_high) / 2, 2)
        forecast.direction = direction
        forecast.confidence_score = confidence_score
        forecast.entry_price = entry_price
        forecast.entry_price_low = entry_price_low
        forecast.entry_price_high = entry_price_high
        forecast.take_profit_price = take_profit_price
        forecast.stop_loss_price = stop_loss_price
        forecast.holding_period = _holding_period(direction, atr, quote.current_price)
        forecast.intraday_action = _intraday_action(
            direction,
            entry_price,
            take_profit_price,
            stop_loss_price,
            entry_price_low,
            entry_price_high,
        )
        forecast.long_term_action = _long_term_action(direction)
        forecast.agent_votes = agent_votes
    if "technical_summary" in state:
        forecast.technical_summary = state["technical_summary"]
    if "macro_summary" in state:
        forecast.macro_summary = state["macro_summary"]
    if "news_summary" in state:
        forecast.news_summary = state["news_summary"]
    if "market_sentiment_summary" in state:
        forecast.market_sentiment_summary = state["market_sentiment_summary"]
    if "alt_data_summary" in state:
        forecast.alt_data_summary = state["alt_data_summary"]
    if "risk_summary" in state:
        forecast.risk_summary = state["risk_summary"]
    if "risk_notes" in state:
        forecast.risk_notes = _merge_notes(forecast.risk_notes, state["risk_notes"])
    feedback_history = state.get("forecast_feedback_history")
    if feedback_history:
        feedback_note = "最近评估反馈：" + " | ".join(feedback_history[:3])
        forecast.risk_notes = _append_note(forecast.risk_notes, feedback_note)
        forecast.risk_summary = f"{forecast.risk_summary} {feedback_note}"
    if state.get("unavailable_signals"):
        unavailable_items = _unique_strings([str(item) for item in state["unavailable_signals"]])
        unavailable_note = "不可用信号：" + "、".join(unavailable_items)
        forecast.risk_notes = _append_note(forecast.risk_notes, unavailable_note)
        forecast.risk_summary = f"{forecast.risk_summary} {unavailable_note}"
    forecast.window_directions = _forecast_window_directions(forecast.direction, forecast.confidence_score)

    return {"forecast": forecast}


async def tool_persist_research_run(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="tool_persist_research_run")
    repository = state.get("repository")
    if repository is None:
        return {"persistence_status": "skipped: repository not provided"}
    if "run_id" in state:
        return {}

    run = await repository.create_research_run(_input_summary(state))
    return {"run_id": run.id, "persistence_status": "research_run_created"}


async def tool_persist_forecast(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="tool_persist_forecast")
    repository = state.get("repository")
    if repository is None:
        return {"persistence_status": "skipped: repository not provided"}

    forecast = state.get("forecast")
    if forecast is None:
        raise ValueError("workflow state missing forecast for persistence")

    run_id = state.get("run_id")
    if run_id is None:
        persisted = await tool_persist_research_run(state)
        run_id = persisted.get("run_id") or state.get("run_id")
    if run_id is None:
        raise ValueError("workflow state missing research run id for forecast persistence")

    saved_forecast = await repository.save_forecast(run_id, forecast)
    await repository.mark_run_success(run_id)
    return {"forecast": saved_forecast, "persistence_status": "forecast_saved"}


def router_finalize_result(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="router_finalize_result")
    forecast = state.get("forecast")
    if forecast is None:
        raise ValueError("workflow state missing forecast result")
    return {"result": forecast}


def _direction_from_inputs(
    price: float,
    latest_bar: DailyBar,
    indicators: TechnicalIndicators,
) -> ForecastDirection:
    bullish_score = 0
    bearish_score = 0

    trend_reference = indicators.sma_20 or indicators.ema_12 or latest_bar.close
    if price > trend_reference:
        bullish_score += 1
    elif price < trend_reference:
        bearish_score += 1

    if price > latest_bar.close:
        bullish_score += 1
    elif price < latest_bar.close:
        bearish_score += 1

    if indicators.rsi_14 is not None:
        if indicators.rsi_14 >= 70:
            bearish_score += 1
        elif indicators.rsi_14 <= 30:
            bullish_score += 1
        elif indicators.rsi_14 >= 55:
            bullish_score += 1
        elif indicators.rsi_14 <= 45:
            bearish_score += 1

    if bullish_score > bearish_score:
        return ForecastDirection.bullish
    if bearish_score > bullish_score:
        return ForecastDirection.bearish
    return ForecastDirection.neutral


def _research_levels(price: float, atr: float, direction: ForecastDirection) -> tuple[float, float, float]:
    entry = round(price, 2)
    if direction == ForecastDirection.bearish:
        take_profit = max(price - (atr * 2), price * 0.5)
        stop_loss = price + atr
    elif direction == ForecastDirection.bullish:
        take_profit = price + (atr * 2)
        stop_loss = max(price - atr, price * 0.5)
    else:
        take_profit = price + atr
        stop_loss = max(price - atr, price * 0.5)
    return entry, round(take_profit, 2), round(stop_loss, 2)


def _neutral_entry_range(price: float, atr: float, latest_bar: DailyBar) -> tuple[float, float]:
    half_band = max(atr * 0.45, price * 0.003)
    lower = max(latest_bar.low, price - half_band)
    upper = min(latest_bar.high, price + half_band)
    if lower >= upper:
        lower = max(price - half_band, price * 0.5)
        upper = price + half_band
    return round(lower, 2), round(upper, 2)


def _usable_atr(indicators: TechnicalIndicators, latest_bar: DailyBar, price: float) -> float:
    if indicators.atr_14 is not None and indicators.atr_14 > 0:
        return indicators.atr_14
    return max(latest_bar.high - latest_bar.low, price * 0.005, 1.0)


def _technical_summary(
    price: float,
    latest_bar: DailyBar,
    indicators: TechnicalIndicators,
    direction: ForecastDirection,
    atr: float,
) -> str:
    direction_text = {
        ForecastDirection.bullish: "看多",
        ForecastDirection.bearish: "看空",
        ForecastDirection.neutral: "震荡/中性",
    }[direction]
    parts = [
        f"当前报价 {price:.2f}，最新完成日线收盘 {latest_bar.close:.2f}，结构化方向为{direction_text}。",
    ]
    if indicators.sma_20 is not None:
        parts.append(f"SMA-20 为 {indicators.sma_20:.2f}。")
    if indicators.ema_12 is not None:
        parts.append(f"EMA-12 为 {indicators.ema_12:.2f}。")
    if indicators.rsi_14 is not None:
        parts.append(f"RSI-14 为 {indicators.rsi_14:.2f}。")
    near_high = latest_bar.high - price
    near_low = price - latest_bar.low
    reversal_threshold = max(atr * 0.35, price * 0.002)
    if 0 <= near_high <= reversal_threshold:
        parts.append("价格接近日内上沿，若继续上探，容易进入短线止盈区并伴随反转或回落。")
    elif 0 <= near_low <= reversal_threshold:
        parts.append("价格接近日内下沿，若继续下探，容易进入短线止损区并伴随反抽或反转。")
    if indicators.unavailable:
        parts.append(f"部分指标不可用：{', '.join(sorted(indicators.unavailable))}。")
    return "".join(parts)


def _smart_money_summary(
    price: float,
    latest_bar: DailyBar,
    indicators: TechnicalIndicators,
    direction: ForecastDirection,
    atr: float,
) -> str:
    upper_buffer = max(atr * 0.25, price * 0.0015)
    lower_buffer = upper_buffer
    near_high = latest_bar.high - price
    near_low = price - latest_bar.low
    parts = ["聪明钱逻辑关注区间边缘的流动性扫单与反向止损触发。"]
    if 0 <= near_high <= upper_buffer:
        parts.append("价格接近日内上沿，若继续冲高，容易先扫掉上方止盈，再观察是否出现回落或假突破。")
    elif 0 <= near_low <= lower_buffer:
        parts.append("价格接近日内下沿，若继续下探，容易先扫掉下方止损，再观察是否出现反抽或假跌破。")
    else:
        parts.append("当前价格位于区间中段，更像是在等待上沿或下沿的流动性被测试。")

    if direction == ForecastDirection.neutral:
        parts.append(
            f"震荡阶段更适合观察 {latest_bar.low:.2f} 到 {latest_bar.high:.2f} 的价格带，"
            "高位偏空、低位偏多的区间思路优先于单点追价。"
        )
    elif direction == ForecastDirection.bullish:
        parts.append("若突破前高并放量，则聪明钱更可能在回踩确认后继续推升。")
    else:
        parts.append("若跌破前低并放量，则聪明钱更可能在反抽确认后继续压低。")

    if indicators.unavailable:
        parts.append(f"该逻辑同时参考了未失效的指标，缺失项有：{', '.join(sorted(indicators.unavailable))}。")
    return "".join(parts)


def _risk_notes(latest_bar: DailyBar, indicators: TechnicalIndicators, atr: float) -> list[str]:
    notes = [
        f"风险分析以 ATR 参考值约 {atr:.2f}、最新日线振幅和 RSI 状态为主，最新K线仅用于判断波动边界，不作为复盘结论。"
    ]
    daily_range = latest_bar.high - latest_bar.low
    if daily_range > atr * 1.5:
        notes.append("最新日线振幅明显高于 ATR 参考，需警惕波动放大。")
    if indicators.rsi_14 is not None and indicators.rsi_14 >= 70:
        notes.append("RSI 处于偏高区域，追多研究假设需要额外确认。")
    if indicators.rsi_14 is not None and indicators.rsi_14 <= 30:
        notes.append("RSI 处于偏低区域，追空研究假设需要额外确认。")
    if indicators.unavailable:
        notes.append("部分技术指标不可用，confidence 已按信息不足做保守处理。")
    return notes


def _technical_confidence(indicators: TechnicalIndicators, direction: ForecastDirection) -> float:
    available = 4 - len(indicators.unavailable)
    base = 0.45 + (available * 0.07)
    if direction == ForecastDirection.neutral:
        base -= 0.08
    return round(min(max(base, 0.25), 0.78), 2)


def _combined_confidence(agent_votes: list[AgentVote], indicators: TechnicalIndicators) -> float:
    if not agent_votes:
        return 0.35
    average = sum(vote.confidence for vote in agent_votes) / len(agent_votes)
    if indicators.unavailable:
        average -= 0.05
    return round(min(max(average, 0.2), 0.85), 2)


def _aggregate_agent_votes(agent_votes: list[AgentVote]) -> tuple[ForecastDirection, float]:
    if not agent_votes:
        return ForecastDirection.neutral, 0.35

    weighted_scores = {direction: 0.0 for direction in ForecastDirection}
    for vote in agent_votes:
        weighted_scores[vote.direction] += vote.confidence

    # 使用 confidence 加权得分决定方向；confidence_score 保留所有 agent 的平均置信度，避免单一高置信票吞掉分歧。
    direction = max(
        ForecastDirection,
        key=lambda candidate: (weighted_scores[candidate], candidate == ForecastDirection.neutral),
    )
    confidence_score = sum(vote.confidence for vote in agent_votes) / len(agent_votes)
    return direction, round(min(max(confidence_score, 0.2), 0.85), 2)


def _risk_vote_direction(direction: ForecastDirection, atr: float, price: float) -> ForecastDirection:
    if atr / price > 0.02:
        return ForecastDirection.neutral
    return direction


def _holding_period(direction: ForecastDirection, atr: float, price: float) -> str:
    if direction == ForecastDirection.neutral or atr / price > 0.015:
        return "1-3 个交易日，等待方向确认"
    return "3-7 个交易日，随每日收盘重新评估"


def _intraday_action(
    direction: ForecastDirection,
    entry_price: float,
    take_profit_price: float,
    stop_loss_price: float,
    entry_price_low: float | None = None,
    entry_price_high: float | None = None,
) -> str:
    if direction == ForecastDirection.bullish:
        return (
            f"研究情景偏多：关注 {entry_price:.2f} 附近的回踩确认，"
            f"止盈参考 {take_profit_price:.2f}，止损参考 {stop_loss_price:.2f}。"
        )
    if direction == ForecastDirection.bearish:
        return (
            f"研究情景偏空：关注 {entry_price:.2f} 附近的反弹承压，"
            f"止盈参考 {take_profit_price:.2f}，止损参考 {stop_loss_price:.2f}。"
        )
    if entry_price_low is not None and entry_price_high is not None:
        return (
            f"研究情景中性：关注 {entry_price_low:.2f}-{entry_price_high:.2f} 的震荡区间，"
            "高位更适合观察反弹后的做空机会，低位更适合观察回踩后的做多机会。"
        )
    return f"研究情景中性：关注 {entry_price:.2f} 附近区间反应，等待突破或跌破后再更新假设。"


def _long_term_action(direction: ForecastDirection) -> str:
    if direction == ForecastDirection.bullish:
        return "中期研究倾向保持多头观察，但需用后续日线收盘和宏观数据确认。"
    if direction == ForecastDirection.bearish:
        return "中期研究倾向保持防守或空头观察，但需用后续日线收盘和宏观数据确认。"
    return "中期研究维持观望，等待趋势指标和外部数据给出更清晰方向。"


def _existing_votes_without(state: WorkflowState, agent_name: str) -> list[AgentVote]:
    return [vote for vote in state.get("agent_votes", []) if vote.agent != agent_name]


def _remote_agent_response(
    state: WorkflowState,
    agent_name: str,
    stage: str,
) -> tuple[AgentApiResponse | None, str | None, dict[str, Any] | None]:
    settings = state.get("settings") or get_settings()
    if not settings.openai_base_url or not settings.openai_model or not settings.openai_api_key:
        message = (
            f"OpenAI-compatible {agent_name} agent 未配置有效 base_url/model/API Key，"
            "已标记为失败，不生成兜底输出。"
        )
        detail = _settings_snapshot_for_agent(settings)
        logger.warning("%s detail=%s", message, detail)
        return (
            None,
            message,
            _agent_diagnostic_record(
                agent=agent_name,
                stage=stage,
                status="unconfigured",
                message=message,
                detail=detail,
            ),
        )

    # 只发送可验证的市场/指标上下文，不把 secret 或 settings 放进 payload。
    payload = _agent_payload(state, agent_name)
    transport = state.get("agent_http_transport")
    try:
        result = OpenAIAgentClient(
            base_url=settings.openai_base_url,
            model=settings.openai_model,
            api_key=settings.openai_api_key.get_secret_value(),
            transport=transport,
        ).invoke_agent(agent_name, payload)
    except OpenAIClientError as exc:
        detail = str(exc).strip() or "agent call failed"
        message = f"OpenAI-compatible {agent_name} agent 调用失败，已标记为失败，不生成兜底输出。"
        logger.warning("%s detail=%s", message, detail)
        return (
            None,
            message,
            _agent_diagnostic_record(
                agent=agent_name,
                stage=stage,
                status="failed",
                message=message,
                detail=detail,
            ),
        )

    validated = AgentApiResponse.model_validate(result.model_dump())
    cleaned_summary = validated.summary.strip()
    if not cleaned_summary:
        detail = "blank summary"
        message = f"OpenAI-compatible {agent_name} agent 返回空摘要，已标记为失败，不生成兜底输出。"
        logger.warning("%s detail=%s", message, detail)
        return (
            None,
            message,
            _agent_diagnostic_record(
                agent=agent_name,
                stage=stage,
                status="invalid_response",
                message=message,
                detail=detail,
            ),
        )

    return validated.model_copy(update={"summary": cleaned_summary}), None, None


def _settings_snapshot_for_agent(settings: GoldFXGraphSettings) -> str:
    base_url = settings.openai_base_url or "unset"
    model = settings.openai_model or "unset"
    api_key = "set" if settings.openai_api_key is not None else "unset"
    return f"base_url={base_url}; model={model}; api_key={api_key}"


def _agent_diagnostic_record(
    *,
    agent: str,
    stage: str,
    status: str,
    message: str,
    detail: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "agent": agent,
        "stage": stage,
        "status": status,
        "message": message,
    }
    if detail:
        record["detail"] = detail
    return record


def _append_agent_diagnostic(
    state: WorkflowState,
    diagnostic: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    diagnostics = list(state.get("agent_diagnostics") or [])
    if diagnostic is not None:
        diagnostics.append(diagnostic)
    return diagnostics


def _append_summary_section(summary: str, title: str, body: str | None) -> str:
    cleaned_body = (body or "").strip()
    if not cleaned_body or title in summary:
        return summary
    if not summary.strip():
        return f"{title}：{cleaned_body}"
    separator = "" if summary.endswith("\n") else "\n"
    return f"{summary}{separator}{title}：{cleaned_body}"


def _failure_summary(agent_name: str, detail: str | None) -> str:
    cleaned_detail = (detail or "").strip()
    if cleaned_detail:
        return f"失败：{agent_name} agent 未能产出有效结果。{cleaned_detail}"
    return f"失败：{agent_name} agent 未能产出有效结果。"


def _normalize_news_summary_representative_titles(summary: str, reference_summary: str) -> str:
    summary_lines = summary.splitlines()
    reference_lines = reference_summary.splitlines()
    summary_marker_index = next(
        (index for index, line in enumerate(summary_lines) if line.strip() == "代表性标题："),
        -1,
    )
    reference_marker_index = next(
        (index for index, line in enumerate(reference_lines) if line.strip() == "代表性标题："),
        -1,
    )
    if summary_marker_index < 0 or reference_marker_index < 0:
        return summary

    prefix = summary_lines[: summary_marker_index + 1]
    reference_block = reference_lines[reference_marker_index + 1 :]
    if not reference_block:
        return summary

    return "\n".join([*prefix, *reference_block])


def _merge_notes(base_notes: list[str] | None, extra_notes: list[str] | None) -> list[str]:
    merged: list[str] = []
    for note in [*(base_notes or []), *(extra_notes or [])]:
        if note not in merged:
            merged.append(note)
    return merged


def _append_note(notes: list[str] | None, note: str | None) -> list[str]:
    if note is None:
        return list(notes or [])
    return _merge_notes(notes, [note])


def _direction_label_cn(value: str) -> str:
    return {
        ForecastDirection.bullish.value: "看多",
        ForecastDirection.bearish.value: "看空",
        ForecastDirection.neutral.value: "中性",
    }.get(value, value)


def _unique_strings(values: list[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return unique


def _agent_payload(state: WorkflowState, agent_name: str) -> dict[str, object]:
    latest_bar = state.get("latest_bar")
    quote = state.get("quote")
    indicators = state.get("indicators")
    payload: dict[str, object] = {"agent": agent_name, "symbol": "XAUUSD"}
    if latest_bar:
        payload["latest_bar"] = latest_bar.model_dump(mode="json")
        payload["symbol"] = latest_bar.symbol
    if quote:
        payload["quote"] = quote.model_dump(mode="json")
        payload["symbol"] = quote.symbol
    if indicators:
        payload["indicators"] = indicators.model_dump(mode="json")
    if agent_name == "market_sentiment":
        payload["market_sentiment_inputs"] = state.get("market_sentiment_inputs", {})
        payload["forecast_feedback_history"] = state.get("forecast_feedback_history", [])
    if agent_name == "alt_data":
        payload["alt_data_inputs"] = state.get("alt_data_inputs", {})
        payload["unavailable_signals"] = state.get("unavailable_signals", [])
    if agent_name == "news":
        newsflow_inputs = state.get("newsflow_inputs", {})
        top_headlines = []
        for item in list(newsflow_inputs.get("top_headlines") or []):
            if not isinstance(item, dict):
                continue
            top_headlines.append(
                {
                    "source_cn": item.get("source_cn"),
                    "title_cn": item.get("title_cn"),
                    "link": item.get("link"),
                    "published_at": item.get("published_at"),
                }
            )
        payload["newsflow_inputs"] = {
            "status": newsflow_inputs.get("status"),
            "summary": newsflow_inputs.get("summary"),
            "headline_count": newsflow_inputs.get("headline_count"),
            "source_count": newsflow_inputs.get("source_count"),
            "sentiment": newsflow_inputs.get("sentiment"),
            "sentiment_score": newsflow_inputs.get("sentiment_score"),
            "topics": newsflow_inputs.get("topics"),
            "top_headlines": top_headlines,
        }
    if agent_name == "macro":
        payload["macro_inputs"] = state.get("macro_inputs", {})
    if agent_name == "market_sentiment":
        payload["polymarket_inputs"] = state.get("polymarket_inputs", {})
    return payload


def _macro_summary(inputs: dict[str, object]) -> str:
    current_price = inputs.get("current_price")
    latest_close = inputs.get("latest_close")
    sma_20 = inputs.get("sma_20")
    ema_12 = inputs.get("ema_12")
    dollar_index = inputs.get("dollar_index") or {}
    real_rates = inputs.get("real_rates") or {}
    unavailable = inputs.get("unavailable_signals") or []
    available = inputs.get("available_signals") or []

    parts = ["宏观面围绕美元指数与实际利率解读，并与价格结构一同作为研究背景。"]
    if isinstance(current_price, (int, float)) and isinstance(latest_close, (int, float)):
        parts.append(f"当前报价 {float(current_price):.2f}，最新完成日线收盘 {float(latest_close):.2f}。")
    if isinstance(sma_20, (int, float)):
        parts.append(f"SMA-20 为 {float(sma_20):.2f}。")
    if isinstance(ema_12, (int, float)):
        parts.append(f"EMA-12 为 {float(ema_12):.2f}。")

    if isinstance(dollar_index, dict) and dollar_index.get("status") == "available":
        value = dollar_index.get("value")
        change = dollar_index.get("change")
        value_text = f"{float(value):.2f}" if isinstance(value, (int, float)) else "未知"
        change_text = f"{float(change):+.2f}" if isinstance(change, (int, float)) else "未知"
        parts.append(f"美元指数 {value_text}，日内变化 {change_text}。")
    else:
        parts.append("美元指数暂不可用。")

    if isinstance(real_rates, dict) and real_rates.get("status") == "available":
        value = real_rates.get("value")
        change = real_rates.get("change")
        value_text = f"{float(value):.2f}%" if isinstance(value, (int, float)) else "未知"
        change_text = f"{float(change):+.2f}" if isinstance(change, (int, float)) else "未知"
        parts.append(f"实际利率 {value_text}，变化 {change_text} 个百分点。")
    else:
        parts.append("实际利率暂不可用。")

    if available:
        parts.append(f"当前可用宏观信号 {len(available)} 项。")
    if unavailable:
        parts.append(f"仍有 {len(unavailable)} 项宏观相关信号暂不可用。")

    return "".join(parts)


def _market_sentiment_summary(inputs: dict[str, object]) -> str:
    trend_bias = str(inputs.get("trend_bias") or "neutral")
    rsi = inputs.get("rsi_14")
    feedback_count = int(inputs.get("feedback_signal_count") or 0)
    feedback_text = "近期反馈较少" if feedback_count == 0 else f"参考了 {feedback_count} 条历史评估反馈"
    unavailable = inputs.get("unavailable_signals") or []
    unavailable_text = f"，其中 {len(unavailable)} 类外部情绪源仍不可用" if unavailable else ""
    rsi_text = f"RSI 参考值 {float(rsi):.2f}" if isinstance(rsi, (int, float)) and rsi is not None else "RSI 缺失"
    cftc = inputs.get("cftc_commitments") or {}
    cftc_text = "美国商品期货交易委员会（CFTC）持仓暂不可用"
    if isinstance(cftc, dict) and cftc.get("status") == "available":
        report_date = str(cftc.get("report_date") or "")
        net_noncommercial = int(cftc.get("net_noncommercial") or 0)
        positioning_bias = str(cftc.get("positioning_bias") or "neutral")
        divergence = ""
        if positioning_bias != trend_bias:
            divergence = "，与价格结构存在分歧"
        cftc_text = (
            f"美国商品期货交易委员会（CFTC）最新报告 {report_date} 的黄金净非商业头寸 {net_noncommercial:+d}，"
            f"定位偏{_direction_label_cn(positioning_bias)}{divergence}"
        )
    newsflow_headline_count = int(inputs.get("newsflow_headline_count") or 0)
    newsflow_sentiment = str(inputs.get("newsflow_sentiment") or "neutral")
    newsflow_text = "新闻流暂不可用"
    if newsflow_headline_count:
        sentiment_text = {
            "bullish": "看多",
            "bearish": "看空",
            "neutral": "中性",
        }.get(newsflow_sentiment, "中性")
        newsflow_text = f"新闻流已抓取 {newsflow_headline_count} 条标题，整体情绪为{sentiment_text}"
    polymarket_count = int(inputs.get("polymarket_gold_related_market_count") or 0)
    polymarket_text = "Polymarket 公开情绪暂不可用"
    if polymarket_count:
        bullish_count = int(inputs.get("polymarket_bullish_count") or 0)
        bearish_count = int(inputs.get("polymarket_bearish_count") or 0)
        neutral_count = int(inputs.get("polymarket_neutral_count") or 0)
        summary = str(inputs.get("polymarket_summary") or "").strip()
        bias_text = f"偏多 {bullish_count} 个，偏空 {bearish_count} 个，中性 {neutral_count} 个"
        polymarket_text = f"Polymarket 已识别到 {polymarket_count} 个与黄金相关的市场，{bias_text}"
        if summary:
            polymarket_text = f"{polymarket_text}；{summary}"
    reference_items = [
        rsi_text,
        cftc_text,
        newsflow_text,
        polymarket_text,
        f"{feedback_text}{unavailable_text}".strip("，。"),
    ]
    lines = [f"主判断：市场情绪按{_direction_label_cn(trend_bias)}方向解读。", "参考依据："]
    lines.extend(f"- {item}。" for item in reference_items if item)
    return "\n".join(lines)


def _market_sentiment_direction(inputs: dict[str, object]) -> ForecastDirection:
    trend_bias = str(inputs.get("trend_bias") or "neutral")
    if trend_bias == ForecastDirection.bullish.value:
        return ForecastDirection.bullish
    if trend_bias == ForecastDirection.bearish.value:
        return ForecastDirection.bearish
    return ForecastDirection.neutral


def _market_sentiment_confidence(inputs: dict[str, object], direction: ForecastDirection) -> float:
    confidence = 0.36
    if direction == ForecastDirection.neutral:
        confidence -= 0.03
    if inputs.get("feedback_signal_count"):
        confidence += 0.05
    if inputs.get("rsi_14") is not None:
        confidence += 0.04
    if inputs.get("polymarket_gold_related_market_count"):
        confidence += 0.04
    return round(min(max(confidence, 0.25), 0.58), 2)


def _alt_data_summary(inputs: dict[str, object]) -> str:
    pizza_index = inputs.get("pizza_index") or {}
    dollar_index = inputs.get("dollar_index") or {}
    real_rates = inputs.get("real_rates") or {}
    unavailable = inputs.get("unavailable_signals") or []
    notes = [
        _pizza_index_note(pizza_index),
        _signal_note("美元指数", dollar_index, value_key="value", value_suffix="", change_key="change"),
        _signal_note(
            "实际利率",
            real_rates,
            value_key="value",
            value_suffix="%",
            change_key="change",
            change_suffix="个百分点",
        ),
    ]
    lines = [
        "另类数据维度以保守处理为主。",
        *[f"- {note}" for note in notes],
        f"- 未接入信号数 {len(unavailable)}，因此本轮仅用于风险提示，不作为方向依据。",
    ]
    return "\n".join(lines)


def _pizza_index_note(item: object) -> str:
    if not isinstance(item, dict) or item.get("status") != "available":
        return "五角大楼披萨指数不可用"

    doughcon_level = item.get("doughcon_level")
    doughcon_label = str(item.get("doughcon_label") or "unknown")
    doughcon_description = str(item.get("doughcon_description") or "")
    average_spike_pct = item.get("average_spike_pct")
    max_spike_pct = item.get("max_spike_pct")
    pizza_index_score = item.get("pizza_index_score")
    activity_bias = str(item.get("activity_bias") or "neutral")
    top_locations = item.get("top_locations") or []
    top_location_text = ""
    if isinstance(top_locations, list) and top_locations:
        top_items = []
        for location in top_locations[:2]:
            if not isinstance(location, dict):
                continue
            name = str(location.get("name") or "unknown")
            spike_pct = location.get("spike_pct")
            if isinstance(spike_pct, (int, float)):
                top_items.append(f"{name} {float(spike_pct):.0f}%")
        if top_items:
            top_location_text = "，门店活动：" + "；".join(top_items)
    avg_text = f"{float(average_spike_pct):.0f}%" if isinstance(average_spike_pct, (int, float)) else "未知"
    max_text = f"{float(max_spike_pct):.0f}%" if isinstance(max_spike_pct, (int, float)) else "未知"
    score_text = f"{int(pizza_index_score)}/100" if isinstance(pizza_index_score, (int, float)) else "未知"
    activity_bias_text = _direction_label_cn(activity_bias)
    if isinstance(doughcon_level, int):
        doughcon_text = f"五角大楼披萨指数 DOUGHCON {doughcon_level}（{doughcon_label}"
        if doughcon_description:
            doughcon_text += f" / {doughcon_description}"
        doughcon_text += "）"
    else:
        doughcon_text = "五角大楼披萨指数 DOUGHCON 未知"
    return (
        f"{doughcon_text}，平均活跃度 {avg_text}，最高 {max_text}，"
        f"指数分 {score_text}，整体偏{activity_bias_text}{top_location_text}"
    )


def _news_summary(inputs: dict[str, object]) -> str:
    if not isinstance(inputs, dict) or inputs.get("status") != "available":
        return "新闻流暂未接入可靠主流媒体标题，本轮不使用未经验证的新闻作为方向依据。"

    headline_count = int(inputs.get("headline_count") or 0)
    source_count = int(inputs.get("source_count") or 0)
    sentiment = str(inputs.get("sentiment") or "neutral")
    topics = [str(topic) for topic in inputs.get("topics") or []]
    top_headlines = inputs.get("top_headlines") or []
    representative = []
    for item in top_headlines[:3]:
        if not isinstance(item, dict):
            continue
        source = str(
            item.get("source_cn") or translate_source_name_to_chinese(str(item.get("source") or "unknown"))
        ).strip()
        title = str(item.get("title_cn") or translate_headline_to_chinese(str(item.get("title") or "").strip())).strip()
        if title:
            representative.append(f"{source}: {title}")
    topic_text = ""
    if topics:
        translated_topics = [
            {
                "Fed": "美联储",
                "Dollar": "美元",
                "Inflation": "通胀",
                "Gold": "黄金",
                "Risk": "风险",
            }.get(topic, topic)
            for topic in topics
        ]
        topic_text = f"，主题聚焦 {'、'.join(translated_topics)}"
    sentiment_text = {
        "bullish": "看多",
        "bearish": "看空",
        "neutral": "中性",
    }.get(sentiment, "中性")
    lines = [
        f"新闻流已从 {source_count} 个主流媒体源抓取到 {headline_count} 条标题。",
        f"整体情绪为{sentiment_text}{topic_text}。",
    ]
    if representative:
        lines.append("代表性标题：")
        lines.extend(f"- {headline}" for headline in representative)
    return "\n".join(lines)


def _signal_note(
    label: str,
    item: object,
    *,
    value_key: str,
    value_suffix: str,
    change_key: str | None = None,
    change_suffix: str = "",
) -> str:
    if not isinstance(item, dict) or item.get("status") != "available":
        return f"{label}不可用"

    value = item.get(value_key)
    if not isinstance(value, (int, float)):
        return f"{label}不可用"

    note = f"{label} {value:.2f}{value_suffix}" if value_suffix else f"{label} {value:.2f}"
    if change_key:
        change_value = item.get(change_key)
        if isinstance(change_value, (int, float)):
            sign = "+" if change_value > 0 else ""
            note += f"，较前值 {sign}{change_value:.2f}{change_suffix}"
    return note


def _external_source_status(signals: list[dict[str, object]]) -> str:
    if all(signal.get("status") == "available" for signal in signals):
        return "available"
    if any(signal.get("status") == "available" for signal in signals):
        return "partial"
    return "unavailable"


def _fetch_cftc_commitments(signal_transport: httpx.BaseTransport | None) -> tuple[dict[str, object], str | None]:
    try:
        return fetch_cftc_gold_commitments(signal_transport), None
    except (ExternalSignalError, httpx.HTTPError, ValueError, TypeError) as exc:
        return {
            "status": "unavailable",
            "source": "publicreporting.cftc.gov",
            "series_id": "CFTC_GOLD_COMMITMENTS",
            "series_name": "CFTC 黄金持仓",
            "note": "CFTC 黄金持仓暂不可用，保持保守处理。",
        }, f"CFTC 黄金持仓源不可用：{exc}"


def _fetch_dollar_index(signal_transport: httpx.BaseTransport | None) -> tuple[dict[str, object], str | None]:
    try:
        return fetch_dollar_index(signal_transport), None
    except (ExternalSignalError, httpx.HTTPError, ValueError, TypeError) as exc:
        return {
            "status": "unavailable",
            "source": "fred.stlouisfed.org",
            "series_id": "DTWEXBGS",
            "series_name": "美元指数",
            "note": "美元指数暂不可用，保持保守处理。",
        }, f"美元指数源不可用：{exc}"


def _fetch_real_rates(signal_transport: httpx.BaseTransport | None) -> tuple[dict[str, object], str | None]:
    try:
        return fetch_real_rates(signal_transport), None
    except (ExternalSignalError, httpx.HTTPError, ValueError, TypeError) as exc:
        return {
            "status": "unavailable",
            "source": "fred.stlouisfed.org",
            "series_id": "DFII10",
            "series_name": "实际利率",
            "note": "实际利率暂不可用，保持保守处理。",
        }, f"实际利率源不可用：{exc}"


def _input_summary(state: WorkflowState) -> dict[str, object]:
    latest_bar = state.get("latest_bar")
    quote = state.get("quote")
    return {
        "symbol": quote.symbol if quote else (latest_bar.symbol if latest_bar else "XAUUSD"),
        "daily_bar_date": latest_bar.date.isoformat() if latest_bar else None,
        "data_source": quote.data_source if quote else None,
        "data_timestamp": quote.data_timestamp.isoformat() if quote else None,
    }


def _required(state: WorkflowState, key: str) -> Any:
    if key not in state:
        raise ValueError(f"workflow state missing required key: {key}")
    return state[key]  # type: ignore[literal-required]
