from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime
from typing import Any, Protocol, TypedDict

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
from goldfxgraph.persistence.repositories import ForecastRepository
from goldfxgraph.schemas.forecast import (
    AgentVote,
    CurrentQuote,
    DailyBar,
    ForecastDirection,
    ForecastEvaluationResult,
    ForecastResult,
    ForecastWindowDirection,
    MarketDataSet,
    TechnicalIndicators,
)

logger = logging.getLogger(__name__)

run_eod_backfill = None


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
        return {**state, "forecast_feedback_history": []}

    limit = int(state.get("feedback_history_limit") or 5)
    history = await repository.get_latest_evaluation_summary(limit=limit)
    return {**state, "forecast_feedback_history": history}


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
        **state,
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
        **state,
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
        **state,
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
    state = _append_agent_diagnostic(state, diagnostic_record)
    fallback_summary = _market_sentiment_summary(inputs)
    summary = _summary_or_fallback(remote.summary if remote else None, fallback_summary)
    polymarket_summary = str(inputs.get("polymarket_summary") or "").strip()
    if "Polymarket" not in summary and polymarket_summary:
        summary = _append_summary_section(summary, "重点·Polymarket", polymarket_summary)
    direction = remote.direction if remote else _market_sentiment_direction(inputs)
    confidence = remote.confidence if remote else _market_sentiment_confidence(inputs, direction)
    vote = AgentVote(
        agent="market_sentiment",
        direction=direction,
        confidence=confidence,
        rationale=summary,
    )
    return {
        **state,
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
    inputs = state.get("alt_data_inputs", {})
    remote, _diagnostic, diagnostic_record = _remote_agent_response(state, "alt_data", "agent_alt_data_analysis")
    state = _append_agent_diagnostic(state, diagnostic_record)
    summary = _summary_or_fallback(remote.summary if remote else None, _alt_data_summary(inputs))
    direction = remote.direction if remote else ForecastDirection.neutral
    confidence = remote.confidence if remote else 0.3
    vote = AgentVote(
        agent="alt_data",
        direction=direction,
        confidence=confidence,
        rationale=summary,
    )
    return {
        **state,
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
    return state


async def tool_load_market_data(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="tool_load_market_data")
    if "market_data" in state and "latest_bar" in state and "bars" in state:
        return state

    repository = state.get("repository")
    if repository is None:
        raise ValueError("workflow state missing repository for market data loading")

    settings = state.get("settings") or get_settings()
    symbol = "XAUUSD"
    latest_bar = await repository.get_latest_market_bar(symbol)
    if latest_bar is None:
        raise ValueError("market data repository does not contain any persisted daily bars")

    bars = await repository.get_market_bars_between(symbol, date(1970, 1, 1), latest_bar.date)
    market_data = MarketDataSet(symbol=latest_bar.symbol, bars=bars, latest_bar=latest_bar)
    return {
        **state,
        "settings": settings,
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
    return state


def tool_fetch_current_gold_quote(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="tool_fetch_current_gold_quote")
    if "quote" in state:
        return state

    provider = state.get("quote_provider")
    if provider is None:
        settings = state.get("settings") or get_settings()
        provider = CurrentQuoteProvider(
            url=settings.current_quote_url,
        )

    quote = provider.fetch()
    quote = _require_tradingview_quote(quote)
    return {**state, "quote": quote}


def _require_tradingview_quote(quote: CurrentQuote) -> CurrentQuote:
    if quote.data_source.strip().lower() != DEFAULT_TRADINGVIEW_SOURCE.lower():
        raise QuoteProviderError("TradingView quote provider returned a non-TradingView data source")
    if quote.data_source != DEFAULT_TRADINGVIEW_SOURCE:
        quote = quote.model_copy(update={"data_source": DEFAULT_TRADINGVIEW_SOURCE})
    return quote


def tool_compute_indicators(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="tool_compute_indicators")
    if "indicators" in state:
        return state

    bars = state.get("bars")
    if bars is None:
        market_data = state.get("market_data")
        bars = market_data.bars if market_data else None
    if not bars:
        raise ValueError("workflow state missing daily bars for technical indicator calculation")

    return {**state, "indicators": compute_technical_indicators(bars)}


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
        **state,
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
    state = _append_agent_diagnostic(state, diagnostic_record)
    direction = remote.direction if remote else _direction_from_inputs(quote.current_price, latest_bar, indicators)
    atr = _usable_atr(indicators, latest_bar, quote.current_price)
    summary = _summary_or_fallback(
        remote.summary if remote else None,
        _technical_summary(quote.current_price, latest_bar, indicators, direction, atr),
    )
    summary = _append_summary_section(
        summary,
        "技术分析·聪明钱",
        _smart_money_summary(quote.current_price, latest_bar, indicators, direction, atr),
    )
    vote = AgentVote(
        agent="technical",
        direction=direction,
        confidence=remote.confidence if remote else _technical_confidence(indicators, direction),
        rationale=summary,
    )
    return {
        **state,
        "technical_summary": summary,
        "agent_votes": [*_existing_votes_without(state, "technical"), vote],
    }


def agent_macro_analysis(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(
        state,
        current_stage="agent_macro_analysis",
        active_agent="macro",
    )
    inputs = state.get("macro_inputs", {})
    remote, _diagnostic, diagnostic_record = _remote_agent_response(state, "macro", "agent_macro_analysis")
    state = _append_agent_diagnostic(state, diagnostic_record)
    summary = _summary_or_fallback(
        remote.summary if remote else None,
        _macro_summary(inputs),
    )
    vote = AgentVote(
        agent="macro",
        direction=remote.direction if remote else ForecastDirection.neutral,
        confidence=remote.confidence if remote else 0.35,
        rationale=summary,
    )
    return {
        **state,
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
    state = _append_agent_diagnostic(state, diagnostic_record)
    inputs = state.get("newsflow_inputs", {})
    fallback_summary = _news_summary(inputs)
    summary = _summary_or_fallback(remote.summary if remote else None, fallback_summary)
    if "代表性标题" not in summary and fallback_summary:
        summary = _append_summary_section(summary, "重点·参考新闻", fallback_summary)
    vote = AgentVote(
        agent="news",
        direction=remote.direction if remote else ForecastDirection.neutral,
        confidence=remote.confidence if remote else 0.35,
        rationale=summary,
    )
    return {
        **state,
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
    state = _append_agent_diagnostic(state, diagnostic_record)
    notes = _merge_notes(
        state.get("risk_notes"),
        remote.risk_notes if remote and remote.risk_notes else _risk_notes(latest_bar, indicators, atr),
    )
    summary = (
        remote.summary if remote else "风险 agent 基于 ATR、日线区间与指标缺失情况生成结构化提示，不触发任何交易执行。"
    )
    vote = AgentVote(
        agent="risk",
        direction=remote.direction
        if remote
        else _risk_vote_direction(
            _direction_from_inputs(quote.current_price, latest_bar, indicators),
            atr,
            quote.current_price,
        ),
        confidence=remote.confidence if remote else 0.55,
        rationale=summary,
    )
    return {
        **state,
        "risk_summary": summary,
        "risk_notes": notes,
        "agent_votes": [*_existing_votes_without(state, "risk"), vote],
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

    return {**state, "forecast": forecast}


async def tool_persist_research_run(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="tool_persist_research_run")
    repository = state.get("repository")
    if repository is None:
        return {**state, "persistence_status": "skipped: repository not provided"}
    if "run_id" in state:
        return state

    run = await repository.create_research_run(_input_summary(state))
    return {**state, "run_id": run.id, "persistence_status": "research_run_created"}


async def tool_persist_forecast(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="tool_persist_forecast")
    repository = state.get("repository")
    if repository is None:
        return {**state, "persistence_status": "skipped: repository not provided"}

    forecast = state.get("forecast")
    if forecast is None:
        raise ValueError("workflow state missing forecast for persistence")

    run_id = state.get("run_id")
    if run_id is None:
        state = await tool_persist_research_run(state)
        run_id = state.get("run_id")
    if run_id is None:
        raise ValueError("workflow state missing research run id for forecast persistence")

    saved_forecast = await repository.save_forecast(run_id, forecast)
    await repository.mark_run_success(run_id)
    return {**state, "forecast": saved_forecast, "persistence_status": "forecast_saved"}


def router_finalize_result(state: WorkflowState) -> WorkflowState:
    _schedule_scheduler_status_update(state, current_stage="router_finalize_result")
    forecast = state.get("forecast")
    if forecast is None:
        raise ValueError("workflow state missing forecast result")
    return {**state, "result": forecast}


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
            "已回退到 deterministic workflow 输出。"
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
        message = f"OpenAI-compatible {agent_name} agent 调用失败，已回退到 deterministic workflow 输出。"
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

    return AgentApiResponse.model_validate(result.model_dump()), None, None


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
) -> WorkflowState:
    if diagnostic is None:
        return state

    diagnostics = list(state.get("agent_diagnostics") or [])
    diagnostics.append(diagnostic)
    return {**state, "agent_diagnostics": diagnostics}


def _summary_or_fallback(summary: str | None, fallback: str) -> str:
    cleaned = (summary or "").strip()
    return cleaned or fallback


def _append_summary_section(summary: str, title: str, body: str | None) -> str:
    cleaned_body = (body or "").strip()
    if not cleaned_body or title in summary:
        return summary
    if not summary.strip():
        return f"{title}：{cleaned_body}"
    separator = "" if summary.endswith("\n") else "\n"
    return f"{summary}{separator}{title}：{cleaned_body}"


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
    return (
        f"市场情绪按{_direction_label_cn(trend_bias)}方向解读，{rsi_text}，{cftc_text}，"
        f"{newsflow_text}，{polymarket_text}，{feedback_text}{unavailable_text}。"
    )


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
